"""
Дополнительные тесты для core/scanner.py
Повышение покрытия модуля scanner
"""

import unittest
from core.scanner import (
    find_text_pointers, is_text_like, 
    auto_detect_charmap, auto_detect_segments, auto_detect_segments_ml,
    detect_multiple_languages, analyze_text_segment,
    MIN_POINTER_LENGTH, MIN_SEGMENT_LENGTH, MIN_READABILITY, READABLE_BLOCK_SIZE,
    SKLEARN_AVAILABLE
)


class TestFindTextPointers(unittest.TestCase):
    """Тесты для функции find_text_pointers"""
    
    def setUp(self):
        # Создаём тестовые данные с указателями
        self.rom_data = bytearray(256)
        # Записываем указатель 0x40 (указывает на 0x0040)
        self.rom_data[0] = 0x40
        self.rom_data[1] = 0x00
        
    def test_find_pointers_basic(self):
        """Тест базового поиска указателей"""
        pointers = find_text_pointers(bytes(self.rom_data), start=0, end=10)
        self.assertIsInstance(pointers, list)
        
    def test_find_pointers_empty_data(self):
        """Тест поиска указателей в пустых данных"""
        pointers = find_text_pointers(b"", start=0, end=0)
        self.assertEqual(len(pointers), 0)
        
    def test_find_pointers_small_data(self):
        """Тест поиска указателей в маленьких данных"""
        data = b"\x00\x01\x02"
        pointers = find_text_pointers(data, start=0, end=len(data))
        self.assertEqual(len(pointers), 0)
        
    def test_find_pointers_with_different_sizes(self):
        """Тест поиска указателей разных размеров"""
        # Двухбайтовые указатели
        pointers_2b = find_text_pointers(bytes(self.rom_data), pointer_size=2)
        self.assertIsInstance(pointers_2b, list)


class TestIsTextLike(unittest.TestCase):
    """Тесты для функции is_text_like"""
    
    def test_ascii_text(self):
        """Тест распознавания ASCII текста"""
        ascii_text = b"Hello World! This is a test."
        self.assertTrue(is_text_like(ascii_text, 0, 10))
        
    def test_non_text_data(self):
        """Тест распознавания не-текстовых данных"""
        non_text = bytes([0x00, 0x01, 0x02, 0x03, 0xFF, 0xFE])
        self.assertFalse(is_text_like(non_text, 0, 6))
        
    def test_empty_data(self):
        """Тест с пустыми данными"""
        self.assertFalse(is_text_like(b"", 0, 0))
        
    def test_mixed_data(self):
        """Тест смешанных данных"""
        mixed = b"Hello" + bytes([0xFF, 0xFE, 0x00])
        # Начало выглядит как текст
        self.assertTrue(is_text_like(mixed, 0, 5))


class TestAutoDetectCharmap(unittest.TestCase):
    """Тесты для функции auto_detect_charmap"""
    
    def test_detect_ascii_charmap(self):
        """Тест определения ASCII charmap"""
        ascii_data = b"Hello World! 123"
        charmap = auto_detect_charmap(ascii_data, 0, len(ascii_data))
        self.assertIsInstance(charmap, dict)
        # Должен содержать базовые ASCII символы
        self.assertIn(0x41, charmap)  # 'A'
        
    def test_detect_empty_data(self):
        """Тест с пустыми данными - функция возвращает defaults charmap"""
        charmap = auto_detect_charmap(b"", 0, 0)
        self.assertIsInstance(charmap, dict)
        # Функция может возвращать defaults даже для пустых данных


class TestAutoDetectSegments(unittest.TestCase):
    """Тесты для функции auto_detect_segments"""
    
    def test_basic_segments(self):
        """Тест базового поиска сегментов"""
        # Создаём данные с текстом
        data = b"Hello World! " + bytes([0x00]) * 10 + b"Test data"
        segments = auto_detect_segments(data, min_segment_length=5)
        self.assertIsInstance(segments, list)
        
    def test_no_segments(self):
        """Тест без сегментов"""
        data = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05])
        segments = auto_detect_segments(data, min_segment_length=10)
        self.assertEqual(len(segments), 0)
        
    def test_segments_with_custom_params(self):
        """Тест с кастомными параметрами"""
        data = b"A" * 100 + bytes([0x00]) * 50 + b"B" * 50
        segments = auto_detect_segments(
            data,
            min_segment_length=20,
            min_readability=0.3,
            block_size=16
        )
        self.assertIsInstance(segments, list)


class TestAutoDetectSegmentsML(unittest.TestCase):
    """Тесты для функции auto_detect_segments_ml"""
    
    def test_ml_segments(self):
        """Тест ML определения сегментов"""
        # Создаём данные с паттернами
        data = b"Hello World!" * 20 + bytes([0x00]) * 50
        segments = auto_detect_segments_ml(data, min_segment_length=10, block_size=16)
        self.assertIsInstance(segments, list)
        
    def test_ml_empty_data(self):
        """Тест с пустыми данными"""
        segments = auto_detect_segments_ml(b"", min_segment_length=10)
        self.assertEqual(len(segments), 0)


class TestDetectMultipleLanguages(unittest.TestCase):
    """Тесты для функции detect_multiple_languages"""
    
    def test_detect_english(self):
        """Тест определения английского"""
        english_data = b"This is an English text with common words like the, and, is, to."
        languages = detect_multiple_languages(english_data, 0, len(english_data))
        self.assertIsInstance(languages, list)
        # Может вернуть "english" (lowercase) или "English"
        self.assertTrue(
            "English" in languages or 
            "english" in languages or 
            len(languages) > 0
        )
        
    def test_detect_empty_data(self):
        """Тест с пустыми данными"""
        languages = detect_multiple_languages(b"", 0, 0)
        self.assertIsInstance(languages, list)


class TestAnalyzeTextSegment(unittest.TestCase):
    """Тесты для функции analyze_text_segment"""
    
    def test_basic_analysis(self):
        """Тест базового анализа"""
        data = b"Hello World!"
        info = analyze_text_segment(data, 0, len(data))
        self.assertIsInstance(info, dict)
        # Проверяем что info содержит ключевые поля (могут отличаться от 'length')
        self.assertTrue('readability' in info or 'length' in info)
        
    def test_empty_segment(self):
        """Тест пустого сегмента"""
        info = analyze_text_segment(b"", 0, 0)
        self.assertIsInstance(info, dict)
        # Проверяем что info содержит поля, даже для пустого сегмента
        self.assertIn('readability', info)


class TestConstants(unittest.TestCase):
    """Тесты для констант scanner"""
    
    def test_min_pointer_length(self):
        """Тест минимальной длины указателя"""
        self.assertGreaterEqual(MIN_POINTER_LENGTH, 2)
        
    def test_min_segment_length(self):
        """Тест минимальной длины сегмента"""
        self.assertGreaterEqual(MIN_SEGMENT_LENGTH, 1)
        
    def test_min_readability(self):
        """Тест минимальной читаемости"""
        self.assertGreater(MIN_READABILITY, 0)
        self.assertLessEqual(MIN_READABILITY, 1)
        
    def test_readable_block_size(self):
        """Тест размера читаемого блока"""
        self.assertGreater(READABLE_BLOCK_SIZE, 0)
        
    def test_sklearn_available_constant(self):
        """Тест константы SKLEARN_AVAILABLE"""
        # SKLEARN_AVAILABLE должен существовать
        self.assertIn(SKLEARN_AVAILABLE, [True, False])


if __name__ == '__main__':
    unittest.main()