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
Модуль для работы с пользовательскими руководствами
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class GuideManager:
    """Менеджер пользовательских руководств"""

    def __init__(self, guides_dir: str = "guides"):
        self.guides_dir = Path(guides_dir)
        self.guides_dir.mkdir(parents=True, exist_ok=True)

    def get_guide(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Получает руководство для конкретной игры"""
        guide_path = self.guides_dir / f"{game_id}.json"
        if guide_path.exists():
            try:
                with open(guide_path) as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def save_guide(self, game_id: str, guide: Dict[str, Any]) -> bool:
        """Сохраняет руководство для игры"""
        try:
            guide_path = self.guides_dir / f"{game_id}.json"
            with open(guide_path, 'w', encoding='utf-8') as f:
                json.dump(guide, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def create_template(self, game_id: str) -> Dict[str, Any]:
        """Создает шаблон руководства для игры"""
        return {
            "game_id": game_id,
            "description": "Руководство по извлечению текста для этой игры",
            "steps": [
                {
                    "title": "Шаг 1: Подготовка",
                    "description": "Описание подготовительных действий"
                },
                {
                    "title": "Шаг 2: Настройка параметров",
                    "description": "Как настроить параметры извлечения"
                },
                {
                    "title": "Шаг 3: Извлечение текста",
                    "description": "Как правильно извлечь текст"
                }
            ],
            "tips": [
                "Совет 1: Описание полезного совета",
                "Совет 2: Еще один полезный совет"
            ]
        }

    def rate_guide(self, game_id: str, rating: int):
        """Оценивает руководство (1-5)"""
        if not 1 <= rating <= 5:
            return False

        rating_file = self.guides_dir / f"{game_id}.rating"
        with open(rating_file, 'w') as f:
            f.write(str(rating))
        return True

    def get_guide_rating(self, game_id: str) -> Optional[int]:
        """Получает оценку руководства"""
        rating_file = self.guides_dir / f"{game_id}.rating"
        if rating_file.exists():
            try:
                with open(rating_file, 'r') as f:
                    return int(f.read().strip())
            except:
                pass
        return None