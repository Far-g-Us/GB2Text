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
Plugin for Astro Boy: Omega Factor (GBA)

Game codes: BTAE (USA), BTAJ (Japan), BTAP (Europe)

Current status: STUB. The game is detected; the text structure is not implemented.

Known facts from RE (scripts_roms/, not guaranteed):
- Text encoding: Caesar cipher (shift -1) + control codes
  (0x21-0x7F stores ASCII shifted +1, space is stored as 0x21).
- Control codes: 0x00 [END], 0x0D/0x8D [NL], 0x8E [PAUSE],
  0xD0-0xD2 [FACE...], 0x7F/0xF8 [?].
- Naive pointer scan + Caesar decode produced ~22k garbage segments
  (many false positives); a proper pointer table location is unknown.

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.astro_boy')

# Game codes for detection
ASTRO_BOY_GAME_CODES = ['BTAE', 'BTAJ', 'BTAP']


class AstroBoyPlugin(GamePlugin):
    """Plugin for Astro Boy: Omega Factor (GBA) - stub"""

    _is_stub = True

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(ASTRO_BOY_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info(
            "Astro Boy: Omega Factor: структура текста не реализована, "
            "возвращаю пустой список"
        )
        return []
