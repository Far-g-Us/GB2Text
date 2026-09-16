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
Plugin for Golden Sun: The Lost Age (GBA) - contextual Huffman.

AGFE = GOLDEN_SUN_B (The Lost Age, USA/EU). Same contextual Huffman
engine as Golden Sun 1 (AGSE, see gba_golden_sun.py), but with separate
tree/offset/string-file addresses and extra two-byte control codes.

Extraction: strings are decompressed with the game's own Huffman trees and
returned via 'raw_text'. Insertion: translations are recompressed with the
stock trees (skip_long when a message does not fit its slot; slot relocation
is not implemented).

Control codes: control bytes below 0x20 are tokenized one-by-one; two
consecutive control bytes (e.g. 0x08 0x05 color, 0x12 0x01 player name,
0x1D 0x02 item prefix) are tokenized as a single '{XX YY}' token so that
the re-inserted string reproduces the original byte stream exactly.

This plugin contains ONLY factual technical information.
Author dialogs and story content are not included.
"""

import logging
import struct

from core.plugin import GamePlugin
from core.rom import GameBoyROM
from plugins.gba_golden_sun import (
    GoldenSunHuffmanDecoder,
    GoldenSunHuffmanEncoder,
)

logger = logging.getLogger('gb2text.plugins.golden_sun_tla')

GAME_CODES = ['AGFE']

# ---- ROM layout constants (Golden Sun: The Lost Age, USA/EU) ----
TLA_TREES_BASE = 0x05F914
TLA_OFFSETS_BASE = 0x060A4C
TLA_STRINGS_PTR_BASE = 0x0A9F54
TLA_DATA_FILES = 49
GS_STRINGS_PER_FILE = 256

# Single-byte control codes with a readable name.
TLA_NAMED_TOKENS: dict[int, str] = {
    0x01: '{NL}',
    0x02: '{END}',
    0x03: '{CONT}',
    0x07: '{CLR}',
    0x1E: '{WAIT}',
}
TLA_TOKEN_REVERSE = {v: k for k, v in TLA_NAMED_TOKENS.items()}


class GoldenSunTLATextDecoder:
    """Maps decoded TLA bytes to readable text (ASCII + control tokens).

    Consecutive control bytes (<0x20, not in the named single-byte set)
    are grouped into one '{XX YY ...}' token so that a two-byte control
    code (e.g. 0x08 0x05 color, 0x12 0x01 player name, 0x1D 0x02 item
    prefix) survives translation unchanged.
    """

    def __init__(self):
        self.charmap = {i: chr(i) for i in range(0x20, 0x7F)}
        self.charmap.update(TLA_NAMED_TOKENS)

    def decode(self, data: bytes) -> str:
        result: list[str] = []
        i = 0
        while i < len(data):
            byte = data[i]
            if 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
                i += 1
                continue
            if byte in TLA_NAMED_TOKENS:
                result.append(TLA_NAMED_TOKENS[byte])
                i += 1
                continue
            group = [byte]
            j = i + 1
            while (j < len(data) and data[j] < 0x20
                   and data[j] not in TLA_NAMED_TOKENS):
                group.append(data[j])
                j += 1
            result.append('{' + ' '.join(f'{b:02X}' for b in group) + '}')
            i = j
        return ''.join(result)

    def encode(self, text: str) -> bytes:
        """Reverse-maps tokens back into bytes (named and hex token groups)."""
        out = bytearray()
        tokens = sorted(TLA_TOKEN_REVERSE, key=len, reverse=True)
        i = 0
        while i < len(text):
            if text[i] != '{':
                code = ord(text[i])
                out.append(code if 0x20 <= code <= 0x7E else 0x00)
                i += 1
                continue
            close = text.find('}', i)
            if close == -1:
                out.append(0x00)
                i += 1
                continue
            token = text[i:close + 1]
            hexes = token[1:-1].split()
            named = TLA_TOKEN_REVERSE.get(token)
            if named is not None:
                out.append(named)
            else:
                try:
                    for part in hexes:
                        out.append(int(part, 16))
                except ValueError:
                    out.append(0x00)
            i = close + 1
        return bytes(out)


class GoldenSunTLAPlugin(GamePlugin):
    """Plugin for Golden Sun: The Lost Age (GBA) - contextual Huffman."""

    def __init__(self):
        super().__init__()
        self._decoder = GoldenSunTLATextDecoder()

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info("Extracting text segments for Golden Sun: The Lost Age")
        if TLA_STRINGS_PTR_BASE + TLA_DATA_FILES * 8 > len(rom.data):
            logger.warning("ROM too small for Golden Sun TLA string table")
            return []

        try:
            huffman = GoldenSunHuffmanDecoder(
                rom.data, TLA_OFFSETS_BASE, TLA_TREES_BASE)
            compressor = GoldenSunHuffmanEncoder(
                rom.data, TLA_OFFSETS_BASE, TLA_TREES_BASE)
        except ValueError as e:
            logger.warning(f"Golden Sun TLA Huffman tables unavailable: {e}")
            return []

        segments: list[dict] = []
        for fid in range(TLA_DATA_FILES):
            strings_addr, lens_addr = struct.unpack_from(
                '<II', rom.data, TLA_STRINGS_PTR_BASE + fid * 8
            )
            if not (0x08000000 <= strings_addr <= 0x0B800000
                    and 0x08000000 <= lens_addr <= 0x0B800000):
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

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00]

    def get_compression_handler(self, segment_name: str):
        return None

    def _make_compressor(self, compressor: GoldenSunHuffmanEncoder):
        """Returns a callable: text -> compressed stream (Huffman)."""
        def compress_text(text: str) -> bytes:
            raw = self._decoder.encode(text)
            return compressor.compress_string(raw)
        return compress_text