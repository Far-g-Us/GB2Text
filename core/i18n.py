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
Модуль для интернационализации приложения
"""

import json, os
from pathlib import Path
from typing import Dict


class I18N:
    """Система интернационализации для приложения"""

    def __init__(self, default_lang: str = "en"):
        self.current_lang = default_lang
        self.translations = {}
        self.locales_dir = Path("locales")

        # Загружаем переводы
        self.load_translations(default_lang)

    def load_translations(self, lang: str) -> None:
        """Загружает переводы для указанного языка"""
        locale_file = self.locales_dir / lang / "messages.json"

        if locale_file.exists():
            try:
                with open(locale_file, 'r', encoding='utf-8') as f:
                    self.translations = json.load(f)
                self.current_lang = lang
            except Exception as e:
                print(f"Ошибка загрузки переводов для {lang}: {str(e)}")
                # Пытаемся загрузить английский как fallback
                if lang != "en":
                    self.load_translations("en")
        else:
            print(f"Файл локализации не найден: {locale_file}")
            # Пытаемся загрузить английский как fallback
            if lang != "en":
                self.load_translations("en")

    def t(self, key: str, **kwargs) -> str:
        """Возвращает перевод для указанного ключа"""
        translation = self.translations.get(key)

        if translation is None:
            # Попробуем найти ключ без префикса
            if '.' in key:
                short_key = key.split('.')[-1]
                translation = self.translations.get(short_key)

                if translation is None:
                    print(f"Предупреждение: Отсутствует перевод для ключа '{key}'")
                    return key
            else:
                print(f"Предупреждение: Отсутствует перевод для ключа '{key}'")
                return key

        # Подстановка аргументов
        try:
            return translation.format(**kwargs)
        except KeyError:
            return translation

    def get_available_languages(self) -> Dict[str, str]:
        """Возвращает доступные языки в формате код: название"""
        return {
            "en": "English",
            "ru": "Русский",
            "ja": "日本語"
        }

    def change_language(self, lang: str) -> None:
        """Изменяет текущий язык интерфейса"""
        self.load_translations(lang)