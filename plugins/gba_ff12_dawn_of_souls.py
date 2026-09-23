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
Plugin for Final Fantasy I & II: Dawn of Souls (GBA)

Game codes: BFFE (USA)

Text encoding: proprietary multibyte (Square Enix)
Source: DataCrystal TBL

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.ff12_dawn_of_souls')

# FF1&2 Dawn of Souls charmap — BFFE (USA)
# Source: DataCrystal TBL
CHARMAP_FF12: dict[int, str] = {
    # Single-byte (0x00-0x2E)
    0x00: '[END]',
    0x0A: '\n',  # New line
    0x2D: '-', 0x2E: '.',
    # Multibyte (0x81XX)
    0x810A: '\r',  # CR
    0x8140: ' ', 0x8143: ',', 0x8144: '.', 0x8145: '?', 0x8146: ':',
    0x8147: ';', 0x8148: '?', 0x8149: '!', 0x8151: '_', 0x815E: '/',
    0x815F: '\\', 0x8160: '~', 0x8163: '...', 0x8164: '..',
    0x8165: "'", 0x8166: "'", 0x8167: '"', 0x8168: '"',
    0x8169: '(', 0x816A: ')', 0x816D: '[', 0x816E: ']',
    0x816F: '{', 0x8170: '}', 0x8173: '\u00AB', 0x8174: '\u00BB',
    0x817B: '+', 0x817C: '-', 0x8193: '%', 0x8195: '&', 0x8196: '*',
    0x8197: '@',
    0x819A: '[STAR]', 0x819B: '[CIRCLE]',
    0x81A3: '[UP_TRIANGLE]', 0x81A5: '[DOWN_TRIANGLE]',
    0x81A8: '[RIGHT_ARROW]', 0x81A9: '[LEFT_ARROW]',
    0x81AA: '[UP_ARROW]', 0x81AB: '[DOWN_ARROW]',
    # Digits (0x824F-0x8258)
    0x824F: '0', 0x8250: '1', 0x8251: '2', 0x8252: '3', 0x8253: '4',
    0x8254: '5', 0x8255: '6', 0x8256: '7', 0x8257: '8', 0x8258: '9',
    # Uppercase letters (0x8260-0x8279)
    0x8260: 'A', 0x8261: 'B', 0x8262: 'C', 0x8263: 'D', 0x8264: 'E',
    0x8265: 'F', 0x8266: 'G', 0x8267: 'H', 0x8268: 'I', 0x8269: 'J',
    0x826A: 'K', 0x826B: 'L', 0x826C: 'M', 0x826D: 'N', 0x826E: 'O',
    0x826F: 'P', 0x8270: 'Q', 0x8271: 'R', 0x8272: 'S', 0x8273: 'T',
    0x8274: 'U', 0x8275: 'V', 0x8276: 'W', 0x8277: 'X', 0x8278: 'Y',
    0x8279: 'Z',
    # Lowercase letters (0x8281-0x8299)
    0x8281: 'a', 0x8282: 'b', 0x8283: 'c', 0x8284: 'd', 0x8285: 'e',
    0x8286: 'f', 0x8287: 'g', 0x8288: 'h', 0x8289: 'i', 0x828A: 'j',
    0x828B: 'k', 0x828C: 'l', 0x828D: 'm', 0x828E: 'n', 0x828F: 'o',
    0x8290: 'p', 0x8291: 'q', 0x8292: 'r', 0x8293: 's', 0x8294: 't',
    0x8295: 'u', 0x8296: 'v', 0x8297: 'w', 0x8298: 'x', 0x8299: 'y',
    0x829A: 'z',
    # Characters with diacritics (0x829F-0x82CF)
    0x829F: '\u0152', 0x82A0: '\u0153', 0x82A1: '\u00A1', 0x82A2: '\u00BF',
    0x82A3: '\u00C0', 0x82A4: '\u00C1', 0x82A5: '\u00C2', 0x82A6: '\u00C4',
    0x82A7: '\u00C7', 0x82A8: '\u00C8', 0x82A9: '\u00C9', 0x82AA: '\u00CA',
    0x82AB: '\u00CB', 0x82AC: '\u00CC', 0x82AD: '\u00CD', 0x82AE: '\u00CE',
    0x82AF: '\u00CF', 0x82B0: '\u00D1', 0x82B1: '\u00D2', 0x82B2: '\u00D3',
    0x82B3: '\u00D4', 0x82B4: '\u00D6', 0x82B5: '\u00D9', 0x82B6: '\u00DA',
    0x82B7: '\u00DB', 0x82B8: '\u00DC', 0x82B9: '\u00DF', 0x82BA: '\u00E0',
    0x82BB: '\u00E1', 0x82BC: '\u00E2', 0x82BD: '\u00E4', 0x82BE: '\u00E7',
    0x82BF: '\u00E8', 0x82C0: '\u00E9', 0x82C1: '\u00EA', 0x82C2: '\u00EB',
    0x82C3: '\u00EC', 0x82C4: '\u00ED', 0x82C5: '\u00EE', 0x82C6: '\u00EF',
    0x82C7: '\u00F1', 0x82C8: '\u00F2', 0x82C9: '\u00F3', 0x82CA: '\u00F4',
    0x82CB: '\u00F6', 0x82CC: '\u00F9', 0x82CD: '\u00FA', 0x82CE: '\u00FB',
    0x82CF: '\u00FC',
    0x82D0: '[HEART]',
    # Item icons (0x8300-0x8317)
    0x8300: '[TREASURE]', 0x8301: '[POTION]', 0x8302: '[TENT]',
    0x8303: '[ITEM]', 0x8304: '[SHIELD]', 0x8305: '[KNIFE]',
    0x8306: '[RAPIER]', 0x8307: '[STAFF]', 0x8308: '[MACE]',
    0x8309: '[SPEAR]', 0x830A: '[SWORD]', 0x830B: '[KATANA]',
    0x830C: '[AXE]', 0x830D: '[DOUBLE_AXE]', 0x830E: '[BOW]',
    0x830F: '[HELMET]', 0x8310: '[ROBE]', 0x8311: '[ARMOR]',
    0x8312: '[GLOVES]', 0x8313: '[BOOK]', 0x8314: '[TRASH]',
    0x8315: '[FIST]', 0x8316: '[WHITE_MAGIC]', 0x8317: '[BLACK_MAGIC]',
    # Equipment icons (0x8740-0x8754)
    0x8740: '[SWORD]', 0x8741: '[KATANA]', 0x8742: '[KNIFE]',
    0x8743: '[NUNCHAKU]', 0x8744: '[AXE]', 0x8745: '[HAMMER]',
    0x8746: '[STAFF]', 0x8747: '[SHIRT]', 0x8748: '[ARMOR]',
    0x8749: '[ARMLET]', 0x874A: '[SHIELD]', 0x874B: '[HELMET]',
    0x874C: '[GLOVES]', 0x874D: '[WHITE_MAGIC]', 0x874E: '[BLACK_MAGIC]',
    0x874F: '[POTION]', 0x8750: '[ITEM]', 0x8751: '[TENT]',
    0x8752: '[CHEST]', 0x8753: '[TRASH]', 0x8754: '[??]',
}

# FF1&2 Dawn of Souls control codes
FF12_CONTROL_CODES: dict[int, str] = {
    0x00: '[END]',
}

# Text terminators
FF12_TERMINATORS = [0x00]

# Game codes for detection
FF12_GAME_CODES = ['BFFE']


class FF12TextDecoder:
    """FF1&2 Dawn of Souls text decoder"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []  # pragma: no cover
        i = start  # pragma: no cover
        end = min(start + length, len(data))  # pragma: no cover

        while i < end:  # pragma: no cover
            byte = data[i]  # pragma: no cover

            if byte in FF12_TERMINATORS:  # pragma: no cover
                break  # pragma: no cover

            # Multibyte characters (prefix 0x81-0x87)
            if 0x81 <= byte <= 0x87 and i + 1 < end:  # pragma: no cover
                second = data[i + 1]  # pragma: no cover
                code = (byte << 8) | second  # pragma: no cover
                if code in FF12_CONTROL_CODES:  # pragma: no cover
                    result.append(FF12_CONTROL_CODES[code])  # pragma: no cover
                elif code in self.charmap:
                    result.append(self.charmap[code])  # pragma: no cover
                else:  # pragma: no cover
                    result.append(f'[{byte:02X}{second:02X}]')
                i += 2
                continue

            # Single-byte characters
            if byte in self.charmap:  # pragma: no cover
                result.append(self.charmap[byte])
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)  # pragma: no cover


class FF12DawnOfSoulsPlugin(GamePlugin):
    """Plugin for Final Fantasy I & II: Dawn of Souls (GBA)"""

    _is_stub = True

    def __init__(self):
        super().__init__()
        self._decoder = FF12TextDecoder(CHARMAP_FF12)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(FF12_GAME_CODES)
        return f'^GBA_({codes})$'  # pragma: no cover

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4  # pragma: no cover

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:  # pragma: no cover
        """Extract FF1&2 Dawn of Souls text segments"""
        logger.info("Извлечение текстовых сегментов для FF1&2 Dawn of Souls")

        segments: list[dict] = []

        # TODO: Find the pointer-table location for BFFE
        # For now return an empty list — a ROM analysis is needed
        logger.warning("Pointer table location not yet determined for BFFE")

        return segments

    def get_terminators(self, segment_name: str) -> list[int]:  # pragma: no cover
        return FF12_TERMINATORS  # pragma: no cover

    def get_compression_handler(self, segment_name: str):
        return None  # pragma: no cover
