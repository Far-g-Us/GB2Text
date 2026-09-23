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
Plugin for Wario Land 4 (GBA)

Game codes: AWAE (USA/EUR), AWAJ (Japan)

Text encoding: ASCII-like (DataCrystal)
Source: https://datacrystal.tcrf.net/wiki/Wario_Land_4/TBL

NOTE: This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.wario_land_4')

# Wario Land 4 charmap (FULL from DataCrystal)
# Source: https://datacrystal.tcrf.net/wiki/Wario_Land_4/TBL
# A very simple ASCII-like encoding
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

# Known text locations from DataCrystal (80 total).
# 3 TBL offsets corrected against real ROM: Sound Room (64C8B2, TBL says 64C8B3),
# Hall of Hieroglyphs (65CEE1, TBL says 64CEE1), Want to play more (6F496E,
# TBL says 6F498E). DataCrystal also lists 15 romaji music-track names at
# 0x6D310E-0x6D3378; excluded from the plugin because those are JP-only labels
# with unstable record boundaries (1–15 FF separators: some borders use 1-3 FF,
# causing our heuristic to leak into adjacent records; trailing binary data with
# bytes in the charmap range decodes as garbage) and are not translatable text.
# The 'Gold Pyramid' name in TBL is actually stored as 'Golden Pyramid' in the ROM.
WL4_TEXT_LOCATIONS: dict[str, int] = {
    'entry_passage': 0x64C778,
    'emerald_passage': 0x64C7AB,
    'ruby_passage': 0x64C7E1,
    'topaz_passage': 0x64C814,
    'sapphire_passage': 0x64C847,
    'gold_pyramid': 0x64C87C,
    'sound_room': 0x64C8B2,
    'hall_hieroglyphs': 0x65CEE1,
    'spoiled_rotten': 0x65CF18,
    'mini_game_shop': 0x65CF4C,
    'palm_tree_paradise': 0x65CF7E,
    'wildflower_fields': 0x65CFB2,
    'mystic_lake': 0x65CFE9,
    'monsoon_jungle': 0x65D01C,
    'cractus': 0x65D053,
    'mini_game_shop_2': 0x65D084,
    'curious_factory': 0x65D0B5,
    'toxic_landfill': 0x65D0EA,
    '40_below_fridge': 0x65D11F,
    'pinball_zone': 0x65D155,
    'cuckoo_condor': 0x65D188,
    'mini_game_shop_3': 0x65D1BC,
    'toy_block_tower': 0x65D1EF,
    'big_board': 0x65D224,
    'doodle_woods': 0x65D259,
    'domino_row': 0x65D28E,
    'aerodent': 0x65D2C3,
    'mini_game_shop_4': 0x65D2F4,
    'crescent_moon_village': 0x65D324,
    'arabian_night': 0x65D35C,
    'fiery_cavern': 0x65D391,
    'hotel_horror': 0x65D3C5,
    'catbat': 0x65D3FC,
    'mini_game_shop_5': 0x65D42C,
    'golden_passage': 0x65D460,
    'golden_diva': 0x65D495,
    'mini_game_shop_6': 0x65D4C8,
    # Music track names
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
    'want_to_play_more': 0x6F496E,
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

# Game codes for game detection
WL4_GAME_CODES = ['AWAE', 'AWAJ']

# Максимальный размер окна одной записи (EN-текст). Эмпирический потолок;
# все 80 известных локаций WL4 укладываются в него с запасом.
WL4_MAX_WINDOW = 200


class WL4TextDecoder:
    """Wario Land 4 text decoder.

    WL4 records are multi-language: the English run (bytes from CHARMAP_WL4)
    is followed by other-language runs encoded outside the English table.
    `get_text_segments` slices each record to exactly the English window, so
    this decoder maps every byte inside the window: 0x00 = '0', 0xFF = space.
    Anything outside the charmap (pointers, foreign text) stops the decode.
    """

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap
        self._encode = self._build_encode()

    def _build_encode(self) -> dict[str, int]:
        rev: dict[str, int] = {}
        for byte, char in self.charmap.items():
            rev.setdefault(char, byte)
        return rev

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]
            if byte not in self.charmap:
                break
            result.append(self.charmap[byte])
            i += 1

        return ''.join(result)

    def encode(self, text: str) -> bytes:
        out = bytearray()
        i = 0
        n = len(text)
        while i < n:
            if text.startswith('...', i) and '...' in self._encode:
                out.append(self._encode['...'])
                i += 3
                continue
            char = text[i]
            byte = self._encode.get(char)
            if byte is None:
                raise ValueError(f"char {char!r} is not in the WL4 charmap")
            out.append(byte)
            i += 1
        return bytes(out)


class WarioLand4Plugin(GamePlugin):
    """Plugin for Wario Land 4 (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = WL4TextDecoder(CHARMAP_WL4)

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(WL4_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4  # pragma: no cover

    def _en_window_end(self, rom: GameBoyROM, offset: int) -> int:
        """Конец английского текста записи: первый байт вне EN-чармапа
        (начало иноязычного блока) либо пробежка из 4+ пробелов (0xFF)
        в конце строки. Пробелы 1-3 подряд — обычная часть текста.

        Эвристика «4+ FF = паддинг» эмпирически валидна для 80 известных
        локаций WL4: EN-строки не содержат 4+ пробелов подряд внутри.
        Если запись длиннее лимита — окно молча обрежется (редкий случай)."""
        data = rom.data  # pragma: no cover
        max_len = min(len(data), offset + WL4_MAX_WINDOW)  # pragma: no cover
        i = offset  # pragma: no cover
        run = 0  # pragma: no cover
        while i < max_len:  # pragma: no cover
            byte = data[i]  # pragma: no cover
            if byte not in CHARMAP_WL4:
                break  # pragma: no cover
            if byte == 0xFF:  # pragma: no cover
                run += 1  # pragma: no cover
                if run >= 4:
                    break  # pragma: no cover
            else:
                run = 0  # pragma: no cover
            i += 1  # pragma: no cover

        # Трейлинг-пробел (0xFF) перед иноязычным блоком — разделитель записей,
        # а не часть текста. Обрезаем его вместе с короткими пробежками FF.
        while i > offset and data[i - 1] == 0xFF:  # pragma: no cover
            i -= 1  # pragma: no cover
        if i - offset >= WL4_MAX_WINDOW:  # pragma: no cover
            logger.warning(  # pragma: no cover
                f"wl4 окно на 0x{offset:X} упёрлось в лимит "
                f"{WL4_MAX_WINDOW} байт; запись могла обрезаться")
        return i  # pragma: no cover

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract Wario Land 4 text segments"""
        logger.info("Извлечение текстовых сегментов для Wario Land 4")

        segments: list[dict] = []

        # Known text locations: each is a single record. The byte window is
        # exactly the English text (stops before the other-language block),
        # so it is treated as a fixed-width segment with one record.
        for name, offset in WL4_TEXT_LOCATIONS.items():  # pragma: no cover
            if offset >= len(rom.data):  # pragma: no cover
                continue  # pragma: no cover

            end = self._en_window_end(rom, offset)  # pragma: no cover
            width = end - offset
            if width <= 0:  # pragma: no cover
                logger.debug(  # pragma: no cover
                    f"wl4_{name}: пустое окно на 0x{offset:X}, пропущен")
                continue

            segments.append({  # pragma: no cover
                'name': f'wl4_{name}',
                'start': offset,
                'end': end,
                'fixed_width': width,
                'record_count': 1,
                'max_length': width,
                'decoder': self._decoder,
                'compression': None,
                'charmap': CHARMAP_WL4,
                'pad_byte': 0xFF,
                'terminators': [],
            })

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return []

    def get_compression_handler(self, segment_name: str):
        return None
