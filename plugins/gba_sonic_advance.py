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
Плагин для Sonic Advance (GBA)

Game codes: ASOE (USA)

Text encoding: ASCII
Source: ROM analysis (credits, zone names, music credits)

Text format: Length-prefixed ASCII strings
- Byte 0: string length
- Byte 1: 0x00
- Bytes 2+: ASCII text

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.sonic_advance')

# Sonic Advance uses standard ASCII encoding
CHARMAP_SONIC: dict[int, str] = {i: chr(i) for i in range(0x20, 0x7F)}

# Text terminators
SONIC_TERMINATORS = [0x00]

# Game codes for detection
SONIC_GAME_CODES = ['ASOE']


class SonicTextDecoder:
    """Decoder for Sonic Advance text (ASCII)"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            if byte in SONIC_TERMINATORS:
                break

            if byte in self.charmap:
                result.append(self.charmap[byte])
            elif 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class SonicAdvancePlugin(GamePlugin):
    """Плагин для Sonic Advance (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = SonicTextDecoder(CHARMAP_SONIC)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(SONIC_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов Sonic Advance"""
        logger.info("Извлечение текстовых сегментов для Sonic Advance")

        segments: list[dict] = []

        # Credits text at 0x682000-0x683000 (verified from ROM analysis)
        # Format: length-prefixed ASCII strings
        credits_start = 0x682000
        credits_end = 0x683000

        if credits_end <= len(rom.data):
            segments.append({
                'name': 'sonic_credits',
                'start': credits_start,
                'end': credits_end,
                'decoder': self._decoder,
                'compression': None,
                'charmap': CHARMAP_SONIC,
                'terminators': SONIC_TERMINATORS,
            })
            logger.info(f"Found credits block at 0x{credits_start:X}-0x{credits_end:X}")

        # Scan for more text blocks using heuristic
        # Look for length-prefixed ASCII strings
        scan_ranges = [
            (0x080000, 0x0C0000),  # Code/data area
            (0x600000, 0x700000),  # Data area
        ]

        for range_start, range_end in scan_ranges:
            if range_start >= len(rom.data):
                continue

            end = min(range_end, len(rom.data))
            i = range_start

            while i + 10 < end:
                # Check for length-prefixed string
                str_len = rom.data[i]
                if 3 <= str_len <= 100:
                    # Check if the next bytes are ASCII
                    has_ascii = False
                    for j in range(1, min(str_len + 1, 20)):
                        if i + j < end:
                            b = rom.data[i + j]
                            if 0x20 <= b <= 0x7E:
                                has_ascii = True
                            else:
                                has_ascii = False
                                break

                    if has_ascii and str_len >= 5:
                        # Found a text string
                        seg_end = min(i + str_len + 2, end)
                        segments.append({
                            'name': f'sonic_text_{len(segments)}',
                            'start': i,
                            'end': seg_end,
                            'decoder': self._decoder,
                            'compression': None,
                            'charmap': CHARMAP_SONIC,
                            'terminators': SONIC_TERMINATORS,
                        })
                        i = seg_end
                    else:
                        i += 1
                else:
                    i += 1

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return SONIC_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
