"""Тесты для модуля analyzer"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.analyzer import TextAnalyzer
from core.rom import GameBoyROM


class TestAnalyzer:
    """Тесты для TextAnalyzer"""
    
    def test_detect_terminators_basic(self):
        """Тест определения терминаторов"""
        text_data = b'Hello World!'
        result = TextAnalyzer.detect_terminators(text_data)
        assert isinstance(result, list)
    
    def test_detect_terminators_empty(self):
        """Тест с пустыми данными"""
        result = TextAnalyzer.detect_terminators(b'')
        assert isinstance(result, list)
    
    def test_detect_terminators_with_length(self):
        """Тест с указанием длины"""
        text_data = b'Hello World! Test data'
        result = TextAnalyzer.detect_terminators(text_data, length=5)
        assert isinstance(result, list)
    
    def test_detect_text_regions_basic(self):
        """Тест определения текстовых регионов"""
        # Создаём минимальный ROM
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\\x00' * 100 + b'Hello World!' + b'\\x00' * 50
        rom.header = {}
        
        result = TextAnalyzer.detect_text_regions(rom)
        assert isinstance(result, list)
    
    def test_detect_text_regions_empty_rom(self):
        """Тест с пустым ROM"""
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b''
        rom.header = {}
        
        result = TextAnalyzer.detect_text_regions(rom)
        assert isinstance(result, list)
    
    def test_validate_extraction_basic(self):
        """Тест валидации извлечения"""
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'test data'
        rom.header = {}
        
        # Требуется ключ offset в результатах
        results = {"test_segment": [{"text": "Hello", "offset": 0}]}
        result = TextAnalyzer.validate_extraction(rom, results)
        assert isinstance(result, dict)
    
    def test_validate_extraction_empty(self):
        """Тест с пустыми результатами"""
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b''
        rom.header = {}
        
        result = TextAnalyzer.validate_extraction(rom, {})
        assert isinstance(result, dict)
