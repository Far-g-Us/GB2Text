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
Плагин для Castlevania: Circle of the Moon (GBA)

Game codes: AAME (USA), AAMJ (Japan), AAMP (Europe)

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

logger = logging.getLogger('gb2text.plugins.castlevania_ctm')

# Game codes for detection
CTM_GAME_CODES = ['AAME', 'AAMJ', 'AAMP']


class CastlevaniaCTMPlugin(CastlevaniaGBAPlugin):
    """Плагин для Castlevania: Circle of the Moon (GBA)"""

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(CTM_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов Castlevania: Circle of the Moon"""
        logger.info("Извлечение текстовых сегментов для Castlevania: Circle of the Moon")

        segments: list[dict] = []

        # TODO: Find actual text block locations for Circle of the Moon
        # For now, use heuristic scanning
        logger.info("Circle of the Moon: Using heuristic scanning")

        logger.info(f"Total segments: {len(segments)}")
        return segments
