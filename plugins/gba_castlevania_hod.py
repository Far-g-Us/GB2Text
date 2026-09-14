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
Plugin for Castlevania: Harmony of Dissonance (GBA)

Game codes: ACHP (Europe), ACHJ (Japan), ACHI (USA)

Text encoding: ASCII + control codes
Known facts:
- Castlevania GBA games use ASCII encoding
- Control codes appear before text blocks
- Text is stored directly in the ROM

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GameBoyROM
from plugins.gba_castlevania import (
    CastlevaniaGBAPlugin,
)

logger = logging.getLogger('gb2text.plugins.castlevania_hod')

# Game codes for detection
HOD_GAME_CODES = ['ACHP', 'ACHJ', 'ACHI']


class CastlevaniaHODPlugin(CastlevaniaGBAPlugin):
    """Plugin for Castlevania: Harmony of Dissonance (GBA)"""

    _is_stub = True

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(HOD_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract Castlevania: Harmony of Dissonance text segments"""
        logger.info("Извлечение текстовых сегментов для Castlevania: Harmony of Dissonance")

        segments: list[dict] = []

        # TODO: Find the actual text-block locations for Harmony of Dissonance
        # For now use heuristic scanning
        logger.info("Диссонанс Гармонии: используется эвристическое сканирование")

        logger.info(f"Всего сегментов: {len(segments)}")
        return segments
