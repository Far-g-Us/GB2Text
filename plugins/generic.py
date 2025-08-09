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
Базовые классы и функции без привязки к коммерческим играм
"""

from core.plugin import GamePlugin


class GenericGBPlugin(GamePlugin):
    """Базовый плагин для игр Game Boy"""

    @property
    def game_id_pattern(self) -> str:
        return r'^GAME_[0-9A-F]{2}$'

    def get_text_segments(self, rom) -> list:
        return [
            {
                'name': 'main_text',
                'start': 0x4000,
                'end': 0x7FFF,
                'decoder': None,
                'compression': None
            }
        ]


class GenericGBCPlugin(GenericGBPlugin):
    """Базовый плагин для игр Game Boy Color"""
    pass


class GenericGBAPlugin(GenericGBPlugin):
    """Базовый плагин для игр Game Boy Advance"""

    def get_text_segments(self, rom) -> list:
        # Проверяем, является ли ROM действительно GBA
        if rom.system != 'gba':
            return []

        return [
            {
                'name': 'main_text',
                'start': 0x083D0000,
                'end': 0x08400000,
                'decoder': None,
                'compression': 'gba_lz77'
            }
        ]