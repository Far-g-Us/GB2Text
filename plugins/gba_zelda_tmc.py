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
Плагин для The Legend of Zelda: The Minish Cap (GBA)

Game codes: BZME (USA), AGZJ (Japan), AGZE (Europe)

Text encoding: Custom tile-based encoding (NOT standard ASCII)
The charmap.txt from zeldaret/tmc decomp defines tile indices used in
the assembly source. Actual ROM bytes are tile indices that need to be
mapped through the game's font system.

Known facts:
- Text is stored as tile indices (not ASCII bytes)
- Control codes: 0x01-0x0F prefix bytes for formatting
- Pointer tables at various ROM offsets
- LZ77 compression used for some text data

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.zelda_tmc')

# Zelda: The Minish Cap charmap (from zeldaret/tmc decomp charmap.txt)
# This maps tile indices to characters for the assembly source code.
# In the actual ROM, bytes are tile indices that map to the game's font.
# The mapping is: ROM byte -> tile index -> rendered glyph
#
# The charmap.txt defines constants for use in .s assembly files:
#   'A' = 41  means tile index 0x41 renders as 'A'
#   'a' = 61  means tile index 0x61 renders as 'a'
# This is essentially ASCII-compatible for the basic Latin characters.
CHARMAP_ZELDA_TMC: dict[int, str] = {
    # Control/special markers (used by CharMapDecoder fallback)
    0x00: '$',  # End/string marker (only for CharMapDecoder fallback)
    0x09: '\t',
    0x0A: '\n',

    # Standard ASCII range (0x20-0x7A) - these tile indices render as ASCII
    0x20: ' ', 0x21: '!', 0x22: '"', 0x27: '\'',
    0x28: '(', 0x29: ')', 0x2C: ',', 0x2D: '-',
    0x2E: '.', 0x30: '0', 0x31: '1', 0x32: '2',
    0x33: '3', 0x34: '4', 0x35: '5', 0x36: '6',
    0x37: '7', 0x38: '8', 0x39: '9', 0x3A: ':',
    0x3B: ';', 0x3C: '<', 0x3D: '=', 0x3E: '>',
    0x3F: '?', 0x40: '@',
    0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E',
    0x46: 'F', 0x47: 'G', 0x48: 'H', 0x49: 'I', 0x4A: 'J',
    0x4B: 'K', 0x4C: 'L', 0x4D: 'M', 0x4E: 'N', 0x4F: 'O',
    0x50: 'P', 0x51: 'Q', 0x52: 'R', 0x53: 'S', 0x54: 'T',
    0x55: 'U', 0x56: 'V', 0x57: 'W', 0x58: 'X', 0x59: 'Y',
    0x5A: 'Z', 0x5B: '[', 0x5D: ']',
    0x61: 'a', 0x62: 'b', 0x63: 'c', 0x64: 'd', 0x65: 'e',
    0x66: 'f', 0x67: 'g', 0x68: 'h', 0x69: 'i', 0x6A: 'j',
    0x6B: 'k', 0x6C: 'l', 0x6D: 'm', 0x6E: 'n', 0x6F: 'o',
    0x70: 'p', 0x71: 'q', 0x72: 'r', 0x73: 's', 0x74: 't',
    0x75: 'u', 0x76: 'v', 0x77: 'w', 0x78: 'x', 0x79: 'y',
    0x7A: 'z',

    # Extended character
    0xE9: 'é',
}

# Control codes: byte -> number of parameter bytes that follow
TMC_CONTROL_CODE_PARAMS: dict[int, int] = {
    0x01: 2,  # CONTROL_01: 3-byte sequences (e.g., 01 01 xx)
    0x02: 1,  # COLOR: followed by color byte
    0x03: 2,  # CONTROL_03: 3-byte sequences (e.g., 03 00 DB)
    0x04: 2,  # CONTROL_04: 3-byte sequences (e.g., 04 13 xx)
    0x05: 2,  # CHOICE: 3-byte sequences (e.g., 05 03 0D)
    0x06: 1,  # VARIABLE: 2-byte sequences (e.g., 06 00=PLAYER)
    0x07: 2,  # CONTROL_07: 3-byte sequences (e.g., 07 05 84)
    0x08: 1,  # CONTROL_08: 2-byte sequences (e.g., 08 FF)
    0x0C: 1,  # BUTTON: 2-byte sequences (e.g., 0C 00=A)
    0x0F: 1,  # SYMBOL: 2-byte sequences (e.g., 0F 0D='&')
}

# Known text locations for Zelda: The Minish Cap (USA)
# Verified: text is stored as ASCII in the 0x9B0000-0x9D0000 range
# These are direct text blocks, not pointer tables
ZELDA_TMC_TEXT_BLOCKS = [
    (0x9B2789, 0x9B3000, 'intro_text'),      # "Zelda and ..'s adventures in Hyrule"
    (0x9CD30B, 0x9CD500, 'npc_dialogue'),    # "Hello? Goro?"
]

ZELDA_TMC_TERMINATORS = [0xFF, 0x00]

# Game codes for detection (from actual ROM game_code field)
ZELDA_TMC_GAME_CODES = ['BZME', 'AGZJ', 'AGZE']


class TMCTextDecoder:
    """Decoder for Zelda TMC text with control code handling.

    Uses the charmap for character lookup and handles multi-byte
    control code sequences with correct parameter counts.
    """

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        """Decode Zelda TMC text from ROM data."""
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            # End of string
            if byte in (0x00, 0xFF):
                break

            # Control codes with known parameter counts
            if byte in TMC_CONTROL_CODE_PARAMS:
                param_count = TMC_CONTROL_CODE_PARAMS[byte]
                # Consume control code + its parameters
                total_bytes = 1 + param_count
                if i + total_bytes <= end:
                    params = data[i+1:i+1+param_count]
                    param_str = ' '.join(f'{p:02X}' for p in params)
                    result.append(f'[{byte:02X} {param_str}]')
                    i += total_bytes
                else:
                    # Not enough bytes for full control code, skip what we can
                    remaining = end - i
                    if remaining > 1:
                        params = data[i+1:end]
                        param_str = ' '.join(f'{p:02X}' for p in params)
                        result.append(f'[{byte:02X} {param_str}]')
                    i = end
                continue

            # Character lookup from charmap (covers 0x09, 0x0A, 0x20-0x7A, 0xE9, etc.)
            if byte in self.charmap:
                result.append(self.charmap[byte])
                i += 1
                continue

            # Unknown byte - output as hex
            result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class ZeldaTMCPlugin(GamePlugin):
    """Плагин для The Legend of Zelda: The Minish Cap (GBA)"""

    def __init__(self) -> None:
        super().__init__()
        self._decoder = TMCTextDecoder(CHARMAP_ZELDA_TMC)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(ZELDA_TMC_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов Zelda TMC

        Uses known text block locations from decomp analysis.
        Text is stored as ASCII directly in the ROM (not via pointer tables).
        """
        logger.info("Извлечение текстовых сегментов для The Legend of Zelda: The Minish Cap")

        segments: list[dict] = []

        # Use known text block locations
        for start, end, name in ZELDA_TMC_TEXT_BLOCKS:
            if start >= len(rom.data) or end > len(rom.data):
                continue

            # Verify there's actual text at this location
            raw = rom.data[start:min(start + 100, end)]
            has_ascii = any(0x20 <= b <= 0x7E for b in raw)

            if has_ascii:
                segments.append({
                    'name': f'zelda_tmc_{name}',
                    'start': start,
                    'end': end,
                    'decoder': self._decoder,
                    'compression': None,
                    'charmap': CHARMAP_ZELDA_TMC,
                    'terminators': ZELDA_TMC_TERMINATORS,
                })
                logger.info(f"Found text block: {name} at 0x{start:X}-0x{end:X}")

        # Fallback to heuristic scanning if no known blocks found
        if not segments:
            logger.info("No known text blocks found, using heuristic scanning")
            segments = self._heuristic_scan(rom)

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def _heuristic_scan(self, rom: GameBoyROM) -> list[dict]:
        """Эвристический поиск текстовых блоков"""
        from core.scanner import is_text_like

        segments: list[dict] = []
        block_size = 16

        scan_ranges = [
            (0x1F0000, 0x2D0000),
            (0x390000, 0x3B0000),
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
                        'name': f'zelda_tmc_heuristic_{len(segments)}',
                        'start': i,
                        'end': seg_end,
                        'decoder': self._decoder,
                        'compression': None,
                        'charmap': CHARMAP_ZELDA_TMC,
                        'terminators': ZELDA_TMC_TERMINATORS,
                    })
                    i = seg_end
                else:
                    i += block_size

        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        """Байт-терминаторы для Zelda TMC"""
        return ZELDA_TMC_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        """Zelda TMC не использует сжатие для основного текста"""
        return None
