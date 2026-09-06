"""Тесты для модуля compression"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compression import AutoDetectCompressionHandler, LZSSHandler, RLEHandler


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
        result, _end = handler.decompress(b'', 0)
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
        result, _end = handler.decompress(b'', 0)
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
        result, _end = handler.decompress(data, 0)
        assert isinstance(result, bytes)

    def test_detect_compression_none(self):
        """Тест определения отсутствия сжатия"""
        handler = AutoDetectCompressionHandler()
        data = b'Plain text data'
        compression_type = handler.detect_compression(data, 0)
        assert isinstance(compression_type, str)


# ─────────────────────────────────────────────────────────────
# P0: Compression round-trip tests
# ─────────────────────────────────────────────────────────────

class TestCompressionRoundtrip:
    """P0: Round-trip тесты compress → decompress."""

    def test_gba_lz77_compress_decompress_roundtrip(self):
        """GBA LZ77: compress → decompress = original."""
        from core.gba_support import GBALZ77Handler
        handler = GBALZ77Handler()
        original = b'ABCDEFGHIJ' * 10
        compressed = handler.compress(original)
        assert compressed != original, "Данные должны сжиматься"
        decompressed, _ = handler.decompress(compressed, 0)
        assert decompressed == original

    def test_gba_lz77_short_data_roundtrip(self):
        """GBA LZ77: короткие данные (1 байт)."""
        from core.gba_support import GBALZ77Handler
        handler = GBALZ77Handler()
        original = b'\x41'
        compressed = handler.compress(original)
        decompressed, _ = handler.decompress(compressed, 0)
        assert decompressed == original

    def test_gba_lz77_empty_roundtrip(self):
        """GBA LZ77: пустые данные."""
        from core.gba_support import GBALZ77Handler
        handler = GBALZ77Handler()
        original = b''
        compressed = handler.compress(original)
        decompressed, _ = handler.decompress(compressed, 0)
        assert decompressed == original

    def test_gba_lz77_repeated_pattern(self):
        """GBA LZ77: повторяющийся паттерн (хорошо сжимается)."""
        from core.gba_support import GBALZ77Handler
        handler = GBALZ77Handler()
        original = b'AAAA' * 100
        compressed = handler.compress(original)
        decompressed, _ = handler.decompress(compressed, 0)
        assert decompressed == original

    def test_gba_lz77_all_bytes(self):
        """GBA LZ77: все 256 значений байта."""
        from core.gba_support import GBALZ77Handler
        handler = GBALZ77Handler()
        original = bytes(range(256))
        compressed = handler.compress(original)
        decompressed, _ = handler.decompress(compressed, 0)
        assert decompressed == original

    def test_lz77_compress_is_identity(self):
        """LZ77 (base) compress — заглушка, возвращает те же данные."""
        from core.decoder import LZ77Handler
        handler = LZ77Handler()
        data = b'HELLO WORLD'
        assert handler.compress(data) == data

    def test_lz77_decompress_non_lz77_data(self):
        """LZ77 decompress на не-LZ77 данных — возвращает исходные данные."""
        from core.decoder import LZ77Handler
        handler = LZ77Handler()
        data = b'PLAIN TEXT'
        result, consumed = handler.decompress(data, 0)
        assert isinstance(result, bytes)
        assert consumed > 0
