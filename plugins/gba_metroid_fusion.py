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
Плагин для Metroid Fusion (GBA)

Game codes: AMTE (USA), AMTP (Europe), AMTJ (Japan)

Text encoding: Custom tile-based encoding
Known facts:
- Metroid Fusion uses custom text encoding with control codes
- Pointer tables are located at specific ROM offsets
- Text includes control codes for formatting

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.metroid_fusion')

# Metroid Fusion charmap (from community TBL dump)
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
# These are verified ASCII text strings
METROID_FUSION_TEXT_BLOCKS = [
    (0x74B8BE, 0x74B8D0, 'credits_samus'),      # "SAMUS DESIGN"
    (0x74B992, 0x74B9B0, 'credits_original'),    # "SAMUS ORIGINAL DESIGN"
    (0x74BF34, 0x74BF50, 'credits_programming'), # "SAMUS PROGRAMMING"
    (0x5821F8, 0x582260, 'save_data'),           # "Met4AGB_BackUp01SAVE_END"
]

# Control codes for Metroid Fusion
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


class MetroidFusionTextDecoder:
    """Decoder for Metroid Fusion text using TBL charmap"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            if byte in (0xFF, 0x53):  # End of string
                break

            if byte in METROID_FUSION_CONTROL_CODES:
                result.append(METROID_FUSION_CONTROL_CODES[byte])
                i += 1
                continue

            if byte in self.charmap:
                result.append(self.charmap[byte])
            elif 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class MetroidFusionPlugin(GamePlugin):
    """Плагин для Metroid Fusion (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = MetroidFusionTextDecoder(CHARMAP_METROID_FUSION)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(METROID_FUSION_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов Metroid Fusion

        Uses known text block locations from ROM analysis.
        Text is stored as plain ASCII in the ROM.
        """
        logger.info("Извлечение текстовых сегментов для Metroid Fusion")

        segments: list[dict] = []

        # Use known text block locations
        for start, end, name in METROID_FUSION_TEXT_BLOCKS:
            if start >= len(rom.data) or end > len(rom.data):
                continue

            # Verify there's actual text at this location
            raw = rom.data[start:min(start + 100, end)]
            has_ascii = any(0x20 <= b <= 0x7E for b in raw)

            if has_ascii:
                segments.append({
                    'name': f'metroid_fusion_{name}',
                    'start': start,
                    'end': end,
                    'decoder': self._decoder,
                    'compression': None,
                    'charmap': CHARMAP_METROID_FUSION,
                    'terminators': METROID_FUSION_TERMINATORS,
                })
                logger.info(f"Found text block: {name} at 0x{start:X}-0x{end:X}")

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return METROID_FUSION_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
