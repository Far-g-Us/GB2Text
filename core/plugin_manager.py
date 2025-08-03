"""
Менеджер плагинов для динамической загрузки
"""
import importlib
import pkgutil
import os
from pathlib import Path

import json
import re
from pathlib import Path
from typing import List, Optional, Dict
from .plugin import GamePlugin
from core.rom import GameBoyROM
from .decoder import CharMapDecoder, LZ77Handler


class PluginManager:
    """Менеджер плагинов"""

    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins = []
        self.plugins_dir = plugins_dir
        self.load_plugins()

    def load_plugins(self) -> None:
        """Загружает все плагины из указанной директории"""
        # Загружаем встроенные плагины
        self._load_builtin_plugins()

        # Загружаем конфигурационные плагины
        self._load_config_plugins()

    def _load_builtin_plugins(self) -> None:
        """Загружает встроенные плагины"""
        try:
            from plugins.pokemon import PokemonPlugin
            self.plugins.append(PokemonPlugin())
        except ImportError:
            pass

        try:
            from plugins.zelda import ZeldaPlugin
            self.plugins.append(ZeldaPlugin())
        except ImportError:
            pass

    def _load_config_plugins(self) -> None:
        """Загружает конфигурационные плагины из JSON-файлов"""
        config_dir = Path(self.plugins_dir) / "config"
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            return

        for json_file in config_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    config = json.load(f)
                self.plugins.append(ConfigurablePlugin(config))
            except Exception:
                pass

    def get_plugin(self, game_id: str) -> Optional[GamePlugin]:
        """Находит подходящий плагин для игры"""
        for plugin in self.plugins:
            if re.match(plugin.game_id_pattern, game_id):
                return plugin
        return None


class ConfigurablePlugin(GamePlugin):
    """Плагин на основе конфигурационного файла"""

    def __init__(self, config: Dict):
        self.config = config

    @property
    def game_id_pattern(self) -> str:
        return self.config['game_id_pattern']

    def get_text_segments(self, rom: GameBoyROM) -> List[Dict]:
        segments = []
        for seg in self.config['segments']:
            decoder = CharMapDecoder(seg['charmap'])
            compression = None
            if 'compression' in seg and seg['compression'] == 'lz77':
                compression = LZ77Handler()

            segments.append({
                'name': seg['name'],
                'start': int(seg['start'], 16),
                'end': int(seg['end'], 16),
                'decoder': decoder,
                'compression': compression
            })
        return segments
from .plugin import GamePlugin


class PluginManager:
    """Менеджер динамической загрузки плагинов"""

    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins = []
        self.plugins_dir = plugins_dir
        self.load_plugins()

    def load_plugins(self) -> None:
        """Загружает все плагины из указанной директории"""
        # Определяем путь к директории с плагинами
        plugins_path = Path(self.plugins_dir)
        if not plugins_path.exists():
            os.makedirs(plugins_path)
            # Создаем пример конфигурации
            self._create_example_plugin(plugins_path / "example.json")

        # Загружаем Python-плагины
        self._load_python_plugins()

        # Загружаем конфигурационные плагины
        self._load_config_plugins()

    def _load_python_plugins(self) -> None:
        """Загружает Python-плагины из директории"""
        for _, module_name, _ in pkgutil.iter_modules([self.plugins_dir]):
            try:
                module = importlib.import_module(f"{self.plugins_dir}.{module_name}")
                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if (
                            isinstance(attribute, type) and
                            issubclass(attribute, GamePlugin) and
                            attribute != GamePlugin
                    ):
                        self.plugins.append(attribute())
                        print(f"Загружен плагин: {attribute.__name__}")
            except Exception as e:
                print(f"Ошибка загрузки модуля {module_name}: {str(e)}")

    def _load_config_plugins(self) -> None:
        """Загружает конфигурационные плагины из JSON-файлов"""
        config_dir = Path(self.plugins_dir) / "config"
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            return

        for json_file in config_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    config = json.load(f)
                self.plugins.append(ConfigurablePlugin(config))
                print(f"Загружена конфигурация: {json_file.name}")
            except Exception as e:
                print(f"Ошибка загрузки конфигурации {json_file.name}: {str(e)}")

    def _create_example_plugin(self, path: Path) -> None:
        """Создает пример конфигурации плагина"""
        example = {
            "game_id_pattern": "^EXAMPLE_.*$",
            "segments": [
                {
                    "name": "main_text",
                    "start": "0x4000",
                    "end": "0x5000",
                    "charmap": {
                        "0x80": "A", "0x81": "B", "0x82": "C",
                        "0xF0": " ", "0x00": "[END]"
                    }
                }
            ]
        }
        with open(path, 'w') as f:
            json.dump(example, f, indent=2)

    def get_plugin(self, game_id: str) -> Optional[GamePlugin]:
        """Находит подходящий плагин для игры"""
        for plugin in self.plugins:
            if re.match(plugin.game_id_pattern, game_id):
                return plugin
        return None