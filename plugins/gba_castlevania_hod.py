"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.

Этот проект НЕ содержит и НЕ распространяет никакие ROM-файлы или
защищенные авторским правом материалы. Все ROM-файлы должны быть
законно приобретены пользователем самостоятельно.

Этот инструмент разработан исключительно для исследовательских целей,
обучения и реверс-инжиниринга в рамках, разрешенных законодательством.
"""

"""
Плагин для Castlevania: Harmony of Dissonance (GBA)

Game codes: ACHP (Europe), ACHJ (Japan), ACHI (USA)

Text encoding: ASCII with control codes
Known facts:
- Castlevania GBA games use ASCII encoding
- Control codes appear before text blocks
- Text is stored directly in ROM

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GameBoyROM
from plugins.gba_castlevania import (
    CVASTextDecoder,
    CHARMAP_CVAS,
    CastlevaniaGBAPlugin,
)

logger = logging.getLogger('gb2text.plugins.castlevania_hod')

# Game codes for detection
HOD_GAME_CODES = ['ACHP', 'ACHJ', 'ACHI']


class CastlevaniaHODPlugin(CastlevaniaGBAPlugin):
    """Плагин для Castlevania: Harmony of Dissonance (GBA)"""

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(HOD_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов Castlevania: Harmony of Dissonance"""
        logger.info("Извлечение текстовых сегментов для Castlevania: Harmony of Dissonance")

        segments: list[dict] = []

        # TODO: Find actual text block locations for Harmony of Dissonance
        # For now, use heuristic scanning
        logger.info("Harmony of Dissonance: Using heuristic scanning")

        logger.info(f"Total segments: {len(segments)}")
        return segments
