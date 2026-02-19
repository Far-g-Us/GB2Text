"""
Тесты для модулей плагинов
"""
import pytest
import os
import tempfile
from core.rom import GameBoyROM
from plugins.generic import GenericGBPlugin, GenericGBCPlugin, GenericGBAPlugin


class TestGenericPlugins:
    """Тесты Generic плагинов"""
    
    def create_test_rom_file(self, size=0x8000, system='gb', title='TEST'):
        """Создание тестового ROM файла"""
        rom_data = bytearray(size)
        title_bytes = title.encode('ascii')[:11].ljust(11, b'\x00')
        rom_data[0x00:0x0B] = title_bytes
        
        if system == 'gba':
            rom_data[0x00:0x04] = b'GBA '
        elif system == 'gbc':
            rom_data[0x0143] = 0x80
        
        rom_data[0x0147] = 0x00
        rom_data[0x0148] = 0x00
        
        return bytes(rom_data)
    
    def test_generic_gb_plugin(self):
        """Тест GenericGBPlugin"""
        plugin = GenericGBPlugin()
        # game_id_pattern - это property
        pattern = plugin.game_id_pattern
        assert isinstance(pattern, str)
        assert 'GAME_' in pattern
    
    def test_generic_gbc_plugin(self):
        """Тест GenericGBCPlugin"""
        plugin = GenericGBCPlugin()
        pattern = plugin.game_id_pattern
        assert isinstance(pattern, str)
    
    def test_generic_gba_plugin(self):
        """Тест GenericGBAPlugin"""
        plugin = GenericGBAPlugin()
        pattern = plugin.game_id_pattern
        assert isinstance(pattern, str)
    
    def test_generic_gb_plugin_get_text_segments(self):
        """Тест получения сегментов текста GB плагином"""
        rom_data = self.create_test_rom_file(system='gb')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            plugin = GenericGBPlugin()
            rom = GameBoyROM(temp_path)
            segments = plugin.get_text_segments(rom)
            assert isinstance(segments, list)
        finally:
            os.unlink(temp_path)
    
    def test_generic_gba_plugin_get_text_segments(self):
        """Тест получения сегментов текста GBA плагином"""
        rom_data = self.create_test_rom_file(system='gba')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gba') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            plugin = GenericGBAPlugin()
            rom = GameBoyROM(temp_path)
            segments = plugin.get_text_segments(rom)
            assert isinstance(segments, list)
        finally:
            os.unlink(temp_path)
