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
Плагин для Astro Boy: Omega Factor (GBA)

Game codes: BTAE (USA), BTAJ (Japan), BTAP (Europe)

Text encoding: Caesar cipher (shift -1) + control codes
Source: Reverse engineered from ROM analysis

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GameBoyROM, GamePlugin

logger = logging.getLogger('gb2text.plugins.astro_boy')

# Astro Boy control codes (from ROM analysis)
ASTRO_BOY_CONTROL_CODES: dict[int, str] = {
    0x00: '[END]',
    0x01: '[A]',
    0x0D: '[NL]',
    0x7F: '[?]',
    0x8D: '[NL]',
    0x8E: '[PAUSE]',
    0xD0: '[FACE]',
    0xD1: '[FACE2]',
    0xD2: '[FACE3]',
    0xF8: '[?]',
}

# Game codes for detection
ASTRO_BOY_GAME_CODES = ['BTAE', 'BTAJ', 'BTAP']


class AstroBoyDecoder:
    """Decoder for Astro Boy text (Caesar cipher shift -1)"""

    def __init__(self):
        self.charmap: dict[int, str] = {}

        # Build charmap: byte -> char (shifted by -1)
        # Note: 0x20 is not included — in Caesar +1 encoding,
        # space (0x20) is stored as 0x21, so byte 0x20 in ROM
        # is either a raw separator or control code
        for i in range(0x21, 0x7F):
            self.charmap[i] = chr(i - 1)

        # Control codes
        self.charmap.update(ASTRO_BOY_CONTROL_CODES)

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            # End of string
            if byte == 0x00:
                break

            if byte in self.charmap:
                result.append(self.charmap[byte])
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class AstroBoyPlugin(GamePlugin):
    """Плагин для Astro Boy: Omega Factor (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = AstroBoyDecoder()

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(ASTRO_BOY_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов Astro Boy"""
        logger.info("Извлечение текстовых сегментов для Astro Boy: Omega Factor")

        segments: list[dict] = []

        # Find pointer tables and decode text
        segments.extend(self._find_pointer_tables(rom))

        # Also scan for text blocks directly
        segments.extend(self._scan_for_text(rom))

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def _find_pointer_tables(self, rom: GameBoyROM) -> list[dict]:
        """Find pointer tables and decode text at destinations"""
        segments: list[dict] = []

        # Scan for 4-byte GBA pointers
        for i in range(0x100000, min(0x200000, len(rom.data) - 4), 4):
            val = int.from_bytes(rom.data[i:i+4], 'little')
            if 0x08100000 <= val <= 0x08800000:
                target = val - 0x08000000
                if target < len(rom.data):
                    # Check if decoded text looks like dialogue
                    decoded = self._decoder.decode(rom.data, target, 50)
                    if any(word in decoded.upper() for word in ['ASTRO', 'TENMA', 'ROBOT', 'QUE', 'HOLA']):
                        segments.append({
                            'name': f'astro_dialogue_{len(segments)}',
                            'start': target,
                            'end': min(target + 0x100, len(rom.data)),
                            'decoder': self._decoder,
                            'compression': None,
                            'charmap': self._decoder.charmap,
                            'terminators': [0x00],
                        })
                        if len(segments) >= 100:
                            break

        return segments

    def _scan_for_text(self, rom: GameBoyROM) -> list[dict]:
        """Scan for Caesar-encoded text blocks"""
        segments: list[dict] = []

        # Scan for ASCII-like sequences (shifted by +1)
        i = 0x100000
        while i < min(0x200000, len(rom.data) - 10):
            # Check for shifted ASCII (0x21-0x7F = shifted 0x20-0x7E)
            if 0x21 <= rom.data[i] <= 0x7F:
                start = i
                while i < len(rom.data) and 0x21 <= rom.data[i] <= 0x7F:
                    i += 1
                length = i - start
                if length >= 5:
                    segments.append({
                        'name': f'astro_scan_{len(segments)}',
                        'start': start,
                        'end': i,
                        'decoder': self._decoder,
                        'compression': None,
                        'charmap': self._decoder.charmap,
                        'terminators': [0x00],
                    })
            else:
                i += 1

        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00]

    def get_compression_handler(self, segment_name: str):
        return None
