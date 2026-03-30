"""
Тесты для модуля multi_charmap
Поддержка нескольких таблиц символов в одном сегменте
и улучшенное определение нестандартных кодировок
"""

import unittest
from core.multi_charmap import (
    CharTable, MultiCharmapSegment, EncodingDetector, get_detector,
    analyze_custom_encoding, _detect_possible_charmaps, _detect_sjis_sequences
)


class TestCharTable(unittest.TestCase):
    """Тесты для класса CharTable"""
    
    def setUp(self):
        self.basic_charmap = {
            0x20: ' ', 0x41: 'A', 0x42: 'B', 0x43: 'C',
            0x61: 'a', 0x62: 'b', 0x63: 'c'
        }
        
    def test_init(self):
        """Тест создания таблицы"""
        table = CharTable("Test", self.basic_charmap, 0.95)
        self.assertEqual(table.name, "Test")
        self.assertEqual(table.confidence, 0.95)
        self.assertEqual(len(table.char_map), 7)
        
    def test_covers_byte(self):
        """Тест проверки покрытия байта"""
        table = CharTable("Test", self.basic_charmap)
        self.assertTrue(table.covers_byte(0x41))  # 'A'
        self.assertTrue(table.covers_byte(0x20))  # ' '
        self.assertFalse(table.covers_byte(0x00))  # Не в таблице
        self.assertFalse(table.covers_byte(0xFF))  # Не в таблице
        
    def test_analyze_covered_ranges(self):
        """Тест анализа диапазонов"""
        table = CharTable("Test", self.basic_charmap)
        ranges = table.covered_ranges
        # ASCII буквы должны быть в одном или нескольких диапазонах
        self.assertIsInstance(ranges, set)
        
    def test_repr(self):
        """Тест строкового представления"""
        table = CharTable("Test", self.basic_charmap, 0.85)
        repr_str = repr(table)
        self.assertIn("Test", repr_str)
        self.assertIn("7 chars", repr_str)


class TestMultiCharmapSegment(unittest.TestCase):
    """Тесты для класса MultiCharmapSegment"""
    
    def setUp(self):
        # Тестовые данные: простой ASCII текст
        self.test_data = b"Hello World! Test data."
        self.katakana_data = bytes([0xA1, 0xA2, 0xA3, 0x41, 0x42, 0xA4])
        
    def test_init(self):
        """Тест создания сегмента"""
        segment = MultiCharmapSegment(self.test_data, 0x1000)
        self.assertEqual(segment.base_offset, 0x1000)
        self.assertEqual(len(segment.tables), 0)
        
    def test_add_table(self):
        """Тест добавления таблицы"""
        segment = MultiCharmapSegment(self.test_data, 0)
        charmap = {0x48: 'H', 0x65: 'e', 0x6C: 'l', 0x6F: 'o'}
        table = CharTable("ASCII", charmap)
        segment.add_table(table)
        self.assertEqual(len(segment.tables), 1)
        
    def test_calculate_coverage(self):
        """Тест вычисления покрытия"""
        segment = MultiCharmapSegment(self.test_data, 0)
        charmap = {0x48: 'H', 0x65: 'e', 0x6C: 'l', 0x6F: 'o'}
        coverage = segment._calculate_coverage(charmap)
        self.assertGreater(coverage, 0)
        self.assertLessEqual(coverage, 1.0)
        
    def test_generate_table_name(self):
        """Тест генерации имени таблицы"""
        segment = MultiCharmapSegment(self.test_data, 0)
        
        # ASCII таблица (только ASCII коды)
        ascii_charmap = {i: chr(i) for i in range(0x20, 0x7F)}
        name = segment._generate_table_name(ascii_charmap)
        # Может быть "English" или "Custom Encoding" в зависимости от реализации
        self.assertIn(name, ["English", "Custom Encoding"])
        
        # Katakana таблица
        kata_charmap = {i: chr(i) for i in range(0xA0, 0xE0)}
        name = segment._generate_table_name(kata_charmap)
        self.assertEqual(name, "Japanese (Halfwidth Katakana)")
        
    def test_build_encoding_map(self):
        """Тест построения карты кодирования"""
        segment = MultiCharmapSegment(self.test_data, 0)
        charmap = {0x48: 'H', 0x65: 'e', 0x6C: 'l', 0x6F: 'o'}
        table = CharTable("Test", charmap)
        segment.add_table(table)
        
        segment.build_encoding_map()
        self.assertIn(0x48, segment.encoding_map)
        self.assertIn(0x65, segment.encoding_map)
        
    def test_detect_tables(self):
        """Тест автоматического определения таблиц"""
        segment = MultiCharmapSegment(self.test_data, 0)
        ascii_charmap = {i: chr(i) for i in range(0x20, 0x7F)}
        
        detected = segment.detect_tables([ascii_charmap])
        self.assertGreater(len(detected), 0)
        
    def test_segment_by_table(self):
        """Тест разбиения на сегменты по таблицам"""
        segment = MultiCharmapSegment(self.test_data, 0)
        charmap = {0x48: 'H', 0x65: 'e', 0x6C: 'l', 0x6F: 'o'}
        table = CharTable("Test", charmap)
        segment.add_table(table)
        
        segments = segment.segment_by_table()
        self.assertIsInstance(segments, list)
        
    def test_decode_segment(self):
        """Тест декодирования сегмента"""
        segment = MultiCharmapSegment(self.test_data, 0)
        charmap = {0x48: 'H', 0x65: 'e', 0x6C: 'l', 0x6F: 'o'}
        table = CharTable("Test", charmap)
        segment.add_table(table)
        
        decoded = segment.decode_segment(0, 5, 0)
        self.assertEqual(decoded, "Hello")
        
    def test_full_decode(self):
        """Тест полного декодирования"""
        segment = MultiCharmapSegment(self.test_data, 0)
        charmap = {i: chr(i) for i in range(0x20, 0x7F)}
        table = CharTable("ASCII", charmap)
        segment.add_table(table)
        
        decoded_parts = segment.full_decode()
        self.assertIsInstance(decoded_parts, list)
        self.assertGreater(len(decoded_parts), 0)
        
    def test_empty_data(self):
        """Тест с пустыми данными"""
        segment = MultiCharmapSegment(b"", 0)
        coverage = segment._calculate_coverage({0x20: ' '})
        self.assertEqual(coverage, 0.0)


class TestAnalyzeCustomEncoding(unittest.TestCase):
    """Тесты для функции анализа кодировки"""
    
    def test_ascii_data(self):
        """Тест ASCII данных"""
        ascii_data = b"Hello World! This is a test message."
        result = analyze_custom_encoding(ascii_data)
        
        self.assertEqual(result['type'], 'ascii')
        self.assertGreater(result['confidence'], 0.9)
        self.assertIn('character_distribution', result)
        
    def test_empty_data(self):
        """Тест пустых данных"""
        result = analyze_custom_encoding(b"")
        
        self.assertEqual(result['type'], 'unknown')
        self.assertEqual(result['confidence'], 0.0)
        
    def test_high_byte_data(self):
        """Тест данных с высоким байтами"""
        # Симулируем данные с японскими символами
        high_byte_data = bytes([0x81, 0x40, 0x82, 0x60, 0x83, 0x80])
        result = analyze_custom_encoding(high_byte_data)
        
        self.assertIn(result['type'], ['shift-jis', 'custom', 'mixed'])
        self.assertGreater(result['confidence'], 0)
        
    def test_mixed_data(self):
        """Тест смешанных данных"""
        mixed_data = b"Hello " + bytes([0xA1, 0xA2, 0xA3]) + b" World!"
        result = analyze_custom_encoding(mixed_data)
        
        # Может быть ascii, mixed, custom, или shift-jis
        self.assertIn(result['type'], ['ascii', 'mixed', 'custom', 'shift-jis'])
        self.assertIn('possible_tables', result)


class TestSjisDetection(unittest.TestCase):
    """Тесты для определения Shift-JIS последовательностей"""
    
    def test_detect_sjis_sequences(self):
        """Тест обнаружения Shift-JIS последовательностей"""
        # Валидные Shift-JIS пары
        sjis_data = bytes([0x82, 0xA0, 0x82, 0xA1, 0x82, 0xA2])  #hiragana
        pairs = _detect_sjis_sequences(sjis_data)
        
        self.assertIsInstance(pairs, dict)
        # Может быть пустым, если последовательности не декодируются
        
    def test_empty_data(self):
        """Тест пустых данных"""
        pairs = _detect_sjis_sequences(b"")
        self.assertEqual(len(pairs), 0)


class TestEncodingDetector(unittest.TestCase):
    """Тесты для класса EncodingDetector"""
    
    def setUp(self):
        self.detector = EncodingDetector()
        self.sample_data = b"Hello World! Test data for encoding detection."
        self.sample_charmap = {i: chr(i) for i in range(0x20, 0x7F)}
        
    def test_init(self):
        """Тест инициализации"""
        self.assertEqual(len(self.detector.known_encodings), 0)
        self.assertEqual(len(self.detector.encoding_patterns), 0)
        
    def test_learn_encoding(self):
        """Тест обучения детектора"""
        self.detector.learn_encoding("English ASCII", self.sample_data, self.sample_charmap)
        
        self.assertIn("English ASCII", self.detector.known_encodings)
        self.assertEqual(len(self.detector.known_encodings["English ASCII"]), 1)
        
    def test_detect_encoding_unknown(self):
        """Тест определения неизвестной кодировки"""
        unknown_data = b"Some unknown data"
        encoding, confidence = self.detector.detect_encoding(unknown_data)
        
        self.assertEqual(encoding, 'unknown')
        self.assertEqual(confidence, 0.0)
        
    def test_detect_encoding_learned(self):
        """Тест определения обученной кодировки"""
        self.detector.learn_encoding("English ASCII", self.sample_data, self.sample_charmap)
        
        encoding, confidence = self.detector.detect_encoding(self.sample_data)
        
        self.assertEqual(encoding, "English ASCII")
        self.assertGreater(confidence, 0)
        
    def test_suggest_charmap_unknown(self):
        """Тест предложения charmap для неизвестных данных"""
        unknown_data = b"Unknown data here"
        charmap = self.detector.suggest_charmap(unknown_data)
        
        self.assertIsNotNone(charmap)
        self.assertIsInstance(charmap, dict)
        
    def test_auto_detect_charmap(self):
        """Тест автоматического определения charmap"""
        mixed_data = b"Hello " + bytes([0xA1, 0xA2]) + b" World!"
        charmap = self.detector._auto_detect_charmap(mixed_data)
        
        self.assertIsInstance(charmap, dict)
        self.assertGreater(len(charmap), 0)
        

class TestGetDetector(unittest.TestCase):
    """Тесты для глобальной функции get_detector"""
    
    def test_get_detector(self):
        """Тест получения глобального детектора"""
        detector1 = get_detector()
        detector2 = get_detector()
        
        # Должен возвращать тот же экземпляр
        self.assertIs(detector1, detector2)
        self.assertIsInstance(detector1, EncodingDetector)


class TestDetectPossibleCharmaps(unittest.TestCase):
    """Тесты для функции _detect_possible_charmaps"""
    
    def test_detect_ascii(self):
        """Тест обнаружения ASCII таблицы"""
        ascii_data = b"Hello World! Test data."
        tables = _detect_possible_charmaps(ascii_data)
        
        self.assertIsInstance(tables, list)
        self.assertGreater(len(tables), 0)
        
    def test_empty_data(self):
        """Тест с пустыми данными"""
        tables = _detect_possible_charmaps(b"")
        self.assertEqual(len(tables), 0)
        
    def test_non_ascii_data(self):
        """Тест с не-ASCII данными"""
        non_ascii = bytes([0x00, 0xFF, 0xFE, 0x80])
        tables = _detect_possible_charmaps(non_ascii)
        
        self.assertIsInstance(tables, list)


if __name__ == '__main__':
    unittest.main()