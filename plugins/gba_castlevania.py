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
Plugin for Castlevania: Aria of Sorrow (GBA)

Game codes: A2CE (USA), AGBJ (Japan), AGBE (Europe)

Text encoding: custom tile-based encoding by Konami
Known facts:
- Castlevania GBA games use custom text encoding
- Pointer tables are located at specific ROM offsets
- Text includes control codes for formatting and special characters

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.castlevania_gba')

# Castlevania: Aria of Sorrow character table
# Source: https://datacrystal.tcrf.net/wiki/Castlevania:_Aria_of_Sorrow/TBL
CHARMAP_CVAS: dict[int, str] = {
    # Control codes
    0x06: '\n',  # [LINE]
    0x0A: '\n',  # end of line inside a record (NOT a record terminator)
    0x0B: '[A_BUTTON]',
    0x0C: '[B_BUTTON]',
    0x0D: '[L_BUTTON]',
    0x0E: '[R_BUTTON]',
    0x0F: '[UP]',
    0x10: '[DOWN]',

    # Printable ASCII characters (0x20-0x7E)
    0x20: ' ', 0x21: '!', 0x22: '"', 0x23: '#', 0x24: '$', 0x25: '%',
    0x26: '&', 0x27: "'", 0x28: '(', 0x29: ')', 0x2A: '*', 0x2B: '+',
    0x2C: ',', 0x2D: '-', 0x2E: '.', 0x2F: '/',
    0x30: '0', 0x31: '1', 0x32: '2', 0x33: '3', 0x34: '4',
    0x35: '5', 0x36: '6', 0x37: '7', 0x38: '8', 0x39: '9',
    0x3A: ':', 0x3B: ';', 0x3C: '<', 0x3D: '=', 0x3E: '>', 0x3F: '?',
    0x40: '@',
    0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E', 0x46: 'F',
    0x47: 'G', 0x48: 'H', 0x49: 'I', 0x4A: 'J', 0x4B: 'K', 0x4C: 'L',
    0x4D: 'M', 0x4E: 'N', 0x4F: 'O', 0x50: 'P', 0x51: 'Q', 0x52: 'R',
    0x53: 'S', 0x54: 'T', 0x55: 'U', 0x56: 'V', 0x57: 'W', 0x58: 'X',
    0x59: 'Y', 0x5A: 'Z', 0x5B: '[', 0x5C: '\\', 0x5D: ']', 0x5E: '^',
    0x5F: '_',
    0x60: '`',
    0x61: 'a', 0x62: 'b', 0x63: 'c', 0x64: 'd', 0x65: 'e', 0x66: 'f',
    0x67: 'g', 0x68: 'h', 0x69: 'i', 0x6A: 'j', 0x6B: 'k', 0x6C: 'l',
    0x6D: 'm', 0x6E: 'n', 0x6F: 'o', 0x70: 'p', 0x71: 'q', 0x72: 'r',
    0x73: 's', 0x74: 't', 0x75: 'u', 0x76: 'v', 0x77: 'w', 0x78: 'x',
    0x79: 'y', 0x7A: 'z', 0x7B: '{', 0x7C: '|', 0x7D: '}', 0x7E: '~',

    # Extended characters (French/German)
    0x80: '[HALF_A1]', 0x81: '[HALF_A2]', 0x82: '[HALF_B1]', 0x83: '[HALF_B2]',
    0x84: '[HALF_L1]', 0x85: '[HALF_L2]', 0x86: '[HALF_R1]', 0x87: '[HALF_R2]',
    0x90: 'Œ', 0x91: 'œ',
    0xAA: 'α', 0xAB: '«',
    0xBA: '°', 0xBB: '»',
    0xC0: 'À', 0xC1: 'Á', 0xC2: 'Â', 0xC4: 'Ä',
    0xC7: 'ç', 0xC8: 'È', 0xC9: 'É', 0xCA: 'Ê', 0xCB: 'Ë',
    0xD6: 'ö',
    0xDB: 'û', 0xDC: 'ü', 0xDF: 'β',
    0xE0: 'à', 0xE2: 'â', 0xE4: 'ä',
    0xE7: 'ç', 0xE8: 'è', 0xE9: 'é', 0xEA: 'ê', 0xEB: 'ë',
    0xEE: 'î', 0xEF: 'ï',
    0xF4: 'ô', 0xF6: 'ö',
    0xF9: 'ù', 0xFB: 'û', 0xFC: 'ü',

    # Multi-byte control codes
    0x0300: '[SOMA_PORTRAIT]', 0x0301: '[MINA_PORTRAIT]',
    0x0302: '[GENYA_PORTRAIT]', 0x0303: '[GRAHAM_PORTRAIT]',
    0x0304: '[YOKO_PORTRAIT]', 0x0305: '[JULIUS_PORTRAIT]',
    0x0306: '[HAMMER_PORTRAIT]',
    0x0307: '[SOMA_PORTRAIT2]', 0x0308: '[GRAHAM_PORTRAIT2]',
    0x0701: '[SOMA]', 0x0702: '[MINA]', 0x0703: '[GENYA]',
    0x0704: '[GRAHAM]', 0x0705: '[YOKO]', 0x0706: '[J]',
    0x0708: '[JULIUS]', 0x0709: '[HAMMER]',
}

# Castlevania: Aria of Sorrow (USA) pointer table - found in Phase 0.
# 2895 records, 4-byte little-endian, value = offset + 0x08000000.
# Targets - start of text records: the preceding byte is always 0x00,
# the first byte of a record is always 0x01 (page marker).
CVAS_POINTER_TABLE = 0x506B38
CVAS_POINTER_COUNT = 2895

# Language blocks in the table: (start_index, end_index, language).
# Consecutive blocks: translating a pointer subrange = relocating a language.
CVAS_LANG_BLOCKS = [
    (0, 40, 'en_ui'),   # UI/system text
    (40, 1013, 'en'),   # English script
    (1013, 2116, 'fr'), # French script
    (2116, 2895, 'de'), # German script
]

# Castlevania GBA text terminators.
# A record ends with a run of 0x00 of length >= 2 (Phase 0 data: 0x00 is NEVER
# a space; 0x0A is an in-record end of line, not a terminator).
CVAS_TERMINATORS = [0x00]

# Game codes for detection
# USA: A2CE, Japan: AGBJ, Europe: AGBE
CVAS_GAME_CODES = ['A2CE', 'AGBJ', 'AGBE']

# Normalized translation representation: 0x06/0x0A both decode to '\n'.
# Byte round-trip (encode(decoder(raw)) == raw) is only performed for
# records without 0x0A; records with 0x0A are checked at the text level.
CVAS_NEWLINE = 0x06


def _build_reverse_charmap() -> dict[str, bytes]:
    rev: dict[str, bytes] = {}
    for code, rep in CHARMAP_CVAS.items():
        if rep == '\n':
            continue
        if rep in rev:
            continue
        if code < 0x100:
            rev[rep] = bytes([code])
        else:
            rev[rep] = bytes([code >> 8, code & 0xFF])
    return rev


CHARMAP_CVAS_REV = _build_reverse_charmap()


class CVASTextEncoder:
    """Reverse mapping of CVAS text back into bytes.

    '\\n' is emitted as 0x06 (engine canon - 0x06 and 0x0A are equivalent).
    0x00 is forbidden in the output stream except for the '[PAGE]' marker -> 01 00
    (record header). The literal '[HH]'/'[HHHH]' notation (raw bytes)
    is encoded back into bytes. Unknown characters and tokens -> ValueError.
    """

    def __init__(self, rev: dict[str, bytes]):
        self._rev = dict(rev)
        self._rev['[PAGE]'] = b'\x01\x00'
        self._rev['[PAGEBREAK]'] = b'\x01'
        self._labels = sorted(
            (k for k in self._rev if len(k) > 1), key=len, reverse=True)
        self._single = {k: v for k, v in self._rev.items() if len(k) == 1 and k != '\n'}

    @staticmethod
    def _raw_bytes(body: str) -> bytes:
        if len(body) == 2:
            value = int(body, 16)
            if value == 0x00:
                raise ValueError("0x00 зарезервирован под терминатор")
            return bytes([value])
        high = int(body[:2], 16)
        if high == 0x00:
            raise ValueError("0x00 первым байтом запрещён")
        return bytes([high, int(body[2:], 16)])

    def encode(self, text: str) -> bytes:
        out = bytearray()
        i = 0
        n = len(text)
        while i < n:
            matched = False
            for label in self._labels:
                if text.startswith(label, i):
                    encoded = self._rev[label]
                    if encoded.startswith(b'\x00'):
                        raise ValueError(f"0x00 первым байтом токена {label!r}")
                    out.extend(encoded)
                    i += len(label)
                    matched = True
                    break
            if matched:
                continue
            ch = text[i]
            if ch == '[':
                close = text.find(']', i + 1)
                if close != -1:
                    body = text[i + 1:close]
                    if (len(body) in (2, 4)) and all(c in '0123456789abcdefABCDEF' for c in body):
                        out.extend(self._raw_bytes(body))
                        i = close + 1
                        continue
            if ch == '\n':
                out.append(CVAS_NEWLINE)
            elif 0x20 <= ord(ch) <= 0x7E:
                out.append(ord(ch))
            else:
                single = self._single.get(ch)
                if single is None:
                    raise ValueError(f"Не удаётся закодировать {ch!r}")
                out.extend(single)
            i += 1
        return bytes(out)


class CVASTextDecoder:
    """Castlevania GBA text decoder

    A text record (per the pointer table) starts with 0x01 (page marker) and
    an optional header 0x00, then a portrait (0x03XX), a speaker (0x07XX),
    and the text. 0x06 is a line break, 0x0A is an end of line.
    The record terminator is a run of 0x00 of length >= 2.
    """

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes | bytearray, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            # Page marker 0x01 + header 0x00 (at the start of a record),
            # page break - a lone 0x01 inside a record.
            if byte == 0x01:
                result.append('[PAGE]' if i == start else '[PAGEBREAK]')
                i += 1
                if i < end and data[i] == 0x00:
                    i += 1
                continue

            # Record terminator (any 0x00 - only padding follows it)
            if byte == 0x00:
                break

            # Line break / end of line
            if byte in (0x06, 0x0A):
                result.append('\n')
                i += 1
                continue

            # Multi-byte codes (0x03XX portraits, 0x07XX speakers)
            if i + 1 < end:
                two_byte = (byte << 8) | data[i + 1]
                if two_byte in self.charmap:
                    result.append(self.charmap[two_byte])
                    i += 2
                    continue

            # Printable ASCII, extended charmap characters, otherwise [XX]
            if 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                char = self.charmap.get(byte)
                result.append(char if char else f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class CastlevaniaGBAPlugin(GamePlugin):
    """Plugin for Castlevania: Aria of Sorrow (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = CVASTextDecoder(CHARMAP_CVAS)
        self._encoder = CVASTextEncoder(CHARMAP_CVAS_REV)

    def make_text_encoder(self) -> CVASTextEncoder:
        return self._encoder

    def get_pointer_table_meta(self) -> dict | None:
        return {
            'table': CVAS_POINTER_TABLE,
            'count': CVAS_POINTER_COUNT,
            'blocks': CVAS_LANG_BLOCKS,
        }

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(CVAS_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract Castlevania GBA text segments via the pointer table"""
        logger.info("Извлечение текстовых сегментов для Castlevania: Aria of Sorrow")

        table_size = 4 * CVAS_POINTER_COUNT
        if CVAS_POINTER_TABLE + table_size > len(rom.data):
            logger.warning("Таблица указателей выходит за пределы ROM: %#x", CVAS_POINTER_TABLE)
            return []

        targets = [
            int.from_bytes(
                rom.data[CVAS_POINTER_TABLE + 4 * i: CVAS_POINTER_TABLE + 4 * i + 4], 'little'
            ) - 0x08000000
            for i in range(CVAS_POINTER_COUNT)
        ]

        if any(not (0 <= t < len(rom.data)) for t in targets):
            logger.warning("Некорректные цели в таблице указателей")
            return []

        segments: list[dict] = []
        for block_start, block_end, lang in CVAS_LANG_BLOCKS:
            block_targets = targets[block_start:block_end]
            if block_targets != sorted(block_targets):
                logger.warning("Блок %s не монотонен — пропуск", lang)
                continue
            for idx, target in enumerate(block_targets):
                upper = block_targets[idx + 1] if idx + 1 < len(block_targets) else (
                    targets[block_end]
                    if block_end < CVAS_POINTER_COUNT
                    and targets[block_end] > block_targets[-1]
                    else len(rom.data))
                seg = self._make_segment(rom.data, target, upper, idx, lang)
                if seg is not None:
                    segments.append(seg)

        logger.info("Всего сегментов: %d", len(segments))
        return segments

    def _make_segment(
        self,
        data: bytes | bytearray,
        target: int,
        upper: int,
        idx: int,
        lang: str,
    ) -> dict | None:
        """Segment of a single record: from target to a run of 0x00 >= 2.

        upper is the start of the next record (or the end of the ROM): the
        scan boundary and end. A record must start with the page marker 0x01
        (self-validation for regions where table 0x506B38 is wrong).
        """
        if not (0 < target < len(data)):
            return None
        if data[target - 1] != 0x00 or data[target] != 0x01:
            return None

        end = target + 2
        i = target + 2
        found = False
        while i + 1 <= upper and i + 1 < len(data):
            if data[i] == 0x00 and data[i + 1] == 0x00:
                end = i
                found = True
                break
            i += 1
        if not found:
            if upper > target + 2:
                logger.warning("Запись без терминатора @0x%X (upper=0x%X)", target, upper)
                end = upper
        if end > upper:
            end = upper
        if end <= target:
            return None

        raw = self._decoder.decode(data, target, end - target)
        return {
            'name': f'cvas_{lang}_{idx}',
            'start': target,
            'end': end,
            'decoder': self._decoder,
            'compression': None,
            'charmap': CHARMAP_CVAS,
            'terminators': CVAS_TERMINATORS,
            'injectable': False,
            'raw_text': raw,
        }

    def get_terminators(self, segment_name: str) -> list[int]:
        """Byte terminators for Castlevania GBA"""
        return CVAS_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        """Castlevania GBA does not use compression for the main text"""
        return None
