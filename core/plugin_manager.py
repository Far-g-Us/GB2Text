"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.

Этот проект НЕ содержит и НЕ распространяет никакие ROM-файлы или
защищенные авторским правом материалы. Все ROM-файлы должны быть
законно приобретены пользователем самостоятельно.

Этот инструмент разработан исключительно для исследовательских целей,
обучения и реверс-инжиниринга в рамках, разрешенных законодательством.
"""

"""
Менеджер плагинов для динамической загрузки
"""

import importlib, pkgutil, os, json, re, logging, threading, sys
from pathlib import Path
from typing import List, Optional, Dict
from core.plugin import GamePlugin
from core.rom import GameBoyROM
from plugins.generic import GenericGBPlugin, GenericGBCPlugin, GenericGBAPlugin
from plugins.auto_detect import AutoDetectPlugin


class CancellationToken:
    """Класс для управления отменой операций"""

    def __init__(self):
        self._cancel_requested = False
        self._lock = threading.Lock()

    def cancel(self):
        """Запрашивает отмену операции"""
        with self._lock:
            self._cancel_requested = True

    def is_cancellation_requested(self) -> bool:
        """Проверяет, запрошена ли отмена"""
        with self._lock:
            return self._cancel_requested


class PluginManager:
    """Менеджер динамической загрузки плагинов"""

    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins = [
            GenericGBPlugin(),
            GenericGBCPlugin(),
            GenericGBAPlugin(),
            AutoDetectPlugin()
        ]
        self.plugins_dir = self._get_resource_path(plugins_dir)
        self.load_plugins()

    def _get_resource_path(self, relative_path: str) -> str:
        """Получает правильный путь к ресурсу для exe и обычного режима"""
        try:
            # PyInstaller создает временную папку и сохраняет путь в _MEIPASS
            base_path = sys._MEIPASS
        except AttributeError:
            # Обычный режим - используем текущую директорию
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def load_plugins(self) -> None:
        """Загружает все плагины из указанной директории"""
        # Определяем путь к директории с плагинами
        plugins_path = Path(self.plugins_dir)
        if not plugins_path.exists():
            os.makedirs(plugins_path, exist_ok=True)
            # Создаем пример конфигурации
            self._create_example_plugin(plugins_path / "example.json")

        # Загружаем Python-плагины
        self._load_python_plugins()

        # Загружаем конфигурационные плагины
        self._load_config_plugins()

    def _load_python_plugins(self) -> None:
        """Загружает Python-плагины из директории"""
        plugins_module_path = self.plugins_dir
        if os.path.exists(plugins_module_path):
            try:
                for _, module_name, _ in pkgutil.iter_modules([plugins_module_path]):
                    try:
                        module = importlib.import_module(f"plugins.{module_name}")
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
            except Exception as e:
                print(f"Ошибка доступа к директории плагинов: {str(e)}")

    def _load_config_plugins(self) -> None:
        """Загружает конфигурационные плагины из JSON-файлов"""
        logger = logging.getLogger('gb2text.plugin_manager')
        config_dir = Path(self.plugins_dir) / "config"

        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Создана директория для конфигураций: plugins/config")
            return

        loaded_configs = 0
        max_configs = 20  # Ограничение на количество конфигураций

        for json_file in config_dir.glob("*.json"):
            if loaded_configs >= max_configs:
                logger.warning(f"Достигнуто максимальное количество конфигураций ({max_configs}). Остальные пропущены.")
                break

            try:
                with open(json_file) as f:
                    config = json.load(f)

                # Проверяем структуру конфигурации
                if not self._is_valid_config(config):
                    logger.warning(f"Пропущен некорректный конфиг: {json_file.name}")
                    continue

                # Проверяем на дубликаты
                is_duplicate = False
                for plugin in self.plugins:
                    if hasattr(plugin, 'game_id_pattern') and plugin.game_id_pattern == config.get('game_id_pattern', ''):
                        logger.info(f"Пропущен дубликат конфигурации: {json_file.name}")
                        is_duplicate = True
                        break

                if not is_duplicate:
                    self.plugins.append(ConfigurablePlugin(config))
                    logger.info(f"Загружена конфигурация: {json_file.name}")
                    loaded_configs += 1
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации {json_file.name}: {str(e)}")

        logger.info(f"Загружено {loaded_configs} конфигураций")

    def _is_valid_config(self, config: dict) -> bool:
        """Проверяет, что конфигурация имеет правильную структуру"""
        if 'game_id_pattern' not in config:
            return False

        segments = config.get('segments', [])
        for seg in segments:
            if 'name' not in seg or 'start' not in seg or 'end' not in seg:
                return False

            # Проверяем, что адреса валидны
            start_valid = isinstance(seg['start'], (int, str)) and (
                    (isinstance(seg['start'], str) and re.match(r'^0x[0-9A-Fa-f]+$', seg['start']))
                    or isinstance(seg['start'], int)
            )
            end_valid = isinstance(seg['end'], (int, str)) and (
                    (isinstance(seg['end'], str) and re.match(r'^0x[0-9A-Fa-f]+$', seg['end']))
                    or isinstance(seg['end'], int)
            )

            if not (start_valid and end_valid):
                return False

        return True

    def _is_config_safe(self, config: dict) -> bool:
        """Проверяет, что конфигурация безопасна с юридической точки зрения"""
        # Разрешаем конфигурации, созданные через GUI
        if config.get('user_created', False):
            return True

        # Проверяем, что нет прямых упоминаний коммерческих игр
        game_id_pattern = config.get('game_id_pattern', '')
        if re.search(r'POKEMON|ZELDA|NINTENDO|GAMEBOY', game_id_pattern, re.IGNORECASE):
            return False

        # Проверяем сегменты
        for segment in config.get('segments', []):
            charmap = segment.get('charmap', {})
            # Проверяем, что таблица символов не слишком специфична
            if len(charmap) > 50 and not self._is_generic_charmap(charmap):
                return False

        return True

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

    def _is_generic_charmap(self, charmap: dict) -> bool:
        """Проверяет, является ли таблица символов общей"""
        # Проверяем, содержит ли таблица символов специфичные для игр элементы
        for value in charmap.values():
            if re.search(r'PK|M[Nn]|POKéMON|ZELDA', value, re.IGNORECASE):
                return False
        return True

    def get_plugin(self, game_id: str, system: str = None,
                   cancellation_token: Optional[CancellationToken] = None) -> Optional[GamePlugin]:
        """Находит подходящий плагин для игры с поддержкой отмены"""
        logger = logging.getLogger('gb2text.plugin_manager')
        logger.info(f"Поиск подходящего плагина для игры с ID: {game_id}, система: {system}")

        # Обновляем статус в GUI, если доступен
        if hasattr(self, 'update_status'):
            self.update_status(f"{self.i18n.t('plugin.searching')} {game_id}...", 10)

        # Сначала пытаемся найти специфичный плагин
        total_plugins = len(self.plugins)
        for i, plugin in enumerate(self.plugins):
            # Проверяем, запрошена ли отмена
            if cancellation_token and cancellation_token.is_cancellation_requested():
                logger.info("Операция отменена пользователем")
                return None

            # Обновляем прогресс
            progress = 10 + int(80 * i / total_plugins) if total_plugins > 0 else 10
            if hasattr(self, 'update_status'):
                self.update_status(f"{self.i18n.t('checking.plugin')} {plugin.__class__.__name__}...", progress)

            # Добавляем небольшую задержку для обновления интерфейса
            if hasattr(self, 'root') and i % 5 == 0:
                self.root.update_idletasks()

            try:
                if re.match(plugin.game_id_pattern, game_id):
                    logger.info(f"Найден подходящий плагин: {plugin.__class__.__name__}")
                    if hasattr(self, 'update_status'):
                        self.update_status(f"{self.i18n.t('plugin.found')} {plugin.__class__.__name__}", 95)
                    return plugin
            except re.error as e:
                logger.warning(f"Ошибка регулярного выражения в плагине {plugin.__class__.__name__}: {str(e)}")

        # Если не найден, возвращаем базовый плагин для системы
        if system == 'gba':
            logger.info("Используем GenericGBAPlugin по умолчанию")
            if hasattr(self, 'update_status'):
                self.update_status(self.i18n.t("using.default.gba"), 90)
            return GenericGBAPlugin()
        elif system == 'gbc':
            logger.info("Используем GenericGBCPlugin по умолчанию")
            if hasattr(self, 'update_status'):
                self.update_status(self.i18n.t("using.default.gbc"), 90)
            return GenericGBCPlugin()
        else:
            logger.info("Используем GenericGBPlugin по умолчанию")
            if hasattr(self, 'update_status'):
                self.update_status(self.i18n.t("using.default.gb"), 90)
            return GenericGBPlugin()


class ConfigurablePlugin(GamePlugin):
    """Плагин на основе конфигурационного файла"""

    def __init__(self, config: Dict):
        self.config = config

    @property
    def game_id_pattern(self) -> str:
        return self.config['game_id_pattern']

    def get_text_segments(self, rom: GameBoyROM) -> List[Dict]:
        logger = logging.getLogger('gb2text.plugin_manager')
        logger.info("Определение текстовых сегментов...")

        segments = []
        for seg in self.config['segments']:
            # Проверяем обязательные поля
            if 'start' not in seg or 'end' not in seg:
                logger.warning("Сегмент пропущен: отсутствуют обязательные поля start или end")
                continue

            # Безопасное преобразование start и end
            try:
                start_value = seg['start']
                if isinstance(start_value, str) and start_value.startswith("0x"):
                    start_addr = int(start_value, 16)
                else:
                    start_addr = int(start_value)

                end_value = seg['end']
                if isinstance(end_value, str) and end_value.startswith("0x"):
                    end_addr = int(end_value, 16)
                else:
                    end_addr = int(end_value)

                logger.debug(f"Преобразованы адреса: start=0x{start_addr:X}, end=0x{end_addr:X}")
            except (ValueError, TypeError) as e:
                logger.error(f"Пропущен сегмент с недопустимыми адресами: {e}")
                continue

            # Проверяем, что адреса в пределах ROM
            if start_addr >= len(rom.data) or end_addr > len(rom.data) or start_addr >= end_addr:
                logger.error(f"Пропущен сегмент с недопустимыми адресами: start=0x{start_addr:X}, end=0x{end_addr:X}, размер ROM={len(rom.data)}")
                continue

            # Автоматическое определение таблицы символов, если не предоставлена
            charmap = seg.get('charmap', {})
            if not charmap:
                logger.info("Таблица символов не предоставлена, пытаемся загрузить из locales или определить автоматически")
                # Пробуем загрузить из locales
                lang = seg.get('language', 'en')
                try:
                    from core.charset import load_charset
                    charmap = load_charset(lang)
                    if charmap:
                        logger.info(f"Загружена таблица символов из locales/{lang}")
                except (FileNotFoundError, ImportError):
                    # Fallback к автоопределению
                    try:
                        from core.scanner import auto_detect_charmap
                        charmap = auto_detect_charmap(rom.data, start_addr)
                        logger.info(f"Автоопределена таблица символов с {len(charmap)} символами")
                        logger.debug(f"Таблица символов: {charmap}")
                    except Exception as e:
                        logger.error(f"Ошибка автоопределения таблицы символов: {e}")
                        charmap = {}

            decoder = None
            if charmap:
                logger.info("Создание декодера с таблицей символов")
                from core.decoder import CharMapDecoder
                decoder = CharMapDecoder(charmap)

            compression = None
            if 'compression' in seg and seg['compression'] == 'gba_lz77':
                from core.gba_support import GBALZ77Handler
                compression = GBALZ77Handler()
                logger.info("Используется обработчик GBA LZ77 сжатия")
            elif 'compression' in seg and seg['compression'] == 'lz77':
                from core.decoder import LZ77Handler
                compression = LZ77Handler()
                logger.info("Используется стандартный LZ77 обработчик")

            segments.append({
                'name': seg['name'],
                'start': start_addr,
                'end': end_addr,
                'decoder': decoder,
                'compression': compression
            })
            logger.info(f"Сегмент добавлен: {seg['name']} (0x{start_addr:X} - 0x{end_addr:X})")

        if not segments:
            logger.warning("Не найдено ни одного валидного текстового сегмента")

        return segments

def get_safe_plugin_manager(plugins_dir: str = "plugins") -> PluginManager:
    """Безопасно создает менеджер плагинов с обработкой ошибок"""
    try:
        return PluginManager(plugins_dir)
    except Exception as e:
        logger = logging.getLogger('gb2text.plugin_manager')
        logger.error(f"Ошибка создания менеджера плагинов: {e}")
        # Возвращаем базовый менеджер плагинов без дополнительных плагинов
        manager = PluginManager.__new__(PluginManager)
        manager.plugins = [
            GenericGBPlugin(),
            GenericGBCPlugin(),
            GenericGBAPlugin(),
            AutoDetectPlugin()
        ]
        manager.plugins_dir = plugins_dir
        return manager