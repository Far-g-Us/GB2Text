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
Plugin for Keitai Denjuu Telefang 2 (GBA)

Game codes: ATPJ (Japan)

Current status: STUB. The game is detected; the text structure is not implemented.

Known facts from RE (scripts_roms/, not guaranteed):
- Pointer table candidate @ 0x101650 (647 entries, stride 4); targets lead
  to the region ~0x0FCF10.
- Targets are Japanese strings (a custom kana mapping, neither ASCII nor
  Shift-JIS directly; frequent bytes 0x38-0x50, 0xBA, 0xF1, 0xF2).

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.telefang_2')

# Game codes for detection
TELEFANG2_GAME_CODES = ['ATPJ']


class Telefang2Plugin(GamePlugin):
    """Plugin for Keitai Denjuu Telefang 2 (GBA) - stub"""

    _is_stub = True

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(TELEFANG2_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info(
            "Telefang 2: структура текста не реализована, "
            "возвращаю пустой список"
        )
        return []
