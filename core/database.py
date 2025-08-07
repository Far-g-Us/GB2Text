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

import requests

class GameDatabase:
    """Интерфейс для работы с базой данных игр"""
    API_URL = "https://api.gbdev.io/v1"

    @classmethod
    def get_game_info(cls, game_id: str) -> dict:
        """Получение информации об игре из базы данных"""
        try:
            response = requests.get(f"{cls.API_URL}/games/{game_id}")
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return {}

    @classmethod
    def get_charmap_for_game(cls, game_id: str) -> dict:
        """Получение таблицы символов для конкретной игры"""
        game_info = cls.get_game_info(game_id)
        return game_info.get('charmap', {})

    @classmethod
    def submit_charmap(cls, game_id: str, charmap: dict) -> bool:
        """Отправка пользовательской таблицы символов в базу"""
        try:
            response = requests.post(
                f"{cls.API_URL}/games/{game_id}/charmap",
                json={'charmap': charmap}
            )
            return response.status_code == 200
        except Exception:
            return False