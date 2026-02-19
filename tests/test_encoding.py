"""
Тесты для модуля encoding
"""
from core.encoding import (
    get_generic_english_charmap,
    get_generic_japanese_charmap,
    get_generic_russian_charmap,
    get_generic_chinese_charmap,
    get_generic_shiftjis_charmap,
    auto_detect_charmap
)


class TestEncoding:
    """Тесты функций кодировок"""
    
    def test_get_generic_english_charmap(self):
        """Тест получения английской таблицы символов"""
        charmap = get_generic_english_charmap()
        assert isinstance(charmap, dict)
        assert len(charmap) > 0
        # Проверяем базовые ASCII символы
        assert charmap.get(0x20) == ' '
        assert charmap.get(0x41) == 'A'
        assert charmap.get(0x61) == 'a'
    
    def test_get_generic_japanese_charmap(self):
        """Тест получения японской таблицы символов"""
        charmap = get_generic_japanese_charmap()
        assert isinstance(charmap, dict)
        assert len(charmap) > 0
        # Проверяем базовые символы
        assert charmap.get(0x20) == ' '
    
    def test_get_generic_russian_charmap(self):
        """Тест получения русской таблицы символов"""
        charmap = get_generic_russian_charmap()
        assert isinstance(charmap, dict)
        assert len(charmap) > 0
        # Проверяем наличие кириллицы
        assert 0xA0 in charmap  # А
    
    def test_get_generic_chinese_charmap(self):
        """Тест получения китайской таблицы символов"""
        charmap = get_generic_chinese_charmap()
        assert isinstance(charmap, dict)
        assert len(charmap) > 0
    
    def test_get_generic_shiftjis_charmap(self):
        """Тест получения Shift-JIS таблицы символов"""
        charmap = get_generic_shiftjis_charmap()
        assert isinstance(charmap, dict)
        assert len(charmap) > 0
    
    def test_auto_detect_charmap_basic(self):
        """Тест автоопределения таблицы символов"""
        # Создаем тестовые данные с ASCII текстом
        test_data = b'Hello World! This is a test string.\x00'
        charmap = auto_detect_charmap(test_data)
        assert isinstance(charmap, dict)
        # Самый частый символ должен быть пробелом
        assert 0x20 in charmap
    
    def test_auto_detect_charmap_with_terminator(self):
        """Тест автоопределения с терминатором"""
        # Данные с повторяющимся терминатором
        test_data = b'Hello\x00World\x00Test\x00'
        charmap = auto_detect_charmap(test_data)
        assert isinstance(charmap, dict)
    
    def test_auto_detect_charmap_empty_data(self):
        """Тест автоопределения с пустыми данными"""
        test_data = b''
        charmap = auto_detect_charmap(test_data)
        assert isinstance(charmap, dict)
    
    def test_charmap_values_are_strings(self):
        """Тест что значения таблицы - строки"""
        for func in [
            get_generic_english_charmap,
            get_generic_japanese_charmap,
            get_generic_russian_charmap,
            get_generic_chinese_charmap,
            get_generic_shiftjis_charmap
        ]:
            charmap = func()
            for value in charmap.values():
                assert isinstance(value, str), f"Value {value} is not str"
