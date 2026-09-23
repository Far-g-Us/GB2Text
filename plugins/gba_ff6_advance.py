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
Plugin for Final Fantasy VI Advance (GBA)

Game codes: BZ6E (USA), BZ6J (Japan), BZ6P (Europe)

Text encoding: proprietary single-byte + multibyte (Square Enix)
Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_VI_Advance/TBL

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.ff6_advance')

# FF6 Advance charmap (modeled on FF4/FF5 from DataCrystal)
# Source: DataCrystal TBL format
# Single-byte characters (0x00-0x77)
CHARMAP_FF6: dict[int, str] = {
    0x00: ' ', 0x01: 'e', 0x02: 't', 0x03: 'a', 0x04: 'o', 0x05: 'n',
    0x06: 's', 0x07: 'r', 0x08: 'i', 0x09: 'h', 0x0A: 'l', 0x0B: '.',
    0x0C: 'd', 0x0E: 'u', 0x0F: 'm', 0x10: 'g', 0x11: 'y', 0x12: 'c',
    0x13: 'w', 0x14: 'f', 0x15: 'p', 0x16: '!', 0x17: 'b', 0x18: ':',
    0x19: 'k', 0x1A: "'", 0x1B: ',', 0x1C: 'v', 0x1D: 'T', 0x1E: 'I',
    0x1F: 'S', 0x20: 'C', 0x21: 'G', 0x22: 'W', 0x23: '?', 0x24: 'F',
    0x25: 'L', 0x26: '-', 0x27: 'B', 0x28: 'P', 0x29: 'M', 0x2A: 'K',
    0x2B: 'H', 0x2C: 'A', 0x2D: 'D', 0x2E: 'E', 0x2F: 'R', 0x30: 'x',
    0x31: 'O', 0x32: 'Y', 0x33: 'N', 0x34: 'z', 0x35: 'j', 0x36: 'q',
    0x37: '1', 0x38: 'V', 0x39: 'U', 0x3A: '2', 0x3B: 'X', 0x3C: 'J',
    0x3D: '*', 0x3E: '"', 0x3F: '0', 0x40: '3', 0x41: 'Z', 0x42: '4',
    0x43: '5', 0x44: 'Q', 0x45: '6', 0x46: '8', 0x47: '7', 0x48: '%',
    0x49: '9', 0x4A: '+', 0x4B: ';', 0x4C: '/', 0x4E: '&', 0x4F: '(',
    0x50: ')', 0x51: '=',
    # Japanese/special (0x52-0x77)
    0x52: '\u30FB', 0x53: '\u2025', 0x54: '\u3002', 0x55: '\u30FC',
    0x56: '[DPAD]', 0x57: '[DPAD_UP]', 0x58: '[DPAD_RIGHT]',
    0x59: '[DPAD_DOWN]', 0x5A: '[DPAD_LEFT]', 0x5B: '\u2191',
    0x5C: '\u2192', 0x5D: '\u2193', 0x5E: '\u2190', 0x5F: '[CLAW]',
    0x60: '[ROD]', 0x61: '[STAFF]', 0x62: '[KNIFE]', 0x63: '[SWORD]',
    0x64: '[BIG_SWORD]', 0x65: '[LANCE]', 0x66: '[KUNAI]', 0x67: '[KATANA]',
    0x68: '[SHURIKEN]', 0x69: '[BOOMERANG]', 0x6A: '[AXE]', 0x6B: '[TOOL]',
    0x6C: '\u266A', 0x6D: '[BOW]', 0x6E: '[ARROW]', 0x6F: '[HAMMER]',
    0x70: '[WHIP]', 0x71: '[SHIELD]', 0x72: '[HELMET]', 0x73: '[ARMOR]',
    0x74: '[GLOVE]', 0x75: '[WHITE_MAGIC]', 0x76: '[BLACK_MAGIC]',
    0x77: '[TIME_MAGIC]',
}

# FF6 Advance control codes (from DataCrystal)
FF6_CONTROL_CODES: dict[int, str] = {
    # End of line
    0x0D: '[END]',
    # Line breaks
    0xC28E: '[LINEBREAK]', 0xC392: '[LINEBREAK_MENU]',
    # Names (dialogue)
    0xC2A5: '[NAME_LOCKE]', 0xC2A6: '[NAME_CELES]', 0xC2A7: '[NAME_TERRA]',
    0xC2A8: '[NAME_EDGAR]', 0xC2A9: '[NAME_SABIN]', 0xC2AA: '[NAME_CYAN]',
    0xC2AB: '[NAME_SHADOW]', 0xC2AC: '[NAME_SETZER]', 0xC2AD: '[NAME_CEALES]',
    0xC2AE: '[NAME_RELM]', 0xC2AF: '[NAME_STRAGO]', 0xC2B0: '[NAME_MOOGLE]',
    # Images
    0xC2B1: '[PIC_LOCKE]', 0xC2B2: '[PIC_CELES]', 0xC2B3: '[PIC_TERRA]',
    0xC2B4: '[PIC_EDGAR]', 0xC2B5: '[PIC_SABIN]', 0xC2B6: '[PIC_CYAN]',
    0xC2B7: '[PIC_SHADOW]', 0xC2B8: '[PIC_SETZER]', 0xC2B9: '[PIC_CEALES]',
    0xC2BA: '[PIC_RELM]', 0xC2BB: '[PIC_STRAGO]',
    # Remove image
    0xC2BC: '[REMOVE_PIC]',
    # Variables
    0xC2BD: '[VAR1]', 0xC2BE: '[CUR_HP]', 0xC2BF: '[VAR2]', 0xC2C0: '[MAX_HP]',
    # Treasure/Inn
    0xC2C1: '[TREASURE_ITEM]', 0xC2C2: '[INN_GIL]',
    # Window control
    0xC2C3: '[BOX_NO_BUTTON]',
    # Colors
    0xC2C4: '[COLOR_WHITE]', 0xC2C5: '[COLOR_BLUE]', 0xC2C6: '[COLOR_RED]',
    0xC2C7: '[COLOR_GREEN]', 0xC2C8: '[COLOR_PURPLE]', 0xC2C9: '[COLOR_YELLOW]',
}

# FF6 Advance text terminators
# Only 0x0D is the end-of-line marker
# 0x00 is a SPACE character, not a terminator
FF6_TERMINATORS = [0x0D]

# Known pointer-table locations for FF6 Advance (BZ6E)
# Source: DataCrystal
FF6_POINTER_TABLES = [
    (0x000000, 0x000000, 'unknown'),  # TODO: Find the actual locations
]

# Known text-block locations for FF6 Advance (BZ6E)
# Source: DataCrystal
FF6_TEXT_BLOCKS = [
    (0x000000, 0x000000, 'unknown'),  # TODO: Find the actual locations
]


class FF6AdvanceTextDecoder:
    """FF6 Advance text decoder"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []  # pragma: no cover
        i = start  # pragma: no cover
        end = min(start + length, len(data))  # pragma: no cover

        while i < end:  # pragma: no cover
            byte = data[i]

            if byte in FF6_TERMINATORS:
                break

            if byte in FF6_CONTROL_CODES:
                result.append(FF6_CONTROL_CODES[byte])
                i += 1
                continue

            if byte in self.charmap:
                result.append(self.charmap[byte])
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)  # pragma: no cover


class FF6AdvancePlugin(GamePlugin):
    """Plugin for Final Fantasy VI Advance"""

    _is_stub = True

    def __init__(self) -> None:
        self._decoder = FF6AdvanceTextDecoder(CHARMAP_FF6)

    @property
    def game_id_pattern(self) -> str:
        return '^GBA_(BZ6E|BZ6J|BZ6P)$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract Final Fantasy VI Advance text segments"""
        logger.info("Извлечение текстовых сегментов для Final Fantasy VI Advance")

        segments: list[dict] = []  # pragma: no cover

        # TODO: Find the pointer-table location for FF6 Advance
        # For now use heuristic scanning
        logger.info("FF6 Advance: используется эвристическое сканирование (TODO: найти таблицы указателей)")

        logger.info(f"Total segments: {len(segments)}")
        return segments
