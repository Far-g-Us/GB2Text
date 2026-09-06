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
Плагин для Wario Land 4 (GBA)

Game codes: AWAE (USA/EUR), AWAJ (Japan)

Text encoding: ASCII-like (DataCrystal)
Source: https://datacrystal.tcrf.net/wiki/Wario_Land_4/TBL

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.wario_land_4')

# Wario Land 4 charmap (COMPLETE from DataCrystal)
# Source: https://datacrystal.tcrf.net/wiki/Wario_Land_4/TBL
# Very simple ASCII-like encoding
CHARMAP_WL4: dict[int, str] = {
    # Digits
    0x00: '0', 0x01: '1', 0x02: '2', 0x03: '3', 0x04: '4',
    0x05: '5', 0x06: '6', 0x07: '7', 0x08: '8', 0x09: '9',
    # Uppercase A-Z
    0x0A: 'A', 0x0B: 'B', 0x0C: 'C', 0x0D: 'D', 0x0E: 'E',
    0x0F: 'F', 0x10: 'G', 0x11: 'H', 0x12: 'I', 0x13: 'J',
    0x14: 'K', 0x15: 'L', 0x16: 'M', 0x17: 'N', 0x18: 'O',
    0x19: 'P', 0x1A: 'Q', 0x1B: 'R', 0x1C: 'S', 0x1D: 'T',
    0x1E: 'U', 0x1F: 'V', 0x20: 'W', 0x21: 'X', 0x22: 'Y',
    0x23: 'Z',
    # Lowercase a-z
    0x24: 'a', 0x25: 'b', 0x26: 'c', 0x27: 'd', 0x28: 'e',
    0x29: 'f', 0x2A: 'g', 0x2B: 'h', 0x2C: 'i', 0x2D: 'j',
    0x2E: 'k', 0x2F: 'l', 0x30: 'm', 0x31: 'n', 0x32: 'o',
    0x33: 'p', 0x34: 'q', 0x35: 'r', 0x36: 's', 0x37: 't',
    0x38: 'u', 0x39: 'v', 0x3A: 'w', 0x3B: 'x', 0x3C: 'y',
    0x3D: 'z',
    # Punctuation
    0x3E: '.', 0x3F: '&', 0xE1: "'", 0xE2: ',', 0xE3: '.',
    0xE4: '-', 0xE5: '~', 0xE6: '...', 0xE7: '!', 0xE8: '?',
    0xE9: '(', 0xEA: ')', 0xEB: '\u300C', 0xEC: '\u300D',  # 「」
    0xED: '\u300E', 0xEE: '\u300F',  # 『』
    0xEF: '[', 0xF0: ']', 0xF1: 'C', 0xF2: '-',
    # Space
    0xFF: ' ',
}

# Known text locations from DataCrystal
WL4_TEXT_LOCATIONS: dict[str, int] = {
    'entry_passage': 0x64C778,
    'emerald_passage': 0x64C7AB,
    'ruby_passage': 0x64C7E1,
    'topaz_passage': 0x64C814,
    'sapphire_passage': 0x64C847,
    'gold_pyramid': 0x64C87C,
    'sound_room': 0x64C8B3,
    'hall_hieroglyphs': 0x64CEE1,
    'spoiled_rotten': 0x65CF18,
    'mini_game_shop': 0x65CF4C,
    'palm_tree_paradise': 0x65CF7E,
    'wildflower_fields': 0x65CFB2,
    'mystic_lake': 0x65CFE9,
    'monsoon_jungle': 0x65D01C,
    'cractus': 0x65D053,
    'curious_factory': 0x65D0B5,
    'toxic_landfill': 0x65D0EA,
    '40_below_fridge': 0x65D11F,
    'pinball_zone': 0x65D155,
    'cuckoo_condor': 0x65D188,
    'toy_block_tower': 0x65D1EF,
    'big_board': 0x65D224,
    'doodle_woods': 0x65D259,
    'domino_row': 0x65D28E,
    'aerodent': 0x65D2C3,
    'crescent_moon_village': 0x65D324,
    'arabian_night': 0x65D35C,
    'fiery_cavern': 0x65D391,
    'hotel_horror': 0x65D3C5,
    'catbat': 0x65D3FC,
    'golden_passage': 0x65D460,
    'golden_diva': 0x65D495,
    # Music names
    'about_that_shepherd': 0x6CB4A5,
    'things_that_never_change': 0x6CB4D7,
    'tomorrows_blood_pressure': 0x6CB50A,
    'beyond_the_headrush': 0x6CB541,
    'driftwood_island_dog': 0x6CB572,
    'judges_feet': 0x6CB5AB,
    'moons_lamppost': 0x6CB5DD,
    'soft_shell': 0x6CB616,
    'so_sleepy': 0x6CB64A,
    'short_futon': 0x6CB67B,
    'avocado_song': 0x6CB6B1,
    'mr_fly': 0x6CB6E7,
    'yesterdays_words': 0x6CB716,
    'the_errand': 0x6CB74E,
    'you_and_your_shoes': 0x6CB77E,
    'mr_ether_planaria': 0x6CB7B1,
    # Mini-game shop messages
    'win_medals': 0x6F4836,
    'homerun_derby': 0x6F486A,
    'wario_hop': 0x6F489E,
    'wario_roulette': 0x6F48D2,
    'need_more_coins': 0x6F4906,
    'under_construction': 0x6F493A,
    'want_to_play_more': 0x6F498E,
    'come_back_after_saving': 0x6F49A2,
    'come_again': 0x6F49D6,
    'welcome_back': 0x6F4A0A,
    'new_high_score': 0x6F4A3E,
    'dont_want_to_play': 0x6F4A72,
    # Item shop messages
    'leaving_without_buying': 0x73D472,
    'apple_bomb': 0x73D4A6,
    'blast_cannon': 0x73D4DA,
    'vizorman': 0x73D50E,
    'bugle': 0x73D542,
    'black_dog': 0x73D576,
    'large_lips': 0x73D5AA,
    'big_fist': 0x73D5DE,
    'black_dragon': 0x73D612,
    'smile_for_you': 0x73D646,
    'welcome_item_shop': 0x73D67A,
    'need_more_medals': 0x73D6AE,
    'thank_you': 0x73D6E2,
    'go_play_mini_games': 0x73D716,
    'hmph': 0x73D74A,
}

# Game codes for detection
WL4_GAME_CODES = ['AWAE', 'AWAJ']


class WL4TextDecoder:
    """Decoder for Wario Land 4 text"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            # End of string (0x00 or 0xFF)
            if byte in (0x00, 0xFF):
                if byte == 0xFF:
                    result.append(' ')
                break

            if byte in self.charmap:
                result.append(self.charmap[byte])
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class WarioLand4Plugin(GamePlugin):
    """Плагин для Wario Land 4 (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = WL4TextDecoder(CHARMAP_WL4)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(WL4_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов Wario Land 4"""
        logger.info("Извлечение текстовых сегментов для Wario Land 4")

        segments: list[dict] = []

        # Add known text locations as individual segments
        for name, offset in WL4_TEXT_LOCATIONS.items():
            if offset < len(rom.data):
                # Find end of string
                end = offset
                while end < len(rom.data) and end - offset < 200:
                    if rom.data[end] in (0x00, 0xFF):
                        end += 1
                        break
                    end += 1

                segments.append({
                    'name': f'wl4_{name}',
                    'start': offset,
                    'end': end,
                    'decoder': self._decoder,
                    'compression': None,
                    'charmap': CHARMAP_WL4,
                    'terminators': [0x00, 0xFF],
                })

        # Also scan for text blocks
        segments.extend(self._scan_for_text(rom))

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def _scan_for_text(self, rom: GameBoyROM) -> list[dict]:
        """Scan for WL4 text blocks"""
        segments: list[dict] = []

        # Scan ranges (ROM is 8MB)
        scan_ranges = [
            (0x600000, 0x800000),  # Text area
        ]

        for range_start, range_end in scan_ranges:
            if range_start >= len(rom.data):
                continue

            end = min(range_end, len(rom.data))
            offset = range_start

            while offset < end - 10:
                # WL4 text: 0x0A-0x23 (A-Z), 0x24-0x3D (a-z)
                chunk = rom.data[offset:offset + 20]
                letter_count = sum(1 for b in chunk if 0x0A <= b <= 0x3D)

                if letter_count > 10:
                    block_start = offset
                    block_end = min(offset + 0x100, end)

                    # Check if already covered
                    is_new = True
                    for seg in segments:
                        if seg['start'] <= block_start < seg['end']:
                            is_new = False
                            break

                    if is_new:
                        # Find actual end of text
                        while block_end < end and rom.data[block_end] not in (0x00, 0xFF):
                            block_end += 1
                        block_end += 1

                        segments.append({
                            'name': f'wl4_scan_{len(segments)}',
                            'start': block_start,
                            'end': block_end,
                            'decoder': self._decoder,
                            'compression': None,
                            'charmap': CHARMAP_WL4,
                            'terminators': [0x00, 0xFF],
                        })
                        offset = block_end
                        continue
                offset += 1

        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00, 0xFF]

    def get_compression_handler(self, segment_name: str):
        return None
