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
Plugin for The Legend of Zelda: Link's Awakening DX (GBC)

game_id: GBC_ZELDAAZLE (header title "ZELDA...AZLE", platform GBC, 0x100000)

Addresses verified against real ROM:
  "Legend of Zelda, The - Link's Awakening DX (USA, Europe).gbc" (0x100000).

Известные факты (DataCrystal + эмпирическая проверка на реальном ROM):
- DX использует тот же движок текста, что и GB-оригинал: прямой ASCII,
  апостроф — байт 0x5E ('^'), терминатор записи 0xFF, разделитель реплик
  0xFE, стрелки 0xF0-0xF3. Декодер общий — plugins/zelda_awakening_common.
- ROM "Legend of Zelda, The - Link's Awakening DX (USA, Europe)" — это
  европейская многоязычная версия (En+Fr+De). Зоны диалогов содержат
  английский блок записей, за которым в той же зоне следует французский
  хвост, а немецкий текст расположен отдельным блоком 0x0FC000-0x0FCB4C
  (в плагин НЕ включён; GB-версия с размером 0x80000 такую зону не
  содержит — сегмент 0x0FC000 просто выходит за пределы ROM).
  Сегменты покрывают ТОЛЬКО английские записи и не захватывают
  примыкающий исполняемый код:
    0x2668E-0x27D42 (90 записей)
    0x51931-0x53F48 (142)
    0x59701-0x5BFA9 (81)
    0x5C095-0x5C48B (1, титры)
    0x70B2A-0x73EB3 (123)
    0x74000-0x77FCC (163)

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

logger = logging.getLogger('gb2text.plugins.zelda_awakening_dx')

# Segments: name, start, end (verified on real ROM). End is exclusive.
# Only English records — French tails (same zone, after EN block) excluded.
ZELDA_SEGMENTS_DX = [
    ('zelda_dx_dialog_a', 0x2668E, 0x27D42),
    ('zelda_dx_dialog_b', 0x51931, 0x53F48),
    ('zelda_dx_dialog_c', 0x59701, 0x5BFA9),
    ('zelda_dx_credits', 0x5C095, 0x5C48B),
    ('zelda_dx_dialog_d', 0x70B2A, 0x73EB3),
    ('zelda_dx_dialog_e', 0x74000, 0x77FCC),
]


class ZeldaAwakeningDXPlugin(GamePlugin):
    """Plugin for The Legend of Zelda: Link's Awakening DX (GBC)."""

    def __init__(self):
        super().__init__()
        self._decoder = ZeldaTextDecoder()

    @property
    def game_id_pattern(self) -> str:
        return r'^GBC_ZELDAAZLE$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info("Extracting text segments for Zelda LA DX (GBC)")
        segments: list[dict] = []
        for name, start, end in ZELDA_SEGMENTS_DX:
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
