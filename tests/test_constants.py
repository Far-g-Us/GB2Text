"""
Тесты для модуля constants
"""
import pytest
import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import constants


class TestConstants:
    """Тесты констант проекта"""

    def test_system_types(self):
        """Тест констант типов систем"""
        assert constants.SYSTEM_GB == 'gb'
        assert constants.SYSTEM_GBC == 'gbc'
        assert constants.SYSTEM_GBA == 'gba'

    def test_pointer_sizes(self):
        """Тест размеров указателей"""
        assert constants.SYSTEM_GB in constants.POINTER_SIZES
        assert constants.SYSTEM_GBC in constants.POINTER_SIZES
        assert constants.SYSTEM_GBA in constants.POINTER_SIZES
        
        # Проверяем что размеры корректны
        assert constants.POINTER_SIZES[constants.SYSTEM_GB] == 2
        assert constants.POINTER_SIZES[constants.SYSTEM_GBC] == 2
        assert constants.POINTER_SIZES[constants.SYSTEM_GBA] == 4

    def test_memory_regions(self):
        """Тест регионов памяти"""
        assert constants.BANK_0_START == 0x4000
        assert constants.VRAM_START == 0xA000
        assert constants.BANK_0_START < constants.VRAM_START

    def test_text_constants(self):
        """Тест констант текста"""
        assert constants.ASCII_PRINTABLE_START == 0x20
        assert constants.ASCII_PRINTABLE_END == 0x7E
        assert constants.ASCII_PRINTABLE_START < constants.ASCII_PRINTABLE_END

    def test_japanese_ranges(self):
        """Тест диапазонов японских символов"""
        assert constants.KATAKANA_RANGE[0] < constants.KATAKANA_RANGE[1]
        assert constants.HIRAGANA_RANGE[0] < constants.HIRAGANA_RANGE[1]

    def test_cyrillic_ranges(self):
        """Тест диапазонов кириллицы"""
        assert constants.CYRILLIC_UPPER[0] < constants.CYRILLIC_UPPER[1]
        assert constants.CYRILLIC_LOWER[0] < constants.CYRILLIC_LOWER[1]

    def test_quality_thresholds(self):
        """Тест порогов качества"""
        assert 0 <= constants.QUALITY_GOOD <= 1
        assert 0 <= constants.MIN_READABILITY_MEDIUM <= 1
        assert constants.MIN_READABILITY_LOW < constants.MIN_READABILITY_MEDIUM

    def test_gba_constants(self):
        """Тест констант GBA"""
        assert constants.GBA_ROM_BASE_ADDRESS == 0x08000000
        assert constants.GBA_MIN_ADDRESS == 0x4000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
