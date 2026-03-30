"""
Тесты для модуля plugin_api
API для создания плагинов
"""

import unittest
from core.plugin_api import (
    PluginState, HookType, PluginInfo, HookContext,
    ExtendedGamePlugin, PluginFactory, register_plugin,
    HookManager, get_hook_manager
)


class TestHookType(unittest.TestCase):
    """Тесты для типа HookType"""
    
    def test_hook_types_exist(self):
        """Тест существования типов хуков"""
        self.assertIsNotNone(HookType.BEFORE_LOAD)
        self.assertIsNotNone(HookType.ROM_LOADED)
        self.assertIsNotNone(HookType.ROM_BEFORE_SCAN)
        self.assertIsNotNone(HookType.ROM_AFTER_SCAN)
        self.assertIsNotNone(HookType.SEGMENT_DETECTED)
        self.assertIsNotNone(HookType.SEGMENT_DECODE)
        self.assertIsNotNone(HookType.SEGMENT_ENCODE)
        self.assertIsNotNone(HookType.TRANSLATION_SAVE)
        self.assertIsNotNone(HookType.TRANSLATION_LOAD)
        
    def test_hook_type_values(self):
        """Тест значений типов хуков"""
        self.assertEqual(HookType.BEFORE_LOAD.value, "before_load")
        self.assertEqual(HookType.ROM_LOADED.value, "rom_loaded")
        self.assertEqual(HookType.SEGMENT_DECODE.value, "segment_decode")
        self.assertEqual(HookType.TRANSLATION_SAVE.value, "translation_save")


class TestPluginState(unittest.TestCase):
    """Тесты для состояний плагина"""
    
    def test_states_exist(self):
        """Тест существования состояний"""
        self.assertIsNotNone(PluginState.UNLOADED)
        self.assertIsNotNone(PluginState.LOADING)
        self.assertIsNotNone(PluginState.LOADED)
        self.assertIsNotNone(PluginState.ACTIVE)
        self.assertIsNotNone(PluginState.ERROR)
        self.assertIsNotNone(PluginState.DISABLED)
        
    def test_state_values(self):
        """Тест значений состояний"""
        self.assertEqual(PluginState.UNLOADED.value, "unloaded")
        self.assertEqual(PluginState.LOADING.value, "loading")
        self.assertEqual(PluginState.LOADED.value, "loaded")
        self.assertEqual(PluginState.ACTIVE.value, "active")


class TestPluginInfo(unittest.TestCase):
    """Тесты для класса PluginInfo"""
    
    def test_creation(self):
        """Тест создания информации о плагине"""
        info = PluginInfo(
            name="Test Plugin",
            version="1.0.0",
            author="Test",
            description="Test plugin",
            supported_games=["GAME1", "GAME2"],
            dependencies=["dep1"],
            priority=10
        )
        
        self.assertEqual(info.name, "Test Plugin")
        self.assertEqual(info.version, "1.0.0")
        self.assertEqual(info.author, "Test")
        self.assertEqual(len(info.supported_games), 2)
        self.assertEqual(len(info.dependencies), 1)
        self.assertEqual(info.priority, 10)
        
    def test_default_values(self):
        """Тест значений по умолчанию"""
        info = PluginInfo(
            name="Test",
            version="1.0",
            author="Test",
            description="Test"
        )
        
        self.assertEqual(len(info.supported_games), 0)
        self.assertEqual(len(info.dependencies), 0)
        self.assertEqual(info.config_file, None)
        self.assertEqual(info.priority, 0)


class TestHookContext(unittest.TestCase):
    """Тесты для класса HookContext"""
    
    def test_creation(self):
        """Тест создания контекста"""
        mock_plugin = None  # Placeholder
        context = HookContext(
            plugin=mock_plugin,
            hook_type=HookType.ROM_LOADED,
            data={'title': 'Test Game', 'size': 1024}
        )
        
        self.assertEqual(context.hook_type, HookType.ROM_LOADED)
        self.assertEqual(context.get('title'), 'Test Game')
        self.assertEqual(context.get('size'), 1024)
        
    def test_get_default(self):
        """Тест получения значения по умолчанию"""
        context = HookContext(None, HookType.ROM_LOADED, {})
        self.assertIsNone(context.get('missing'))
        self.assertEqual(context.get('missing', 'default'), 'default')
        
    def test_set_value(self):
        """Тест установки значения"""
        context = HookContext(None, HookType.ROM_LOADED, {})
        context.set('key', 'value')
        self.assertEqual(context.get('key'), 'value')


class TestHookManager(unittest.TestCase):
    """Тесты для класса HookManager"""
    
    def setUp(self):
        self.manager = HookManager()
        
    def test_register_hook(self):
        """Тест регистрации хука"""
        callback_called = []
        def test_callback(ctx):
            callback_called.append(True)
            
        self.manager.register(HookType.ROM_LOADED, test_callback, priority=10)
        
        # Проверяем, что хук зарегистрирован
        hooks = self.manager._hooks[HookType.ROM_LOADED]
        self.assertEqual(len(hooks), 1)
        
    def test_unregister_hook(self):
        """Тест удаления хука"""
        callback = lambda ctx: None
        self.manager.register(HookType.ROM_LOADED, callback)
        self.manager.unregister(HookType.ROM_LOADED, callback)
        
        hooks = self.manager._hooks[HookType.ROM_LOADED]
        self.assertEqual(len(hooks), 0)
        
    def test_trigger_hook(self):
        """Тест вызова хука"""
        results = []
        def callback(ctx):
            results.append(ctx.get('value'))
            
        self.manager.register(HookType.ROM_LOADED, callback)
        
        context = HookContext(None, HookType.ROM_LOADED, {'value': 42})
        self.manager.trigger(HookType.ROM_LOADED, context)
        
        self.assertEqual(results, [42])
        
    def test_priority_order(self):
        """Тест порядка приоритетов"""
        order = []
        
        def callback1(ctx):
            order.append(1)
            
        def callback2(ctx):
            order.append(2)
            
        # Регистрируем в обратном порядке приоритета
        self.manager.register(HookType.ROM_LOADED, callback2, priority=10)
        self.manager.register(HookType.ROM_LOADED, callback1, priority=20)
        
        context = HookContext(None, HookType.ROM_LOADED, {})
        self.manager.trigger(HookType.ROM_LOADED, context)
        
        # callback1 должен вызваться первым из-за большего приоритета
        self.assertEqual(order, [1, 2])


class TestGetHookManager(unittest.TestCase):
    """Тесты для глобальной функции get_hook_manager"""
    
    def test_singleton(self):
        """Тест синглтона"""
        manager1 = get_hook_manager()
        manager2 = get_hook_manager()
        
        self.assertIs(manager1, manager2)
        self.assertIsInstance(manager1, HookManager)


class TestPluginFactory(unittest.TestCase):
    """Тесты для фабрики плагинов"""
    
    def test_register_and_list(self):
        """Тест регистрации и списка плагинов"""
        @register_plugin("test_list_plugin")
        class TestPlugin(ExtendedGamePlugin):
            @property
            def info(self):
                return PluginInfo(
                    name="Test",
                    version="1.0",
                    author="Test",
                    description="Test"
                )
            
            def initialize(self):
                return True
                
            def shutdown(self):
                pass
                
            def match_rom(self, header):
                return True
                
            def get_text_segments(self, rom):
                return []
        
        self.assertIn("test_list_plugin", PluginFactory.list_plugins())
        
    def test_create_plugin(self):
        """Тест создания плагина"""
        @register_plugin("test_create_plugin")
        class TestPlugin(ExtendedGamePlugin):
            @property
            def info(self):
                return PluginInfo(
                    name="Test Create",
                    version="1.0",
                    author="Test",
                    description="Test"
                )
            
            def initialize(self):
                return True
                
            def shutdown(self):
                pass
                
            def match_rom(self, header):
                return True
                
            def get_text_segments(self, rom):
                return []
        
        plugin = PluginFactory.create("test_create_plugin")
        self.assertIsNotNone(plugin)
        self.assertIsInstance(plugin, TestPlugin)
        
    def test_create_nonexistent(self):
        """Тест создания несуществующего плагина"""
        plugin = PluginFactory.create("nonexistent_plugin")
        self.assertIsNone(plugin)
        
    def test_get_plugin_class(self):
        """Тест получения класса плагина"""
        @register_plugin("test_class_plugin")
        class TestPlugin(ExtendedGamePlugin):
            @property
            def info(self):
                return PluginInfo(
                    name="Test Class",
                    version="1.0",
                    author="Test",
                    description="Test"
                )
            
            def initialize(self):
                return True
                
            def shutdown(self):
                pass
                
            def match_rom(self, header):
                return True
                
            def get_text_segments(self, rom):
                return []
        
        plugin_class = PluginFactory.get_plugin_class("test_class_plugin")
        self.assertIsNotNone(plugin_class)
        self.assertTrue(issubclass(plugin_class, ExtendedGamePlugin))


class TestExtendedGamePlugin(unittest.TestCase):
    """Тесты для базового класса плагина"""
    
    def setUp(self):
        @register_plugin("test_base_plugin")
        class TestPlugin(ExtendedGamePlugin):
            @property
            def info(self):
                return PluginInfo(
                    name="Test Base Plugin",
                    version="1.0.0",
                    author="Test",
                    description="Test plugin",
                    supported_games=["TEST"],
                    priority=10
                )
            
            def initialize(self):
                self.initialized = True
                return True
                
            def shutdown(self):
                self.shut_down = True
                
            def match_rom(self, header):
                return header.get('title', '').upper() == 'TEST'
                
            def get_text_segments(self, rom):
                return [
                    {
                        'name': 'test_segment',
                        'start': 0x4000,
                        'end': 0x7FFF
                    }
                ]
        
        self.TestPlugin = TestPlugin
        self.plugin = TestPlugin()
        
    def test_initial_state(self):
        """Тест начального состояния"""
        self.assertEqual(self.plugin.state, PluginState.UNLOADED)
        
    def test_load(self):
        """Тест загрузки плагина"""
        result = self.plugin.on_load()
        self.assertTrue(result)
        self.assertEqual(self.plugin.state, PluginState.LOADED)
        self.assertTrue(self.plugin.initialized)
        
    def test_unload(self):
        """Тест выгрузки плагина"""
        self.plugin.on_load()
        self.plugin.on_unload()
        self.assertEqual(self.plugin.state, PluginState.UNLOADED)
        self.assertTrue(self.plugin.shut_down)
        
    def test_enable_disable(self):
        """Тест включения/выключения"""
        self.plugin.on_load()
        self.plugin.on_enable()
        self.assertEqual(self.plugin.state, PluginState.ACTIVE)
        
        self.plugin.on_disable()
        self.assertEqual(self.plugin.state, PluginState.DISABLED)
        
    def test_match_rom(self):
        """Тест сопоставления ROM"""
        self.plugin.on_load()
        self.assertTrue(self.plugin.match_rom({'title': 'Test'}))
        self.assertFalse(self.plugin.match_rom({'title': 'Other'}))
        
    def test_config(self):
        """Тест конфигурации"""
        self.plugin.set_config('key', 'value')
        self.assertEqual(self.plugin.get_config('key'), 'value')
        self.assertIsNone(self.plugin.get_config('missing'))
        self.assertEqual(self.plugin.get_config('missing', 'default'), 'default')


if __name__ == '__main__':
    unittest.main()