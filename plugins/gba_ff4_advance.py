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
Плагин для Final Fantasy IV Advance (GBA)

Game codes: BZ4E (USA), BZ4J (Japan), BZ4P (Europe)

Text encoding: Custom single-byte + multi-byte (Square Enix)
Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_IV_Advance/TBL

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.ff4_advance')

# FF4 Advance charmap — BZ4E (USA)
# Source: FF4 Hacking Wiki / DataCrystal TBL
# Single-byte characters (0x00-0x7F)
CHARMAP_FF4: dict[int, str] = {
    0x00: ' ', 0x01: 'e', 0x02: 'o', 0x03: 't', 0x04: 'a', 0x05: 'r',
    0x06: 'n', 0x07: 's', 0x08: 'i', 0x09: 'h', 0x0A: 'l', 0x0B: '.',
    0x0D: 'u', 0x0E: 'd', 0x0F: 'm', 0x10: 'y', 0x11: 'g', 0x12: 'c',
    0x13: 'w', 0x14: ':', 0x15: 'f', 0x16: '!', 0x17: 'p', 0x18: 'b',
    0x19: 'v', 0x1A: 'I', 0x1B: 'k', 0x1C: "'", 0x1D: ',', 0x1E: 'T',
    0x1F: 'S', 0x20: '?', 0x21: 'W', 0x22: 'C', 0x23: 'A', 0x24: 'B',
    0x25: 'M', 0x26: 'H', 0x27: 'G', 0x28: 'R', 0x29: 'Y', 0x2A: 'D',
    0x2B: 'E', 0x2C: 'L', 0x2D: 'P', 0x2E: 'O', 0x2F: 'N', 0x30: 'F',
    0x31: '-', 0x32: 'z', 0x34: 'K', 0x37: 'U', 0x38: 'j', 0x39: 'x',
    0x3F: '1', 0x40: 'Z', 0x42: '0', 0x43: 'q', 0x45: '2', 0x48: '*',
    0x49: '3', 0x4A: 'V', 0x4B: '"', 0x4F: '(', 0x50: ')', 0x52: '4',
    0x54: 'Q', 0x55: '5', 0x56: '9', 0x57: 'J', 0x58: 'X', 0x5A: '/',
    0x5C: '6', 0x5E: '7', 0x60: '+', 0x64: '8', 0x66: '&', 0x67: '%',
    0x69: ';', 0x6A: '_',
    # Hiragana (0x6F-0x7F)
    0x6F: '\u3042', 0x70: '\u3044', 0x71: '\u3046', 0x72: '\u3048', 0x73: '\u304A',
    0x74: '\u304B', 0x75: '\u304D', 0x76: '\u304F', 0x77: '\u3051', 0x78: '\u3053',
    0x79: '\u3055', 0x7A: '\u3057', 0x7B: '\u3059', 0x7C: '\u305B', 0x7D: '\u305D',
    0x7E: '\u305F', 0x7F: '\u3061',
    # Multi-byte kanji — BZ4E (0xC2XX-0xD6XX)
    0xC4A4: '\u2026',  # Ellipsis
    0xC3A3: '\u793C', 0xC6B6: '\u516C', 0xC48E: '\u6210', 0xC4BA: '\u901A',
    0xC68E: 'h', 0xC69E: 'a', 0xC69F: 'c', 0xC6A0: 'r',
    0xC7BF: ',',
    0xCB81: '%', 0xCBB0: 'i', 0xCBBB: 'g', 0xCBBD: 'l', 0xCBBF: '\u78BA',
    0xCE8E: 'b', 0xCE8F: 'f', 0xCE90: 'j', 0xCE91: 'k', 0xCE94: 'q',
    0xCE95: 'v', 0xCE96: 'w', 0xCE97: 'x', 0xCE99: 'z',
    0xD181: '4',
}

# FF4 Advance control codes (from DataCrystal)
FF4_CONTROL_CODES: dict[int, str] = {
    # Endstring
    0x0C: '[END]',
    # Linebreaks
    0xC596: '[LINEBREAK_DIALOGUE]',
    0xC683: '[LINEBREAK_MENU]',
    # Names
    0xC598: '[NAME_CECIL]', 0xC599: '[NAME_KAIN]', 0xC59A: '[NAME_ROSA]',
    0xC59B: '[NAME_RYDIA]', 0xC59C: '[NAME_CID]', 0xC59D: '[NAME_TELLAH]',
    0xC59E: '[NAME_EDWARD]', 0xC59F: '[NAME_YANG]',
    0xC5A0: '[NAME_PALOM]', 0xC5A1: '[NAME_POLOM]', 0xC5A2: '[NAME_EDGE]',
    0xC5A3: '[NAME_FUSOYA]',
    # Clean Box
    0xC5AC: '[CLEAN_BOX]',
    # Pictures
    0xC5AD: '[PIC_CECIL]', 0xC5AE: '[PIC_KAIN]', 0xC5AF: '[PIC_ROSA]',
    0xC5B0: '[PIC_RYDIA]', 0xC5B1: '[PIC_CID]', 0xC5B2: '[PIC_TELLAH]',
    0xC5B3: '[PIC_EDWARD]', 0xC5B4: '[PIC_YANG]',
    0xC5B5: '[PIC_PALOM]', 0xC5B6: '[PIC_POLOM]', 0xC5B7: '[PIC_EDGE]',
    0xC5B8: '[PIC_FUSOYA]', 0xC5B9: '[PIC_GOLBEZ]',
    # Remove Picture
    0xC5BA: '[REMOVE_PIC]',
    # Variables
    0xC5BB: '[VAR1]', 0xC5BD: '[CUR_HP]', 0xC5BE: '[VAR2]', 0xC5BF: '[MAX_HP]',
    # Treasure/Inn
    0xC680: '[TREASURE_ITEM]', 0xC681: '[INN_GIL]',
    # Box control
    0xC682: '[BOX_NO_BUTTON]',
}

# FF4 Advance text terminators
# Only 0x0C is the end-of-string marker
# 0x00 is a SPACE character, not a terminator
FF4_TERMINATORS = [0x0C]

# Known pointer table locations for FF4 Advance (BZ4E)
# Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_IV_Advance/ROM_map
# Verified: pointer table at 0x2E3680, text data starts at 0x2E98BC
FF4_POINTER_TABLE_OFFSET = 0x2E3680  # Pointer table start (6287 entries, 4 bytes each)
FF4_POINTER_COUNT = 6287             # Number of pointers
FF4_TEXT_DATA_START = 0x2E98BC       # Text data starts at 0x2E98BC (verified from DataCrystal)
FF4_TEXT_BLOCK_END = 0x323B64        # Text block ending
FF4_POINTER_SIZE = 4                 # Each pointer is 4 bytes (2 bytes value + 2 bytes padding)

# Game codes for detection
FF4_GAME_CODES = ['BZ4E', 'BZ4J', 'BZ4P']


class FF4TextDecoder:
    """Decoder for FF4 Advance text with multi-byte control code support"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            if byte in FF4_TERMINATORS:
                break

            # Multi-byte characters (0xC2-0xD6 prefix)
            if 0xC2 <= byte <= 0xD6 and i + 1 < end:
                second = data[i + 1]
                code = (byte << 8) | second
                if code in FF4_CONTROL_CODES:
                    result.append(FF4_CONTROL_CODES[code])
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


class FF4AdvancePlugin(GamePlugin):
    """Плагин для Final Fantasy IV Advance (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = FF4TextDecoder(CHARMAP_FF4)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(FF4_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return FF4_POINTER_SIZE

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов FF4 Advance using pointer table"""
        logger.info("Извлечение текстовых сегментов для Final Fantasy IV Advance")

        segments: list[dict] = []

        # Read pointer table and create segments for each text entry
        # Pointer table at 0x2E3680, each entry is 4 bytes (2 bytes value + 2 bytes padding)
        # Pointers are relative offsets from FF4_TEXT_DATA_START
        ptr_table_size = FF4_POINTER_COUNT * FF4_POINTER_SIZE
        if FF4_POINTER_TABLE_OFFSET + ptr_table_size > len(rom.data):
            logger.error("Pointer table extends beyond ROM data")
            return segments

        # Create segments for all pointers
        for i in range(FF4_POINTER_COUNT):
            ptr_offset = FF4_POINTER_TABLE_OFFSET + i * FF4_POINTER_SIZE
            ptr_val = int.from_bytes(rom.data[ptr_offset:ptr_offset+2], 'little')

            # Calculate actual offset in ROM
            actual_offset = FF4_TEXT_DATA_START + ptr_val

            # Validate offset
            if actual_offset >= len(rom.data):
                continue

            # Find end of text (next pointer or end of block)
            if i + 1 < FF4_POINTER_COUNT:
                next_ptr_offset = FF4_POINTER_TABLE_OFFSET + (i + 1) * FF4_POINTER_SIZE
                next_ptr_val = int.from_bytes(rom.data[next_ptr_offset:next_ptr_offset+2], 'little')
                next_offset = FF4_TEXT_DATA_START + next_ptr_val
            else:
                next_offset = FF4_TEXT_BLOCK_END

            # Ensure valid range
            if next_offset <= actual_offset:
                next_offset = actual_offset + 100  # Fallback

            segments.append({
                'name': f'ff4_text_{i}',
                'start': actual_offset,
                'end': min(next_offset, FF4_TEXT_BLOCK_END),
                'decoder': self._decoder,
                'compression': None,
                'charmap': CHARMAP_FF4,
                'terminators': FF4_TERMINATORS,
                'pointer_table': FF4_POINTER_TABLE_OFFSET,
                'pointer_count': FF4_POINTER_COUNT,
            })

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return FF4_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
