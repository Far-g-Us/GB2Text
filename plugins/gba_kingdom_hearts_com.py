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
Plugin for Kingdom Hearts: Chain of Memories (GBA)

Game codes: B8CE (USA)

Current status: STUB. The game is detected; the text structure is not implemented.

Known facts from RE (scripts_roms/, not guaranteed):
- ASCII encoding is used, with control codes in the 0x01-0x0F range
  (LINE/PAUSE/END/COLOR/SIZE/SPEED/SFX/BGM/VAR/CHOICE/SCRIPT/WAIT/CLEAR/
  SHIFT/ICON), terminators 0x00 / 0x03.
- Naive ASCII block scan produced unreadable output
  (wrong encoding/offsets); a verified pointer/text layout is unknown.

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.kingdom_hearts_com')

# Game codes for detection
KHCOM_GAME_CODES = ['B8CE']


class KingdomHeartsCOMPlugin(GamePlugin):
    """Plugin for Kingdom Hearts: Chain of Memories (GBA) - stub"""

    _is_stub = True

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(KHCOM_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info(
            "Kingdom Hearts: Chain of Memories: структура текста не "
            "реализована, возвращаю пустой список"
        )
        return []
