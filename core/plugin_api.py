"""
API для создания плагинов GB2Text

Этот модуль предоставляет интерфейсы и утилиты для разработки плагинов:
- Расширенный базовый класс GamePlugin
- Хуки для жизненного цикла плагина
- API для работы с ROM и сегментами
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import os

logger = logging.getLogger('gb2text.plugin_api')


class PluginState(Enum):
    """Состояния плагина"""
    UNLOADED = "unloaded"       # Не загружен
    LOADING = "loading"         # Загружается
    LOADED = "loaded"           # Загружен и готов
    ACTIVE = "active"           # Активен и обрабатывает
    ERROR = "error"             # Ошибка
    DISABLED = "disabled"        # Отключен пользователем


class HookType(Enum):
    """Типы хуков"""
    # Жизненный цикл
    BEFORE_LOAD = "before_load"
    AFTER_LOAD = "after_load"
    BEFORE_UNLOAD = "before_unload"
    
    # Обработка ROM
    ROM_LOADED = "rom_loaded"
    ROM_BEFORE_SCAN = "rom_before_scan"
    ROM_AFTER_SCAN = "rom_after_scan"
    
    # Обработка сегментов
    SEGMENT_DETECTED = "segment_detected"
    SEGMENT_DECODE = "segment_decode"
    SEGMENT_ENCODE = "segment_encode"
    
    # Перевод
    TRANSLATION_SAVE = "translation_save"
    TRANSLATION_LOAD = "translation_load"
    
    # UI
    UI_UPDATE = "ui_update"
    MENU_BUILD = "menu_build"


@dataclass
class PluginInfo:
    """Информация о плагине"""
    name: str
    version: str
    author: str
    description: str
    supported_games: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config_file: Optional[str] = None
    priority: int = 0  # Чем больше, тем раньше вызывается


@dataclass
class HookContext:
    """Контекст выполнения хука"""
    plugin: 'GamePlugin'
    hook_type: HookType
    data: Dict[str, Any]
    result: Any = None
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получает значение из контекста"""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any):
        """Устанавливает значение в контексте"""
        self.data[key] = value


# Тип хука - функция, которая принимает HookContext
HookCallback = Callable[[HookContext], Optional[Any]]


class HookManager:
    """Менеджер хуков плагинов"""
    
    def __init__(self):
        self._hooks: Dict[HookType, List[Tuple[int, HookCallback]]] = {h: [] for h in HookType}
        
    def register(self, hook_type: HookType, callback: HookCallback, priority: int = 0):
        """Регистрирует хук"""
        self._hooks[hook_type].append((priority, callback))
        # Сортируем по приоритету (больший приоритет первым)
        self._hooks[hook_type].sort(key=lambda x: -x[0])
        
    def unregister(self, hook_type: HookType, callback: HookCallback):
        """Удаляет хук"""
        self._hooks[hook_type] = [(p, c) for p, c in self._hooks[hook_type] if c != callback]
        
    def trigger(self, hook_type: HookType, context: HookContext) -> Optional[Any]:
        """Вызывает все хуки определённого типа"""
        results = []
        for priority, callback in self._hooks[hook_type]:
            try:
                result = callback(context)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(f"Ошибка в хуке {hook_type.value}: {e}")
                
        return results if results else None


# Глобальный менеджер хуков
_global_hook_manager: Optional[HookManager] = None

def get_hook_manager() -> HookManager:
    """Возвращает глобальный экземпляр HookManager"""
    global _global_hook_manager
    if _global_hook_manager is None:
        _global_hook_manager = HookManager()
    return _global_hook_manager


class ROMContext:
    """Контекст ROM для плагинов"""
    
    def __init__(self, rom_data: bytes, header: Dict[str, Any], segments: List[Dict]):
        self.rom_data = rom_data
        self.header = header
        self.segments = segments
        self._custom_data: Dict[str, Any] = {}
        
    def get_segment(self, name: str) -> Optional[Dict]:
        """Получает сегмент по имени"""
        for seg in self.segments:
            if seg.get('name') == name:
                return seg
        return None
        
    def get_segment_data(self, name: str) -> Optional[bytes]:
        """Получает данные сегмента"""
        seg = self.get_segment(name)
        if seg:
            start = seg.get('start', 0)
            end = seg.get('end', len(self.rom_data))
            return self.rom_data[start:end]
        return None
        
    def set_custom_data(self, key: str, value: Any):
        """Устанавливает пользовательские данные"""
        self._custom_data[key] = value
        
    def get_custom_data(self, key: str, default: Any = None) -> Any:
        """Получает пользовательские данные"""
        return self._custom_data.get(key, default)


class ExtendedGamePlugin(ABC):
    """
    Расширенный базовый класс для плагинов
    
    Предоставляет:
    - Управление состоянием плагина
    - Систему хуков
    - API для работы с ROM
    - Конфигурацию плагина
    """
    
    def __init__(self):
        self._state = PluginState.UNLOADED
        self._config: Dict[str, Any] = {}
        self._hooks: HookManager = get_hook_manager()
        self._logger = logging.getLogger(f'gb2text.plugin.{self.__class__.__name__}')
        
    # === Информация о плагине ===
    
    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Возвращает информацию о плагине"""
        pass
        
    # === Состояние плагина ===
    
    @property
    def state(self) -> PluginState:
        """Текущее состояние плагина"""
        return self._state
        
    def _set_state(self, state: PluginState):
        """Устанавливает состояние (внутренний метод)"""
        old_state = self._state
        self._state = state
        self._logger.debug(f"Плагин {self.info.name}: {old_state.value} -> {state.value}")
        
    # === Жизненный цикл ===
    
    def on_load(self) -> bool:
        """
        Вызывается при загрузке плагина.
        Возвращает True при успехе.
        """
        self._set_state(PluginState.LOADING)
        try:
            # Вызываем хуки before_load
            context = HookContext(self, HookType.BEFORE_LOAD, {})
            self._hooks.trigger(HookType.BEFORE_LOAD, context)
            
            # Инициализация
            result = self.initialize()
            
            if result:
                self._set_state(PluginState.LOADED)
                self._logger.info(f"Плагин {self.info.name} загружен")
                
                # Хуки after_load
                context = HookContext(self, HookType.AFTER_LOAD, {})
                self._hooks.trigger(HookType.AFTER_LOAD, context)
                
            return result
            
        except Exception as e:
            self._logger.error(f"Ошибка загрузки плагина {self.info.name}: {e}")
            self._set_state(PluginState.ERROR)
            return False
            
    def on_unload(self):
        """Вызывается при выгрузке плагина"""
        try:
            context = HookContext(self, HookType.BEFORE_UNLOAD, {})
            self._hooks.trigger(HookType.BEFORE_UNLOAD, context)
            
            self.shutdown()
            
            self._set_state(PluginState.UNLOADED)
            self._logger.info(f"Плагин {self.info.name} выгружен")
            
        except Exception as e:
            self._logger.error(f"Ошибка выгрузки плагина {self.info.name}: {e}")
            
    def on_enable(self):
        """Включает плагин"""
        if self._state == PluginState.LOADED:
            self._set_state(PluginState.ACTIVE)
            self._logger.debug(f"Плагин {self.info.name} активирован")
            
    def on_disable(self):
        """Отключает плагин"""
        if self._state == PluginState.ACTIVE:
            self._set_state(PluginState.DISABLED)
            self._logger.debug(f"Плагин {self.info.name} деактивирован")
            
    # === Обязательные методы для реализации ===
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Инициализация плагина.
        Вернуть True при успехе.
        """
        pass
        
    @abstractmethod
    def shutdown(self):
        """Очистка при выгрузке"""
        pass
        
    # === Обработка ROM ===
    
    @abstractmethod
    def match_rom(self, header: Dict[str, Any]) -> bool:
        """
        Проверяет, подходит ли ROM для этого плагина.
        Вызывается автоматически при выборе плагина.
        """
        pass
        
    @abstractmethod
    def get_text_segments(self, rom: 'ROMContext') -> List[Dict]:
        """
        Возвращает список текстовых сегментов для ROM.
        
        Args:
            rom: Контекст ROM с данными и метаинформацией
            
        Returns:
            Список сегментов [{name, start, end, charmap, ...}, ...]
        """
        pass
        
    # === Опциональные методы ===
    
    def preprocess_rom(self, rom: 'ROMContext') -> 'ROMContext':
        """
        Предобработка ROM перед сканированием.
        Может модифицировать контекст.
        """
        return rom
        
    def postprocess_segments(self, segments: List[Dict], rom: 'ROMContext') -> List[Dict]:
        """
        Постобработка найденных сегментов.
        """
        return segments
        
    def decode_segment(self, data: bytes, charmap: Dict[int, str], segment_info: Dict) -> str:
        """
        Декодирование сегмента.
        Можно переопределить для кастомной логики.
        """
        result = []
        for byte in data:
            char = charmap.get(byte, f'[{byte:02X}]')
            result.append(char)
        return ''.join(result)
        
    def encode_segment(self, text: str, charmap: Dict[int, str], segment_info: Dict) -> bytes:
        """
        Кодирование сегмента.
        Можно переопределить для кастомной логики.
        """
        reverse_map = {v: k for k, v in charmap.items() if len(v) == 1}
        result = []
        for char in text:
            byte = reverse_map.get(char, 0x20)  # пробел как fallback
            result.append(byte)
        return bytes(result)
        
    # === Конфигурация ===
    
    def load_config(self, config_path: str = None) -> bool:
        """
        Загружает конфигурацию плагина.
        
        Args:
            config_path: Путь к файлу конфигурации. 
                        Если None, используется info.config_file
        """
        if config_path is None:
            config_path = self.info.config_file
            
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                self._logger.info(f"Конфигурация загружена: {config_path}")
                return True
            except Exception as e:
                self._logger.error(f"Ошибка загрузки конфигурации: {e}")
                
        return False
        
    def save_config(self, config_path: str = None):
        """Сохраняет конфигурацию плагина"""
        if config_path is None:
            config_path = self.info.config_file
            
        if config_path:
            try:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(self._config, f, indent=2, ensure_ascii=False)
                self._logger.info(f"Конфигурация сохранена: {config_path}")
            except Exception as e:
                self._logger.error(f"Ошибка сохранения конфигурации: {e}")
                
    def get_config(self, key: str, default: Any = None) -> Any:
        """Получает значение из конфигурации"""
        return self._config.get(key, default)
        
    def set_config(self, key: str, value: Any):
        """Устанавливает значение в конфигурации"""
        self._config[key] = value
        
    # === Регистрация хуков ===
    
    def register_hook(self, hook_type: HookType, callback: HookCallback, priority: int = 0):
        """Регистрирует хук для этого плагина"""
        self._hooks.register(hook_type, callback, priority)
        
    def unregister_hook(self, hook_type: HookType, callback: HookCallback):
        """Удаляет хук"""
        self._hooks.unregister(hook_type, callback)


# === Фабрика плагинов ===

class PluginFactory:
    """Фабрика для создания плагинов"""
    
    _registry: Dict[str, type] = {}
    
    @classmethod
    def register(cls, plugin_class: type, name: str = None):
        """Регистрирует класс плагина"""
        plugin_name = name or plugin_class.__name__
        cls._registry[plugin_name] = plugin_class
        logger.debug(f"Зарегистрирован плагин: {plugin_name}")
        
    @classmethod
    def create(cls, plugin_name: str) -> Optional[ExtendedGamePlugin]:
        """Создаёт экземпляр плагина по имени"""
        plugin_class = cls._registry.get(plugin_name)
        if plugin_class:
            return plugin_class()
        logger.warning(f"Плагин не найден: {plugin_name}")
        return None
        
    @classmethod
    def list_plugins(cls) -> List[str]:
        """Возвращает список зарегистрированных плагинов"""
        return list(cls._registry.keys())
        
    @classmethod
    def get_plugin_class(cls, plugin_name: str) -> Optional[type]:
        """Возвращает класс плагина"""
        return cls._registry.get(plugin_name)


# === Декоратор для регистрации плагинов ===

def register_plugin(name: str = None):
    """Декоратор для регистрации плагина в фабрике"""
    def decorator(plugin_class: type):
        PluginFactory.register(plugin_class, name)
        return plugin_class
    return decorator


# === Пример использования ===

def create_example_plugin():
    """Пример создания плагина с использованием API"""
    
    @register_plugin("example_game")
    class ExampleGamePlugin(ExtendedGamePlugin):
        
        @property
        def info(self) -> PluginInfo:
            return PluginInfo(
                name="Example Game Plugin",
                version="1.0.0",
                author="GB2Text",
                description="Пример плагина для демонстрации API",
                supported_games=["EXAMPLE", "SAMPLE"],
                priority=10
            )
        
        def initialize(self) -> bool:
            # Загрузка конфигурации
            self.load_config()
            
            # Регистрация хуков
            self.register_hook(HookType.ROM_LOADED, self.on_rom_loaded)
            
            self._logger.info("Example плагин инициализирован")
            return True
            
        def shutdown(self):
            self._logger.info("Example плагин завершает работу")
            
        def on_rom_loaded(self, context: HookContext):
            self._logger.debug(f"ROM загружен: {context.get('title')}")
            
        def match_rom(self, header: Dict[str, Any]) -> bool:
            title = header.get('title', '')
            return any(game in title.upper() for game in self.info.supported_games)
            
        def get_text_segments(self, rom: ROMContext) -> List[Dict]:
            return [
                {
                    'name': 'dialogue',
                    'start': 0x4000,
                    'end': 0x7FFF,
                    'charmap': self._get_charmap(),
                },
                {
                    'name': 'system',
                    'start': 0x8000,
                    'end': 0xBFFF,
                    'charmap': self._get_charmap(),
                }
            ]
            
        def _get_charmap(self) -> Dict[int, str]:
            return {
                0x20: ' ', 0x41: 'A', 0x42: 'B', 0x43: 'C',
                0x61: 'a', 0x62: 'b', 0x63: 'c',
                0xFF: '[END]'
            }
    
    return ExampleGamePlugin


# Создаём и регистрируем пример плагина
create_example_plugin()