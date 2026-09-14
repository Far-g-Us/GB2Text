"""
Поддержка нескольких таблиц символов в одном сегменте
и улучшенное определение нестандартных кодировок

Этот модуль позволяет:
1. Определять и использовать несколько таблиц символов в одном текстовом сегменте
2. Автоматически определять нестандартные кодировки на основе анализа данных
3. Обрабатывать смешанные кодировки (например, katakana + латиница в одном сегменте)
"""

import logging
from collections import Counter
from typing import Any

logger = logging.getLogger('gb2text.multi_charmap')


class CharTable:
    """Представляет одну таблицу символов"""

    def __init__(self, name: str, char_map: dict[int | tuple[int, int], str], confidence: float = 1.0):
        self.name = name
        self.char_map = char_map
        self.confidence = confidence
        self.covered_ranges = self._analyze_covered_ranges()

    def _analyze_covered_ranges(self) -> set[tuple[int, int]]:
        """Анализирует диапазоны символов в таблице"""
        ranges = set()
        current_range = None

        for code in sorted(k for k in self.char_map.keys() if isinstance(k, int)):
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
        self.tables: list[CharTable] = []
        self.encoding_map: dict[int, int] = {}  # byte -> table_index
        self.segments: list[tuple[int, int, int]] = []  # (start, end, table_index)

    def add_table(self, table: CharTable):
        """Добавляет таблицу символов в сегмент"""
        self.tables.append(table)

    def detect_tables(self, known_tables: list[dict[int | tuple[int, int], str]]) -> list[CharTable]:
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

    def _calculate_coverage(self, char_map: dict[int | tuple[int, int], str]) -> float:
        """Вычисляет процент покрытия данных таблицей"""
        if not self.data:
            return 0.0

        covered = sum(1 for b in self.data if b in char_map)
        return covered / len(self.data)

    def _generate_table_name(self, char_map: dict[int | tuple[int, int], str]) -> str:
        """Генерирует имя таблицы на основе анализа символов"""
        # Определяем тип символов (только int-ключи; tuple-ключи — пары, пропускаем)
        ranges = []
        for code in char_map.keys():
            if not isinstance(code, int):
                continue
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

            # Пары (SJIS-подобные, ключ = (first, second)): мапим оба байта
            # на таблицу, чтобы пара не разрывалась между сегментами.
            for j in range(len(self.data) - 1):
                pair = (self.data[j], self.data[j + 1])
                if pair in table.char_map:
                    for b in pair:
                        if b not in self.encoding_map:
                            self.encoding_map[b] = i

    def segment_by_table(self) -> list[tuple[int, int, int]]:
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
        if table_index < 0 or table_index >= len(self.tables):
            return self.decode_with_fallback(start, end)

        table = self.tables[table_index]
        result: list[str] = []
        i = start

        while i < end:
            byte_val = self.data[i]
            # Пробуем двухбайтовую пару (SJIS и др.)
            if i + 1 < end:
                pair_char = table.char_map.get((byte_val, self.data[i + 1]))
                if pair_char is not None:
                    result.append(pair_char)
                    i += 2
                    continue
            # Одиночный байт
            char = table.char_map.get(byte_val, f'[{byte_val:02X}]')
            result.append(char)
            i += 1

        return ''.join(result)

    def decode_with_fallback(self, start: int, end: int) -> str:
        """Декодирует с использованием fallback для неизвестных символов"""
        result: list[str] = []
        i = start

        while i < end:
            byte_val = self.data[i]
            matched = False

            # Пробуем двухбайтовую пару
            if i + 1 < end:
                pair = (byte_val, self.data[i + 1])
                for table in self.tables:
                    if pair in table.char_map:
                        result.append(table.char_map[pair])
                        i += 2
                        matched = True
                        break

            if matched:
                continue

            # Одиночный байт
            for table in self.tables:
                if byte_val in table.char_map:
                    result.append(table.char_map[byte_val])
                    break
            else:
                # Fallback
                result.append(f'[{byte_val:02X}]')
            i += 1

        return ''.join(result)

    def full_decode(self) -> list[tuple[str, int]]:
        """
        Полностью декодирует данные с разбивкой по таблицам

        Returns:
            Список кортежей (decoded_text, table_index)
        """
        segments = self.segment_by_table()
        return [(self.decode_segment(s, e, t), t) for s, e, t in segments]


def analyze_custom_encoding(data: bytes) -> dict[str, Any]:
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


def _detect_possible_charmaps(data: bytes) -> list[dict[int | tuple[int, int], str]]:
    """Обнаруживает возможные таблицы символов в данных"""
    tables: list[dict[int | tuple[int, int], str]] = []

    # Проверяем наличие ASCII
    ascii_chars: dict[int | tuple[int, int], str] = {
        b: chr(b) for b in range(0x20, 0x7F) if bytes([b]) in data
    }
    if len(ascii_chars) > 10:
        tables.append(ascii_chars)

    # Проверяем наличие Shift-JIS последовательностей
    sjis_pairs: dict[int | tuple[int, int], str] = {}
    for pair, char in _detect_sjis_sequences(data).items():
        sjis_pairs[pair] = char
    if sjis_pairs:
        tables.append(sjis_pairs)

    return tables


def _detect_sjis_sequences(data: bytes) -> dict[tuple[int, int], str]:
    """Обнаруживает Shift-JIS последовательности"""
    pairs: dict[tuple[int, int], str] = {}

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
                        pairs[(first, second)] = char
                except (UnicodeDecodeError, ValueError, OverflowError):
                    pass

    return pairs


class EncodingDetector:
    """Детектор кодировок с обучением"""

    def __init__(self):
        self.known_encodings: dict[str, list[CharTable]] = {}
        self.encoding_patterns: dict[str, list[tuple[bytes, str]]] = {}  # pattern -> encoding

    def learn_encoding(self, name: str, sample_data: bytes, char_map: dict[int | tuple[int, int], str]):
        """Запоминает паттерн кодировки из образца"""
        if name not in self.known_encodings:
            self.known_encodings[name] = []

        coverage = sum(1 for b in sample_data if b in char_map) / len(sample_data) if sample_data else 0.0
        table = CharTable(name, char_map, confidence=coverage)
        self.known_encodings[name].append(table)

        # Сохраняем паттерн
        pattern = sample_data[:min(100, len(sample_data))]
        if name not in self.encoding_patterns:
            self.encoding_patterns[name] = []
        self.encoding_patterns[name].append((pattern, name))

    def detect_encoding(self, data: bytes) -> tuple[str, float]:
        """
        Определяет кодировку данных, используя как обученные паттерны,
        так и эвристический анализ.

        Returns:
            Кортеж (encoding_name, confidence)
        """
        best_match = ('unknown', 0.0)

        # 1. Проверяем обученные паттерны
        for encoding_name, tables in self.known_encodings.items():
            for table in tables:
                coverage = sum(1 for b in data if b in table.char_map) / len(data) if data else 0
                if coverage > best_match[1]:
                    best_match = (encoding_name, coverage)

        # 2. Если нет обученных паттернов — эвристика
        if best_match[1] < 0.3 and data:
            ascii_count = sum(1 for b in data if 0x20 <= b <= 0x7E)
            high_count = sum(1 for b in data if b >= 0x80)
            total = len(data)

            ascii_ratio = ascii_count / total
            high_ratio = high_count / total

            if ascii_ratio > 0.8:
                candidate = ('ascii', ascii_ratio)
                if candidate[1] > best_match[1]:
                    best_match = candidate
            elif high_ratio > 0.2:
                # Проверяем Shift-JIS паттерны
                sjis_score = self._score_shiftjis(data)
                if sjis_score > 0.3:
                    candidate = ('shift-jis', sjis_score)
                    if candidate[1] > best_match[1]:
                        best_match = candidate

        return best_match

    def _score_shiftjis(self, data: bytes) -> float:
        """Оценивает вероятность что данные в Shift-JIS"""
        if len(data) < 2:
            return 0.0
        sjis_pairs = 0
        total_pairs = 0
        for i in range(len(data) - 1):
            first = data[i]
            second = data[i + 1]
            if 0x81 <= first <= 0x9F or 0xE0 <= first <= 0xEF:
                total_pairs += 1
                if 0x40 <= second <= 0x7E or 0x80 <= second <= 0xFC:
                    sjis_pairs += 1
        if total_pairs == 0:
            return 0.0
        return sjis_pairs / total_pairs

    def suggest_charmap(self, data: bytes) -> dict[int | tuple[int, int], str] | None:
        """
        Предлагает таблицу символов для данных

        Returns:
            Наиболее подходящая таблица или None
        """
        encoding_name, _confidence = self.detect_encoding(data)

        if encoding_name != 'unknown' and encoding_name in self.known_encodings:
            # Возвращаем таблицу с наибольшим покрытием
            best_table = max(self.known_encodings[encoding_name],
                           key=lambda t: t.confidence)
            return best_table.char_map

        # Пытаемся автоматически определить
        return self._auto_detect_charmap(data)

    def _auto_detect_charmap(self, data: bytes) -> dict[int | tuple[int, int], str]:
        """Автоматически создаёт таблицу символов"""
        charmap: dict[int | tuple[int, int], str] = {}

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
