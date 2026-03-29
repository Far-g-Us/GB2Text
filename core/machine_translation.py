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
Модуль для машинного перевода с использованием различных сервисов
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class Translator(ABC):
    """Базовый класс для переводчиков"""

    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Перевести текст с source_lang на target_lang"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Проверить доступность сервиса"""
        pass


class GoogleTranslator(Translator):
    """Переводчик через Google Translate"""

    def __init__(self):
        try:
            from googletrans import Translator as GoogleTrans
            self.translator = GoogleTrans()
        except ImportError:
            self.translator = None
            logger.warning("googletrans не установлен")

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not self.is_available():
            raise Exception("Google Translate недоступен")

        try:
            result = self.translator.translate(text, src=source_lang, dest=target_lang)
            return result.text
        except Exception as e:
            logger.error(f"Ошибка Google Translate: {e}")
            raise

    def is_available(self) -> bool:
        return self.translator is not None


class DeepLTranslator(Translator):
    """Переводчик через DeepL"""

    def __init__(self, auth_key: str):
        try:
            import deepl
            self.translator = deepl.Translator(auth_key)
        except ImportError:
            self.translator = None
            logger.warning("deepl не установлен")
        except Exception as e:
            self.translator = None
            logger.error(f"Ошибка инициализации DeepL: {e}")

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not self.is_available():
            raise Exception("DeepL недоступен")

        # Преобразование языков в формат DeepL
        lang_map = {
            'en': 'EN',
            'ru': 'RU',
            'ja': 'JA',
            'zh': 'ZH'
        }
        source = lang_map.get(source_lang, source_lang.upper())
        target = lang_map.get(target_lang, target_lang.upper())

        try:
            result = self.translator.translate_text(text, source_lang=source, target_lang=target)
            return result.text
        except Exception as e:
            logger.error(f"Ошибка DeepL: {e}")
            raise

    def is_available(self) -> bool:
        if self.translator is None:
            return False
        try:
            # Проверка доступности API
            usage = self.translator.get_usage()
            return usage.any_limit_reached is False
        except Exception:
            return False


class BingTranslator(Translator):
    """Переводчик через Microsoft Bing/Azure Translator"""

    def __init__(self, api_key: str, region: str = 'global'):
        self.api_key = api_key
        self.region = region
        self.endpoint = f"https://api.cognitive.microsofttranslator.com/translate?api-version=3.0"
        self.headers = {
            'Ocp-Apim-Subscription-Key': api_key,
            'Ocp-Apim-Subscription-Region': region,
            'Content-type': 'application/json'
        }
        self.available = True

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not self.is_available():
            raise Exception("Bing Translator недоступен")

        try:
            import requests
            url = f"{self.endpoint}&from={source_lang}&to={target_lang}"
            body = [{"text": text}]
            response = requests.post(url, headers=self.headers, json=body)
            response.raise_for_status()
            result = response.json()
            return result[0]["translations"][0]["text"]
        except ImportError:
            raise Exception("requests не установлен")
        except Exception as e:
            logger.error(f"Ошибка Bing: {e}")
            raise

    def is_available(self) -> bool:
        return self.available and self.api_key


class MachineTranslation:
    """Менеджер машинного перевода"""

    def __init__(self):
        self.translators = {}
        self.current_service = None

    def add_google_translator(self) -> None:
        """Добавить Google Translate"""
        self.translators['google'] = GoogleTranslator()

    def add_deepl_translator(self, auth_key: str) -> None:
        """Добавить DeepL"""
        self.translators['deepl'] = DeepLTranslator(auth_key)

    def add_bing_translator(self, api_key: str, region: str = 'global') -> None:
        """Добавить Bing"""
        self.translators['bing'] = BingTranslator(api_key, region)

    def set_service(self, service: str) -> None:
        """Установить текущий сервис"""
        if service in self.translators and self.translators[service].is_available():
            self.current_service = service
        else:
            raise ValueError(f"Сервис {service} недоступен")

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Перевести текст"""
        if not self.current_service:
            raise Exception("Сервис перевода не выбран")

        translator = self.translators.get(self.current_service)
        if not translator:
            raise Exception(f"Переводчик {self.current_service} не найден")

        return translator.translate(text, source_lang, target_lang)

    def get_available_services(self) -> list:
        """Получить список доступных сервисов"""
        return [service for service, translator in self.translators.items() if translator.is_available()]