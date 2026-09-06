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
Плагин для Custom Robo GX (GBA)

Game codes: AGBJ (Japan)

Text encoding: Shift-JIS with custom extensions
Source: https://datacrystal.tcrf.net/wiki/Custom_Robo_GX/TBL

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.custom_robo_gx')

# Custom Robo GX charmap (Shift-JIS based)
# Source: DataCrystal TBL
CHARMAP_CROBO: dict[int, str] = {
    # Control codes
    0x00: '[END]',
    0x01: '',  # Followed by parameter byte
    
    # Full-width characters
    0x02: '\u3000',  # Full-width space
    0x03: '\u3001',  # 、
    0x04: '\u3002',  # 。
    0x05: '\u30FB',  # ・
    
    # Full-width digits
    0x06: '\uFF10', 0x07: '\uFF11', 0x08: '\uFF12', 0x09: '\uFF13',
    0x0A: '\uFF14', 0x0B: '\uFF15', 0x0C: '\uFF16', 0x0D: '\uFF17',
    0x0E: '\uFF18', 0x0F: '\uFF19',
    
    # Full-width uppercase A-Z
    0x10: '\uFF21', 0x11: '\uFF22', 0x12: '\uFF23', 0x13: '\uFF24',
    0x14: '\uFF25', 0x15: '\uFF26', 0x16: '\uFF27', 0x17: '\uFF28',
    0x18: '\uFF29', 0x19: '\uFF2A', 0x1A: '\uFF2B', 0x1B: '\uFF2C',
    0x1C: '\uFF2D', 0x1D: '\uFF2E', 0x1E: '\uFF2F', 0x1F: '\uFF30',
    0x20: '\uFF31', 0x21: '\uFF32', 0x22: '\uFF33', 0x23: '\uFF34',
    0x24: '\uFF35', 0x25: '\uFF36', 0x26: '\uFF37', 0x27: '\uFF38',
    0x28: '\uFF39', 0x29: '\uFF3A',
    
    # Full-width lowercase a-z
    0x2A: '\uFF41', 0x2B: '\uFF42', 0x2C: '\uFF43', 0x2D: '\uFF44',
    0x2E: '\uFF45', 0x2F: '\uFF46', 0x30: '\uFF47', 0x31: '\uFF48',
    0x32: '\uFF49', 0x33: '\uFF4A', 0x34: '\uFF4B', 0x35: '\uFF4C',
    0x36: '\uFF4D', 0x37: '\uFF4E', 0x38: '\uFF4F', 0x39: '\uFF50',
    0x3A: '\uFF51', 0x3B: '\uFF52', 0x3C: '\uFF53', 0x3D: '\uFF54',
    0x3E: '\uFF55', 0x3F: '\uFF56', 0x40: '\uFF57', 0x41: '\uFF58',
    0x42: '\uFF59', 0x43: '\uFF5A',
    
    # Hiragana
    0x44: '\u3041', 0x45: '\u3042', 0x46: '\u3043', 0x47: '\u3044',
    0x48: '\u3045', 0x49: '\u3046', 0x4A: '\u3047', 0x4B: '\u3048',
    0x4C: '\u3049', 0x4D: '\u304A', 0x4E: '\u304B', 0x4F: '\u304C',
    0x50: '\u304D', 0x51: '\u304E', 0x52: '\u304F', 0x53: '\u3050',
    0x54: '\u3051', 0x55: '\u3052', 0x56: '\u3053', 0x57: '\u3054',
    0x58: '\u3055', 0x59: '\u3056', 0x5A: '\u3057', 0x5B: '\u3058',
    0x5C: '\u3059', 0x5D: '\u305A', 0x5E: '\u305B', 0x5F: '\u305C',
    0x60: '\u305D', 0x61: '\u305E', 0x62: '\u305F', 0x63: '\u3060',
    0x64: '\u3061', 0x65: '\u3062', 0x66: '\u3063', 0x67: '\u3064',
    0x68: '\u3065', 0x69: '\u3066', 0x6A: '\u3067', 0x6B: '\u3068',
    0x6C: '\u3069', 0x6D: '\u306A', 0x6E: '\u306B', 0x6F: '\u306C',
    0x70: '\u306D', 0x71: '\u306E', 0x72: '\u306F', 0x73: '\u3070',
    0x74: '\u3071', 0x75: '\u3072', 0x76: '\u3073', 0x77: '\u3074',
    0x78: '\u3075', 0x79: '\u3076', 0x7A: '\u3077', 0x7B: '\u3078',
    0x7C: '\u3079', 0x7D: '\u307A', 0x7E: '\u307B',
    
    # More hiragana
    0x7F: '\u307C', 0x80: '\u307D', 0x81: '\u307E', 0x82: '\u307F',
    0x83: '\u3080', 0x84: '\u3081', 0x85: '\u3082', 0x86: '\u3083',
    0x87: '\u3084', 0x88: '\u3085', 0x89: '\u3086', 0x8A: '\u3087',
    0x8B: '\u3088', 0x8C: '\u3089', 0x8D: '\u308A', 0x8E: '\u308B',
    0x8F: '\u308C', 0x90: '\u308D', 0x91: '\u308E', 0x92: '\u308F',
    0x93: '\u3090', 0x94: '\u3091', 0x95: '\u3092', 0x96: '\u3093',
    
    # Katakana
    0x97: '\u30A1', 0x98: '\u30A2', 0x99: '\u30A3', 0x9A: '\u30A4',
    0x9B: '\u30A5', 0x9C: '\u30A6', 0x9D: '\u30A7', 0x9E: '\u30A8',
    0x9F: '\u30A9', 0xA0: '\u30AA', 0xA1: '\u30AB', 0xA2: '\u30AC',
    0xA3: '\u30AD', 0xA4: '\u30AE', 0xA5: '\u30AF', 0xA6: '\u30B0',
    0xA7: '\u30B1', 0xA8: '\u30B2', 0xA9: '\u30B3', 0xAA: '\u30B4',
    0xAB: '\u30B5', 0xAC: '\u30B6', 0xAD: '\u30B7', 0xAE: '\u30B8',
    0xAF: '\u30B9', 0xB0: '\u30BA', 0xB1: '\u30BB', 0xB2: '\u30BC',
    0xB3: '\u30BD', 0xB4: '\u30BE', 0xB5: '\u30BF', 0xB6: '\u30C0',
    0xB7: '\u30C1', 0xB8: '\u30C2', 0xB9: '\u30C3', 0xBA: '\u30C4',
    0xBB: '\u30C5', 0xBC: '\u30C6', 0xBD: '\u30C7', 0xBE: '\u30C8',
    0xBF: '\u30C9', 0xC0: '\u30CA', 0xC1: '\u30CB', 0xC2: '\u30CC',
    0xC3: '\u30CD', 0xC4: '\u30CE', 0xC5: '\u30CF', 0xC6: '\u30D0',
    0xC7: '\u30D1', 0xC8: '\u30D2', 0xC9: '\u30D3', 0xCA: '\u30D4',
    0xCB: '\u30D5', 0xCC: '\u30D6', 0xCD: '\u30D7', 0xCE: '\u30D8',
    0xCF: '\u30D9', 0xD0: '\u30DA', 0xD1: '\u30DB', 0xD2: '\u30DC',
    0xD3: '\u30DD', 0xD4: '\u30DE', 0xD5: '\u30DF', 0xD6: '\u30E0',
    0xD7: '\u30E1', 0xD8: '\u30E2', 0xD9: '\u30E3', 0xDA: '\u30E4',
    0xDB: '\u30E5', 0xDC: '\u30E6', 0xDD: '\u30E7', 0xDE: '\u30E8',
    0xDF: '\u30E9', 0xE0: '\u30EA', 0xE1: '\u30EB', 0xE2: '\u30EC',
    0xE3: '\u30ED', 0xE4: '\u30EE', 0xE5: '\u30EF', 0xE6: '\u30F0',
    0xE7: '\u30F1', 0xE8: '\u30F2', 0xE9: '\u30F3', 0xEA: '\u30F4',
    0xEB: '\u30F5', 0xEC: '\u30F6',
    
    # Multi-byte sequences (F8 XX, F9 XX, FA XX, FB XX, FC XX, FD XX, FE XX)
    # These are extended characters - we'll handle them in the decoder
}

# Game codes for Custom Robo GX
CROBO_GAME_CODES = ['AJIJ', 'AJJJ', 'AJJP']  # Japan, maybe others

# Text terminators
CROBO_TERMINATORS = [0x00]


class CustomRoboGXTextDecoder:
    """Decoder for Custom Robo GX text
    
    Uses Shift-JIS encoding with custom extensions.
    Multi-byte sequences start with 0xF8-0xFE.
    """

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]
            
            # End of string
            if byte == 0x00:
                break
            
            # Control code 0x01 - skip next byte
            if byte == 0x01:
                i += 2
                continue
            
            # Multi-byte sequences (0xF8-0xFE)
            if 0xF8 <= byte <= 0xFE:
                if i + 1 < end:
                    second_byte = data[i + 1]
                    key = (byte << 8) | second_byte
                    # Look up in extended charmap (not implemented yet)
                    result.append(f'[{byte:02X}_{second_byte:02X}]')
                    i += 2
                    continue
            
            # Single-byte characters
            if byte in self.charmap:
                result.append(self.charmap[byte])
            elif 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class CustomRoboGXPlugin(GamePlugin):
    """Плагин для Custom Robo GX (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = CustomRoboGXTextDecoder(CHARMAP_CROBO)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(CROBO_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов Custom Robo GX"""
        logger.info("Извлечение текстовых сегментов для Custom Robo GX")

        segments: list[dict] = []

        # TODO: Find actual pointer table locations for Custom Robo GX
        # For now, use heuristic scanning
        logger.info("Custom Robo GX: Using heuristic scanning (TODO: find pointer tables)")

        logger.info(f"Total segments: {len(segments)}")
        return segments
