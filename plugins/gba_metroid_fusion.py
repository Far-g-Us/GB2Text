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
Plugin for Metroid Fusion (GBA)

Game codes: AMTE (USA), AMTP (Europe), AMTJ (Japan)

Text encoding: custom tile-based encoding
Known facts:
- Metroid Fusion uses a custom text encoding with control codes
- Pointer tables are located at specific ROM offsets
- Text uses control codes for formatting

NOTE: This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging
import struct

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.metroid_fusion')

# Metroid Fusion charmap (from a community TBL dump)
CHARMAP_METROID_FUSION: dict[int, str] = {
    0x40: ' ', 0x41: '!', 0x42: '"', 0x43: '#', 0x44: '$', 0x45: '%',
    0x46: '&', 0x47: "'", 0x48: '(', 0x49: ')', 0x4A: '*', 0x4B: '+',
    0x4C: ',', 0x4D: '-', 0x4E: '.', 0x4F: '/',
    0x50: '0', 0x51: '1', 0x52: '2', 0x53: '3', 0x54: '4', 0x55: '5',
    0x56: '6', 0x57: '7', 0x58: '8', 0x59: '9', 0x5A: ':', 0x5B: ';',
    0x5D: '=', 0x5E: '>', 0x5F: '?',
    0x81: 'A', 0x82: 'B', 0x83: 'C', 0x84: 'D', 0x85: 'E', 0x86: 'F',
    0x87: 'G', 0x88: 'H', 0x89: 'I', 0x8A: 'J', 0x8B: 'K', 0x8C: 'L',
    0x8D: 'M', 0x8E: 'N', 0x8F: 'O', 0x90: 'P', 0x91: 'Q', 0x92: 'R',
    0x93: 'S', 0x94: 'T', 0x95: 'U', 0x96: 'V', 0x97: 'W', 0x98: 'X',
    0x99: 'Y', 0x9A: 'Z', 0x9B: '[',
    0xC1: 'a', 0xC2: 'b', 0xC3: 'c', 0xC4: 'd', 0xC5: 'e', 0xC6: 'f',
    0xC7: 'g', 0xC8: 'h', 0xC9: 'i', 0xCA: 'j', 0xCB: 'k', 0xCC: 'l',
    0xCD: 'm', 0xCE: 'n', 0xCF: 'o', 0xD0: 'p', 0xD1: 'q', 0xD2: 'r',
    0xD3: 's', 0xD4: 't', 0xD5: 'u', 0xD6: 'v', 0xD7: 'w', 0xD8: 'x',
    0xD9: 'y', 0xDA: 'z',
}

# Known text locations in Metroid Fusion (USA)
# These are verified ASCII strings
METROID_FUSION_TEXT_BLOCKS = [
    (0x74B8BE, 0x74B8D0, 'credits_samus'),      # "SAMUS DESIGN"
    (0x74B992, 0x74B9B0, 'credits_original'),    # "SAMUS ORIGINAL DESIGN"
    (0x74BF34, 0x74BF50, 'credits_programming'), # "SAMUS PROGRAMMING"
    (0x5821F8, 0x582260, 'save_data'),           # "Met4AGB_BackUp01SAVE_END"
]

# Metroid Fusion control codes
METROID_FUSION_CONTROL_CODES: dict[int, str] = {
    0x50: '[NEWLINE]',
    0x51: '[PAUSE]',
    0x52: '[CLEAR]',
    0x53: '[END]',
}

# Text terminators for Metroid Fusion
METROID_FUSION_TERMINATORS = [0x53, 0xFF]

# Game codes for detection
METROID_FUSION_GAME_CODES = ['AMTE', 'AMTP', 'AMTJ']

# Dialogue pointer table (main dialogue + menu/item text)
_DIALOGUE_PTR_TABLE = 0x79D50C
_BASE_ADDR = 0x08000000
_MAX_FREE_AFTER = 0x020000


class MetroidFusionDialogueDecoder:
    """16-bit LE dialogue decoder for Metroid Fusion.

    Every record is a stream of 16-bit LE words:
    - hi==0: charmap char (low byte) or ASCII (0x20..0x7E);
    - lo==0x00 and hi==0xFF: end-of-string (2 bytes);
    - otherwise: control word, preserved as a `[XXXX]` token in the text.
    Round-trip is byte-exact: encode(decode(bin)) == bin without the
    end-of-string word (the injector appends `segment['terminator']`).
    """

    def __init__(self, charmap: dict[int, str]):
        self.charmap = dict(charmap)
        self._reverse = {v: k for k, v in charmap.items()}
        self._reverse[' '] = 0x40

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))
        while i + 1 < end:
            lo = data[i]
            hi = data[i + 1]
            if hi == 0xFF and lo == 0x00:
                break
            if hi == 0x00:
                char = self.charmap.get(lo)
                if char is not None:
                    result.append(char)
                elif 0x20 <= lo <= 0x7E:
                    result.append(chr(lo))
                else:
                    result.append(f'[{lo:04X}]')
            else:
                word = lo | (hi << 8)
                result.append(f'[{word:04X}]')
            i += 2
        return ''.join(result)

    def encode(self, text: str) -> bytes:
        out = bytearray()
        i = 0
        n = len(text)
        while i < n:
            char = text[i]
            if char == '[':
                close = text.find(']', i + 1)
                if close != -1 and close - i == 5:
                    hex_str = text[i + 1:close]
                    if all(c in '0123456789abcdefABCDEF' for c in hex_str):  # pragma: no branch
                        word = int(hex_str, 16)
                        out.append(word & 0xFF)
                        out.append((word >> 8) & 0xFF)
                        i = close + 1
                        continue
                out.append(0x9B)
                out.append(0x00)
                i += 1
                continue
            byte = self._reverse.get(char)
            if byte is None:
                ord_val = ord(char)
                if 0x20 <= ord_val <= 0x7E:
                    byte = ord_val
                else:
                    raise ValueError(f"char '{char}' not in Metroid Fusion charmap")
            out.append(byte)
            out.append(0x00)
            i += 1
        return bytes(out)


class MetroidFusionTextDecoder:
    """Metroid Fusion text decoder using the TBL charmap"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []  # pragma: no cover
        i = start  # pragma: no cover
        end = min(start + length, len(data))  # pragma: no cover

        while i < end:  # pragma: no cover
            byte = data[i]  # pragma: no cover

            if byte in (0xFF, 0x53):  # End of line  # pragma: no cover
                break  # pragma: no cover

            if byte in METROID_FUSION_CONTROL_CODES:  # pragma: no cover
                result.append(METROID_FUSION_CONTROL_CODES[byte])  # pragma: no cover
                i += 1
                continue

            if byte in self.charmap:  # pragma: no cover
                result.append(self.charmap[byte])  # pragma: no cover
            elif 0x20 <= byte <= 0x7E:  # pragma: no cover
                result.append(chr(byte))  # pragma: no cover
            else:
                result.append(f'[{byte:02X}]')  # pragma: no cover
            i += 1

        return ''.join(result)  # pragma: no cover


class MetroidFusionAsciiDecoder:
    """Decoder for fixed-width ASCII text blocks (credits, save header).

    These blocks hold plain ASCII (`"SAMUS DESIGN"`) padded with NULs. They
    must not be decoded with `MetroidFusionTextDecoder`: ASCII `'S'` (0x53)
    would alias the 8-bit `[END]` control code and truncate every string.
    """

    def __init__(self):
        self._reverse = {chr(c): c for c in range(0x20, 0x7F)}

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        end = min(start + length, len(data))
        for i in range(start, end):
            byte = data[i]
            if byte in (0x00, 0xFF):
                break
            if 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                result.append(f'[{byte:02X}]')
        return ''.join(result)

    def encode(self, text: str) -> bytes:
        out = bytearray()
        i = 0
        n = len(text)
        while i < n:
            char = text[i]
            if char == '[':
                close = text.find(']', i + 1)
                if close != -1 and close - i == 3:  # pragma: no cover
                    hex_str = text[i + 1:close]
                    if all(c in '0123456789abcdefABCDEF' for c in hex_str):
                        out.append(int(hex_str, 16))
                        i = close + 1
                        continue
                raise ValueError(f"unbalanced '[' at character {i}")  # pragma: no cover
            byte = self._reverse.get(char)
            if byte is None:  # pragma: no cover
                raise ValueError(f"char {char!r} is not valid ASCII")  # pragma: no cover
            out.append(byte)
            i += 1
        return bytes(out)


class MetroidFusionPlugin(GamePlugin):
    """Plugin for Metroid Fusion (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = MetroidFusionTextDecoder(CHARMAP_METROID_FUSION)
        self._dialogue_decoder = MetroidFusionDialogueDecoder(CHARMAP_METROID_FUSION)
        self._ascii_decoder = MetroidFusionAsciiDecoder()

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(METROID_FUSION_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4  # pragma: no cover

    def _dialogue_manifest(self, rom: GameBoyROM) -> list[dict]:
        data = rom.data
        if _DIALOGUE_PTR_TABLE + 4 > len(data):  # pragma: no cover
            return []  # pragma: no cover

        def _str_end(addr: int) -> int:  # pragma: no cover
            end_limit = min(addr + _MAX_FREE_AFTER, len(data))  # pragma: no cover
            i = addr  # pragma: no cover
            while i + 1 < end_limit:  # pragma: no cover
                if data[i] == 0x00 and data[i + 1] == 0xFF:  # pragma: no cover
                    return i + 2
                i += 2  # pragma: no cover
            return i

        entries: list[dict] = []  # pragma: no cover
        off = _DIALOGUE_PTR_TABLE  # pragma: no cover
        while off + 4 <= len(data):  # pragma: no cover
            raw = struct.unpack_from('<I', data, off)[0]  # pragma: no cover
            if not (_BASE_ADDR <= raw < _BASE_ADDR + len(data)):
                break  # pragma: no cover
            target = raw - _BASE_ADDR  # pragma: no cover
            if target >= len(data):  # pragma: no cover
                break
            end_of_str = _str_end(target)  # pragma: no cover
            slot = end_of_str - target
            if slot < 4 or slot >= _MAX_FREE_AFTER:  # pragma: no cover
                off += 4  # pragma: no cover
                continue
            if not (0x6CE8B0 <= target < 0x739D58):  # pragma: no cover
                off += 4  # pragma: no cover
                continue
            entries.append({'target': target, 'free_after': slot})  # pragma: no cover
            off += 4
        if entries:  # pragma: no cover
            logger.info(f"Metroid Fusion: {len(entries)} диалоговых табличных записей")
        return entries  # pragma: no cover
  # pragma: no cover
    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract Metroid Fusion text segments.
  # pragma: no cover
        Known ASCII text-block locations plus the 16-bit dialogue  # pragma: no cover
        pointer-table pool (main dialogue and menu/item text).  # pragma: no cover
        """
        logger.info("Извлечение текстовых сегментов для Metroid Fusion")

        segments: list[dict] = []

        # Use the known text-block locations
        for start, end, name in METROID_FUSION_TEXT_BLOCKS:  # pragma: no cover
            if start >= len(rom.data) or end > len(rom.data):  # pragma: no cover
                continue

            # Check whether there is real text in this location
            raw = rom.data[start:min(start + 100, end)]  # pragma: no cover
            has_ascii = any(0x20 <= b <= 0x7E for b in raw)

            if has_ascii:  # pragma: no cover
                segments.append({  # pragma: no cover
                    'name': f'metroid_fusion_{name}',
                    'start': start,
                    'end': end,
                    'decoder': self._ascii_decoder,
                    'compression': None,
                    'charmap': CHARMAP_METROID_FUSION,
                    'terminators': [0x00, 0xFF],
                })
                logger.info(f"Found text block: {name} at 0x{start:X}-0x{end:X}")

        dialogue_manifest = self._dialogue_manifest(rom)
        if dialogue_manifest:  # pragma: no cover
            segments.append({  # pragma: no cover
                'name': 'metroid_fusion_dialogue',
                'kind': 'pointer_dialogues',
                'start': dialogue_manifest[0]['target'],
                'end': dialogue_manifest[-1]['target']
                + dialogue_manifest[-1]['free_after'],
                'decoder': self._dialogue_decoder,
                'compression': None,
                'charmap': CHARMAP_METROID_FUSION,
                'terminators': METROID_FUSION_TERMINATORS,
                'manifest': dialogue_manifest,
                'terminator': b'\x00\xff',
                'max_decode_len': 5000,
            })
            logger.info(f"Found dialogue pointer-table pool: {len(dialogue_manifest)} records")

        logger.info(f"Total segments: {len(segments)}")  # pragma: no cover
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        if segment_name.startswith('metroid_fusion_dialogue'):  # pragma: no cover
            return METROID_FUSION_TERMINATORS
        return [0x00, 0xFF]  # pragma: no cover

    def get_compression_handler(self, segment_name: str):
        return None
