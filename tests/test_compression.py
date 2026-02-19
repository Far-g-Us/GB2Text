"""Тесты для модуля compression"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compression import LZSSHandler, RLEHandler, AutoDetectCompressionHandler


class TestLZSSHandler:
    """Тесты для LZSS обработчика"""
    
    def test_init(self):
        """Тест инициализации"""
        handler = LZSSHandler()
        assert handler is not None
    
    def test_decompress_basic(self):
        """Тест базовой распаковки"""
        handler = LZSSHandler()
        data = bytes([0x10, 0x41, 0x42, 0x43]) + bytes(100)
        result, end = handler.decompress(data, 0)
        assert isinstance(result, bytes)
        assert isinstance(end, int)
    
    def test_decompress_empty(self):
        """Тест с пустыми данными"""
        handler = LZSSHandler()
        result, end = handler.decompress(b'', 0)
        assert isinstance(result, bytes)


class TestRLEHandler:
    """Тесты для RLE обработчика"""
    
    def test_init(self):
        """Тест инициализации"""
        handler = RLEHandler()
        assert handler is not None
    
    def test_decompress_basic(self):
        """Тест базовой распаковки"""
        handler = RLEHandler()
        data = bytes([0x41, 0x03]) + bytes(100)
        result, end = handler.decompress(data, 0)
        assert isinstance(result, bytes)
        assert isinstance(end, int)
    
    def test_decompress_empty(self):
        """Тест с пустыми данными"""
        handler = RLEHandler()
        result, end = handler.decompress(b'', 0)
        assert isinstance(result, bytes)


class TestAutoDetectCompressionHandler:
    """Тесты для AutoDetectCompressionHandler"""
    
    def test_init(self):
        """Тест инициализации"""
        handler = AutoDetectCompressionHandler()
        assert handler is not None
    
    def test_decompress_auto(self):
        """Тест автоопределения распаковки"""
        handler = AutoDetectCompressionHandler()
        data = b'Hello World!'
        result, end = handler.decompress(data, 0)
        assert isinstance(result, bytes)
    
    def test_detect_compression_none(self):
        """Тест определения отсутствия сжатия"""
        handler = AutoDetectCompressionHandler()
        data = b'Plain text data'
        compression_type = handler.detect_compression(data, 0)
        assert isinstance(compression_type, str)
