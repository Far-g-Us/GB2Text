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