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
Плагин для Kingdom Hearts: Chain of Memories (GBA)

Game codes: B8CE (USA)

Text encoding: ASCII with control codes
Source: ROM analysis

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.kingdom_hearts_com')

# KH:CoM uses ASCII encoding
CHARMAP_KHCOM: dict[int, str] = {i: chr(i) for i in range(0x20, 0x7F)}

# Control codes for KH:CoM
KHCOM_CONTROL_CODES: dict[int, str] = {
    0x01: '[LINE]',
    0x02: '[PAUSE]',
    0x03: '[END]',
    0x04: '[COLOR]',
    0x05: '[SIZE]',
    0x06: '[SPEED]',
    0x07: '[SFX]',
    0x08: '[BGM]',
    0x09: '[VAR]',
    0x0A: '[CHOICE]',
    0x0B: '[SCRIPT]',
    0x0C: '[WAIT]',
    0x0D: '[CLEAR]',
    0x0E: '[SHIFT]',
    0x0F: '[ICON]',
}

# Text terminators
KHCOM_TERMINATORS = [0x00, 0x03]

# Game codes for detection
KHCOM_GAME_CODES = ['B8CE']


class KHCOMTextDecoder:
    """Decoder for KH:CoM text (ASCII + control codes)"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            if byte in KHCOM_TERMINATORS:
                break

            if byte in KHCOM_CONTROL_CODES:
                result.append(KHCOM_CONTROL_CODES[byte])
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


class KingdomHeartsCOMPlugin(GamePlugin):
    """Плагин для Kingdom Hearts: Chain of Memories (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = KHCOMTextDecoder(CHARMAP_KHCOM)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(KHCOM_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов KH:CoM"""
        logger.info("Извлечение текстовых сегментов для KH: Chain of Memories")

        segments: list[dict] = []

        # Scan for ASCII text blocks
        scan_ranges = [
            (0x080000, 0x100000),  # Code area
            (0x200000, 0x300000),  # Data area
            (0x400000, 0x500000),  # More data
        ]

        for range_start, range_end in scan_ranges:
            if range_start >= len(rom.data):
                continue

            end = min(range_end, len(rom.data))
            i = range_start

            while i + 10 < end:
                # Look for ASCII strings (minimum 10 chars)
                length = 0
                while i + length < end and length < 200:
                    b = rom.data[i + length]
                    if 0x20 <= b <= 0x7E:
                        length += 1
                    elif b in (0x00, 0x03):  # terminator
                        break
                    else:
                        break

                if length >= 20:  # Found a text string (minimum 20 chars)
                    segments.append({
                        'name': f'khcom_text_{len(segments)}',
                        'start': i,
                        'end': i + length,
                        'decoder': self._decoder,
                        'compression': None,
                        'charmap': CHARMAP_KHCOM,
                        'terminators': KHCOM_TERMINATORS,
                    })
                    i += length + 1
                else:
                    i += 1

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return KHCOM_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
