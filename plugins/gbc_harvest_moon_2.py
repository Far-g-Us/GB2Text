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
Plugin for Harvest Moon 2 (GBC)

game_id: GBC_HMOON2 (header title "H-MOON2 CGBBM2E", platform GBC)

Current status: STUB. The game is detected; the text structure is not implemented.

Known facts from DataCrystal (user-provided TBL, not guaranteed):
- Non-ASCII charmap:
  0x00-0x09 = digits, 0x0A-0x23 = A-Z, 0x24-0x3D = a-z,
  0x3E-0x61 = special characters.
- Control codes: 0xF0 = [END], 0xF1 = [NEWLINE], 0xF5 = [HOLD],
  0xF8 = [PLAYER NAME].
- DataCrystal ROM map covers only graphics — text segment addresses are unknown.

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.harvest_moon_2')


class HarvestMoon2Plugin(GamePlugin):
    """Plugin for Harvest Moon 2 (GBC) - stub"""

    _is_stub = True

    @property
    def game_id_pattern(self) -> str:
        return r'^GBC_HMOON2CGBBM2E$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info(
            "Harvest Moon 2: структура текста не реализована, "
            "возвращаю пустой список"
        )
        return []
