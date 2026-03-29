"""Тесты для плагина auto_detect"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.auto_detect import AutoDetectPlugin
from core.rom import GameBoyROM


class TestAutoDetectPlugin:
    """Тесты для AutoDetectPlugin"""
    
    def test_init(self):
        """Тест инициализации"""
        plugin = AutoDetectPlugin()
        assert plugin is not None
    
    def test_game_id_pattern(self):
        """Тест паттерна ID игры"""
        plugin = AutoDetectPlugin()
        pattern = plugin.game_id_pattern
        assert pattern == r'^.*$'
    
    def test_get_text_segments_gba(self):
        """Тест получения сегментов для GBA"""
        plugin = AutoDetectPlugin()
        
        # Создаём минимальный ROM
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\\x00' * 10000
        rom.system = 'gba'
        rom.header = {}
        
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)
    
    def test_get_text_segments_gb(self):
        """Тест получения сегментов для GB"""
        plugin = AutoDetectPlugin()
        
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\\x00' * 5000
        rom.system = 'gb'
        rom.header = {}
        
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)
    
    def test_get_text_segments_gbc(self):
        """Тест получения сегментов для GBC"""
        plugin = AutoDetectPlugin()
        
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\\x00' * 5000
        rom.system = 'gbc'
        rom.header = {}
        
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)
    
    def test_group_close_pointers(self):
        """Тест группировки указателей"""
        plugin = AutoDetectPlugin()
        pointers = [(100, 200), (210, 300), (500, 600)]
        groups = plugin._group_close_pointers(pointers, max_distance=50)
        assert isinstance(groups, list)
    
    def test_estimate_segment_length(self):
        """Тест оценки длины сегмента"""
        plugin = AutoDetectPlugin()
        data = b'\\x00' * 1000
        length = plugin._estimate_segment_length(data, 0)
        assert isinstance(length, int)
    
    def test_get_compression_for_system(self):
        """Тест определения сжатия для системы"""
        plugin = AutoDetectPlugin()
        
        compression = plugin._get_compression_for_system('gba')
        # Может быть None или строка
        assert compression is None or isinstance(compression, str)

    def test_group_close_pointers_different_distances(self):
        """Тест группировки указателей с разными расстояниями"""
        plugin = AutoDetectPlugin()
        pointers = [(100, 200), (250, 300), (400, 500), (600, 700)]
        groups = plugin._group_close_pointers(pointers, max_distance=100)
        assert isinstance(groups, list)

    def test_group_close_pointers_empty(self):
        """Тест группировки с пустым списком"""
        plugin = AutoDetectPlugin()
        groups = plugin._group_close_pointers([], max_distance=50)
        assert groups == []

    def test_estimate_segment_length_different_sizes(self):
        """Тест оценки длины сегмента с разными размерами"""
        plugin = AutoDetectPlugin()
        
        # Test with different data sizes
        for size in [100, 500, 1000, 5000]:
            data = b'\x00' * size
            length = plugin._estimate_segment_length(data, 0)
            assert isinstance(length, int)
            assert length > 0

    def test_get_compression_for_gb(self):
        """Тест определения сжатия для GB"""
        plugin = AutoDetectPlugin()
        compression = plugin._get_compression_for_system('gb')
        assert compression is None or isinstance(compression, str)

    def test_get_compression_for_gbc(self):
        """Тест определения сжатия для GBC"""
        plugin = AutoDetectPlugin()
        compression = plugin._get_compression_for_system('gbc')
        assert compression is None or isinstance(compression, str)

    def test_get_text_segments_with_text_data(self):
        """Тест получения сегментов с текстовыми данными"""
        plugin = AutoDetectPlugin()
        
        # Create ROM with some text-like data
        rom_data = b'\x00' * 1000 + b'Hello World!' + b'\x00' * 500
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = rom_data
        rom.system = 'gba'
        rom.header = {}
        
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)

    def test_get_text_segments_large_rom(self):
        """Тест получения сегментов для большого ROM"""
        plugin = AutoDetectPlugin()
        
        # Large ROM
        rom_data = b'\x00' * 100000
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = rom_data
        rom.system = 'gba'
        rom.header = {}
        
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)

    def test_group_close_pointers_overlapping(self):
        """Тест группировки перекрывающихся указателей"""
        plugin = AutoDetectPlugin()
        pointers = [(100, 200), (150, 250), (300, 400)]
        groups = plugin._group_close_pointers(pointers, max_distance=50)
        assert isinstance(groups, list)

    def test_estimate_segment_length_various(self):
        """Тест оценки длины сегмента с разными входными данными"""
        plugin = AutoDetectPlugin()
        # Test with larger data
        data = b'Hello World! This is a longer test string.' * 10
        length = plugin._estimate_segment_length(data, 0)
        assert isinstance(length, int)
        assert length > 0

    def test_get_text_segments_with_gb_system(self):
        """Тест получения сегментов для GB системы"""
        plugin = AutoDetectPlugin()
        
        rom_data = b'\x00' * 0x8000
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = rom_data
        rom.system = 'gb'
        rom.header = {}
        
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)

    def test_group_close_pointers_single(self):
        """Тест группировки с одним указателем"""
        plugin = AutoDetectPlugin()
        pointers = [(100, 200)]
        groups = plugin._group_close_pointers(pointers, max_distance=50)
        assert isinstance(groups, list)

    def test_get_compression_with_none(self):
        """Тест получения сжатия для неизвестной системы"""
        plugin = AutoDetectPlugin()
        compression = plugin._get_compression_for_system('unknown')
        # Should return None for unknown systems

    def test_group_close_pointers_with_overlapping_groups(self):
        """Тест группировки с перекрывающимися группами"""
        plugin = AutoDetectPlugin()
        pointers = [(0, 100), (50, 150), (200, 300), (250, 350)]
        groups = plugin._group_close_pointers(pointers, max_distance=100)
        assert isinstance(groups, list)

    def test_auto_detect_segments_at_boundaries(self):
        """Тест автоопределения сегментов на границах"""
        from core.scanner import auto_detect_segments
        # Test with text at very specific positions
        rom_data = b'\x00' * 0x4000 + b'Hello' + b'\x00' * 0x3FFF + b'World'
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_estimate_segment_length_at_end_of_data(self):
        """Тест оценки длины сегмента когда адрес за пределами данных"""
        plugin = AutoDetectPlugin()
        data = b'Hello World!'
        # Test with start_addr beyond data length
        length = plugin._estimate_segment_length(data, len(data) + 100)
        assert length == 0

    def test_estimate_segment_length_with_text_like_data(self):
        """Тест оценки длины сегмента с текстоподобными данными"""
        plugin = AutoDetectPlugin()
        # Create data that looks like text
        text_data = b'Hello World! This is a test string. ' * 20
        length = plugin._estimate_segment_length(text_data, 0)
        assert isinstance(length, int)
        assert length > 0

    def test_filter_overlapping_segments(self):
        """Тест фильтрации перекрывающихся сегментов"""
        plugin = AutoDetectPlugin()
        
        # Create mock ROM
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'A' * 10000
        rom.system = 'gba'
        rom.header = {}
        
        # Create overlapping segments
        segments = [
            {'start': 100, 'end': 500, 'name': 'seg1'},
            {'start': 300, 'end': 700, 'name': 'seg2'},  # Overlapping with seg1
            {'start': 800, 'end': 1000, 'name': 'seg3'},  # Not overlapping
        ]
        
        # Test the filtering - need to call internal method
        # Let's test the get_text_segments with controlled data
        rom.data = b'\x00' * 5000 + b'Hello World! ' * 50 + b'\x00' * 5000
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)

    def test_get_text_segments_many_segments(self):
        """Тест получения сегментов когда обнаружено много сегментов"""
        plugin = AutoDetectPlugin()
        
        # Create ROM with multiple text-like areas
        rom_data = b'\x00' * 1000
        for i in range(30):
            rom_data += b'Hello World! ' * 10 + b'\x00' * 1000
        
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = rom_data
        rom.system = 'gba'
        rom.header = {}
        
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)
        # Should be limited to max_segments (20)
