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

# Metroid Fusion charmap (ASCII encoding)
# Verified: text is stored as plain ASCII in the ROM
# Source: ROM analysis - "SAMUS DESIGN" found at 0x74B8BE as ASCII
CHARMAP_METROID_FUSION: dict[int, str] = {
    # Control codes (0x00-0x1F)
    0x00: '',  # Null/padding
    0x01: '', 0x02: '', 0x03: '', 0x04: '', 0x05: '',
    0x06: '', 0x07: '', 0x08: '', 0x09: '\t', 0x0A: '\n',
    0x0B: '', 0x0C: '', 0x0D: '\r', 0x0E: '', 0x0F: '',
    
    # ASCII printable characters (0x20-0x7E) - direct mapping
    # No need to enumerate - chr(byte) works for all ASCII
    
    # Special
    0xFF: '',  # End of string
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
    """Decoder for Metroid Fusion text
    
    Text is stored as plain ASCII with control codes.
    Control codes (0x00-0x0F) are skipped during decoding.
    """

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))
        found_text = False

        while i < end:
            byte = data[i]
            
            # End of string
            if byte == 0xFF:
                break
            
            # Control codes (0x00-0x0F) - skip them
            if byte <= 0x0F:
                i += 1
                continue
            
            # ASCII printable characters (0x20-0x7E)
            if 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
                found_text = True
            elif byte in self.charmap:
                char = self.charmap[byte]
                if char:
                    result.append(char)
                    found_text = True
            else:
                result.append(f'[{byte:02X}]')
                found_text = True
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
