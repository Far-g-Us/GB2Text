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
from typing import Dict, Tuple, Optional, List, Callable

# Импортируем multi_charmap для поддержки нескольких таблиц символов
try:
    from core.multi_charmap import (
        CharTable, MultiCharmapSegment, EncodingDetector, get_detector,
        analyze_custom_encoding
    )
    MULTI_CHARMAP_AVAILABLE = True
except ImportError:
    MULTI_CHARMAP_AVAILABLE = False
    CharTable = None
    MultiCharmapSegment = None
    EncodingDetector = None
    get_detector = None
    analyze_custom_encoding = None


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


class MultiCharMapDecoder:
    """
    Декодер с поддержкой нескольких таблиц символов в одном сегменте
    
    Использует модуль multi_charmap для:
    - Автоматического определения нестандартных кодировок
    - Обработки смешанных кодировок (например, katakana + латиница)
    - Динамического переключения между таблицами
    """

    def __init__(self, primary_charmap: Dict[int, str] = None):
        self.logger = logging.getLogger('gb2text.decoder.multi')
        self.primary_charmap = primary_charmap or {}
        
        # Инициализируем детектор кодировок если доступен
        if MULTI_CHARMAP_AVAILABLE and get_detector:
            self.detector = get_detector()
        else:
            self.detector = None
            self.logger.warning("Multi-charmap модуль недоступен, используется базовый декодер")
    
    def decode_segment(self, data: bytes, start: int, length: int,
                       alternative_charmaps: List[Dict[int, str]] = None) -> str:
        """
        Декодирует сегмент с использованием нескольких таблиц символов
        
        Args:
            data: Данные ROM
            start: Начальная позиция
            length: Длина сегмента
            alternative_charmaps: Дополнительные таблицы символов для анализа
            
        Returns:
            Декодированная строка
        """
        if not MULTI_CHARMAP_AVAILABLE or not MultiCharmapSegment:
            # Fallback на базовый декодер
            return self._decode_basic(data, start, length)
        
        segment_data = data[start:start + length]
        
        # Анализируем кодировку
        encoding_info = analyze_custom_encoding(segment_data)
        self.logger.debug(f"Определена кодировка: {encoding_info['type']} "
                         f"(уверенность: {encoding_info['confidence']:.2f})")
        
        # Создаем MultiCharmapSegment
        multi_segment = MultiCharmapSegment(segment_data, start)
        
        # Добавляем все доступные таблицы
        all_charmaps = [self.primary_charmap]
        if alternative_charmaps:
            all_charmaps.extend(alternative_charmaps)
        
        for charmap in all_charmaps:
            if charmap:
                table = CharTable("Dynamic Table", charmap, confidence=1.0)
                multi_segment.add_table(table)
        
        # Добавляем обнаруженные таблицы из encoding_info
        for possible_table in encoding_info.get('possible_tables', []):
            if possible_table:
                name = self._generate_table_name(possible_table)
                table = CharTable(name, possible_table, confidence=0.8)
                multi_segment.add_table(table)
        
        # Строим карту кодирования
        multi_segment.build_encoding_map()
        
        # Декодируем
        decoded_parts = []
        for text, table_idx in multi_segment.full_decode():
            decoded_parts.append(text)
        
        return ''.join(decoded_parts)
    
    def _decode_basic(self, data: bytes, start: int, length: int) -> str:
        """Базовый fallback декодер"""
        result = []
        end = min(start + length, len(data))
        
        for i in range(start, end):
            byte = data[i]
            char = self.primary_charmap.get(byte)
            if char:
                result.append(char)
            elif byte in [0x00, 0xFF, 0xFE]:
                result.append('\n')
            elif 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                result.append(f'[{byte:02X}]')
        
        return ''.join(result)
    
    def _generate_table_name(self, char_map: Dict[int, str]) -> str:
        """Генерирует имя таблицы на основе анализа символов"""
        ranges = set()
        for code in char_map.keys():
            if 0x20 <= code <= 0x7E:
                ranges.add('ASCII')
            elif 0xA0 <= code <= 0xDF:
                ranges.add('Katakana')
            elif code >= 0xE0:
                ranges.add('Extended')
        
        if 'ASCII' in ranges and len(ranges) == 1:
            return "English"
        elif 'Katakana' in ranges:
            return "Japanese"
        elif 'Extended' in ranges:
            return "Extended"
        return "Custom"
    
    def learn_encoding(self, name: str, sample_data: bytes, char_map: Dict[int, str]):
        """
        Обучает детектор кодировок на примере
        
        Args:
            name: Название кодировки/игры
            sample_data: Образец данных
            char_map: Таблица символов для этого образца
        """
        if self.detector:
            self.detector.learn_encoding(name, sample_data, char_map)
            self.logger.info(f"Детектор обучен на кодировке: {name}")
    
    def detect_encoding(self, data: bytes) -> Tuple[str, float]:
        """
        Определяет кодировку данных
        
        Returns:
            Кортеж (encoding_name, confidence)
        """
        if self.detector:
            return self.detector.detect_encoding(data)
        return ('unknown', 0.0)
    
    def suggest_charmap(self, data: bytes) -> Optional[Dict[int, str]]:
        """
        Предлагает таблицу символов для данных
        
        Returns:
            Наиболее подходящая таблица символов
        """
        if self.detector:
            return self.detector.suggest_charmap(data)
        return self.primary_charmap