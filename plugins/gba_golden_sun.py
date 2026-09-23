"""
GB Text Extraction Framework

COPYRIGHT WARNING:
This software tool is intended ONLY for the analysis of ROM files
lawfully owned by the user. Any use of this tool to
illegally copy, distribute, or modify copyrighted
material is strictly prohibited.

This project does NOT contain or distribute any ROM files or
copyrighted material. All ROM files must be
lawfully acquired by the user independently.

This tool is developed exclusively for research purposes,
education, and reverse engineering within the limits permitted by law.
"""

"""
Plugin for Golden Sun (GBA) - contextual Huffman.

Text encoding: contextual Huffman (256 trees, one per
previous character). The format was recovered from the goldensun-decomp
project (tools/pack_strings.c, src/decompress/huffman.s). Verified against
ROM SHA1 5c4695205413df7db52b9a184815a07783999971.

Extraction: decompressed strings are returned via 'raw_text'.
Insertion: translations are recompressed with the game's stock Huffman trees
(bit order as in pack_strings.c) and written into the string file slots.
A translation that does not fit its slot (compressed size larger than the
original) can only be inserted with slot data relocation, which is
not implemented - the injector skips such messages (skip_long).

Game codes: AGSE (Golden Sun 1, USA/EU). TLA uses AGFE (separate plugin).

NOTE: this plugin contains ONLY factual technical information.
Author dialogs and story content are not included.
"""

import logging
import struct

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.golden_sun')

GAME_CODES = ['AGSE']

# ---- ROM layout constants (Golden Sun 1, USA/EU, SHA1 5c4695...) ----
GS_TREES_BASE = 0x37464
GS_OFFSETS_BASE = 0x38334
GS_STRINGS_PTR_BASE = 0x736B8
GS_DATA_FILES = 42
GS_STRINGS_PER_FILE = 256
GS_NO_TREE = 0x8000

# A decoded 0x00 byte terminates a string (the decoder stops on it).
# Control tokens must not contain '[', '\n' or the patterns '[XX]'/'[END]',
# so core.extractor._split_messages keeps every line as a single message.
GS_CONTROL_TOKENS: dict[int, str] = {
    0x01: '{NL}',        # newline inside the box
    0x02: '{END}',       # end of the message box
    0x03: '{CONT}',      # continue text on a new line
    0x07: '{CLR}',       # reset text color
    0x12: '{NAME}',      # character name placeholder
    0x13: '{CLASS}',     # class/level placeholder
    0x15: '{ABILITY}',   # psynergy/ability name placeholder
    0x16: '{NUM}',       # numeric placeholder (HP/PP/level/coins)
    0x1E: '{WAIT}',      # prompt "..."
}
GS_TOKEN_REVERSE = {v: k for k, v in GS_CONTROL_TOKENS.items()}


class _BitReader:
    """LSB-first bit reader over a byte-array slice."""

    __slots__ = ('bitpos', 'bytepos', 'data')

    def __init__(self, data: bytes, start: int = 0):
        self.data = data
        self.bytepos = start
        self.bitpos = 0

    def read_bit(self) -> int:
        byte = self.data[self.bytepos]  # pragma: no cover
        bit = (byte >> self.bitpos) & 1  # pragma: no cover
        self.bitpos += 1  # pragma: no cover
        if self.bitpos == 8:  # pragma: no cover
            self.bitpos = 0
            self.bytepos += 1
        return bit


class _BitWriter:
    """LSB-first bit writer, mirrors bit_writer from pack_strings.c."""

    __slots__ = ('bits', 'bits_pending', 'out')

    def __init__(self):
        self.bits = 0
        self.bits_pending = 0
        self.out = bytearray()

    def append(self, bit: int) -> None:
        self.bits |= (bit << self.bits_pending)
        self.bits_pending += 1
        if self.bits_pending == 8:
            self.out.append(self.bits)
            self.bits = 0
            self.bits_pending = 0

    def flush(self) -> None:
        if self.bits_pending:
            self.out.append(self.bits)
            self.bits = 0
            self.bits_pending = 0


class GoldenSunHuffmanDecoder:
    """
    Contextual Huffman decoder for Golden Sun's compressed strings.

    Trees: 256 (indexed by the previous decoded byte).
    Tree i starts at trees_base + offsets[i]; offsets[i] == 0x8000
    means tree i is unused. Each tree consists of a leaf array
    (packed symbols, growing backwards from the start of the topology),
    followed by a pre-order topology bit stream (0=internal node,
    1=leaf, LSB-first).

    Base addresses are configurable so both Golden Sun 1 (AGSE) and
    The Lost Age (AGFE) share this decoder; defaults are GS1.
    """

    def __init__(self, rom_data: bytes | bytearray,
                 offsets_base: int = GS_OFFSETS_BASE,
                 trees_base: int = GS_TREES_BASE):
        self.data = bytes(rom_data)
        self.trees_base = trees_base
        if offsets_base + 512 > len(rom_data):
            raise ValueError('ROM too small for Golden Sun Huffman tables')
        self.offsets = list(struct.unpack_from('<256H', rom_data, offsets_base))
        self._topo_cache: dict[int, int] = {}

    def _read_leaf(self, topo_start: int, leaf_id: int) -> int:
        """Read a symbol from a tree's packed leaf array."""
        off = leaf_id + (leaf_id >> 1)
        if leaf_id & 1:
            return self.data[topo_start - off - 2]
        return ((self.data[topo_start - off - 1] & 0x0F) << 4) | \
            ((self.data[topo_start - off - 2] >> 4) & 0x0F)

    def _count_skipped_leaves(self, topo_start: int, tp: _BitReader) -> int:
        """Skip one topology subtree, counting its leaves."""
        count = 0

        def walk() -> None:
            nonlocal count
            if tp.read_bit() == 1:
                count += 1
            else:
                walk()
                walk()

        walk()
        return count

    def _decode_symbol(self, bitstream: _BitReader, prev: int) -> int:
        """Decode one symbol from the bit stream using the 'prev' tree."""
        tree_rel = self.offsets[prev]
        if tree_rel == GS_NO_TREE or tree_rel == 0:
            raise ValueError(f'no valid Huffman tree for prev=0x{prev:02X}')
        topo_start = self.trees_base + tree_rel
        if topo_start - 2 < 0 or topo_start >= len(self.data):
            raise ValueError(f'tree topology out of bounds: 0x{topo_start:X}')

        tp = _BitReader(self.data, topo_start)
        leaf_count = 0

        while True:
            if tp.read_bit() == 1:
                # reached a leaf: leaf_count at this point == this leaf's id
                return self._read_leaf(topo_start, leaf_count)
            # internal node: the data bit selects the child
            if bitstream.read_bit() == 1:
                # right: skip the left subtree, counting its leaves
                leaf_count += self._count_skipped_leaves(topo_start, tp)
            # left: continue descending the topology without counting

    def decode_string(self, compressed: bytes) -> bytes:
        """Decode a single compressed string (stops at 0x00)."""
        if not compressed:
            return b''
        dr = _BitReader(compressed)
        out = bytearray()
        prev = 0
        while True:
            try:
                sym = self._decode_symbol(dr, prev)
            except (EOFError, IndexError, ValueError):
                break
            if sym == 0:
                break
            out.append(sym)
            prev = sym
        return bytes(out)


class GoldenSunHuffmanEncoder:
    """
    Recompresses Golden Sun dialogs with the game's stock Huffman trees.

    For each tree (one per previous byte) builds a code map
    symbol -> bit path by walking the serialized topology exactly like the
    game does, then emits the bit stream with the same LSB-first writer as
    tools/pack_strings.c. The 0x00 terminator is encoded as part of the
    string, so decoding stops at the same logical point as in the original.

    Base addresses are configurable so both Golden Sun 1 (AGSE) and
    The Lost Age (AGFE) share this encoder; defaults are GS1.
    """

    def __init__(self, rom_data: bytes | bytearray,
                 offsets_base: int = GS_OFFSETS_BASE,
                 trees_base: int = GS_TREES_BASE):
        self.data = bytes(rom_data)
        self.trees_base = trees_base
        if offsets_base + 512 > len(rom_data):
            raise ValueError('ROM too small for Golden Sun Huffman tables')
        self.offsets = list(struct.unpack_from('<256H', rom_data, offsets_base))
        self._codes_cache: dict[int, dict[int, tuple[int, ...]]] = {}

    def _read_leaf(self, topo_start: int, leaf_id: int) -> int:
        off = leaf_id + (leaf_id >> 1)
        if leaf_id & 1:
            return self.data[topo_start - off - 2]
        return ((self.data[topo_start - off - 1] & 0x0F) << 4) | \
            ((self.data[topo_start - off - 2] >> 4) & 0x0F)

    def _build_codes(self, prev: int) -> dict[int, tuple[int, ...]]:
        tree_rel = self.offsets[prev]
        if tree_rel == GS_NO_TREE or tree_rel == 0:
            raise ValueError(f'no valid Huffman tree for prev=0x{prev:02X}')
        topo_start = self.trees_base + tree_rel
        tp = _BitReader(self.data, topo_start)
        codes: dict[int, tuple[int, ...]] = {}
        leaf_id = 0

        def walk(bits: tuple[int, ...]) -> None:
            nonlocal leaf_id
            if tp.read_bit() == 1:
                codes[self._read_leaf(topo_start, leaf_id)] = bits
                leaf_id += 1
            else:
                walk((*bits, 0))
                walk((*bits, 1))

        walk(())
        return codes

    def _codes_for(self, prev: int) -> dict[int, tuple[int, ...]]:
        codes = self._codes_cache.get(prev)
        if codes is None:
            codes = self._build_codes(prev)
            self._codes_cache[prev] = codes
        return codes

    def compress_string(self, raw: bytes) -> bytes:
        """Compress one string: encode each byte plus the 0x00 terminator."""
        writer = _BitWriter()
        prev = 0
        for byte in raw + b'\x00':
            path = self._codes_for(prev).get(byte)
            if path is None:
                raise ValueError(
                    f'char 0x{byte:02X} not encodable after 0x{prev:02X}'
                )
            for bit in path:
                writer.append(bit)
            prev = byte
        writer.flush()
        return bytes(writer.out)


class GoldenSunTextDecoder:
    """Maps decoded GS bytes to readable tokens (ASCII + codes)."""

    def __init__(self):
        self.charmap = {i: chr(i) for i in range(0x20, 0x7F)}
        self.charmap.update(GS_CONTROL_TOKENS)

    def decode(self, data: bytes) -> str:
        result: list[str] = []
        for byte in data:
            if 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                result.append(GS_CONTROL_TOKENS.get(byte, f'{{{byte:02X}}}'))
        return ''.join(result)

    def encode(self, text: str) -> bytes:
        """Reverse-maps tokens and ASCII back into bytes."""
        out = bytearray()
        tokens = sorted(GS_TOKEN_REVERSE, key=len, reverse=True)
        i = 0
        while i < len(text):
            tok = next((t for t in tokens if text.startswith(t, i)), None)
            if tok is not None:
                out.append(GS_TOKEN_REVERSE[tok])
                i += len(tok)
                continue
            if text[i] == '{':
                close = text.find('}', i)
                if close == -1:
                    out.append(0x00)
                    i += 1
                    continue
                token = text[i:close + 1]
                byte = GS_TOKEN_REVERSE.get(token)
                if byte is None:
                    try:
                        byte = int(token[1:-1], 16)
                    except ValueError:
                        byte = 0x00
                out.append(byte)
                i = close + 1
                continue
            code = ord(text[i])
            out.append(code if 0x20 <= code <= 0x7E else 0x00)
            i += 1
        return bytes(out)


class GoldenSunPlugin(GamePlugin):
    """Plugin for Golden Sun (GBA) - contextual Huffman dialogs."""

    def __init__(self):
        super().__init__()
        self._decoder = GoldenSunTextDecoder()

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract text segments from a Golden Sun ROM."""
        logger.info("Extracting text segments for Golden Sun")
        if GS_STRINGS_PTR_BASE + GS_DATA_FILES * 8 > len(rom.data):
            logger.warning("ROM too small for Golden Sun string table")
            return []

        try:
            huffman = GoldenSunHuffmanDecoder(rom.data)
            compressor = GoldenSunHuffmanEncoder(rom.data)
        except ValueError as e:
            logger.warning(f"Golden Sun Huffman tables unavailable: {e}")
            return []

        segments: list[dict] = []
        for fid in range(GS_DATA_FILES):
            strings_addr, lens_addr = struct.unpack_from(
                '<II', rom.data, GS_STRINGS_PTR_BASE + fid * 8
            )
            if not (0x08000000 <= strings_addr <= 0x08800000
                    and 0x08000000 <= lens_addr <= 0x08800000):
                logger.warning(f"Bad string table pointers in file {fid}")
                continue
            strings_addr -= 0x08000000
            lens_addr -= 0x08000000
            data_len = lens_addr - strings_addr
            pos = 0
            for sid in range(GS_STRINGS_PER_FILE):
                if pos >= data_len:
                    break
                length = rom.data[lens_addr + sid]
                if length == 0 or pos + length > data_len:
                    break

                compressed = bytes(rom.data[strings_addr + pos:strings_addr + pos + length])
                decoded = huffman.decode_string(compressed)
                text = self._decoder.decode(decoded)

                segments.append({
                    'name': f'gs_dialogue_f{fid:02d}_{sid:03d}',
                    'start': strings_addr + pos,
                    'end': strings_addr + pos + length,
                    'decoder': self._decoder,
                    'compression': 'huffman',
                    'compressed_length': length,
                    'pad_byte': 0xFF,
                    'charmap': self._decoder.charmap,
                    'terminators': [0x00],
                    'raw_text': text,
                    'encoder': self._make_compressor(compressor),
                })
                pos += length

        segments.extend(self._ascii_credits_segments(rom))
        logger.info(f"Total segments: {len(segments)}")
        return segments

    def _ascii_credits_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract the staff credits (a pure-ASCII area) as extra segments."""
        segments: list[dict] = []
        start = 0x0F0000
        end = min(0x0F2000, len(rom.data))
        if start >= len(rom.data):
            return segments

        i = start
        while i < end:
            if 0x20 <= rom.data[i] <= 0x7E:
                str_start = i
                while i < end and 0x20 <= rom.data[i] <= 0x7E:
                    i += 1
                length = i - str_start
                if length >= 5:
                    text = bytes(rom.data[str_start:str_start + length]).decode(
                        'ascii', errors='replace')
                    segments.append({
                        'name': f'gs_credits_{len(segments)}',
                        'start': str_start,
                        'end': str_start + length,
                        'decoder': None,
                        'compression': None,
                        'charmap': {},
                        'terminators': [0x00],
                        'raw_text': text,
                    })
            else:
                i += 1
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00]

    def get_compression_handler(self, segment_name: str):
        return None

    def _make_compressor(self, compressor: GoldenSunHuffmanEncoder):
        """Returns a callable: text -> compressed stream (Huffman, via the token table)."""
        def compress_text(text: str) -> bytes:
            raw = self._decoder.encode(text)
            return compressor.compress_string(raw)
        return compress_text
