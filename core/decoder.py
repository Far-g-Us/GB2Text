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
Модуль для декодирования текста и обработки сжатия
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional


class CompressionHandler(ABC):
    """Базовый класс для обработчиков сжатия"""

    @abstractmethod
    def decompress(self, data: bytes, start: int) -> Tuple[bytes, int]:
        pass


class CharMapDecoder:
    """Декодер с использованием таблицы символов"""

    def __init__(self, charmap: Dict[int, str]):
        self.charmap = charmap
        self.reverse_charmap = {v: k for k, v in charmap.items() if len(v) == 1}
        self.logger = logging.getLogger('gb2text.decoder')
        self.logger.debug(f"Инициализирован CharMapDecoder с {len(charmap)} символами")

    def decode(self, data: bytes, start: int, length: int) -> str:
        """Декодирует данные в строку"""
        logger = logging.getLogger('gb2text.decoder')
        self.logger.debug(f"Декодирование данных с 0x{start:X}, длина: {length}")

        result = []
        i = start
        unknown_count = 0
        total_count = 0

        while i < min(start + length, len(data)):
            byte = data[i]
            total_count += 1

            char = self.charmap.get(byte)
            if char is not None:
                result.append(char)
                i += 1
                continue

            # Проверяем на распространенные терминаторы
            if byte in [0x00, 0xFF, 0xFE]:
                result.append('\n')
                i += 1
                continue
            elif byte == 0x0D:  # Возврат каретки
                result.append('\n')
                i += 1
                continue
            elif byte == 0x0A:  # Новая строка
                if i == 0 or data[i - 1] != 0x0D:  # Не дублируем, если уже есть возврат каретки
                    result.append('\n')
                i += 1
                continue

            # Проверяем на специфичные для Game Boy паттерны
            if i + 1 < len(data):
                next_byte = data[i + 1]
                # Паттерн для указателей
                if byte == 0xCD and next_byte in [0x1B, 0x20, 0x51]:
                    i += 2
                    continue
                # Паттерн для команд
                if byte == 0xE0 and next_byte == 0x9A:
                    i += 2
                    continue

            # Для неизвестных байтов пробуем найти похожие символы
            similar_char = self._find_similar_char(byte)
            if similar_char:
                result.append(similar_char)
                i += 1
                continue

            # Если ничего не помогло, пропускаем байт
            unknown_count += 1
            i += 1

        # Логируем статистику
        if total_count > 0:
            unknown_percent = (unknown_count / total_count) * 100
            if unknown_percent > 30:
                logger.warning(f"Высокий процент неизвестных байтов: {unknown_percent:.1f}%")

        decoded_text = ''.join(result)
        self.logger.info(f"Успешно декодировано {len(result)} символов")
        self.logger.debug(f"Декодированный текст: {decoded_text[:100]}...")
        return decoded_text

    def _find_similar_char(self, byte: int) -> Optional[str]:
        """Пытается найти похожий символ в таблице"""
        # Проверяем, есть ли похожие байты в таблице
        for known_byte, char in self.charmap.items():
            # Если разница небольшая и похоже на закономерность
            diff = byte - known_byte
            if -5 <= diff <= 5 and diff != 0:
                return char
        return None

    def encode(self, text: str) -> bytes:
        """Кодирует строку в байты"""
        self.logger.debug(f"Кодирование текста: {text[:50]}...")
        result = []
        for char in text:
            byte = self.reverse_charmap.get(char)
            if byte is None:
                # Попробуем найти похожий символ
                for c, b in self.reverse_charmap.items():
                    if c.lower() == char.lower():
                        byte = b
                        break
                if byte is None:
                    # Используем пробел как fallback
                    byte = self.reverse_charmap.get(' ', 0x20)
                    self.logger.warning(f"Символ '{char}' не найден в таблице, заменен на пробел")

            result.append(byte)

        encoded = bytes(result)
        self.logger.info(f"Успешно закодировано {len(result)} символов")
        self.logger.debug(f"Закодированные байты: {encoded[:20].hex() if len(encoded) > 0 else 'пусто'}")

        return encoded

class LZ77Handler:
    """Обработчик LZ77 сжатия"""

    def decompress(self, data: bytes, start: int) -> tuple:
        """Декомпрессия LZ77"""
        # Простая реализация (должна быть заменена на реальную)
        return data[start:], len(data) - start

    def compress(self, data: bytes) -> bytes:
        """Компрессия LZ77"""
        # Простая реализация (должна быть заменена на реальную)
        return data


class TextDecoder(ABC):
    """Базовый класс для декодеров текста"""

    @abstractmethod
    def decode(self, data: bytes, start: int, end: int) -> str:
        pass