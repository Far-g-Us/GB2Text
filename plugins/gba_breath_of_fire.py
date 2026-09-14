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
Plugin for Breath of Fire (GBA)

Game codes: ABFE (USA)

Current status: STUB. The game is detected; the text structure is not implemented.

Known facts from RE (scripts_roms/, not guaranteed):
- Pointer table candidate @ 0x117DD4 (1794 entries, stride 4); targets lead
  to the text region ~0x101238.
- Text bytes are in the ~0x30-0x60 range; lines start with 0x02,
  separators 0x03/0x09, terminator 0x00. This is NOT plain ASCII -
  an empirical charmap / transform is required.

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.breath_of_fire')

# Game codes for detection
BOF_GAME_CODES = ['ABFE']


class BreathOfFirePlugin(GamePlugin):
    """Plugin for Breath of Fire (GBA) - stub"""

    _is_stub = True

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(BOF_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info(
            "Breath of Fire: структура текста не реализована, "
            "возвращаю пустой список"
        )
        return []
