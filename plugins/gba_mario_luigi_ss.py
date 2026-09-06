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
Плагин для Mario & Luigi: Superstar Saga (GBA)

Game code: A88E (USA), BTAE (Europe)
Text encoding: Custom tile-based (0x00-0xFF maps to font tiles)
Pointer table: 4-byte little-endian pointers at 0x08000000 + offset
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.mario_luigi_ss')

# Mario & Luigi: Superstar Saga charmap
# This game uses standard ASCII encoding for text
# Source: ROM analysis, found "MARIO" at header offset 0xA0 (ASCII 0x4D4152494F)
CHARMAP_MLSS: dict[int, str] = {
    # Standard ASCII printable characters
    0x00: ' ',  # Space (or padding)
    0x0A: '\n',  # Newline
    0x0D: '\r',  # Carriage return
    0x20: ' ',  # Space
    0x21: '!', 0x22: '"', 0x23: '#', 0x24: '$', 0x25: '%',
    0x26: '&', 0x27: "'", 0x28: '(', 0x29: ')', 0x2A: '*',
    0x2B: '+', 0x2C: ',', 0x2D: '-', 0x2E: '.', 0x2F: '/',
    0x30: '0', 0x31: '1', 0x32: '2', 0x33: '3', 0x34: '4',
    0x35: '5', 0x36: '6', 0x37: '7', 0x38: '8', 0x39: '9',
    0x3A: ':', 0x3B: ';', 0x3C: '<', 0x3D: '=', 0x3E: '>',
    0x3F: '?', 0x40: '@',
    0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E',
    0x46: 'F', 0x47: 'G', 0x48: 'H', 0x49: 'I', 0x4A: 'J',
    0x4B: 'K', 0x4C: 'L', 0x4D: 'M', 0x4E: 'N', 0x4F: 'O',
    0x50: 'P', 0x51: 'Q', 0x52: 'R', 0x53: 'S', 0x54: 'T',
    0x55: 'U', 0x56: 'V', 0x57: 'W', 0x58: 'X', 0x59: 'Y',
    0x5A: 'Z', 0x5B: '[', 0x5C: '\\', 0x5D: ']', 0x5E: '^',
    0x5F: '_',
    0x60: '`',
    0x61: 'a', 0x62: 'b', 0x63: 'c', 0x64: 'd', 0x65: 'e',
    0x66: 'f', 0x67: 'g', 0x68: 'h', 0x69: 'i', 0x6A: 'j',
    0x6B: 'k', 0x6C: 'l', 0x6D: 'm', 0x6E: 'n', 0x6F: 'o',
    0x70: 'p', 0x71: 'q', 0x72: 'r', 0x73: 's', 0x74: 't',
    0x75: 'u', 0x76: 'v', 0x77: 'w', 0x78: 'x', 0x79: 'y',
    0x7A: 'z', 0x7B: '{', 0x7C: '|', 0x7D: '}', 0x7E: '~',
    # Control characters
    0xFF: '[END]',  # End of string marker
}

# Known text locations for MLSS USA
# Based on ROM analysis: text is stored as plain ASCII strings
MLSS_TEXT_LOCATIONS = [
    (0x211000, 0x212000, 'menu_phrases'),  # "Hello!", "Thank you!", etc.
    (0x3F4000, 0x3F6000, 'shop_dialogue'),  # Shop dialogue
    (0x3FF000, 0x400000, 'npc_dialogue'),  # NPC dialogue
]

# Text terminators
MLSS_TERMINATORS = [0xFF, 0x00]

# Text terminator
MLSS_TERMINATORS = [0xFF, 0x00]


class MLSSTextDecoder:
    """Decoder for Mario & Luigi SS text"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]
            if byte in (0x00, 0xFF):
                break
            if byte in self.charmap:
                result.append(self.charmap[byte])
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class MarioLuigiSSPlugin(GamePlugin):
    """Плагин для Mario & Luigi: Superstar Saga (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = MLSSTextDecoder(CHARMAP_MLSS)

    @property
    def game_id_pattern(self) -> str:
        # USA: A88E, Japan: BTEJ, Europe: BTEP
        return r'^GBA_(A88E|BTEJ|BTEP)$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов MLSS"""
        logger.info("Извлечение текстовых сегментов для Mario & Luigi: Superstar Saga")

        segments: list[dict] = []

        # Search for ASCII text blocks in known locations
        for start, end, name in MLSS_TEXT_LOCATIONS:
            if start >= len(rom.data):
                continue

            end = min(end, len(rom.data))
            block = rom.data[start:end]

            # Check if block contains ASCII text
            if self._has_ascii_text(block):
                segments.append({
                    'name': f'mlss_{name}',
                    'start': start,
                    'end': end,
                    'decoder': self._decoder,
                    'compression': None,
                    'charmap': CHARMAP_MLSS,
                    'terminators': MLSS_TERMINATORS,
                })
                logger.info(f"Found text block at 0x{start:X}: {name}")

        # Also scan for ASCII text in dialogue banks
        segments.extend(self._scan_for_ascii_text(rom))

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def _scan_for_ascii_text(self, rom: GameBoyROM) -> list[dict]:
        """Scan for ASCII text blocks in the ROM"""
        segments: list[dict] = []

        # Scan ranges where text is likely to be found
        scan_ranges = [
            (0x1D0000, 0x220000),  # Dialogue banks
            (0x3D0000, 0x400000),  # Menu/UI text
        ]

        for range_start, range_end in scan_ranges:
            if range_start >= len(rom.data):
                continue

            end = min(range_end, len(rom.data))
            offset = range_start

            while offset < end - 100:
                # Look for sequences of printable ASCII
                block = rom.data[offset:offset + 200]
                text = block.decode('ascii', errors='ignore')

                # Check if we found a text block
                if len(text) >= 20:
                    # Count printable characters
                    printable = sum(1 for c in text if c.isprintable())
                    if printable / len(text) > 0.7:
                        # Find the end of the text block
                        text_end = offset
                        for i in range(offset, min(offset + 0x1000, end)):
                            if rom.data[i] == 0xFF or rom.data[i] == 0x00:
                                text_end = i
                                break
                        text_end = min(text_end + 1, end)

                        # Check if this is a new segment
                        is_new = True
                        for seg in segments:
                            if abs(seg['start'] - offset) < 0x100:
                                is_new = False
                                break

                        if is_new and text_end - offset >= 50:
                            segments.append({
                                'name': f'mlss_scan_{len(segments)}',
                                'start': offset,
                                'end': text_end,
                                'decoder': self._decoder,
                                'compression': None,
                                'charmap': CHARMAP_MLSS,
                                'terminators': MLSS_TERMINATORS,
                            })
                            offset = text_end
                            continue

                offset += 100

        return segments

    def _has_ascii_text(self, data: bytes) -> bool:
        """Check if data contains ASCII text"""
        if len(data) < 100:
            return False

        # Sample the data
        sample = data[:500]
        try:
            text = sample.decode('ascii', errors='ignore')
            printable = sum(1 for c in text if c.isprintable() or c in '\n\r')
            return printable / len(text) > 0.5
        except Exception:
            return False

    def get_terminators(self, segment_name: str) -> list[int]:
        """Text terminators for MLSS"""
        return MLSS_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        """MLSS does not use compression for text"""
        return None
