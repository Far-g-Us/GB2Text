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
Plugin for CT Special Forces (GBA)
Stub - a character table is needed.

Game codes: AC7E (USA)

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.ct_special_forces')

GAME_CODES = ['AC7E']


class CTSpecialForcesPlugin(GamePlugin):
    """Plugin for CT Special Forces (GBA)"""

    _is_stub = True

    def __init__(self):
        super().__init__()

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info("STUB: таблица символов для CT Special Forces не реализована")
        return []

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00, 0xFF]

    def get_compression_handler(self, segment_name: str):
        return None
