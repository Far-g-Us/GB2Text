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
Базовые классы для плагинов
"""

from abc import ABC, abstractmethod
from typing import Dict, List
from core.rom import GameBoyROM


class GamePlugin(ABC):
    """Базовый класс для плагинов поддержки игр"""

    @property
    @abstractmethod
    def game_id_pattern(self) -> str:
        pass

    @abstractmethod
    def get_text_segments(self, rom: GameBoyROM) -> List[Dict]:
        pass


class GenericGamePlugin(GamePlugin):
    """Общий плагин для игр без привязки к конкретным коммерческим играм"""

    @property
    def game_id_pattern(self) -> str:
        return r'^GAME_[0-9A-F]{2}$'

    def get_text_segments(self, rom: GameBoyROM) -> List[Dict]:
        return [
            {
                'name': 'main_text',
                'start': 0x4000,
                'end': 0x7FFF,
                'decoder': None,  # Будет определен автоматически
                'compression': None
            }
        ]