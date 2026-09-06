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
Плагин для Golden Sun (GBA)
Extracts staff credits (ASCII) and detects text pointer structures.

Game codes: AGSE (USA), AGFE (Europe)

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.golden_sun')

GAME_CODES = ['AGSE', 'AGFE']


class GoldenSunTextDecoder:
    """Decoder for Golden Sun text (ASCII credits + custom encoding)"""

    def __init__(self):
        pass

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            # Null terminator
            if byte == 0x00:
                break

            # ASCII printable characters
            if 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class GoldenSunPlugin(GamePlugin):
    """Плагин для Golden Sun (GBA) - extracts staff credits"""

    def __init__(self):
        super().__init__()
        self._decoder = GoldenSunTextDecoder()

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract text segments from Golden Sun ROM"""
        logger.info("Extracting text segments for Golden Sun")

        segments = []

        # Known text areas with ASCII content
        # Credits area (0x0F0000-0x0F2000) contains staff names
        ascii_areas = [
            (0x0F0000, 0x0F2000, 'credits'),
        ]

        for start, end, name in ascii_areas:
            if start >= len(rom.data):
                continue

            end = min(end, len(rom.data))

            # Scan for ASCII text strings
            i = start
            while i < end:
                # Check if current byte is printable ASCII
                if 0x20 <= rom.data[i] <= 0x7E:
                    # Start of a potential string
                    str_start = i
                    while i < end and 0x20 <= rom.data[i] <= 0x7E:
                        i += 1
                    length = i - str_start

                    if length >= 5:  # Minimum 5 characters
                        text = bytes(rom.data[str_start:str_start+length]).decode('ascii', errors='replace')
                        seg_name = f'golden_sun_{name}_{len(segments)}'
                        segments.append({
                            'name': seg_name,
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

        # Also scan for GBA pointers to ASCII text in the ROM
        logger.info("Scanning for GBA pointers to ASCII text...")
        pointer_count = 0

        for i in range(0, len(rom.data) - 4, 4):
            val = int.from_bytes(rom.data[i:i+4], 'little')
            if 0x08000000 <= val <= 0x09000000:
                target = val - 0x08000000
                if target < len(rom.data) - 20:
                    # Check if target points to printable ASCII
                    target_data = rom.data[target:target+20]
                    printable_count = sum(1 for b in target_data[:10] if 0x20 <= b <= 0x7E)

                    if printable_count >= 8:
                        # Extract the text
                        text = self._extract_string(rom.data, target)
                        if text and len(text.strip()) >= 3:
                            seg_name = f'golden_sun_ptr_{len(segments)}'
                            segments.append({
                                'name': seg_name,
                                'start': target,
                                'end': target + len(text),
                                'decoder': None,
                                'compression': None,
                                'charmap': {},
                                'terminators': [0x00],
                                'raw_text': text,
                            })
                            pointer_count += 1

        logger.info(f"Found {pointer_count} pointers to ASCII text")
        logger.info(f"Total segments: {len(segments)}")
        return segments

    def _extract_string(self, rom_data: bytes | bytearray, offset: int) -> str:
        """Extract a single ASCII text string from ROM data"""
        result: list[str] = []
        i = offset
        end = min(offset + 500, len(rom_data))

        while i < end:
            byte = rom_data[i]

            # Null terminator
            if byte == 0x00:
                break

            # ASCII printable characters
            if 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                # Non-ASCII byte - might be control code
                break
            i += 1

        return ''.join(result)

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00]

    def get_compression_handler(self, segment_name: str):
        return None
