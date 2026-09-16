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
Plugin for Harvest Moon 3 (GBC)

game_id: GBC_HMOON3CGBBWAE (header title "H-MOON3 CGBBWAE", platform GBC)

Current status: STUB. The game is detected; the text structure is not implemented.

Known facts: none beyond detection (header title only). Text layout unknown,
needs RE (charmap/pointers). Harvest Moon 2 (gbc_harvest_moon_2) uses a
non-ASCII charmap; Harvest Moon 3 may differ.

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.harvest_moon_3')


class HarvestMoon3Plugin(GamePlugin):
    """Plugin for Harvest Moon 3 (GBC) - stub"""

    _is_stub = True

    @property
    def game_id_pattern(self) -> str:
        return r'^GBC_HMOON3CGBBWAE$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info(
            "Harvest Moon 3: структура текста не реализована, "
            "возвращаю пустой список"
        )
        return []
