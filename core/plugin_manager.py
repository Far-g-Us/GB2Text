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

import importlib
import importlib.metadata as importlib_metadata
import json
import logging
import os
import pkgutil
import re
import sys
import threading
from pathlib import Path

from core.decoder import CompressionHandler
from core.plugin import GamePlugin
from core.rom import GameBoyROM
from plugins.auto_detect import AutoDetectPlugin
from plugins.generic import GenericGBAPlugin, GenericGBCPlugin, GenericGBPlugin

logger = logging.getLogger('gb2text.plugin_manager')

# Группа entry points для регистрации сторонних плагинов через setuptools:
# [project.entry-points."gb2text.plugins"]
# my_game_plugin = "my_package.plugins:MyGamePluginClass"
ENTRY_POINT_GROUP = "gb2text.plugins"

# Имя env-переменной для CSV-allowlist плагинов.
ALLOWLIST_ENV = "GB2TEXT_PLUGIN_ALLOWLIST"
# Файл allowlist рядом с настройками (dict {"plugins": [...]} или список).
ALLOWLIST_FILE = Path("settings") / "plugin_allowlist.json"

# Модули, которые грузятся СРАЗУ при создании менеджера, а не лениво:
# generic.py (fallback GB/GBC/GBA) и auto_detect.py (последний fallback)
# содержат generic-классы, которые должны быть доступны в любом случае.
# Все остальные Python-модули из plugins/ откладываются (lazy) до первого
# get_plugin()/обращения к .plugins.
EAGER_PYTHON_MODULES = frozenset({"generic", "auto_detect"})


def resolve_plugin_allowlist(allowlist: set[str] | None = None) -> set[str] | None:
    """Union allowlist из env, файла settings/plugin_allowlist.json и аргумента.

    Имена — это module_name файла .py в plugins/ (без расширения), stem
    конфиг-JSON (plugins/config/*.json) и name entry point'а группы
    gb2text.plugins. AutoDetect создаётся напрямую и не гейтится; все модули
    из plugins/ (включая generic.py) гейтятся, если allowlist задан.

    Если ни один источник не задан — возвращает None: грузятся все плагины
    (обратная совместимость). Пустой результат означает «не грузить ничего»,
    но только когда источник был задан явно.
    """
    names: set[str] = set()
    env_raw = os.environ.get(ALLOWLIST_ENV, "").strip()
    if env_raw:
        names.update(n.strip() for n in env_raw.split(",") if n.strip())
        if not names:
            logger.warning(
                "GB2TEXT_PLUGIN_ALLOWLIST содержит только разделители — "
                "ни один плагин не будет загружен"
            )

    have_file = False
    try:
        if ALLOWLIST_FILE.exists():
            with open(ALLOWLIST_FILE, encoding="utf-8") as f:
                data = json.load(f)
            have_file = True
            if isinstance(data, list):
                names.update(n for n in data if isinstance(n, str) and n.strip())
            elif isinstance(data, dict):
                names.update(
                    n for n in data.get("plugins", [])
                    if isinstance(n, str) and n.strip()
                )
            else:
                logger.warning(
                    "plugin_allowlist.json: ожидался список или {'plugins': [...]}"
                )
    except (OSError, ValueError) as e:
        logger.warning(f"Ошибка чтения plugin_allowlist.json: {e!s}")

    if allowlist is not None:
        names.update(allowlist)

    if not names and not env_raw and not have_file and allowlist is None:
        return None
    return names


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

    def __init__(self, plugins_dir: str = "plugins", allowlist: set[str] | None = None):
        # Generic плагины (fallback) — регистрируются при load_plugins() ниже
        self.generic_plugins = []
        # Специфичные плагины — проверяются ПЕРВЫМИ
        self.specific_plugins = []
        # Ленивая загрузка specific-плагинов: модули копятся в _lazy_pending,
        # импортируются при первом get_plugin()/обращении к .plugins.
        self._lazy_pending: list[str] = []
        self._lazy_loaded = False
        self._lazy_realizing = False
        self._plugin_lock = threading.RLock()
        # Защита от дубликатов при повторном load_plugins(): уже загруженные
        # конфиги (по resolved-пути) и entry point классы (по точному типу).
        self._loaded_config_paths: set = set()
        self._loaded_entry_point_classes: set = set()
        # AutoDetect — последний fallback
        self.auto_detect = AutoDetectPlugin()
        # Allowlist плагинов: None = грузим все, set = только перечисленные.
        # Union из env GB2TEXT_PLUGIN_ALLOWLIST + settings/plugin_allowlist.json.
        self.allowlist = resolve_plugin_allowlist(allowlist)

        self.plugins_dir = self._get_resource_path(plugins_dir)
        self.load_plugins()

    @property
    def plugins(self) -> list:
        """Возвращает объединённый список всех плагинов (specific + generic).

        Первое обращение к этому свойству реализует отложенную загрузку
        питоновских specific-плагинов — контракт «все плагины» сохраняется.
        """
        if not getattr(self, "_lazy_loaded", True):
            self._realize_lazy_plugins()
        return self.specific_plugins + self.generic_plugins

    @plugins.setter
    def plugins(self, value: list):
        """Устанавливает список плагинов (заменяет specific_plugins)."""
        self.specific_plugins = list(value)
        self.generic_plugins = []
        # Ручная установка снимает ленивое состояние: pending более не нужен.
        self._lazy_pending = []
        self._lazy_loaded = True

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

        # Внешние плагины через entry_points — грузим ПОСЛЕДНИМИ,
        # чтобы встроенные/локальные плагины выигрывали при равной специфичности.
        self._load_entry_point_plugins()

    def _load_python_plugins(self) -> None:
        """Планирует загрузку Python-плагинов из директории.

        Модули с generic-классами (EAGER_PYTHON_MODULES) импортируются и
        инстанцируются сразу; остальные (specific) откладываются: имена
        копятся в _lazy_pending для _realize_lazy_plugins(). и тот, и другой
        путь гейтится allowlist-ом строго ДО import_module — код
        specific-модуля вне allowlist не исполняется никогда (ни на старте,
        ни лениво). Встроенные generic/auto_detect — доверенный builtin-код,
        грузятся всегда (EAGER_PYTHON_MODULES).

        Повторный вызов load_plugins() после реализованной ленивой загрузки
        — no-op (не задваивает экземпляры). Планирование под RLock —
        конкурентный load_plugins+realize не теряет обновления pending.
        """
        if getattr(self, "_lazy_loaded", True):
            return
        lock = getattr(self, "_plugin_lock", None)
        if lock is None:
            lock = threading.RLock()
            self._plugin_lock = lock
        with lock:
            allowlist = self.allowlist
            pending = list(getattr(self, "_lazy_pending", []))
            if not os.path.exists(self.plugins_dir):
                self._lazy_pending = pending
                return
            try:
                for _, module_name, _ in pkgutil.iter_modules([self.plugins_dir]):
                    if allowlist is not None and module_name not in allowlist:
                        logger.debug("Плагин %s пропущен: не в allowlist", module_name)
                        continue
                    if module_name in EAGER_PYTHON_MODULES:
                        self._instantiate_from_module(module_name)
                        continue
                    if module_name not in pending:
                        pending.append(module_name)
            except Exception as e:
                logger.error(f"Ошибка доступа к директории плагинов: {e!s}")
            self._lazy_pending = pending

    def _instantiate_from_module(self, module_name: str) -> list:
        """Импортирует модуль plugins.<module_name> и инстанцирует плагины.

        Возвращает экземпляры specific-плагинов (для вставки в списки);
        generic-классы регистрируются в generic_plugins сразу (с дедупом по
        классу — защита от повторной ленивой реализации после отмены).
        Ошибки импорта/инстанцирования изолированы: проблемный модуль или
        класс пропускается.
        """
        try:
            module = importlib.import_module(f"plugins.{module_name}")
        except Exception as e:
            logger.error(f"Ошибка загрузки модуля {module_name}: {e!s}")
            return []
        instances: list = []
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if (
                    isinstance(attribute, type) and
                    getattr(attribute, '__module__', None) == module.__name__ and
                    issubclass(attribute, GamePlugin) and
                    attribute != GamePlugin
            ):
                try:
                    plugin_instance = attribute()
                except Exception as e:
                    logger.error(
                        f"Ошибка инстанцирования плагина "
                        f"{attribute.__name__} из {module_name}: {e!s}")
                    continue
                # Определяем, является ли плагин generic или specific
                if self._is_generic_plugin(attribute):
                    # Дедуп по ТОЧНОМУ классу: подклассы GenericGBPlugin
                    # (GBC/GBA) не должны вытеснять родительский класс из списка.
                    if not any(type(p) is attribute
                               for p in self.generic_plugins):
                        self.generic_plugins.append(plugin_instance)
                else:
                    instances.append(plugin_instance)
                logger.info(f"Загружен плагин: {attribute.__name__}")
        return instances

    def _realize_lazy_plugins(
            self, cancellation_token: CancellationToken | None = None) -> None:
        """Импортирует отложенные specific-модули (ленивая загрузка).

        Экземпляры вставляются В НАЧАЛО specific_plugins (specific_plugins[:0])
        — питоновские плагины идут до config/entry-point и сохраняют порядок
        планирования и приоритет «первый-в-списке» при равной специфичности.

        Потокобезопасен через RLock: повторный вызов из любого потока
        оказывается no-op. Реентрантный вызов (инициализатор плагина
        callback'ом тянет менеджер) тоже no-op благодаря флагу
        _lazy_realizing — внешняя реализация доводит дело до конца,
        дубли specific-экземпляров не создаются. При отмене
        (cancellation_token) pending-состояние восстанавливается целиком —
        частично реализованные экземпляры не вставляются, повторная
        попытка не создаёт дублей.
        """
        if getattr(self, "_lazy_loaded", True):
            return
        lock = getattr(self, "_plugin_lock", None)
        if lock is None:
            lock = threading.RLock()
            self._plugin_lock = lock
        with lock:
            if self._lazy_loaded:
                return
            if getattr(self, "_lazy_realizing", False):
                return
            self._lazy_realizing = True
            try:
                pending = list(self._lazy_pending)
                if not pending:
                    self._lazy_pending = []
                    self._lazy_loaded = True
                    return
                if cancellation_token and cancellation_token.is_cancellation_requested():
                    logger.info("Ленивая загрузка плагинов отменена")
                    return
                realized: list = []
                for module_name in pending:
                    if cancellation_token and cancellation_token.is_cancellation_requested():
                        logger.info("Ленивая загрузка плагинов отменена")
                        return
                    # Повторный gate до import: защита от подмены allowlist в рантайме.
                    if self.allowlist is not None and module_name not in self.allowlist:
                        continue
                    realized.extend(self._instantiate_from_module(module_name))
                self._drop_shadowed_configs(realized)
                self.specific_plugins[0:0] = realized
                self._lazy_pending = []
                self._lazy_loaded = True
            finally:
                self._lazy_realizing = False

    def _drop_shadowed_configs(self, realized: list) -> None:
        """Убирает JSON-конфиги, затенённые реализованными python-плагинами.

        Восстанавливает pre-lazy поведение: раньше python-specific грузились
        первыми и дедуп _load_config_plugins видел их паттерны, отклоняя
        конфиг-дубликат. Теперь дедуп при загрузке конфигов работает на
        неполном списке (pending ещё не реализован), поэтому дубликат
        убирается здесь — python-specific выигрывает, как и раньше.
        """
        patterns = {
            getattr(p, "game_id_pattern", None) for p in realized
        } - {None}
        if not patterns:
            return
        kept = []
        for p in self.specific_plugins:
            if (isinstance(p, ConfigurablePlugin)
                    and getattr(p, "game_id_pattern", None) in patterns
                    and not p.config.get("rom_signature")):
                # Только бесссигнатурные: сигнатурный конфиг (ROM-хак) pre-lazy
                # сохранялся рядом с python-плагином как легитимный вариант.
                logger.info(
                    "Конфиг %s затенён python-плагином %s — удалён",
                    getattr(p, "config_path", "?"),
                    getattr(p, "game_id_pattern", "?"))
                continue
            kept.append(p)
        if len(kept) != len(self.specific_plugins):
            self.specific_plugins[:] = kept

    def _is_generic_plugin(self, plugin_class) -> bool:
        """Проверяет, является ли плагин generic (fallback)"""
        generic_names = ['GenericGBPlugin', 'GenericGBCPlugin', 'GenericGBAPlugin', 'AutoDetectPlugin']
        return plugin_class.__name__ in generic_names

    def _load_config_plugins(self) -> None:
        """Загружает конфигурационные плагины из JSON-файлов"""
        config_dir = Path(self.plugins_dir) / "config"

        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Создана директория для конфигураций: plugins/config")
            return

        loaded_configs = 0
        max_configs = 20  # Ограничение на количество конфигураций

        for json_file in config_dir.glob("*.json"):
            # Пропускаем шаблоны и скрытые файлы
            if json_file.name.startswith('_') or json_file.name.startswith('.'):
                continue
            if self.allowlist is not None and json_file.stem not in self.allowlist:
                logger.debug("Конфигурация %s пропущена: не в allowlist", json_file.name)
                continue
            resolved = json_file.resolve()
            if resolved in self._loaded_config_paths:
                logger.debug("Конфигурация %s уже загружена, пропуск", json_file.name)
                continue
            if loaded_configs >= max_configs:
                logger.warning(f"Достигнуто максимальное количество конфигураций ({max_configs}). Остальные пропущены.")
                break

            try:
                with open(json_file, encoding='utf-8') as f:
                    config = json.load(f)

                # Проверяем структуру конфигурации
                if not self._is_valid_config(config):
                    logger.warning(f"Пропущен некорректный конфиг: {json_file.name}")
                    continue

                # Проверяем на дубликаты
                is_duplicate = False
                config_pattern = config.get('game_id_pattern', '')
                has_signature = bool(config.get('rom_signature'))
                same_pattern = [
                    p for p in (self.specific_plugins + self.generic_plugins)
                    if getattr(p, 'game_id_pattern', None) == config_pattern
                ]
                if has_signature:
                    # Конфиг с сигнатурой — легитимный вариант этой же игры
                    # (ROM-хак с тем же game_code). НЕ дубликат.
                    if any(isinstance(p, ConfigurablePlugin) and p.config.get('rom_signature')
                           for p in same_pattern):
                        logger.warning(
                            f"Конфигурация {json_file.name}: несколько плагинов с "
                            f"game_id_pattern='{config_pattern}' — приоритет по порядку загрузки")
                else:
                    # Сигнатурные плагины (ROM-хаки) не считаются дубликатами
                    # для обычного конфига той же игры — порядок загрузки не должен
                    # решать, переживёт vanilla-конфиг или нет.
                    is_duplicate = any(
                        not (isinstance(p, ConfigurablePlugin)
                             and p.config.get('rom_signature'))
                        for p in same_pattern
                    )
                    if is_duplicate:
                        logger.info(f"Пропущен дубликат конфигурации: {json_file.name}")

                if not is_duplicate:
                    self.specific_plugins.append(ConfigurablePlugin(config))
                    self._loaded_config_paths.add(resolved)
                    logger.info(f"Загружена конфигурация: {json_file.name}")
                    loaded_configs += 1
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации {json_file.name}: {e!s}")

        logger.info(f"Загружено {loaded_configs} конфигураций")

    def _load_entry_point_plugins(self) -> int:
        """Загружает плагины, зарегистрированные через setuptools entry_points.

        Позволяет сторонним пакетам подключать плагины простой установкой в
        окружение (pip install my-game-plugin), без копирования файлов в
        plugins/. В exe-сборке PyInstaller entry_points недоступны — метод
        корректно возвращает 0.

        Returns:
            Количество загруженных плагинов.
        """
        try:
            eps = importlib_metadata.entry_points()
        except Exception as e:
            logger.warning(f"Не удалось получить entry_points: {e}")
            return 0

        if hasattr(eps, 'select'):
            # Python < 3.12: EntryPoints.select(group=...)
            group_eps = eps.select(group=ENTRY_POINT_GROUP)
        else:
            # Python >= 3.12: dict-like {group: EntryPoints}
            try:
                group_eps = eps.get(ENTRY_POINT_GROUP, ())
            except AttributeError:
                group_eps = ()

        loaded = 0
        for ep in group_eps:
            if self.allowlist is not None and ep.name not in self.allowlist:
                logger.debug("Entry point %s пропущен: не в allowlist", ep.name)
                continue
            try:
                obj = ep.load()
                cls = obj if isinstance(obj, type) else type(obj)
                if issubclass(cls, GamePlugin):
                    if cls in self._loaded_entry_point_classes:
                        logger.debug("Entry point %s уже загружен, пропуск", ep.name)
                        continue
                    instance = cls() if isinstance(obj, type) else obj
                    if self._is_generic_plugin(cls):
                        self.generic_plugins.append(instance)
                    else:
                        self.specific_plugins.append(instance)
                    self._loaded_entry_point_classes.add(cls)
                    logger.info(f"Загружен entry point плагин: {ep.name} -> {cls.__name__}")
                    loaded += 1
                else:
                    logger.warning(f"Entry point {ep.name} не является GamePlugin, пропущен")
            except Exception as e:
                logger.error(f"Ошибка загрузки entry point плагина {ep.name}: {e}")

        if loaded:
            logger.info(f"Загружено {loaded} плагинов из entry points")
        return loaded

    def _is_valid_config(self, config: dict) -> bool:
        """Проверяет, что конфигурация имеет правильную структуру"""
        if 'game_id_pattern' not in config:
            return False

        if not isinstance(config.get('segments'), list):
            # Без segments плагин не сможет извлечь текст (KeyError в
            # get_text_segments) — такой конфиг бесполезен.
            return False

        segments = config['segments']
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

        # rom_signature: необязательное поле для хак-вариантов (ROM с тем же game_id)
        signature = config.get('rom_signature')
        if signature is not None:
            entries = signature if isinstance(signature, list) else [signature]
            if not entries or not all(isinstance(e, dict) for e in entries):
                return False
            known_fields = {'title_pattern', 'min_size', 'max_size'}
            for entry in entries:
                if not known_fields.intersection(entry):
                    return False
                if not set(entry).issubset(known_fields):
                    return False
                if 'title_pattern' in entry:
                    try:
                        re.compile(entry['title_pattern'])
                    except (re.error, TypeError):
                        return False
                for field in ('min_size', 'max_size'):
                    if field in entry and (not isinstance(entry[field], int)
                                           or entry[field] < 0):
                        return False
                if ('min_size' in entry and 'max_size' in entry
                        and entry['min_size'] > entry['max_size']):
                    return False

        return True

    def _is_config_safe(self, config: dict) -> bool:
        """Проверяет, что конфигурация безопасна с юридической точки зрения"""

        # Разрешаем конфигурации, созданные через GUI
        if config.get('user_created', False):
            return True

        # Проверяем сегменты на наличие специфичных таблиц символов
        # Большие (>50 символов) нестандартные charmap могут указывать на
        # коммерческие игры - выдаём предупреждение, но не блокируем
        for segment in config.get('segments', []):
            charmap = segment.get('charmap', {})
            if len(charmap) > 50 and not self._is_generic_charmap(charmap):
                logger.warning(
                    f"Конфиг содержит специфичную таблицу символов ({len(charmap)} символов). "
                    f"Это может указывать на специфичную игру. "
                    f"Вы используете этот инструмент на свой страх и риск."
                )
                return True

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
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(example, f, indent=2)

    def _is_generic_charmap(self, charmap: dict) -> bool:
        """Проверяет, является ли таблица символов общей"""
        # Проверяем, содержит ли таблица символов специфичные для игр элементы
        for value in charmap.values():
            if re.search(r'PK|M[Nn]|POKéMON|ZELDA', value, re.IGNORECASE):
                return False
        return True

    @staticmethod
    def _plugin_gate_level(plugin: GamePlugin) -> int:
        """Специфичность плагина: 0 = без сигнатуры, 1 = с сигнатурой-гейтом.

        Плагин «с гейтом» претендует только на ROM, реально подходящий под его
        сигнатуру (validate_rom возвращает False для остальных). Такой плагин
        выигрывает выбор у плагина без гейта при совпадении game_id_pattern —
        это позволяет хак-варианту игры (тот же game_code) перебить ванильный.
        """
        if isinstance(plugin, ConfigurablePlugin):
            return 1 if plugin.config.get('rom_signature') else 0
        return 1 if type(plugin).validate_rom is not GamePlugin.validate_rom else 0

    def get_plugin(self, game_id: str, system: str | None = None,
                   cancellation_token: CancellationToken | None = None,
                   rom: GameBoyROM | None = None) -> GamePlugin | None:
        """Находит подходящий плагин для игры с поддержкой отмены.

        rom is None — обратная совместимость: первый regex-match по game_id,
        сигнатуры не применяются.
        rom передан — кандидат должен совпасть по regex И (если у плагина есть
        гейт) вернуть True из validate_rom(rom); из кандидатов выбирается
        более специфичный (с гейтом), при равенстве — первый по порядку.
        """
        logger.info(f"Поиск подходящего плагина для игры с ID: {game_id}, система: {system}")

        # Ленивая загрузка отложенных specific-плагинов (только при первом вызове).
        self._realize_lazy_plugins(cancellation_token)

        all_plugins = self.specific_plugins + self.generic_plugins

        if rom is None:
            # Режим обратной совместимости: первый regex-match
            for plugin in all_plugins:
                if cancellation_token and cancellation_token.is_cancellation_requested():
                    logger.info("Операция отменена пользователем")
                    return None

                try:
                    if re.match(plugin.game_id_pattern, game_id):
                        logger.info(f"Найден плагин: {plugin.__class__.__name__}")
                        return plugin
                except re.error as e:
                    logger.warning(f"Ошибка regex в плагине {plugin.__class__.__name__}: {e!s}")

            logger.info("Используем AutoDetectPlugin по умолчанию")
            return self.auto_detect

        # Режим с ROM: селекция по (specificity, порядок загрузки)
        best: GamePlugin | None = None
        best_level = -1
        for plugin in all_plugins:
            if cancellation_token and cancellation_token.is_cancellation_requested():
                logger.info("Операция отменена пользователем")
                return None

            try:
                if not re.match(plugin.game_id_pattern, game_id):
                    continue
            except re.error as e:
                logger.warning(f"Ошибка regex в плагине {plugin.__class__.__name__}: {e!s}")
                continue

            level = self._plugin_gate_level(plugin)
            if level:
                try:
                    if not plugin.validate_rom(rom):
                        logger.debug(f"Плагин {plugin.__class__.__name__} отклонил ROM по сигнатуре")
                        continue
                except Exception as e:
                    logger.warning(f"Ошибка validate_rom плагина {plugin.__class__.__name__}: {e!s}")
                    continue

            if level > best_level:
                best = plugin
                best_level = level

        if best is not None:
            logger.info(f"Найден специфичный плагин: {best.__class__.__name__}")
            return best

        # Последний fallback — AutoDetect
        logger.info("Используем AutoDetectPlugin по умолчанию")
        return self.auto_detect


class ConfigurablePlugin(GamePlugin):
    """Плагин на основе конфигурационного файла"""

    def __init__(self, config: dict):
        self.config = config

    @property
    def game_id_pattern(self) -> str:
        return self.config['game_id_pattern']

    def validate_rom(self, rom: GameBoyROM) -> bool:
        """Проверяет ROM по rom_signature конфигурации (если задана).

        Без сигнатуры конфиг претендует на любой ROM с подходящим game_id —
        поведение как раньше. С сигнатурой плагин становится «гейтом» и
        принимает только ROM, подходящий хотя бы под одну сигнатуру из списка.
        """
        sig = self.config.get('rom_signature')
        if not sig:
            return True
        entries = sig if isinstance(sig, list) else [sig]
        for entry in entries:
            if self._signature_matches(entry, rom):
                return True
        return False

    @staticmethod
    def _normalize_charmap(charmap: dict) -> dict[int, str]:
        """Нормализует charmap из JSON-конфига в dict[int, str] для CharMapDecoder.

        Ключи: '0x20' или диапазоны '0x41-0x5A' (либо уже int). Значения:
        'A' (литерал), 'A-Z'/'0-9' (диапазоны символов), 'ASCII printable'
        (байт → chr(byte)) или 'a,b' (явный список).
        """
        if charmap and all(isinstance(k, int) for k in charmap):
            # Уже нормализованный (dict[int, str]); сохраняем как есть.
            return dict(charmap)

        expanded: dict[int, str] = {}
        for key, value in charmap.items():
            m = re.fullmatch(r'0x([0-9A-Fa-f]{1,2})(?:-0x([0-9A-Fa-f]{1,2}))?', str(key))
            if not m:
                raise ValueError(f"Некорректный ключ charmap: {key!r}")
            start_b = int(m.group(1), 16)
            end_b = int(m.group(2), 16) if m.group(2) else start_b
            if end_b < start_b:
                raise ValueError(f"Инвертированный диапазон charmap: {key!r}")

            value_str = str(value)
            if value_str == "ASCII printable":
                chars = [chr(b) for b in range(start_b, end_b + 1)]
            else:
                vm = re.fullmatch(r'([ -~])-([ -~])', value_str)
                if vm and ord(vm.group(2)) >= ord(vm.group(1)):
                    chars = [chr(ord(vm.group(1)) + i)
                             for i in range(ord(vm.group(2)) - ord(vm.group(1)) + 1)]
                    if len(chars) != end_b - start_b + 1:
                        raise ValueError(
                            f"Длина значения {value_str!r} не совпадает с диапазоном {key!r}")
                elif "," in value_str:
                    chars = value_str.split(",")
                    if len(chars) != end_b - start_b + 1:
                        raise ValueError(
                            f"Количество значений не совпадает с диапазоном {key!r}")
                else:
                    chars = [value_str] * (end_b - start_b + 1)

            for byte, char in zip(range(start_b, end_b + 1), chars, strict=True):
                expanded[byte] = char
        return expanded

    @staticmethod
    def _signature_matches(entry: dict, rom: GameBoyROM) -> bool:
        """Проверяет одну сигнатуру: AND всех заданных полей.

        title_pattern матчится через re.match (префикс) — чтобы хак не
        перехватывал чужие ROM, используй ЯВНЫЕ якоря, например
        "^POKEMON HACK$".
        """
        if 'title_pattern' in entry:
            try:
                if not re.match(entry['title_pattern'], rom.header.get('title', '')):
                    return False
            except re.error:
                return False
        if 'min_size' in entry and len(rom.data) < entry['min_size']:
            return False
        if 'max_size' in entry and len(rom.data) > entry['max_size']:
            return False
        return True

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
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
                lang = seg.get('lang')
                try:
                    from core.charset import load_charset
                    charmap = load_charset(lang) if lang else {}
                    if charmap:
                        logger.info(f"Загружена таблица символов из locales/{lang}")
                except (FileNotFoundError, ImportError):
                    # Fallback к автоопределению
                    try:
                        from core.scanner import auto_detect_charmap
                        charmap = auto_detect_charmap(rom.data, start_addr,
                                                      prefer_lang=lang)
                        logger.info(f"Автоопределена таблица символов с {len(charmap)} символами")
                        logger.debug(f"Таблица символов: {charmap}")
                    except Exception as e:
                        logger.error(f"Ошибка автоопределения таблицы символов: {e}")
                        charmap = {}

            decoder = None
            if charmap:
                logger.info("Создание декодера с таблицей символов")
                try:
                    from core.decoder import CharMapDecoder
                    decoder = CharMapDecoder(self._normalize_charmap(charmap))
                except ValueError as e:
                    logger.error(
                        f"Некорректная таблица символов сегмента {seg['name']}: {e}"
                    )
                    decoder = None

            compression = None
            if seg.get('compression'):
                compression_type = seg['compression']
                if isinstance(compression_type, str):
                    from core.compression import get_compression_handler
                    compression = get_compression_handler(compression_type)
                    if compression:
                        logger.info(f"Используется обработчик сжатия: {compression_type}")
                    else:
                        logger.warning(f"Неизвестный тип сжатия: {compression_type}")
                elif isinstance(compression_type, CompressionHandler):
                    compression = compression_type

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

def get_safe_plugin_manager(plugins_dir: str = "plugins",
                            allowlist: set[str] | None = None) -> PluginManager:
    """Безопасно создает менеджер плагинов с обработкой ошибок"""
    try:
        return PluginManager(plugins_dir, allowlist=allowlist)
    except Exception as e:
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
        manager.auto_detect = AutoDetectPlugin()
        manager.allowlist = resolve_plugin_allowlist(allowlist)
        return manager
