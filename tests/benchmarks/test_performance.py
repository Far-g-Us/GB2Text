"""
Performance benchmarks for GB2Text core modules.
Run with: pytest tests/benchmarks/test_performance.py --benchmark-only
"""

import os
import tempfile
import pytest

from core.rom import GameBoyROM
from core.scanner import auto_detect_segments
from core.decoder import TextDecoder, CharMapDecoder
from core.encoding import auto_detect_charmap
from core.compression import decode_compressed_data


class TestPerformanceBenchmarks:
    """Performance benchmarks for critical operations."""

    @pytest.fixture
    def sample_rom_path(self, tmp_path):
        """Create a sample ROM file for testing."""
        rom_file = tmp_path / "test_rom.gb"
        # Create minimal ROM header
        rom_data = bytearray(0x8000)  # 32KB ROM
        rom_data[0x104:0x108] = b'NTEJ'  # Nintendo logo
        rom_data[0x134:0x14C] = b'TEST GAME\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'  # Title
        rom_data[0x143] = 0x00  # CGB flag (DMG)
        rom_data[0x146] = 0x00  # MBC type (ROM only)
        rom_data[0x148] = 0x00  # ROM size (32KB)
        rom_data[0x149] = 0x00  # RAM size
        
        # Add some text patterns for scanning
        text_data = bytes([
            0x48, 0x45, 0x4C, 0x4C, 0x4F, 0x00,  # "HELLO"
            0x57, 0x4F, 0x52, 0x4C, 0x44, 0x00,  # "WORLD"
        ])
        rom_data[0x200:0x200 + len(text_data)] = text_data
        
        rom_file.write_bytes(bytes(rom_data))
        return str(rom_file)

    @pytest.mark.benchmark(group="rom_loading")
    def test_rom_loading_benchmark(self, benchmark, sample_rom_path):
        """Benchmark ROM loading time."""
        result = benchmark(GameBoyROM, sample_rom_path)
        assert result is not None

    @pytest.mark.benchmark(group="rom_loading")
    def test_rom_loading_multiple_formats(self, benchmark, tmp_path):
        """Benchmark loading different ROM formats."""
        # Create GB file
        gb_file = tmp_path / "test.gb"
        gb_data = bytearray(0x8000)
        gb_data[0x104:0x108] = b'NTEJ'
        gb_data[0x134:0x14C] = b'TEST\x00' + bytes(12)
        gb_file.write_bytes(bytes(gb_data))
        
        result = benchmark(GameBoyROM, str(gb_file))
        assert result is not None

    @pytest.mark.benchmark(group="scanning")
    def test_text_scanning_benchmark(self, benchmark, sample_rom_path):
        """Benchmark text scanning performance."""
        rom = GameBoyROM(sample_rom_path)
        scanner = TextScanner(rom)
        
        result = benchmark(scanner.scan_text_blocks)
        assert result is not None

    @pytest.mark.benchmark(group="scanning")
    def test_large_rom_scanning(self, benchmark, tmp_path):
        """Benchmark scanning large ROM data."""
        large_rom = tmp_path / "large.gb"
        rom_data = bytearray(0x20000)  # 128KB
        rom_data[0x104:0x108] = b'NTEJ'
        rom_data[0x134:0x14C] = b'LARGE ROM\x00' + bytes(13)
        
        # Add multiple text patterns
        text_pattern = bytes([0x54, 0x45, 0x53, 0x54, 0x00])  # "TEST"
        for offset in range(0, len(rom_data) - len(text_pattern), 256):
            rom_data[offset:offset + len(text_pattern)] = text_pattern
        
        large_rom.write_bytes(bytes(rom_data))
        rom = GameBoyROM(str(large_rom))
        scanner = TextScanner(rom)
        
        result = benchmark(scanner.scan_text_blocks)
        assert result is not None

    @pytest.mark.benchmark(group="decoding")
    def test_text_decoding_benchmark(self, benchmark):
        """Benchmark text decoding operations."""
        decoder = TextDecoder()
        encoded_data = bytes([
            0x48, 0x45, 0x4C, 0x4C, 0x4F, 0x00,
            0x57, 0x4F, 0x52, 0x4C, 0x44, 0x00,
        ])
        
        result = benchmark(decoder.decode_text, encoded_data)
        assert result is not None

    @pytest.mark.benchmark(group="encoding")
    def test_encoding_benchmark(self, benchmark):
        """Benchmark text encoding operations."""
        encoder = GB2TextEncoder()
        text = "HELLO WORLD"
        
        result = benchmark(encoder.encode_text, text)
        assert result is not None

    @pytest.mark.benchmark(group="compression")
    def test_decompression_benchmark(self, benchmark):
        """Benchmark data decompression."""
        # Create compressed-like data
        original = bytes([0x00, 0x01, 0x02] * 100)
        compressed = bytes([0x03, 0x03, 0x64]) + bytes([0x00, 0x01, 0x02])  # Simple compression marker
        
        result = benchmark(decode_compressed_data, compressed)
        assert result is not None

    @pytest.mark.benchmark(group="memory")
    def test_rom_cache_operations(self, benchmark, tmp_path):
        """Benchmark ROM cache operations."""
        from core.rom_cache import ROMCache
        
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        rom_file = tmp_path / "cached_rom.gb"
        rom_data = bytearray(0x8000)
        rom_data[0x104:0x108] = b'NTEJ'
        rom_data[0x134:0x14C] = b'CACHED\x00' + bytes(14)
        rom_file.write_bytes(bytes(rom_data))
        
        cache = ROMCache(str(cache_dir))
        
        result = benchmark(cache.get, str(rom_file))
        assert result is not None


class TestMemoryBenchmarks:
    """Memory usage benchmarks."""

    @pytest.mark.benchmark(group="memory")
    def test_rom_memory_footprint(self, benchmark, sample_rom_path):
        """Measure ROM memory usage."""
        import tracemalloc
        
        tracemalloc.start()
        rom = GameBoyROM(sample_rom_path)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Store result for benchmark output
        result = peak
        assert result > 0

    @pytest.mark.benchmark(group="memory")
    def test_scanner_memory_usage(self, benchmark, sample_rom_path):
        """Measure scanner memory usage."""
        import tracemalloc
        
        rom = GameBoyROM(sample_rom_path)
        
        tracemalloc.start()
        scanner = TextScanner(rom)
        results = scanner.scan_text_blocks()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        result = peak
        assert result > 0


class TestIOBenchmarks:
    """I/O operation benchmarks."""

    @pytest.mark.benchmark(group="io")
    def test_file_read_benchmark(self, benchmark, sample_rom_path):
        """Benchmark file reading operations."""
        def read_file():
            with open(sample_rom_path, 'rb') as f:
                return f.read()
        
        result = benchmark(read_file)
        assert result is not None

    @pytest.mark.benchmark(group="io")
    def test_tmx_export_benchmark(self, benchmark, tmp_path):
        """Benchmark TMX file export."""
        from core.tmx import TMXExporter
        import tempfile
        
        exporter = TMXExporter()
        
        def export_tmx():
            output_file = tmp_path / "export.tmx"
            segments = [
                {'id': 1, 'source': 'Test source text', 'target': 'Test target text'},
                {'id': 2, 'source': 'Another text', 'target': 'Another target'},
            ]
            exporter.export(segments, str(output_file))
            return str(output_file)
        
        result = benchmark(export_tmx)
        assert os.path.exists(result)


if __name__ == '__main__':
    pytest.main([__file__, '--benchmark-only'])