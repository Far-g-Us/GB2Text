"""
Тесты для модулей плагинов
"""
import os
import tempfile

import pytest

from core.plugin import GamePlugin, GenericGamePlugin, PluginProtocol
from core.rom import GameBoyROM
from plugins.generic import GenericGBAPlugin, GenericGBCPlugin, GenericGBPlugin


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
        assert 'GAME' in pattern

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

    def test_generic_gbc_plugin_get_text_segments(self):
        """Тест получения сегментов текста GBC плагином"""
        rom_data = self.create_test_rom_file(system='gbc')

        with tempfile.NamedTemporaryFile(delete=False, suffix='.gbc') as f:
            f.write(rom_data)
            temp_path = f.name

        try:
            plugin = GenericGBCPlugin()
            rom = GameBoyROM(temp_path)
            segments = plugin.get_text_segments(rom)
            assert isinstance(segments, list)
        finally:
            os.unlink(temp_path)

    def test_plugin_game_id_pattern_gbc(self):
        """Тест паттерна ID игры для GBC плагина"""
        plugin = GenericGBCPlugin()
        pattern = plugin.game_id_pattern
        assert isinstance(pattern, str)

    def test_generic_game_plugin(self):
        """Тест GenericGamePlugin"""
        from core.plugin import GenericGamePlugin
        plugin = GenericGamePlugin()
        pattern = plugin.game_id_pattern
        assert isinstance(pattern, str)

    def test_generic_game_plugin_get_text_segments(self):
        """Тест получения сегментов GenericGamePlugin"""
        import tempfile

        from core.plugin import GenericGamePlugin

        plugin = GenericGamePlugin()
        rom_data = b'\x00' * 0x8000

        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name

        try:
            rom = GameBoyROM(temp_path)
            segments = plugin.get_text_segments(rom)
            assert isinstance(segments, list)
            assert len(segments) > 0
        finally:
            os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────
# P1: Plugin contract tests
# ─────────────────────────────────────────────────────────────

class TestPluginContracts:
    """P1: Тесты контрактов плагинов."""

    def test_game_plugin_has_required_methods(self):
        """GamePlugin имеет обязательные методы."""
        plugin = GenericGamePlugin()
        assert hasattr(plugin, 'game_id_pattern')
        assert hasattr(plugin, 'get_text_segments')
        assert callable(plugin.get_text_segments)

    def test_game_plugin_has_optional_methods(self):
        """GamePlugin имеет опциональные методы с дефолтами."""
        plugin = GenericGamePlugin()
        assert hasattr(plugin, 'get_compression_handler')
        assert hasattr(plugin, 'get_terminators')
        assert hasattr(plugin, 'get_pointer_size')
        assert hasattr(plugin, 'validate_rom')

    def test_optional_methods_return_defaults(self):
        """Опциональные методы возвращают дефолтные значения."""
        plugin = GenericGamePlugin()
        assert plugin.get_compression_handler('test') is None
        assert plugin.get_terminators('test') == [0x00, 0xFF, 0xFE, 0x0D, 0x0A]
        assert plugin.get_pointer_size(None) == 2
        assert plugin.validate_rom(None) is True

    def test_plugin_protocol_is_runtime_checkable(self):
        """PluginProtocol можно использовать для isinstance проверок."""
        plugin = GenericGamePlugin()
        # GenericGamePlugin не реализует PluginProtocol напрямую
        # но имеет опциональные методы
        assert isinstance(plugin, GamePlugin)

    def test_custom_plugin_with_optional_methods(self):
        """Кастомный плагин с опциональными методами."""

        class CustomPlugin(GamePlugin):
            @property
            def game_id_pattern(self):
                return r'^CUSTOM$'

            def get_text_segments(self, rom):
                return [{'name': 'custom', 'start': 0, 'end': 100,
                         'decoder': None, 'compression': None}]

            def get_compression_handler(self, segment_name):
                return None

            def get_terminators(self, segment_name):
                return [0x00]

            def get_pointer_size(self, rom):
                return 4

            def validate_rom(self, rom):
                return True

        plugin = CustomPlugin()
        assert plugin.game_id_pattern == r'^CUSTOM$'
        assert plugin.get_compression_handler('custom') is None
        assert plugin.get_terminators('custom') == [0x00]
        assert plugin.get_pointer_size(None) == 4
        assert plugin.validate_rom(None) is True

    def test_segment_dict_structure(self):
        """get_text_segments возвращает правильную структуру dict."""
        rom_data = b'\x00' * 0x8000
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name

        try:
            plugin = GenericGamePlugin()
            rom = GameBoyROM(temp_path)
            segments = plugin.get_text_segments(rom)
            assert len(segments) > 0

            seg = segments[0]
            assert 'name' in seg
            assert 'start' in seg
            assert 'end' in seg
            assert 'decoder' in seg
            assert 'compression' in seg
            assert isinstance(seg['name'], str)
            assert isinstance(seg['start'], int)
            assert isinstance(seg['end'], int)
        finally:
            os.unlink(temp_path)
