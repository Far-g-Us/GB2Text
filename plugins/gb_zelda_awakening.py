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
Plugin for The Legend of Zelda: Link's Awakening (GB)

game_id: GB_ZELDA (header title "ZELDA", platform GB)

Addresses verified against real ROM:
  "Legend of Zelda, The - Link's Awakening (USA, Europe).gb" (0x80000).

Известные факты (DataCrystal + эмпирическая проверка на реальном ROM):
- Текст — прямой ASCII, апостроф — байт 0x5E ('^').
- Записи разделяются 0xFF; внутри записи 0xFE = разделитель реплик
  (независимый выбор "Yes  No" и т.п.).
- 0xF0-0xF3 — стрелки UP/DOWN/LEFT/RIGHT.
- Зоны текста (острова чистого ASCII+глифов, найдены скриптом
  scripts_roms/la_find_islands.py):
    0x26700-0x26D9F (19 записей)
    0x27D00-0x27EEF (10)
    0x51C00-0x539CD (107)
    0x59700-0x5BFF0 (87)
    0x5C093-0x5C2FD (1, титры)
    0x70A00-0x7335F (104)
    0x74000-0x77FB6 (165)

NOTE: This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM
from plugins.zelda_awakening_common import (
    ZELDA_PAD_BYTE,
    ZELDA_TERMINATORS,
    ZeldaTextDecoder,
)

logger = logging.getLogger('gb2text.plugins.zelda_awakening')

# Segments: name, start, end (verified on real ROM). End is exclusive.
ZELDA_SEGMENTS_GB = [
    ('zelda_gb_dialog_a', 0x26700, 0x26D9F),
    ('zelda_gb_dialog_b', 0x27D00, 0x27EEF),
    ('zelda_gb_dialog_c', 0x51C00, 0x539CD),
    ('zelda_gb_dialog_d', 0x59700, 0x5BFF0),
    ('zelda_gb_credits', 0x5C093, 0x5C2FD),
    ('zelda_gb_dialog_e', 0x70A00, 0x7335F),
    ('zelda_gb_dialog_f', 0x74000, 0x77FB6),
]


class ZeldaAwakeningPlugin(GamePlugin):
    """Plugin for The Legend of Zelda: Link's Awakening (GB)."""

    def __init__(self):
        super().__init__()
        self._decoder = ZeldaTextDecoder()

    @property
    def game_id_pattern(self) -> str:
        return r'^GB_ZELDA$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info("Extracting text segments for Zelda: Link's Awakening (GB)")
        segments: list[dict] = []
        for name, start, end in ZELDA_SEGMENTS_GB:
            if end > len(rom.data):
                logger.warning(
                    f"Segment {name} (0x{start:X}-0x{end:X}) exceeds ROM size, "
                    f"skipped")
                continue
            segments.append({
                'name': name,
                'start': start,
                'end': end,
                'decoder': self._decoder,
                'compression': None,
                'terminators': ZELDA_TERMINATORS,
                'pad_byte': ZELDA_PAD_BYTE,
            })
        logger.info(f"Found {len(segments)} text segments")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return ZELDA_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
