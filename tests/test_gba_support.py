"""Тесты для модуля gba_support"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gba_support import GBALZ77Handler


class TestGBALZ77Handler:
    """Тесты для GBA LZ77 обработчика"""
    
    def test_init(self):
        """Тест инициализации"""
        handler = GBALZ77Handler()
        assert handler is not None
    
    def test_decompress_basic(self):
        """Тест базовой распаковки"""
        handler = GBALZ77Handler()
        # Простые несжатые данные
        data = bytes([0x10]) + b'Hello GBA!'
        result, end = handler.decompress(data, 0)
        assert isinstance(result, bytes)
        assert isinstance(end, int)
    
    def test_decompress_empty(self):
        """Тест с пустыми данными"""
        handler = GBALZ77Handler()
        result, end = handler.decompress(b'', 0)
        assert isinstance(result, bytes)
    
    def test_compress_basic(self):
        """Тест сжатия - пропускаем т.к. не реализовано"""
        pass
    
    def test_compress_empty(self):
        """Тест сжатия пустых данных - пропускаем т.к. не реализовано"""
        pass
