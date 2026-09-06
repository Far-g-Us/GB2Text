"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.

Этот проект НЕ содержит и НЕ распространяет никакие ROM-файлы или
защищенные авторским правом материалы. Все ROM-файлы должны быть
законно приобретены пользователем самостоятельно.

Этот инструмент разработан исключительно для исследовательских целей,
обучения и реверс-инжиниринга в рамках, разрешенных законодательством.
"""

"""
Плагин для Castlevania: Aria of Sorrow (GBA)

Game codes: AGBB (USA), AGBJ (Japan), AGBE (Europe)

Text encoding: Konami custom tile-based encoding
Known facts:
- Castlevania GBA games use custom text encoding
- Pointer tables are located at specific ROM offsets
- Text includes control codes for formatting and special characters

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.castlevania_gba')

# Castlevania: Aria of Sorrow charmap
# Source: https://datacrystal.tcrf.net/wiki/Castlevania:_Aria_of_Sorrow/TBL
CHARMAP_CVAS: dict[int, str] = {
    # Control codes
    0x06: '\n',  # [LINE]
    0x0A: '[END]',
    0x0B: '[A_BUTTON]',
    0x0C: '[B_BUTTON]',
    0x0D: '[L_BUTTON]',
    0x0E: '[R_BUTTON]',
    0x0F: '[UP]',
    0x10: '[DOWN]',

    # ASCII printable characters (0x20-0x7E)
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

# Known pointer table locations for Castlevania: Aria of Sorrow (multi-language ROM)
# Source: Analysis of GBA pointers (0x08XXXXXX) pointing to ASCII text
CVAS_POINTER_TABLES = [
    # English UI/system text
    (0x08000000 + 0x0E0000, 0x08000000 + 0x0F0000),
    # English dialogue (main text bank)
    (0x08000000 + 0x0F0000, 0x08000000 + 0x100000),
    # French dialogue
    (0x08000000 + 0x100000, 0x08000000 + 0x110000),
    # German dialogue
    (0x08000000 + 0x110000, 0x08000000 + 0x120000),
]

# Text terminators for Castlevania GBA
# 0x06 = line break/pause, 0x0A = [END] per TBL
CVAS_TERMINATORS = [0x0A]

# Game codes for detection
# USA: A2CE, Japan: AGBJ, Europe: AGBE
CVAS_GAME_CODES = ['A2CE', 'AGBJ', 'AGBE']


class CVASTextDecoder:
    """Decoder for Castlevania GBA text

    Text is ASCII with control codes (0x01-0x0F) that precede text blocks.
    0x06 = line break/pause, 0x0A = [END] terminator.
    Control codes are output as labels during decoding.
    """

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            # Check for multi-byte codes first (0x03XX, 0x07XX)
            if i + 1 < end:
                two_byte = (byte << 8) | data[i + 1]
                if two_byte in self.charmap:
                    result.append(self.charmap[two_byte])
                    i += 2
                    continue

            # End of string (0x0A per TBL)
            if byte == 0x0A:
                break

            # Line break / pause (0x06)
            if byte == 0x06:
                result.append('\n')
                i += 1
                continue

            # Control codes - output their labels
            if byte in self.charmap:
                char = self.charmap[byte]
                if char:
                    result.append(char)
                i += 1
                continue

            # ASCII printable characters (0x20-0x7E)
            if 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class CastlevaniaGBAPlugin(GamePlugin):
    """Плагин для Castlevania: Aria of Sorrow (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = CVASTextDecoder(CHARMAP_CVAS)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(CVAS_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов Castlevania GBA using pointer scanning"""
        logger.info("Извлечение текстовых сегментов для Castlevania: Aria of Sorrow")

        segments = []

        # Known text areas in this multi-language ROM
        text_areas = [
            (0x0F0000, 0x100000, 'en'),  # English dialogue
            (0x100000, 0x110000, 'fr'),  # French dialogue
            (0x110000, 0x120000, 'de'),  # German dialogue
        ]

        # Scan for GBA pointers (0x08XXXXXX) that point to text areas
        for text_start, text_end, lang in text_areas:
            found_pointers = []

            # Scan entire ROM for pointers to this text area
            for i in range(0, len(rom.data) - 4, 4):
                val = int.from_bytes(rom.data[i:i+4], 'little')
                if 0x08000000 <= val <= 0x09000000:
                    target = val - 0x08000000
                    if text_start <= target < text_end:
                        found_pointers.append((i, target))

            logger.info(f"Found {len(found_pointers)} pointers to {lang} text area")

            # Extract individual strings from pointer targets
            for _ptr_addr, target in found_pointers:
                text = self._extract_string(rom.data, target)
                if text and len(text.strip()) >= 2:
                    seg_name = f'cvas_{lang}_{len(segments)}'
                    segments.append({
                        'name': seg_name,
                        'start': target,
                        'end': target + len(text),
                        'decoder': None,
                        'compression': None,
                        'charmap': CHARMAP_CVAS,
                        'terminators': CVAS_TERMINATORS,
                        'raw_text': text,
                    })

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def _extract_string(self, rom_data: bytes | bytearray, offset: int) -> str:
        """Extract a single text string from ROM data"""
        result: list[str] = []
        i = offset
        end = min(offset + 1000, len(rom_data))

        while i < end:
            byte = rom_data[i]

            # End of string (0x0A per TBL)
            if byte == 0x0A:
                break

            # Null byte might be padding or terminator
            if byte == 0x00:
                # Check if next bytes are also null (likely end of string)
                if i + 1 < end and rom_data[i + 1] == 0x00:
                    break
                # Single null might be space
                result.append(' ')
                i += 1
                continue

            # Line break / pause (0x06)
            if byte == 0x06:
                result.append('\n')
                i += 1
                continue

            # Control codes (0x01-0x0F) - skip
            if 0x01 <= byte <= 0x0F:
                i += 1
                continue

            # ASCII printable characters (0x20-0x7E)
            if 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                # Extended characters (accented)
                if byte in self._decoder.charmap:
                    result.append(self._decoder.charmap[byte])
                else:
                    result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)

    def _heuristic_scan(self, rom: GameBoyROM) -> list[dict]:
        """Эвристический поиск текстовых блоков"""
        from core.scanner import is_text_like

        segments = []
        block_size = 16

        scan_ranges = [
            (0x1E0000, 0x2A0000),  # Dialogue banks
            (0x380000, 0x3A0000),  # Menu/UI
        ]

        for range_start, range_end in scan_ranges:
            if range_start >= len(rom.data):
                continue

            end = min(range_end, len(rom.data))
            i = range_start

            while i + block_size <= end:
                if is_text_like(rom.data, i, block_size, min_printable_ratio=0.4):
                    seg_end = min(i + 0x1000, end)
                    segments.append({
                        'name': f'cvas_heuristic_{len(segments)}',
                        'start': i,
                        'end': seg_end,
                        'decoder': self._decoder,
                        'compression': None,
                        'charmap': CHARMAP_CVAS,
                        'terminators': CVAS_TERMINATORS,
                    })
                    i = seg_end
                else:
                    i += block_size

        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        """Байт-терминаторы для Castlevania GBA"""
        return CVAS_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        """Castlevania GBA не использует сжатие для основного текста"""
        return None
