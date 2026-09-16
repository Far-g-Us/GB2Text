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
Plugin for Sonic Advance (GBA)

Game codes: ASOE (Sonic Advance USA), A2NE (Sonic Advance 2)

Current status: STUB. The game is detected; the text structure is not implemented.

Known facts from RE (scripts_roms/, not guaranteed):
- SA1 (ASOE): "length prefix + ASCII" heuristic produced garbage output;
  the credits block decode to spaces. A verified pointer/text layout is unknown.
- SA2 (A2NE): the text engine differs from SA1, the structure is not implemented.
- Plain ASCII is used for what little readable text is known.

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.sonic_advance')

# Game codes for game detection
SONIC_GAME_CODES = ['ASOE', 'A2NE']


class SonicAdvancePlugin(GamePlugin):
    """Plugin for Sonic Advance (GBA) - stub"""

    _is_stub = True

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(SONIC_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info(
            "Sonic Advance: структура текста не реализована, "
            "возвращаю пустой список"
        )
        return []
