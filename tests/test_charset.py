"""
Тесты для модуля charset
"""
import pytest
import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.charset import load_charset


class TestCharset:
    """Тесты для функций работы с charset"""

    def test_load_charset_english(self):
        """Тест загрузки английского charset"""
        charset = load_charset('en')
        assert isinstance(charset, dict)
        assert len(charset) > 0
        # Проверяем базовые символы
        assert 0x41 in charset  # 'A'
        assert 0x61 in charset  # 'a'
        assert 0x30 in charset  # '0'

    def test_load_charset_russian(self):
        """Тест загрузки русского charset"""
        charset = load_charset('ru')
        assert isinstance(charset, dict)
        assert len(charset) > 0
        # Проверяем символы кириллицы
        assert 0x81 in charset  # 'А'
        assert 0xA1 in charset  # 'а'

    def test_load_charset_japanese(self):
        """Тест загрузки японского charset"""
        charset = load_charset('ja')
        assert isinstance(charset, dict)
        assert len(charset) > 0
        # Проверяем символы катаканы
        assert 0x97 in charset  # 'ア'

    def test_load_charset_nonexistent(self):
        """Тест загрузки несуществующего charset"""
        with pytest.raises(FileNotFoundError):
            load_charset('nonexistent')

    def test_charset_terminal_symbols(self):
        """Тест наличия терминаторов"""
        for lang in ['en', 'ru', 'ja']:
            charset = load_charset(lang)
            # Проверяем наличие управляющих символов
            assert 0x00 in charset  # null terminator
            assert 0x0D in charset  # carriage return
            assert 0x0A in charset  # line feed


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
