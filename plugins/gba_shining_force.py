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
Плагин для Shining Force (GBA)
STUB — requires charmap work.

Game codes: AF5E (USA)

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.shining_force')

GAME_CODES = ['AF5E']


class ShiningForcePlugin(GamePlugin):
    """Плагин для Shining Force (GBA)"""

    def __init__(self):
        super().__init__()

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info("STUB: charmap not implemented for Shining Force")
        return []

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00, 0xFF]

    def get_compression_handler(self, segment_name: str):
        return None
