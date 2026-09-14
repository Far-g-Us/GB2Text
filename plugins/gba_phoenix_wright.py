"""
GB Text Extraction Framework

COPYRIGHT WARNING:
This software tool is intended ONLY for the analysis of ROM files
lawfully owned by the user. Any use of this tool to
illegally copy, distribute, or modify copyrighted
material is strictly prohibited.

This project does NOT contain or distribute any ROM files or
copyrighted material. All ROM files must be
lawfully acquired by the user independently.

This tool is developed exclusively for research purposes,
education, and reverse engineering within the limits permitted by law.
"""

"""
Plugin for Phoenix Wright: Ace Attorney (GBA) - fan translation

Game codes: ASBJ (Japan, fan translation ROM)

Text encoding: ASCII (fan translation)
Source: ROM reverse engineering

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.phoenix_wright')

# The Phoenix Wright fan translation uses ASCII
CHARMAP_PW: dict[int, str] = {i: chr(i) for i in range(0x20, 0x7F)}

# Phoenix Wright control codes
PW_CONTROL_CODES: dict[int, str] = {
    0x01: '[LINE]',
    0x02: '[PAUSE]',
    0x03: '[END]',
    0x04: '[COLOR]',
    0x05: '[SPEED]',
    0x06: '[SFX]',
    0x07: '[BGM]',
    0x08: '[VAR]',
    0x09: '[CHOICE]',
    0x0A: '[WAIT]',
    0x0B: '[CLEAR]',
    0x0C: '[SHIFT]',
    0x0D: '[ICON]',
    0x0E: '[NAME]',
    0x0F: '[TEXTBOX]',
}

# Text terminators
PW_TERMINATORS = [0x00, 0x03]

# Game codes for detection
PW_GAME_CODES = ['ASBJ']


class PhoenixWrightTextDecoder:
    """Text decoder for the Phoenix Wright fan translation"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            if byte in PW_TERMINATORS:
                break

            if byte in PW_CONTROL_CODES:
                result.append(PW_CONTROL_CODES[byte])
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


class PhoenixWrightPlugin(GamePlugin):
    """Plugin for Phoenix Wright: Ace Attorney (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = PhoenixWrightTextDecoder(CHARMAP_PW)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(PW_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract Phoenix Wright text segments"""
        logger.info("Извлечение текстовых сегментов для Phoenix Wright")

        segments: list[dict] = []

        # Scan ASCII text blocks
        scan_ranges = [
            (0x080000, 0x100000),  # Code area
            (0x200000, 0x300000),  # Data area
            (0x400000, 0x500000),  # Additional data
        ]

        for range_start, range_end in scan_ranges:
            if range_start >= len(rom.data):
                continue

            end = min(range_end, len(rom.data))
            i = range_start

            while i + 10 < end:
                # Search for ASCII strings (minimum 10 characters)
                length = 0
                while i + length < end and length < 200:
                    b = rom.data[i + length]
                    if 0x20 <= b <= 0x7E:
                        length += 1
                    elif b in (0x00, 0x03):  # terminator
                        break
                    else:
                        break

                if length >= 20:  # A text string was found (minimum 20 characters)
                    segments.append({
                        'name': f'pw_text_{len(segments)}',
                        'start': i,
                        'end': i + length,
                        'decoder': self._decoder,
                        'compression': None,
                        'charmap': CHARMAP_PW,
                        'terminators': PW_TERMINATORS,
                    })
                    i += length + 1
                else:
                    i += 1

        logger.info(f"Всего сегментов: {len(segments)}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return PW_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
