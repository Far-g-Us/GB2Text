"""Тесты для модуля scanner"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scanner import (
    find_text_pointers,
    is_text_like,
    detect_multiple_languages,
    auto_detect_charmap,
    analyze_text_segment,
    auto_detect_segments
)


class TestScanner:
    """Тесты для функций сканера"""
    
    def test_find_text_pointers_basic(self):
        """Тест базового поиска указателей"""
        # Создаём тестовые данные с указателями
        rom_data = bytes(range(256)) * 100
        pointers = find_text_pointers(rom_data, pointer_size=2)
        assert isinstance(pointers, list)
    
    def test_find_text_pointers_empty(self):
        """Тест с пустыми данными"""
        rom_data = b''
        pointers = find_text_pointers(rom_data)
        assert isinstance(pointers, list)
    
    def test_find_text_pointers_gba(self):
        """Тест поиска указателей для GBA"""
        rom_data = bytes(range(256)) * 100
        pointers = find_text_pointers(rom_data, pointer_size=4)
        assert isinstance(pointers, list)
    
    def test_is_text_like_valid(self):
        """Тест определения текста"""
        # ASCII текст
        text_data = b'Hello World!'
        result = is_text_like(text_data, 0, 5)
        assert isinstance(result, bool)
    
    def test_is_text_like_empty(self):
        """Тест с пустыми данными"""
        result = is_text_like(b'', 0, 0)
        assert result == False
    
    def test_detect_multiple_languages_english(self):
        """Тест определения английского языка"""
        # ASCII текст
        text_data = b'Hello World! This is a test.'
        result = detect_multiple_languages(text_data, 0, 100)
        assert isinstance(result, list)
        assert 'english' in result
    
    def test_detect_multiple_languages_empty(self):
        """Тест с пустыми данными"""
        result = detect_multiple_languages(b'', 0, 10)
        assert isinstance(result, list)
    
    def test_detect_multiple_languages_japanese(self):
        """Тест определения японского языка"""
        # Катакана
        text_data = b'Hello' + b'\\x83\\x80\\x83\\x81'  #  Hello катаканой
        result = detect_multiple_languages(text_data, 0, 50)
        assert isinstance(result, list)
    
    def test_auto_detect_charmap_basic(self):
        """Тест автоопределения таблицы символов"""
        text_data = b'Hello World!'
        charmap = auto_detect_charmap(text_data, 0, 50)
        assert isinstance(charmap, dict)
        assert len(charmap) > 0
    
    def test_auto_detect_charmap_empty(self):
        """Тест с пустыми данными"""
        charmap = auto_detect_charmap(b'', 0, 0)
        assert isinstance(charmap, dict)
    
    def test_analyze_text_segment_basic(self):
        """Тест анализа текстового сегмента"""
        text_data = b'Hello World!'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)
        assert 'readability' in result
        assert 'has_pointers' in result
    
    def test_analyze_text_segment_empty(self):
        """Тест анализа пустого сегмента"""
        result = analyze_text_segment(b'', 0, 0)
        assert isinstance(result, dict)
    
    def test_auto_detect_segments_basic(self):
        """Тест автоопределения сегментов"""
        # Создаём данные с текстовыми блоками
        rom_data = b'\\x00' * 100 + b'Hello World!' + b'\\x00' * 50
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)
    
    def test_auto_detect_segments_empty(self):
        """Тест с пустыми данными"""
        segments = auto_detect_segments(b'')
        assert isinstance(segments, list)
    
    def test_find_text_pointers_with_start(self):
        """Тест поиска указателей с указанием start"""
        rom_data = bytes(range(256)) * 50
        pointers = find_text_pointers(rom_data, start=1000)
        assert isinstance(pointers, list)
    
    def test_find_text_pointers_with_end(self):
        """Тест поиска указателей с указанием end"""
        rom_data = bytes(range(256)) * 50
        pointers = find_text_pointers(rom_data, end=1000)
        assert isinstance(pointers, list)
    
    def test_find_text_pointers_min_length(self):
        """Тест с min_length"""
        rom_data = bytes(range(256)) * 50
        pointers = find_text_pointers(rom_data, min_length=4)
        assert isinstance(pointers, list)
    
    def test_is_text_like_longer(self):
        """Тест is_text_like с более длинным текстом"""
        text_data = b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        result = is_text_like(text_data, 0, 20)
        assert isinstance(result, bool)
    
    def test_detect_multiple_languages_russian(self):
        """Тест определения русского языка"""
        # Кириллица
        text_data = b'Hello' + b'\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82'  # Привет
        result = detect_multiple_languages(text_data, 0, 50)
        assert isinstance(result, list)
    
    def test_auto_detect_charmap_with_terminator(self):
        """Тест автоопределения charmap с терминатором"""
        text_data = b'Hello\x00World!'
        charmap = auto_detect_charmap(text_data, 0, 100)
        assert isinstance(charmap, dict)
    
    def test_analyze_text_segment_with_pointers(self):
        """Тест анализа сегмента с указателями"""
        # Данные с указателями
        text_data = b'\x00\x10\x00\x20Hello World!'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)
