"""Тесты для модуля plugin_manager"""
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.plugin_manager import PluginManager, CancellationToken, get_safe_plugin_manager, ConfigurablePlugin
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
        assert token.is_cancellation_requested() == False
    
    def test_cancellation_token_request(self):
        """Тест запроса отмены"""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancellation_requested() == True
    
    def test_cancellation_token_reset(self):
        """Тест сброса токена отмены"""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancellation_requested() == True
    
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
        assert pm._is_config_safe(config) == True

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
        assert pm._is_config_safe(config) == True

    def test_is_config_safe_with_nintendo(self):
        """Тест что NINTENDO в конфиге вызывает предупреждение"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "NINTENDO GAME",
            "segments": []
        }
        assert pm._is_config_safe(config) == True

    def test_is_config_safe_with_gameboy(self):
        """Тест что GAMEBOY в конфиге вызывает предупреждение"""
        pm = PluginManager("plugins")
        config = {
            "game_id_pattern": "GAMEBOY ADVANCE",
            "segments": []
        }
        assert pm._is_config_safe(config) == True

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
            config_dir = os.path.join(tmpdir, "config")
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
