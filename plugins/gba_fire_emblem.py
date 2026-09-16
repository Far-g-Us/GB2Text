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
Plugin for Fire Emblem GBA (FE7/FE8)

Game codes: FE7 - BE7E (US), BE7J (JP), AE7Y (EU); FE8 - BE8E (US),
           BE8J (JP), BE8P (EU)

Current status: STUB. The game is detected; the text structure is not implemented.

Known facts from RE (scripts_roms/, FEBuilderGBA, not guaranteed):
- Text encoding: standard ASCII + FE control codes (0x00-0x1C, 0x40, 0x80;
  LoadFace 0x10 + 2 params, escape 0x80 + @XX) + Huffman compression.
- Huffman tree candidates: FE7U @ 0xB808AC, FE8U @ 0x15D48C.
  The tree format is not implemented; the scan produced no reliable blocks.
- Font tile indices 0xA0-0xFF map to Latin glyphs with diacritics on
  US/EU ROMs (approximate, ROM font dependent).

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.fire_emblem_gba')

# Game codes for detection
# FE7: BE7E (US), BE7J (JP), AE7Y (EU)
# FE8: BE8E (US), BE8J (JP), BE8P (EU)
FE7_GAME_CODES = ['BE7E', 'BE7J', 'AE7Y']
FE8_GAME_CODES = ['BE8E', 'BE8J', 'BE8P']
FE_GAME_CODES = FE7_GAME_CODES + FE8_GAME_CODES


class FireEmblemGBAPlugin(GamePlugin):
    """Plugin for Fire Emblem GBA (FE7/FE8) - stub"""

    _is_stub = True

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(FE_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info(
            "Fire Emblem GBA: структура текста не реализована, "
            "возвращаю пустой список"
        )
        return []
