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
Plugin for Mega Man Battle Network (GBA)

Game codes: AREP (Europe), ABKE (USA), ABKJ (Japan)

Text encoding: custom encoding with control codes
Known facts:
- MMBN uses a custom text encoding with control codes
- The TextPet tool ships with built-in tables for this game
- Pointer tables are located at specific ROM offsets
- Text uses control codes for portraits, menu items, etc.

Source: https://github.com/Prof9/TextPet

NOTE: This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.megaman_battle_network')

# Mega Man Battle Network charmap (ASCII-like encoding)
# Source: analysis of the TextPet plugin
CHARMAP_MMBN: dict[int, str] = {
    # Standard ASCII range
    0x00: ' ', 0x01: 'A', 0x02: 'B', 0x03: 'C', 0x04: 'D', 0x05: 'E',
    0x06: 'F', 0x07: 'G', 0x08: 'H', 0x09: 'I', 0x0A: 'J', 0x0B: 'K',
    0x0C: 'L', 0x0D: 'M', 0x0E: 'N', 0x0F: 'O', 0x10: 'P', 0x11: 'Q',
    0x12: 'R', 0x13: 'S', 0x14: 'T', 0x15: 'U', 0x16: 'V', 0x17: 'W',
    0x18: 'X', 0x19: 'Y', 0x1A: 'Z', 0x1B: 'a', 0x1C: 'b', 0x1D: 'c',
    0x1E: 'd', 0x1F: 'e', 0x20: 'f', 0x21: 'g', 0x22: 'h', 0x23: 'i',
    0x24: 'j', 0x25: 'k', 0x26: 'l', 0x27: 'm', 0x28: 'n', 0x29: 'o',
    0x2A: 'p', 0x2B: 'q', 0x2C: 'r', 0x2D: 's', 0x2E: 't', 0x2F: 'u',
    0x30: 'v', 0x31: 'w', 0x32: 'x', 0x33: 'y', 0x34: 'z',
    0x35: '0', 0x36: '1', 0x37: '2', 0x38: '3', 0x39: '4', 0x3A: '5',
    0x3B: '6', 0x3C: '7', 0x3D: '8', 0x3E: '9',
    0x3F: '!', 0x40: '?', 0x41: '.', 0x42: ',', 0x43: ':', 0x44: ';',
    0x45: '-', 0x46: '+', 0x47: '=', 0x48: '(', 0x49: ')', 0x4A: '/',
    0x4B: "'", 0x4C: '"',
    0x50: '\n',  # Line feed
    0xFF: '\n',  # End of line
}

# Mega Man Battle Network control codes
MMBN_CONTROL_CODES: dict[int, str] = {
    0xE5: '[END]',
    0xE6: '[KEY_WAIT]',
    0xF1: '[CLEAR_MSG]',
    0xF4: '[MUGSHOT_SHOW]',
}

# Text terminators for MMBN
MMBN_TERMINATORS = [0xE5, 0xFF]

# Game codes for detection
MMBN_GAME_CODES = ['AREP', 'ABKE', 'ABKJ']


class MMBNTextDecoder:
    """Mega Man Battle Network text decoder"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            if byte in MMBN_TERMINATORS:
                break

            if byte in MMBN_CONTROL_CODES:
                result.append(MMBN_CONTROL_CODES[byte])
                i += 1
                continue

            if byte in self.charmap:
                result.append(self.charmap[byte])
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class MegaManBattleNetworkPlugin(GamePlugin):
    """Plugin for Mega Man Battle Network (GBA)"""

    _is_stub = True

    def __init__(self):
        super().__init__()
        self._decoder = MMBNTextDecoder(CHARMAP_MMBN)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(MMBN_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract Mega Man Battle Network text segments"""
        logger.info("Извлечение текстовых сегментов для Mega Man Battle Network")

        segments: list[dict] = []

        # TODO: find the actual pointer-table locations for MMBN
        # Heuristic scanning is used for now
        logger.info("MMBN: Using heuristic scanning (TODO: find pointer tables)")

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return MMBN_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
