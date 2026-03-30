"""
Поддержка нескольких таблиц символов в одном сегменте
и улучшенное определение нестандартных кодировок

Этот модуль позволяет:
1. Определять и использовать несколько таблиц символов в одном текстовом сегменте
2. Автоматически определять нестандартные кодировки на основе анализа данных
3. Обрабатывать смешанные кодировки (например, katakana + латиница в одном сегменте)
"""

import logging
from typing import Dict, List, Tuple, Optional, Set
from collections import Counter

logger = logging.getLogger('gb2text.multi_charmap')


class CharTable:
    """Представляет одну таблицу символов"""
    
    def __init__(self, name: str, char_map: Dict[int, str], confidence: float = 1.0):
        self.name = name
        self.char_map = char_map
        self.confidence = confidence
        self.covered_ranges = self._analyze_covered_ranges()
        
    def _analyze_covered_ranges(self) -> Set[Tuple[int, int]]:
        """Анализирует диапазоны символов в таблице"""
        ranges = set()
        current_range = None
        
        for code in sorted(self.char_map.keys()):
            if current_range is None:
                current_range = (code, code)
            elif code == current_range[1] + 1:
                current_range = (current_range[0], code)
            else:
                ranges.add(current_range)
                current_range = (code, code)
                
        if current_range:
            ranges.add(current_range)
        return ranges
    
    def covers_byte(self, byte_val: int) -> bool:
        """Проверяет, покрывает ли таблица данный байт"""
        return byte_val in self.char_map
    
    def __repr__(self):
        return f"CharTable('{self.name}', {len(self.char_map)} chars, conf={self.confidence:.2f})"


class MultiCharmapSegment:
    """Сегмент с несколькими таблицами символов"""
    
    def __init__(self, data: bytes, base_offset: int):
        self.data = data
        self.base_offset = base_offset
        self.tables: List[CharTable] = []
        self.encoding_map: Dict[int, int] = {}  # byte -> table_index
        self.segments: List[Tuple[int, int, int]] = []  # (start, end, table_index)
        
    def add_table(self, table: CharTable):
        """Добавляет таблицу символов в сегмент"""
        self.tables.append(table)
        
    def detect_tables(self, known_tables: List[Dict[int, str]]) -> List[CharTable]:
        """
        Автоматически определяет таблицы символов в данных
        
        Args:
            known_tables: Список известных таблиц (char_map)
            
        Returns:
            Список обнаруженных CharTable
        """
        detected = []
        
        for char_map in known_tables:
            # Анализируем покрытие данным
            coverage = self._calculate_coverage(char_map)
            if coverage > 0.3:  # Минимум 30% покрытия
                name = self._generate_table_name(char_map)
                table = CharTable(name, char_map, confidence=coverage)
                detected.append(table)
                
        # Сортируем по покрытию (от большего к меньшему)
        detected.sort(key=lambda t: t.confidence, reverse=True)
        self.tables = detected
        
        return detected
    
    def _calculate_coverage(self, char_map: Dict[int, str]) -> float:
        """Вычисляет процент покрытия данных таблицей"""
        if not self.data:
            return 0.0
            
        covered = sum(1 for b in self.data if b in char_map)
        return covered / len(self.data)
    
    def _generate_table_name(self, char_map: Dict[int, str]) -> str:
        """Генерирует имя таблицы на основе анализа символов"""
        # Определяем тип символов
        ranges = []
        for code in char_map.keys():
            if 0x20 <= code <= 0x7E:
                ranges.append('ASCII')
            elif 0xA0 <= code <= 0xDF:
                ranges.append('Halfwidth Katakana')
            elif 0xE0 <= code <= 0xFF:
                ranges.append('Extended')
                
        if 'ASCII' in ranges and len(ranges) == 1:
            return "English"
        elif 'Halfwidth Katakana' in ranges:
            return "Japanese (Halfwidth Katakana)"
        elif 'Extended' in ranges:
            return "Extended Encoding"
            
        return "Custom Encoding"
    
    def build_encoding_map(self):
        """Строит карту кодирования: байт -> индекс таблицы"""
        self.encoding_map.clear()
        
        for i, table in enumerate(self.tables):
            for byte_val in self.data:
                if byte_val in table.char_map and byte_val not in self.encoding_map:
                    self.encoding_map[byte_val] = i
                    
    def segment_by_table(self) -> List[Tuple[int, int, int]]:
        """
        Разбивает данные на сегменты по таблицам символов
        
        Returns:
            Список кортежей (start_offset, end_offset, table_index)
        """
        if not self.tables or not self.encoding_map:
            self.build_encoding_map()
            
        self.segments.clear()
        current_table = None
        segment_start = 0
        
        for i, byte_val in enumerate(self.data):
            table_idx = self.encoding_map.get(byte_val, -1)
            
            if table_idx != current_table:
                if current_table is not None:
                    self.segments.append((segment_start, i, current_table))
                current_table = table_idx
                segment_start = i
                
        # Добавляем последний сегмент
        if current_table is not None:
            self.segments.append((segment_start, len(self.data), current_table))
            
        return self.segments
    
    def decode_segment(self, start: int, end: int, table_index: int) -> str:
        """Декодирует сегмент данных с использованием указанной таблицы"""
        if table_index >= len(self.tables):
            return self.decode_with_fallback(start, end)
            
        table = self.tables[table_index]
        result = []
        
        for i in range(start, end):
            byte_val = self.data[i]
            char = table.char_map.get(byte_val, f'[{byte_val:02X}]')
            result.append(char)
            
        return ''.join(result)
    
    def decode_with_fallback(self, start: int, end: int) -> str:
        """Декодирует с использованием fallback для неизвестных символов"""
        result = []
        
        for i in range(start, end):
            byte_val = self.data[i]
            
            # Пробуем найти в любой таблице
            for table in self.tables:
                if byte_val in table.char_map:
                    result.append(table.char_map[byte_val])
                    break
            else:
                # Fallback
                result.append(f'[{byte_val:02X}]')
                
        return ''.join(result)
    
    def full_decode(self) -> List[Tuple[str, int]]:
        """
        Полностью декодирует данные с разбивкой по таблицам
        
        Returns:
            Список кортежей (decoded_text, table_index)
        """
        segments = self.segment_by_table()
        return [(self.decode_segment(s, e, t), t) for s, e, t in segments]


def analyze_custom_encoding(data: bytes) -> Dict[str, any]:
    """
    Анализирует данные для определения нестандартной кодировки
    
    Returns:
        Словарь с информацией о кодировке:
        - 'type': тип кодировки ('shift-jis', 'custom', 'mixed', 'ascii')
        - 'confidence': уверенность в определении (0-1)
        - 'character_distribution': распределение символов
        - 'possible_tables': список возможных таблиц символов
    """
    result = {
        'type': 'unknown',
        'confidence': 0.0,
        'character_distribution': {},
        'possible_tables': []
    }
    
    if not data:
        return result
        
    # Считаем частоту байтов
    freq = Counter(data)
    result['character_distribution'] = dict(freq.most_common(50))
    
    # Определяем тип кодировки
    ascii_count = sum(1 for b in data if 0x20 <= b <= 0x7E)
    high_byte_count = sum(1 for b in data if b >= 0x80)
    
    ascii_ratio = ascii_count / len(data)
    
    if ascii_ratio > 0.9:
        result['type'] = 'ascii'
        result['confidence'] = 0.95
    elif high_byte_count > 0:
        # Анализируем паттерны для определения Shift-JIS или custom
        result['type'] = 'shift-jis'  # Предполагаем Shift-JIS
        result['confidence'] = 0.7
    else:
        result['type'] = 'custom'
        result['confidence'] = 0.5
        
    # Ищем возможные таблицы символов
    possible_tables = _detect_possible_charmaps(data)
    result['possible_tables'] = possible_tables
    
    return result


def _detect_possible_charmaps(data: bytes) -> List[Dict[int, str]]:
    """Обнаруживает возможные таблицы символов в данных"""
    tables = []
    
    # Проверяем наличие ASCII
    ascii_chars = {b: chr(b) for b in range(0x20, 0x7F) if bytes([b]) in data}
    if len(ascii_chars) > 10:
        tables.append(ascii_chars)
        
    # Проверяем наличие Shift-JIS последовательностей
    sjis_pairs = _detect_sjis_sequences(data)
    if sjis_pairs:
        tables.append(sjis_pairs)
        
    return tables


def _detect_sjis_sequences(data: bytes) -> Dict[int, str]:
    """Обнаруживает Shift-JIS последовательности"""
    pairs = {}
    
    for i in range(len(data) - 1):
        first = data[i]
        second = data[i + 1]
        
        # Проверяем валидные Shift-JIS пары
        if (0x81 <= first <= 0x9F or 0xE0 <= first <= 0xEF):
            if (0x40 <= second <= 0x7E or 0x80 <= second <= 0xFC):
                try:
                    sjis = bytes([first, second])
                    char = sjis.decode('shift-jis', errors='ignore')
                    if char:
                        pairs[first * 256 + second] = char
                except:
                    pass
                    
    return pairs


class EncodingDetector:
    """Детектор кодировок с обучением"""
    
    def __init__(self):
        self.known_encodings: Dict[str, List[CharTable]] = {}
        self.encoding_patterns: Dict[str, List[Tuple[bytes, str]]] = {}  # pattern -> encoding
        
    def learn_encoding(self, name: str, sample_data: bytes, char_map: Dict[int, str]):
        """Запоминает паттерн кодировки из образца"""
        if name not in self.known_encodings:
            self.known_encodings[name] = []
            
        coverage = sum(1 for b in sample_data if b in char_map) / len(sample_data)
        table = CharTable(name, char_map, confidence=coverage)
        self.known_encodings[name].append(table)
        
        # Сохраняем паттерн
        pattern = sample_data[:min(100, len(sample_data))]
        if name not in self.encoding_patterns:
            self.encoding_patterns[name] = []
        self.encoding_patterns[name].append((pattern, name))
        
    def detect_encoding(self, data: bytes) -> Tuple[str, float]:
        """
        Определяет кодировку данных
        
        Returns:
            Кортеж (encoding_name, confidence)
        """
        best_match = ('unknown', 0.0)
        
        for encoding_name, tables in self.known_encodings.items():
            for table in tables:
                coverage = sum(1 for b in data if b in table.char_map) / len(data)
                if coverage > best_match[1]:
                    best_match = (encoding_name, coverage)
                    
        return best_match
        
    def suggest_charmap(self, data: bytes) -> Optional[Dict[int, str]]:
        """
        Предлагает таблицу символов для данных
        
        Returns:
            Наиболее подходящая таблица или None
        """
        encoding_name, confidence = self.detect_encoding(data)
        
        if encoding_name != 'unknown' and encoding_name in self.known_encodings:
            # Возвращаем таблицу с наибольшим покрытием
            best_table = max(self.known_encodings[encoding_name], 
                           key=lambda t: t.confidence)
            return best_table.char_map
            
        # Пытаемся автоматически определить
        return self._auto_detect_charmap(data)
        
    def _auto_detect_charmap(self, data: bytes) -> Dict[int, str]:
        """Автоматически создаёт таблицу символов"""
        charmap = {}
        
        # Добавляем ASCII
        for b in range(0x20, 0x7F):
            if bytes([b]) in data:
                charmap[b] = chr(b)
                
        # Анализируем паттерны для не-ASCII символов
        freq = Counter(data)
        for byte_val, count in freq.most_common(100):
            if byte_val >= 0x80 and count > 2:
                # Создаём placeholder символ
                charmap[byte_val] = f'[{byte_val:02X}]'
                
        return charmap


# Глобальный экземпляр для удобства
_global_detector = None

def get_detector() -> EncodingDetector:
    """Возвращает глобальный экземпляр EncodingDetector"""
    global _global_detector
    if _global_detector is None:
        _global_detector = EncodingDetector()
    return _global_detector