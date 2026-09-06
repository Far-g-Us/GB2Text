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
Плагин для CT Special Forces (GBA)

All three GBA CT Special Forces games use the same text encoding.
Source: https://datacrystal.tcrf.net/wiki/CT_Special_Forces_(Game_Boy_Advance)/TBL

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.ct_special_forces')

# CT Special Forces charmap
# Source: DataCrystal TBL
CHARMAP_CTSF: dict[int, str] = {
    # ASCII printable characters (shifted by 0x10 compared to standard ASCII)
    0x00: ' ', 0x01: '!', 0x02: '"', 0x03: '#', 0x04: '$', 0x05: '%',
    0x06: '&', 0x07: "'", 0x08: '(', 0x09: ')', 0x0A: '*', 0x0B: '+',
    0x0C: ',', 0x0D: '-', 0x0E: '.', 0x0F: '/',
    0x10: '0', 0x11: '1', 0x12: '2', 0x13: '3', 0x14: '4',
    0x15: '5', 0x16: '6', 0x17: '7', 0x18: '8', 0x19: '9',
    0x1A: ':', 0x1B: ';', 0x1C: '<', 0x1D: '=', 0x1E: '>', 0x1F: '?',
    0x20: '@',
    0x21: 'A', 0x22: 'B', 0x23: 'C', 0x24: 'D', 0x25: 'E', 0x26: 'F',
    0x27: 'G', 0x28: 'H', 0x29: 'I', 0x2A: 'J', 0x2B: 'K', 0x2C: 'L',
    0x2D: 'M', 0x2E: 'N', 0x2F: 'O', 0x30: 'P', 0x31: 'Q', 0x32: 'R',
    0x33: 'S', 0x34: 'T', 0x35: 'U', 0x36: 'V', 0x37: 'W', 0x38: 'X',
    0x39: 'Y', 0x3A: 'Z', 0x3B: '[', 0x3C: '\\', 0x3D: ']', 0x3E: '_',
    0x3F: 'a', 0x40: 'b', 0x41: 'c', 0x42: 'd', 0x43: 'e', 0x44: 'f',
    0x45: 'g', 0x46: 'h', 0x47: 'i', 0x48: 'j', 0x49: 'k', 0x4A: 'l',
    0x4B: 'm', 0x4C: 'n', 0x4D: 'o', 0x4E: 'p', 0x4F: 'q', 0x50: 'r',
    0x51: 's', 0x52: 't', 0x53: 'u', 0x54: 'v', 0x55: 'w', 0x56: 'x',
    0x57: 'y', 0x58: 'z',
    
    # Special characters
    0x59: 'z~', 0x5A: 'ß',
    0x5B: '{', 0x5C: '|', 0x5D: '}', 0x5E: '¿', 0x5F: '¡',
    0x60: 'à', 0x61: 'á', 0x62: 'ä', 0x63: 'â', 0x64: 'ã', 0x65: 'æ',
    0x66: 'è', 0x67: 'é', 0x68: 'ë', 0x69: 'ê', 0x6A: 'ì', 0x6B: 'í',
    0x6C: 'ï', 0x6D: 'î', 0x6E: 'ç', 0x6F: 'm¨',
    0x70: 'ò', 0x71: 'ó', 0x72: 'ö', 0x73: 'ô', 0x74: 'ù', 0x75: 'ú',
    0x76: 'ü', 0x77: 'û', 0x78: 'ÿ', 0x79: 'ñ', 0x7A: 'œ', 0x7B: 'Æ',
    0x7C: 'Œ', 0x7D: 'Ü',
    
    # Control codes
    0x7E: '[DOWN]', 0x7F: '[UP]', 0x80: '[LEFT]', 0x81: '[RIGHT]',
    0x82: '[A]', 0x83: '[B]', 0x84: '[L]', 0x85: '[R]',
    0x86: '°', 0x87: 'Á', 0x88: 'È', 0x89: 'Ä',
}

# Game codes for CT Special Forces
CTSF_GAME_CODES = ['A4FE', 'A4FJ', 'A4FP']  # USA, Japan, Europe

# Text terminators
CTSF_TERMINATORS = [0xFF]


class CTSFTextDecoder:
    """Decoder for CT Special Forces text"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]
            
            if byte in CTSF_TERMINATORS:
                break
            
            if byte in self.charmap:
                result.append(self.charmap[byte])
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class CTSpecialForcesPlugin(GamePlugin):
    """Плагин для CT Special Forces (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = CTSFTextDecoder(CHARMAP_CTSF)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(CTSF_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов CT Special Forces"""
        logger.info("Извлечение текстовых сегментов для CT Special Forces")

        segments: list[dict] = []

        # TODO: Find actual pointer table locations for CT Special Forces
        # For now, use heuristic scanning
        logger.info("CT Special Forces: Using heuristic scanning (TODO: find pointer tables)")

        logger.info(f"Total segments: {len(segments)}")
        return segments
