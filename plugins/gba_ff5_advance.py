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
Плагин для Final Fantasy V Advance (GBA)

Game codes: BZ5E (USA), BZ5J (Japan), BZ5P (Europe)

Text encoding: Custom single-byte + multi-byte (Square Enix)
Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_V_Advance/TBL

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.ff5_advance')

# FF5 Advance charmap (COMPLETE from DataCrystal BZ5E)
# Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_V_Advance/TBL
# Single-byte characters (0x00-0x77)
CHARMAP_FF5: dict[int, str] = {
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

# FF5 Advance control codes (from DataCrystal)
FF5_CONTROL_CODES: dict[int, str] = {
    # Endstring
    0x0D: '[END]',
    # Linebreaks
    0xC28E: '[LINEBREAK]', 0xC392: '[LINEBREAK_MENU]',
    # Pictures
    0xC2A5: '[PIC_BARTZ]', 0xC2A6: '[PIC_LENNA]', 0xC2A7: '[PIC_GALUF]',
    0xC2A8: '[PIC_FARIS]', 0xC2A9: '[PIC_KRILE]', 0xC2AA: '[PIC_BOKO]',
    0xC2AB: '[PIC_CID]', 0xC2AC: '[PIC_MID]', 0xC2AD: '[PIC_DORGANN]',
    0xC2AE: '[PIC_KELGER]', 0xC2AF: '[PIC_XEZAT]', 0xC2B0: '[PIC_KING_TYCOON]',
    0xC2B1: '[PIC_GILGAMESH]', 0xC2B2: '[PIC_EXDEATH]',
    # Bartz' name
    0xC2B3: '[BARTZ_NAME]',
    # Dialogue variables
    0xC2B4: '[DIALOGUE_ITEM]', 0xC2B5: '[DIALOGUE_GIL]',
    0xC2B6: '[DIALOGUE_ABILITY]',
    # Box control
    0xC2B7: '[CLEAN_BOX]', 0xC2B8: '[AUTO_RESPONSE]',
    # Pauses
    0xC2B9: '[PAUSE1]', 0xC2BA: '[PAUSE2]', 0xC2BB: '[PAUSE3]',
    0xC2BC: '[PAUSE4]', 0xC2BD: '[PAUSE5]',
    # Battle variables
    0xC380: '[BATTLE_VAR1]', 0xC381: '[BATTLE_VAR2]', 0xC382: '[BATTLE_VAR3]',
    0xC383: '[BATTLE_ITEM]', 0xC384: '[JOB_ABILITY]', 0xC385: '[MAGIC_ABILITY]',
    0xC386: '[CHAR_NAME]', 0xC391: '[REMOVE_PIC]',
}

# FF5 Advance text terminators
# Only 0x0D is the end-of-string marker
# 0x00 is a SPACE character, not a terminator
FF5_TERMINATORS = [0x0D]

# Game codes for detection
FF5_GAME_CODES = ['BZ5E', 'BZ5J', 'BZ5P']


class FF5TextDecoder:
    """Decoder for FF5 Advance text with multi-byte control code support"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            if byte in FF5_TERMINATORS:
                break

            # Multi-byte characters (0xC2-0xD2 prefix)
            if 0xC2 <= byte <= 0xD2 and i + 1 < end:
                second = data[i + 1]
                code = (byte << 8) | second
                if code in FF5_CONTROL_CODES:
                    result.append(FF5_CONTROL_CODES[code])
                elif code in self.charmap:
                    result.append(self.charmap[code])
                else:
                    result.append(f'[{byte:02X}{second:02X}]')
                i += 2
                continue

            # Single-byte characters
            if byte in self.charmap:
                result.append(self.charmap[byte])
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class FF5AdvancePlugin(GamePlugin):
    """Плагин для Final Fantasy V Advance (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = FF5TextDecoder(CHARMAP_FF5)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(FF5_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов FF5 Advance"""
        logger.info("Извлечение текстовых сегментов для Final Fantasy V Advance")

        segments: list[dict] = []

        # FF5 text block (approximate - needs verification)
        # Scan for text-dense regions
        scan_ranges = [
            (0x200000, 0x500000),
        ]

        for range_start, range_end in scan_ranges:
            if range_start >= len(rom.data):
                continue

            end = min(range_end, len(rom.data))
            offset = range_start

            while offset < end - 100:
                chunk = rom.data[offset:offset + 100]
                letter_count = sum(1 for b in chunk if b in CHARMAP_FF5)

                if letter_count > 20:
                    block_start = offset
                    block_end = min(offset + 0x10000, end)

                    segments.append({
                        'name': f'ff5_text_{len(segments)}',
                        'start': block_start,
                        'end': block_end,
                        'decoder': self._decoder,
                        'compression': None,
                        'charmap': CHARMAP_FF5,
                        'terminators': FF5_TERMINATORS,
                    })
                    offset = block_end
                    continue
                offset += 1

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return FF5_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
