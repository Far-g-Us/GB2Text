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
