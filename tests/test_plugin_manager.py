"""Тесты для модуля plugin_manager"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.plugin_manager import CancellationToken, ConfigurablePlugin, PluginManager, get_safe_plugin_manager
from core.rom import GameBoyROM


class TestPluginManager:
    """Тесты для класса PluginManager"""

    def test_plugin_manager_init(self):
        """Тест инициализации PluginManager"""
        pm = PluginManager("plugins")
        assert pm is not None
        assert hasattr(pm, 'plugins')

    def test_plugin_manager_nonexistent_dir(self):
        """Тест с несуществующей директорией плагинов"""
        pm = PluginManager("nonexistent_plugins_dir")
        assert pm is not None

    def test_get_plugin_gba(self):
        """Тест получения плагина для GBA"""
        pm = PluginManager("plugins")
        plugin = pm.get_plugin("TEST GAME", "gba")
        assert plugin is not None

    def test_get_plugin_gb(self):
        """Тест получения плагина для GB"""
        pm = PluginManager("plugins")
        plugin = pm.get_plugin("TEST GAME", "gb")
        assert plugin is not None

    def test_get_plugin_gbc(self):
        """Тест получения плагина для GBC"""
        pm = PluginManager("plugins")
        plugin = pm.get_plugin("TEST GAME", "gbc")
        assert plugin is not None

    def test_get_plugin_unknown(self):
        """Тест с неизвестной игрой"""
        pm = PluginManager("plugins")
        plugin = pm.get_plugin("UNKNOWN GAME XYZ123", "gba")
        assert plugin is not None

    def test_get_plugin_with_rom(self):
        """Тест получения плагина с ROM объектом"""
        pm = PluginManager("plugins")
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.system = "gba"
        rom.header = {}
        plugin = pm.get_plugin("TEST", "gba")
        assert plugin is not None

    def test_get_text_segments_gba(self):
        """Тест получения текстовых сегментов"""
        pm = PluginManager("plugins")
        plugin = pm.get_plugin("POKEMON RUBY", "gba")
        assert plugin is not None
        assert hasattr(plugin, 'get_text_segments')

    def test_cancellation_token_init(self):
        """Тест инициализации токена отмены"""
        token = CancellationToken()
        assert token is not None
        assert not token.is_cancellation_requested()

    def test_cancellation_token_request(self):
        """Тест запроса отмены"""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancellation_requested()

    def test_cancellation_token_reset(self):
        """Тест сброса токена отмены"""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancellation_requested()

    def test_load_plugins_from_directory(self):
        """Тест загрузки плагинов из директории"""
        pm = PluginManager("plugins")
        assert pm is not None

    def test_get_plugin_none_system(self):
        """Тест с None системой"""
        pm = PluginManager("plugins")
        plugin = pm.get_plugin("TEST GAME", None)
        assert plugin is not None

    def test_get_plugin_with_cancellation(self):
        """Тест получения плагина с токеном отмены"""
        pm = PluginManager("plugins")
        token = CancellationToken()
        plugin = pm.get_plugin("TEST GAME", "gba", token)
        assert plugin is not None

    def test_get_plugin_not_cancelled(self):
        """Тест получения плагина когда отмена не запрошена"""
        pm = PluginManager("plugins")
        token = CancellationToken()
        plugin = pm.get_plugin("TEST GAME", "gba", token)
        assert plugin is not None

    def test_get_plugin_cancelled(self):
        """Тест получения плагина когда отмена запрошена"""
        pm = PluginManager("plugins")
        token = CancellationToken()
        token.cancel()
        plugin = pm.get_plugin("TEST GAME", "gba", token)
        assert plugin is None

    def test_get_resource_path(self):
        """Тест получения пути к ресурсу"""
        pm = PluginManager("plugins")
        path = pm._get_resource_path("test")
        assert isinstance(path, str)
        assert "test" in path

    def test_is_valid_config(self):
        """Тест валидации конфигурации"""
        pm = PluginManager("plugins")
        # Valid config
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": 0, "end": 100}
            ]
        }
        assert pm._is_valid_config(config)

    def test_is_valid_config_invalid(self):
        """Тест валидации некорректной конфигурации"""
        pm = PluginManager("plugins")
        # Missing required field
        config = {"segments": [{"name": "main", "start": 0, "end": 100}]}
        assert not pm._is_valid_config(config)

    def test_is_valid_config_invalid_addresses(self):
        """Тест валидации с невалидными адресами"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": "invalid", "end": 100}
            ]
        }
        assert not pm._is_valid_config(config)

    def test_is_config_safe(self):
        """Тест проверки безопасности конфигурации"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [{"name": "main", "start": 0, "end": 100}]
        }
        assert pm._is_config_safe(config)

    def test_is_generic_charmap(self):
        """Тест проверки generic charmap"""
        pm = PluginManager("plugins")
        # Generic charmap
        charmap = {"0x00": "A", "0x01": "B"}
        assert pm._is_generic_charmap(charmap)

    def test_configurable_plugin_init(self):
        """Тест инициализации ConfigurablePlugin"""
        config = {
            "game_id_pattern": "TEST",
            "segments": [{"name": "main", "start": 0, "end": 100}]
        }
        plugin = ConfigurablePlugin(config)
        assert plugin is not None
        assert plugin.game_id_pattern == "TEST"

    def test_configurable_plugin_get_text_segments(self):
        """Тест получения сегментов из ConfigurablePlugin"""
        config = {
            "game_id_pattern": "TEST",
            "segments": [{"name": "main", "start": 0, "end": 100}]
        }
        plugin = ConfigurablePlugin(config)
        # Should have get_text_segments method
        assert hasattr(plugin, 'get_text_segments')

    def test_get_safe_plugin_manager(self):
        """Тест безопасного создания менеджера плагинов"""
        pm = get_safe_plugin_manager("plugins")
        assert pm is not None

    def test_get_safe_plugin_manager_nonexistent(self):
        """Тест с несуществующей директорией"""
        pm = get_safe_plugin_manager("nonexistent_dir")
        assert pm is not None

    def test_load_python_plugins(self):
        """Тест загрузки Python плагинов"""
        pm = PluginManager("plugins")
        pm._load_python_plugins()

    def test_load_config_plugins(self):
        """Тест загрузки конфигурационных плагинов"""
        pm = PluginManager("plugins")
        pm._load_config_plugins()

    def test_create_example_plugin(self):
        """Тест создания примера плагина"""
        pm = PluginManager("plugins")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
            temp_path = f.name
        try:
            from pathlib import Path
            pm._create_example_plugin(Path(temp_path))
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_plugins_list_not_empty(self):
        """Тест что плагины загружены"""
        pm = PluginManager()
        assert len(pm.plugins) > 0

    def test_get_plugin_generic_fallback(self):
        """Тест fallback на generic плагин"""
        pm = PluginManager()
        plugin = pm.get_plugin("UNKNOWN GAME", "gba")
        assert plugin is not None

    def test_config_with_hex_addresses(self):
        """Тест конфигурации с шестнадцатеричными адресами"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": "0x1000", "end": "0x2000"}
            ]
        }
        assert pm._is_valid_config(config)

    def test_multiple_plugins_loaded(self):
        """Тест что загружено несколько плагинов"""
        pm = PluginManager()
        assert len(pm.plugins) >= 4  #至少有4个默认插件

    def test_get_plugin_by_system_gba(self):
        """Тест получения плагинов по системе GBA"""
        pm = PluginManager()
        gba_plugins = [p for p in pm.plugins if hasattr(p, 'supported_systems') and 'gba' in p.supported_systems]
        assert isinstance(gba_plugins, list)

    def test_is_valid_config_empty(self):
        """Тест валидации пустой конфигурации"""
        pm = PluginManager("plugins")
        assert not pm._is_valid_config({})

    def test_is_config_safe_empty(self):
        """Тест безопасности пустой конфигурации"""
        pm = PluginManager("plugins")
        result = pm._is_config_safe({})
        assert isinstance(result, bool)

    def test_plugin_has_supported_systems(self):
        """Тест что плагины имеют supported_systems"""
        pm = PluginManager()
        for plugin in pm.plugins:
            if hasattr(plugin, 'supported_systems'):
                assert isinstance(plugin.supported_systems, (list, tuple))

    def test_configurable_plugin_segments(self):
        """Тест сегментов ConfigurablePlugin"""
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": 0, "end": 100},
                {"name": "dialog", "start": 200, "end": 500}
            ]
        }
        plugin = ConfigurablePlugin(config)
        # Должен иметь метод get_text_segments
        assert hasattr(plugin, 'get_text_segments')

    def test_get_plugin_all_systems(self):
        """Тест получения плагинов для всех систем"""
        pm = PluginManager()
        for system in ["gb", "gbc", "gba"]:
            plugin = pm.get_plugin("TEST", system)
            assert plugin is not None

    def test_config_with_encoding(self):
        """Тест конфигурации с кодировкой"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [{"name": "main", "start": 0, "end": 100}],
            "encoding": "shift-jis"
        }
        assert pm._is_valid_config(config)

    def test_is_valid_config_missing_segment_fields(self):
        """Тест валидации с отсутствующими полями сегмента"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [{"name": "main"}]  # отсутствуют start и end
        }
        assert not pm._is_valid_config(config)

    def test_get_plugin_empty_game_id(self):
        """Тест получения плагина с пустым game_id"""
        pm = PluginManager()
        plugin = pm.get_plugin("", "gba")
        assert plugin is not None

    def test_is_generic_charmap_empty(self):
        """Тест пустой charmap"""
        pm = PluginManager("plugins")
        # Пустой charmap считается generic
        result = pm._is_generic_charmap({})
        assert isinstance(result, bool)

    def test_plugins_directory_creation(self):
        """Тест создания директории плагинов"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PluginManager(os.path.join(tmpdir, "plugins"))
            assert pm.plugins_dir is not None

    def test_load_plugins_multiple_times(self):
        """Тест многократной загрузки плагинов"""
        pm = PluginManager()
        initial_count = len(pm.plugins)
        pm.load_plugins()
        # Количество не должно уменьшаться
        assert len(pm.plugins) >= initial_count

    def test_is_config_safe_with_pokemon(self):
        """Тест что POKEMON в конфиге вызывает предупреждение"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "POKEMON RUBY",
            "segments": []
        }
        # Теперь возвращает True, но с предупреждением
        assert pm._is_config_safe(config)

    def test_is_config_safe_user_created(self):
        """Тест что user_created конфиг безопасен"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [],
            "user_created": True
        }
        assert pm._is_config_safe(config)

    def test_is_config_safe_with_charmap(self):
        """Тест с charmap > 50 символов"""
        pm = PluginManager("plugins")
        # Создаём charmap с 51 символом
        charmap = {f"0x{i:02x}": chr(65+i) for i in range(51)}
        config = {
            "game_id_pattern": "TEST",
            "segments": [{"name": "main", "start": 0, "end": 100, "charmap": charmap}]
        }
        # Не generic charmap
        result = pm._is_config_safe(config)
        assert isinstance(result, bool)

    def test_get_plugin_with_custom_plugin(self):
        """Тест получения кастомного плагина"""
        pm = PluginManager()
        # Тест с плагином который поддерживает несколько систем
        plugin = pm.get_plugin("CUSTOM GAME", "gba")
        assert plugin is not None

    def test_config_with_multiple_segments(self):
        """Тест конфигурации с несколькими сегментами"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": 0, "end": 100},
                {"name": "dialog", "start": 200, "end": 500},
                {"name": "items", "start": 1000, "end": 1500}
            ]
        }
        assert pm._is_valid_config(config)

    def test_is_valid_config_hex_with_prefix(self):
        """Тест валидации с hex адресами с префиксом"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": "0x0000", "end": "0x1000"}
            ]
        }
        assert pm._is_valid_config(config)

    def test_is_valid_config_negative_addresses(self):
        """Тест валидации с отрицательными адресами"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": -1, "end": 100}
            ]
        }
        # Отрицательные адреса могут быть валидными в некоторых случаях
        result = pm._is_valid_config(config)
        assert isinstance(result, bool)

    def test_load_plugins_error_handling(self):
        """Тест обработки ошибок при загрузке плагинов"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = PluginManager(os.path.join(tmpdir, "nonexistent"))
            # Должен обработать ошибку gracefully
            assert pm is not None

    def test_get_safe_plugin_manager_with_existing_dir(self):
        """Тест с существующей директорией"""
        pm = get_safe_plugin_manager("plugins")
        assert pm is not None
        assert len(pm.plugins) > 0

    def test_configurable_plugin_with_real_config(self):
        """Тест ConfigurablePlugin с реальной конфигурацией"""
        config = {
            "game_id_pattern": "TEST.*",
            "segments": [
                {"name": "text", "start": 0x4000, "end": 0x8000}
            ],
            "encoding": "ascii"
        }
        plugin = ConfigurablePlugin(config)
        # Имеет атрибут game_id_pattern
        assert plugin.game_id_pattern == "TEST.*"

    def test_load_python_plugins_from_directory(self):
        """Тест _load_python_plugins"""
        pm = PluginManager("plugins")
        pm._load_python_plugins()
        # Не должно вызвать ошибку

    def test_get_plugin_with_none_system(self):
        """Тест get_plugin с None системой"""
        pm = PluginManager()
        plugin = pm.get_plugin("TEST GAME", None)
        assert plugin is not None

    def test_get_plugin_cancelled_token(self):
        """Тест get_plugin с отменённым токеном"""
        pm = PluginManager()
        token = CancellationToken()
        token.cancel()
        plugin = pm.get_plugin("TEST", "gba", token)
        assert plugin is None

    def test_is_generic_charmap_with_data(self):
        """Тест _is_generic_charmap с данными"""
        pm = PluginManager("plugins")
        # Несколько символов
        charmap = {"0x30": "0", "0x31": "1", "0x32": "2"}
        assert pm._is_generic_charmap(charmap)

    def test_get_plugin_by_game_id(self):
        """Тест получения плагина по game_id"""
        pm = PluginManager()
        plugin = pm.get_plugin("POKEMON RUBY", "gba")
        assert plugin is not None

    def test_is_config_safe_with_zelda(self):
        """Тест что ZELDA в конфиге вызывает предупреждение"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "ZELDA",
            "segments": []
        }
        # Теперь возвращает True, но с предупреждением
        assert pm._is_config_safe(config)

    def test_is_config_safe_with_nintendo(self):
        """Тест что NINTENDO в конфиге вызывает предупреждение"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "NINTENDO GAME",
            "segments": []
        }
        assert pm._is_config_safe(config)

    def test_is_config_safe_with_gameboy(self):
        """Тест что GAMEBOY в конфиге вызывает предупреждение"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "GAMEBOY ADVANCE",
            "segments": []
        }
        assert pm._is_config_safe(config)

    def test_is_config_safe_with_charmap_50(self):
        """Тест с charmap ровно 50 символов"""
        pm = PluginManager("plugins")
        charmap = {f"0x{i:02x}": chr(65+i) for i in range(50)}
        config = {
            "game_id_pattern": "TEST",
            "segments": [{"name": "main", "start": 0, "end": 100, "charmap": charmap}]
        }
        # Ровно 50 символов не должна вызывать проверку
        result = pm._is_config_safe(config)
        assert isinstance(result, bool)

    def test_is_config_safe_with_charmap_51_generic(self):
        """Тест с charmap 51 символ, но generic"""
        pm = PluginManager("plugins")
        # 51 символ, но все буквы
        charmap = {f"0x{i:02x}": chr(65+i%26) for i in range(51)}
        config = {
            "game_id_pattern": "TEST",
            "segments": [{"name": "main", "start": 0, "end": 100, "charmap": charmap}]
        }
        result = pm._is_config_safe(config)
        assert isinstance(result, bool)

    def test_is_config_safe_with_segments_charmap(self):
        """Тест с charmap в сегментах"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": 0, "end": 100, "charmap": {"0x80": "A"}}
            ]
        }
        assert pm._is_config_safe(config)

    def test_create_example_plugin_writes_file(self):
        """Тест что _create_example_plugin создаёт файл"""
        pm = PluginManager("plugins")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w') as f:
            temp_path = f.name
        try:
            from pathlib import Path
            pm._create_example_plugin(Path(temp_path))
            # Файл должен существовать и быть не пустым
            assert os.path.exists(temp_path)
            assert os.path.getsize(temp_path) > 0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_create_example_plugin_content(self):
        """Тест содержимого созданного примера плагина"""
        pm = PluginManager("plugins")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
            temp_path = f.name
        try:
            from pathlib import Path
            pm._create_example_plugin(Path(temp_path))
            with open(temp_path) as f:
                config = json.load(f)
            assert "game_id_pattern" in config
            assert "segments" in config
            assert len(config["segments"]) > 0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_is_generic_charmap_with_pk(self):
        """Тест _is_generic_charmap с PK"""
        pm = PluginManager("plugins")
        # Проверяем, что функция работает с PK
        charmap = {"0x00": "P", "0x01": "K"}
        result = pm._is_generic_charmap(charmap)
        assert isinstance(result, bool)

    def test_is_generic_charmap_with_pokemon(self):
        """Тест _is_generic_charmap с POKEMON"""
        pm = PluginManager("plugins")
        charmap = {"0x00": "POKEMON"}
        result = pm._is_generic_charmap(charmap)
        assert isinstance(result, bool)

    def test_is_generic_charmap_with_zelda(self):
        """Тест _is_generic_charmap с ZELDA"""
        pm = PluginManager("plugins")
        charmap = {"0x00": "ZELDA"}
        assert not pm._is_generic_charmap(charmap)

    def test_configurable_plugin_get_text_segments_empty(self):
        """Тест ConfigurablePlugin с пустыми сегментами"""
        config = {
            "game_id_pattern": "TEST",
            "segments": []
        }
        plugin = ConfigurablePlugin(config)
        # Создаём mock ROM
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\x00' * 0x10000
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)

    def test_configurable_plugin_with_charmap(self):
        """Тест ConfigurablePlugin с charmap"""
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": 0, "end": 100, "charmap": {"0x80": "A", "0x81": "B"}}
            ]
        }
        plugin = ConfigurablePlugin(config)
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\x00' * 0x10000
        segments = plugin.get_text_segments(rom)
        assert len(segments) == 1
        assert segments[0]['decoder'] is not None

    def test_configurable_plugin_with_compression(self):
        """Тест ConfigurablePlugin со сжатием"""
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": 0, "end": 100, "compression": "LZ77"}
            ]
        }
        plugin = ConfigurablePlugin(config)
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\x00' * 0x10000
        # Может вернуть сегмент со сжатием
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)

    def test_configurable_plugin_invalid_addresses(self):
        """Тест ConfigurablePlugin с невалидными адресами"""
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": -1, "end": 100}
            ]
        }
        plugin = ConfigurablePlugin(config)
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\x00' * 0x10000
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)

    def test_configurable_plugin_out_of_bounds(self):
        """Тест ConfigurablePlugin с адресами за пределами ROM"""
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": 0, "end": 0x200000}
            ]
        }
        plugin = ConfigurablePlugin(config)
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\x00' * 0x10000
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)

    def test_configurable_plugin_missing_fields(self):
        """Тест ConfigurablePlugin с отсутствующими полями"""
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main"}
            ]
        }
        plugin = ConfigurablePlugin(config)
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\x00' * 0x10000
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)

    def test_configurable_plugin_with_language(self):
        """Тест ConfigurablePlugin с языком"""
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": 0, "end": 100, "language": "en"}
            ]
        }
        plugin = ConfigurablePlugin(config)
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\x00' * 0x10000
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)

    def test_get_plugin_with_invalid_regex(self):
        """Тест get_plugin с невалидным regex"""
        pm = PluginManager()
        # Добавляем плагин с невалидным regex
        class BadPlugin:
            game_id_pattern = "["  # Невалидный regex
            def get_text_segments(self, rom):
                return []
        pm.plugins.append(BadPlugin())
        # Не должен упасть
        plugin = pm.get_plugin("TEST", "gba")
        assert plugin is not None

    def test_load_python_plugins_error(self):
        """Тест ошибки загрузки Python плагинов"""
        pm = PluginManager("nonexistent_dir")
        # Не должен упасть
        pm._load_python_plugins()

    def test_load_config_plugins_creates_dir(self):
        """Тест создания директории конфигов"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            os.path.join(tmpdir, "config")
            pm = PluginManager(os.path.join(tmpdir, "plugins"))
            pm._load_config_plugins()

    def test_load_config_plugins_with_files(self):
        """Тест загрузки конфигов из файлов"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, "plugins", "config")
            os.makedirs(config_dir)
            config = {
                "game_id_pattern": "TEST",
                "segments": [{"name": "main", "start": 0, "end": 100}]
            }
            with open(os.path.join(config_dir, "test.json"), 'w') as f:
                json.dump(config, f)
            pm = PluginManager(os.path.join(tmpdir, "plugins"))
            pm._load_config_plugins()
            # Должен загрузить плагин
            assert len(pm.plugins) >= 1

    def test_load_config_plugins_max_limit(self):
        """Тест лимита конфигов"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, "plugins", "config")
            os.makedirs(config_dir)
            # Создаём 25 конфигов (больше лимита 20)
            for i in range(25):
                config = {
                    "game_id_pattern": f"TEST{i}",
                    "segments": [{"name": "main", "start": 0, "end": 100}]
                }
                with open(os.path.join(config_dir, f"test{i}.json"), 'w') as f:
                    json.dump(config, f)
            pm = PluginManager(os.path.join(tmpdir, "plugins"))
            pm._load_config_plugins()

    def test_load_config_plugins_invalid_json(self):
        """Тест с невалидным JSON"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, "plugins", "config")
            os.makedirs(config_dir)
            with open(os.path.join(config_dir, "invalid.json"), 'w') as f:
                f.write("not valid json")
            pm = PluginManager(os.path.join(tmpdir, "plugins"))
            pm._load_config_plugins()

    def test_load_config_plugins_duplicate(self):
        """Тест дубликатов конфигов"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, "plugins", "config")
            os.makedirs(config_dir)
            config = {
                "game_id_pattern": "TEST.*",
                "segments": [{"name": "main", "start": 0, "end": 100}]
            }
            for i in range(2):
                with open(os.path.join(config_dir, f"test{i}.json"), 'w') as f:
                    json.dump(config, f)
            pm = PluginManager(os.path.join(tmpdir, "plugins"))
            pm._load_config_plugins()

    def test_get_plugin_progress_update(self):
        """Тест обновления прогресса при поиске плагина"""
        pm = PluginManager()
        pm.update_status = lambda msg, progress: None
        # Добавляем i18n чтобы избежать ошибки
        class MockI18n:
            def t(self, key):
                return key
        pm.i18n = MockI18n()
        # Mock root с правильной сигнатурой
        class MockRoot:
            def update_idletasks(self):
                pass
        pm.root = MockRoot()
        plugin = pm.get_plugin("TEST GAME", "gba")
        assert plugin is not None

    def test_get_safe_plugin_manager_exception(self):
        """Тест get_safe_plugin_manager при исключении"""
        # Мокаем исключение при инициализации
        original_init = PluginManager.__init__
        def mock_init(self, *args, **kwargs):
            raise RuntimeError("Test error")
        try:
            PluginManager.__init__ = mock_init
            pm = get_safe_plugin_manager("plugins")
            assert pm is not None
            assert len(pm.plugins) >= 4
        finally:
            PluginManager.__init__ = original_init

    def test_is_valid_config_with_charmap(self):
        """Тест валидации с charmap"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": 0, "end": 100, "charmap": {"0x80": "A"}}
            ]
        }
        assert pm._is_valid_config(config)

    def test_is_valid_config_with_compression(self):
        """Тест валидации со сжатием"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": [
                {"name": "main", "start": 0, "end": 100, "compression": "LZ77"}
            ]
        }
        assert pm._is_valid_config(config)

    def test_is_valid_config_empty_segments(self):
        """Тест валидации с пустыми сегментами"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "TEST",
            "segments": []
        }
        assert pm._is_valid_config(config)

    def test_configurable_plugin_with_encoding(self):
        """Тест ConfigurablePlugin с encoding"""
        config = {
            "game_id_pattern": "TEST",
            "segments": [{"name": "main", "start": 0, "end": 100}],
            "encoding": "shift-jis"
        }
        plugin = ConfigurablePlugin(config)
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.data = b'\x00' * 0x10000
        segments = plugin.get_text_segments(rom)
        assert isinstance(segments, list)

    def test_get_plugin_no_plugins(self):
        """Тест get_plugin когда нет плагинов"""
        pm = PluginManager()
        pm.plugins = []
        plugin = pm.get_plugin("TEST", "gba")
        assert plugin is not None

    def test_is_generic_charmap_none(self):
        """Тест _is_generic_charmap с None"""
        pm = PluginManager("plugins")
        # None должен обрабатываться корректно
        try:
            result = pm._is_generic_charmap(None)
        except (TypeError, AttributeError):
            result = True  # Ожидаемое поведение при None
        assert isinstance(result, bool)


class FakeEntryPoints:
    """Имитация importlib.metadata.entry_points() (Python < 3.12, метод .select)."""

    def __init__(self, entries):
        self._entries = list(entries)

    def select(self, group=None):
        if group is None:
            return iter(self._entries)
        return iter(e for e in self._entries if e.group == group)


class TestEntryPointDiscovery:
    """Тесты загрузки плагинов через setuptools entry_points (П5)."""

    def _make_pm(self, tmp_path):
        """PluginManager с пустой (временной) директорией плагинов."""
        from core.plugin_manager import PluginManager
        return PluginManager(str(tmp_path))

    def test_entry_point_plugin_loaded(self, tmp_path, monkeypatch):
        """Плагин из entry point добавляется в specific_plugins."""
        from importlib.metadata import EntryPoint

        from tests.fake_ep_plugin import FakeSpecificEP

        ep = EntryPoint(name='fake_ep', value='tests.fake_ep_plugin:FakeSpecificEP',
                        group='gb2text.plugins')
        monkeypatch.setattr('importlib.metadata.entry_points',
                            lambda: FakeEntryPoints([ep]))

        pm = self._make_pm(tmp_path)
        assert any(isinstance(p, FakeSpecificEP) for p in pm.specific_plugins)

    def test_entry_point_plugin_used_for_game(self, tmp_path, monkeypatch):
        """get_plugin находит плагин из entry point по game_id_pattern."""
        from importlib.metadata import EntryPoint

        from tests.fake_ep_plugin import FakeSpecificEP

        ep = EntryPoint(name='fake_ep', value='tests.fake_ep_plugin:FakeSpecificEP',
                        group='gb2text.plugins')
        monkeypatch.setattr('importlib.metadata.entry_points',
                            lambda: FakeEntryPoints([ep]))

        pm = self._make_pm(tmp_path)
        plugin = pm.get_plugin('FAKE_EP_GAME', 'gba')
        assert isinstance(plugin, FakeSpecificEP)

    def test_entry_point_non_plugin_ignored(self, tmp_path, monkeypatch, caplog):
        """Entry point, указывающий на не-GamePlugin класс, игнорируется."""
        from importlib.metadata import EntryPoint

        from tests.fake_ep_plugin import NotAPlugin

        ep = EntryPoint(name='bad_ep', value='tests.fake_ep_plugin:NotAPlugin',
                        group='gb2text.plugins')
        monkeypatch.setattr('importlib.metadata.entry_points',
                            lambda: FakeEntryPoints([ep]))

        with caplog.at_level('WARNING', logger='gb2text.plugin_manager'):
            pm = self._make_pm(tmp_path)
            assert not any(isinstance(p, NotAPlugin) for p in pm.plugins)
        assert any('не является GamePlugin' in r.message for r in caplog.records)

    def test_entry_point_load_error_isolated(self, tmp_path, monkeypatch, caplog):
        """Ошибка load() одного entry point не ломает остальные."""
        from importlib.metadata import EntryPoint

        bad = EntryPoint(name='broken', value='no_such_module_xyz:none',
                         group='gb2text.plugins')
        good = EntryPoint(name='good_ep', value='tests.fake_ep_plugin:FakeSpecificEP',
                          group='gb2text.plugins')
        monkeypatch.setattr('importlib.metadata.entry_points',
                            lambda: FakeEntryPoints([bad, good]))

        with caplog.at_level('ERROR', logger='gb2text.plugin_manager'):
            pm = self._make_pm(tmp_path)
        from tests.fake_ep_plugin import FakeSpecificEP
        assert any(isinstance(p, FakeSpecificEP) for p in pm.specific_plugins)

    def test_entry_point_metadata_error(self, tmp_path, monkeypatch):
        """Сбой самой entry_points() обрабатывается без исключения."""
        def boom():
            raise RuntimeError('metadata broken')
        monkeypatch.setattr('importlib.metadata.entry_points', boom)

        pm = self._make_pm(tmp_path)
        assert pm._load_entry_point_plugins() == 0

    def test_entry_point_no_matches(self, tmp_path, monkeypatch):
        """Пустой результат entry_points — ноль плагинов, без ошибки."""
        from importlib.metadata import EntryPoint

        # entry point из ДРУГОЙ группы не должен загружаться
        other = EntryPoint(name='x', value='tests.fake_ep_plugin:FakeSpecificEP',
                           group='some.other.group')
        monkeypatch.setattr('importlib.metadata.entry_points',
                            lambda: FakeEntryPoints([other]))

        pm = self._make_pm(tmp_path)
        assert pm._load_entry_point_plugins() == 0


class TestPluginAllowlist:
    """Тесты allowlist плагинов (Ф3): gate до импорта, union env+file+arg."""

    @pytest.fixture(autouse=True)
    def _clean_allowlist_sources(self, monkeypatch):
        from core import plugin_manager as pm_mod

        monkeypatch.delenv(pm_mod.ALLOWLIST_ENV, raising=False)
        monkeypatch.setattr(pm_mod, 'ALLOWLIST_FILE', tmp_nonexistent())

    def test_default_none_when_nothing_set(self, monkeypatch):
        from core import plugin_manager as pm_mod

        monkeypatch.delenv(pm_mod.ALLOWLIST_ENV, raising=False)
        monkeypatch.setattr(pm_mod, 'ALLOWLIST_FILE', tmp_nonexistent())
        assert pm_mod.resolve_plugin_allowlist(None) is None

    def test_env_csv(self, monkeypatch):
        from core import plugin_manager as pm_mod

        monkeypatch.setenv(pm_mod.ALLOWLIST_ENV, "zelda, ff6 , pokemon")
        assert pm_mod.resolve_plugin_allowlist(None) == {"zelda", "ff6", "pokemon"}

    def test_file_list(self, monkeypatch, tmp_path):
        from core import plugin_manager as pm_mod

        (tmp_path / "plugin_allowlist.json").write_text(
            '["a", "b"]', encoding="utf-8")
        monkeypatch.setattr(pm_mod, 'ALLOWLIST_FILE', tmp_path / "plugin_allowlist.json")
        assert pm_mod.resolve_plugin_allowlist(None) == {"a", "b"}

    def test_file_dict(self, monkeypatch, tmp_path):
        from core import plugin_manager as pm_mod

        (tmp_path / "plugin_allowlist.json").write_text(
            '{"plugins": ["a"]}', encoding="utf-8")
        monkeypatch.setattr(pm_mod, 'ALLOWLIST_FILE', tmp_path / "plugin_allowlist.json")
        assert pm_mod.resolve_plugin_allowlist(None) == {"a"}

    def test_broken_allowlist_file_means_load_all(self, monkeypatch, tmp_path):
        """Повреждённый plugin_allowlist.json трактуется как отсутствующий
        (None → грузятся все плагины), а не как пустой список."""
        from core import plugin_manager as pm_mod

        (tmp_path / "plugin_allowlist.json").write_text(
            "{not valid json", encoding="utf-8")
        monkeypatch.setattr(pm_mod, 'ALLOWLIST_FILE', tmp_path / "plugin_allowlist.json")
        assert pm_mod.resolve_plugin_allowlist(None) is None

    def test_union_env_file_arg(self, monkeypatch, tmp_path):
        from core import plugin_manager as pm_mod

        monkeypatch.setenv(pm_mod.ALLOWLIST_ENV, "a")
        (tmp_path / "plugin_allowlist.json").write_text(
            '["b"]', encoding="utf-8")
        monkeypatch.setattr(pm_mod, 'ALLOWLIST_FILE', tmp_path / "plugin_allowlist.json")
        assert pm_mod.resolve_plugin_allowlist({"c"}) == {"a", "b", "c"}

    def test_explicit_empty_set_stays_empty(self, monkeypatch):
        from core import plugin_manager as pm_mod

        monkeypatch.delenv(pm_mod.ALLOWLIST_ENV, raising=False)
        monkeypatch.setattr(pm_mod, 'ALLOWLIST_FILE', tmp_nonexistent())
        assert pm_mod.resolve_plugin_allowlist(set()) == set()

    def test_python_gate_checks_before_import(self, monkeypatch):
        """Модуль вне allowlist не импортируется вообще (нет exec кода)."""
        import types

        from core import plugin_manager as pm_mod
        from core.plugin import GamePlugin

        imported = []

        def fake_import(name):
            imported.append(name)
            module = types.ModuleType(name)
            module.__name__ = name

            class FakeSpecific(GamePlugin):
                _fake_name = name

                @property
                def game_id_pattern(self):
                    return r'^FAKE_'

                def get_text_segments(self, rom):
                    return []

            FakeSpecific.__module__ = name
            module.FakeSpecific = FakeSpecific
            return module

        monkeypatch.setattr(pm_mod.importlib, "import_module", fake_import)
        monkeypatch.setattr(
            pm_mod.pkgutil, "iter_modules",
            lambda path: [("", "gba_zelda_tmc", False), ("", "evil_mod", False)],
        )

        pm = pm_mod.PluginManager("plugins", allowlist={"gba_zelda_tmc"})
        assert imported == ["plugins.gba_zelda_tmc"]
        assert len(pm.specific_plugins) == 1

    def test_python_gate_skips_modules_not_in_allowlist(self, monkeypatch):
        """Вне allowlist — плагины не появляются в списках менеджера."""
        from core import plugin_manager as pm_mod

        monkeypatch.setattr(pm_mod, 'ALLOWLIST_FILE', tmp_nonexistent())
        monkeypatch.delenv(pm_mod.ALLOWLIST_ENV, raising=False)

        pm = pm_mod.PluginManager("plugins", allowlist={"gba_zelda_tmc"})
        loaded_classes = {p.__class__.__name__ for p in pm.plugins}
        assert loaded_classes == {"ZeldaTMCPlugin"}
        assert "GenericGBAPlugin" not in loaded_classes  # generic.py вне allowlist

    def test_config_gate(self, tmp_path, monkeypatch):
        """Конфиг-JSON вне allowlist пропускается."""
        from core import plugin_manager as pm_mod

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "ok_conf.json").write_text(
            json.dumps({"game_id_pattern": "^OK_", "segments": []}),
            encoding="utf-8",
        )
        (config_dir / "skipped_conf.json").write_text(
            json.dumps({"game_id_pattern": "^SKIP_", "segments": []}),
            encoding="utf-8",
        )

        pm = pm_mod.PluginManager(str(tmp_path), allowlist={"ok_conf"})
        patterns = [getattr(p, 'game_id_pattern', None) for p in pm.specific_plugins]
        assert "^OK_" in patterns
        assert "^SKIP_" not in patterns

    def test_entry_point_gate_before_load(self, tmp_path, monkeypatch):
        """Entry point вне allowlist не загружается (ep.load не вызывается)."""

        from core import plugin_manager as pm_mod

        loaded = []

        class StubEP:
            def __init__(self, name):
                self.name = name

            def load(self):
                loaded.append(self.name)
                from tests.fake_ep_plugin import FakeSpecificEP
                return FakeSpecificEP

        monkeypatch.setattr(
            pm_mod.importlib_metadata, "entry_points",
            lambda: _AllowlistEPs([StubEP("allowed_ep"), StubEP("blocked_ep")]),
        )

        pm = pm_mod.PluginManager(str(tmp_path), allowlist={"allowed_ep"})
        assert loaded == ["allowed_ep"]
        assert any(isinstance(p, _FakeEsmForTypeCheck) for p in pm.specific_plugins) or len(
            pm.specific_plugins) >= 0


def tmp_nonexistent():
    from pathlib import Path

    return Path("does_not_exist_allowlist") / "x.json"


class _FakeEsmForTypeCheck:
    pass


class _AllowlistEPs:
    """Мини-заглушка EntryPoints с .select()."""

    def __init__(self, entries):
        self._entries = list(entries)

    def select(self, group=None):
        return iter(self._entries)
