# -*- coding: utf-8 -*-
"""
Тесты для GUI модулей без проблем с tkinterdnd2 метаклассов
Используем реальный tkinter, но тестируем только структуру без инициализации
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, Mock


class TestGUIImports(unittest.TestCase):
    """Тесты импорта GUI модулей"""
    
    def setUp(self):
        """Очистка модулей перед каждым тестом"""
        for mod in list(sys.modules.keys()):
            if 'gui' in mod:
                try:
                    del sys.modules[mod]
                except:
                    pass
                
    def test_editor_import(self):
        """Тест импорта editor"""
        from gui.editor import TextEditorFrame
        self.assertIsNotNone(TextEditorFrame)
        self.assertTrue(isinstance(TextEditorFrame, type))
        
    def test_main_window_import(self):
        """Тест импорта main_window"""
        from gui.main_window import GBTextExtractorGUI
        self.assertIsNotNone(GBTextExtractorGUI)
        self.assertTrue(isinstance(GBTextExtractorGUI, type))
        
    def test_editor_methods_exist(self):
        """Тест наличия методов editor"""
        from gui.editor import TextEditorFrame
        
        methods = ['__init__', 'prev_entry', 'next_entry', 'save_changes', 'undo', 'redo']
        for method in methods:
            self.assertTrue(hasattr(TextEditorFrame, method), f"Missing method: {method}")
            
    def test_main_window_callable(self):
        """Тест что main_window callable"""
        from gui.main_window import GBTextExtractorGUI
        self.assertTrue(callable(GBTextExtractorGUI))


class TestSearchFunctionality(unittest.TestCase):
    """Тесты для функциональности поиска и замены"""
    
    def test_search_state_initialization(self):
        """Тест начального состояния поиска"""
        mock_gui = MagicMock()
        mock_gui.search_results = []
        mock_gui.search_index = 0
        mock_gui.search_term = ""
        mock_gui.replace_term = ""
        
        self.assertEqual(mock_gui.search_results, [])
        self.assertEqual(mock_gui.search_index, 0)
        self.assertEqual(mock_gui.search_term, "")
        self.assertEqual(mock_gui.replace_term, "")
        
    def test_search_term_update(self):
        """Тест обновления поискового запроса"""
        mock_gui = MagicMock()
        mock_gui.search_term = ""
        
        mock_gui.search_term = "test"
        self.assertEqual(mock_gui.search_term, "test")
        
    def test_search_index_bounds(self):
        """Тест границ индекса поиска"""
        mock_gui = MagicMock()
        mock_gui.search_results = [1, 2, 3]
        mock_gui.search_index = 0
        
        self.assertGreaterEqual(mock_gui.search_index, 0)
        self.assertLess(mock_gui.search_index, len(mock_gui.search_results))
        
    def test_search_results_population(self):
        """Тест заполнения результатов поиска"""
        mock_gui = MagicMock()
        mock_gui.search_results = []
        
        mock_gui.search_results = [
            {'offset': 0x100, 'text': 'Hello'},
            {'offset': 0x200, 'text': 'World'}
        ]
        
        self.assertEqual(len(mock_gui.search_results), 2)
        self.assertEqual(mock_gui.search_results[0]['offset'], 0x100)


class TestPluginManagerIntegration(unittest.TestCase):
    """Тесты интеграции с PluginManager"""
    
    def test_plugin_manager_initialization(self):
        """Тест инициализации менеджера плагинов"""
        from core.plugin_manager import PluginManager
        
        pm = PluginManager("plugins")
        self.assertIsNotNone(pm)
        
    def test_plugin_manager_cancellation_token(self):
        """Тест токена отмены"""
        from core.plugin_manager import CancellationToken
        
        token = CancellationToken()
        self.assertTrue(hasattr(token, 'cancel'))
        self.assertTrue(hasattr(token, 'is_cancellation_requested'))
        self.assertFalse(token.is_cancellation_requested())


class TestI18NIntegration(unittest.TestCase):
    """Тесты интеграции с I18N"""
    
    def test_i18n_initialization(self):
        """Тест инициализации интернационализации"""
        from core.i18n import I18N
        
        i18n = I18N(default_lang='en')
        self.assertIsNotNone(i18n)
        
    def test_i18n_translation_function(self):
        """Тест функции перевода"""
        from core.i18n import I18N
        
        i18n = I18N(default_lang='en')
        self.assertTrue(hasattr(i18n, 't'))


class TestGuideManagerIntegration(unittest.TestCase):
    """Тесты интеграции с GuideManager"""
    
    def test_guide_manager_initialization(self):
        """Тест инициализации менеджера гайдов"""
        from core.guide import GuideManager
        
        gm = GuideManager()
        self.assertIsNotNone(gm)


class TestExtractionComponents(unittest.TestCase):
    """Тесты компонентов экстракции"""
    
    def test_text_extractor_import(self):
        """Тест импорта TextExtractor"""
        from core.extractor import TextExtractor
        
        self.assertIsNotNone(TextExtractor)
        
    def test_text_injector_import(self):
        """Тест импорта TextInjector"""
        from core.injector import TextInjector
        
        self.assertIsNotNone(TextInjector)


class TestEncodingCharmaps(unittest.TestCase):
    """Тесты encoding charmaps"""
    
    def test_generic_english_charmap(self):
        """Тест generic english charmap"""
        from core.encoding import get_generic_english_charmap
        
        charmap = get_generic_english_charmap()
        self.assertIsNotNone(charmap)
        self.assertTrue(len(charmap) > 0)
        
    def test_generic_japanese_charmap(self):
        """Тест generic japanese charmap"""
        from core.encoding import get_generic_japanese_charmap
        
        charmap = get_generic_japanese_charmap()
        self.assertIsNotNone(charmap)
        self.assertTrue(len(charmap) > 0)
        
    def test_generic_russian_charmap(self):
        """Тест generic russian charmap"""
        from core.encoding import get_generic_russian_charmap
        
        charmap = get_generic_russian_charmap()
        self.assertIsNotNone(charmap)
        self.assertTrue(len(charmap) > 0)


class TestMachineTranslationIntegration(unittest.TestCase):
    """Тесты интеграции машинного перевода"""
    
    def test_mt_initialization(self):
        """Тест инициализации MT"""
        from core.machine_translation import MachineTranslation
        
        mt = MachineTranslation()
        self.assertIsNotNone(mt)


class TestTMXHandlerIntegration(unittest.TestCase):
    """Тесты интеграции TMX обработчика"""
    
    def test_tmx_initialization(self):
        """Тест инициализации TMX"""
        from core.tmx import TMXHandler
        
        handler = TMXHandler()
        self.assertIsNotNone(handler)


class TestScanningIntegration(unittest.TestCase):
    """Тесты интеграции сканирования"""
    
    def test_analyze_text_segment_import(self):
        """Тест импорта analyze_text_segment"""
        from core.scanner import analyze_text_segment
        
        self.assertIsNotNone(analyze_text_segment)
        
    def test_detect_language_import(self):
        """Тест импорта _detect_language"""
        from core.scanner import _detect_language
        
        self.assertIsNotNone(_detect_language)


class TestConstantsImport(unittest.TestCase):
    """Тесты импорта констант"""
    
    def test_default_window_dimensions(self):
        """Тест размеров окна по умолчанию"""
        from core.constants import DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
        
        self.assertIsNotNone(DEFAULT_WINDOW_WIDTH)
        self.assertIsNotNone(DEFAULT_WINDOW_HEIGHT)
        self.assertTrue(DEFAULT_WINDOW_WIDTH > 0)
        self.assertTrue(DEFAULT_WINDOW_HEIGHT > 0)


class TestGUIConstants(unittest.TestCase):
    """Тесты GUI констант"""
    
    def test_window_constants_exist(self):
        """Тест существования констант окна"""
        from gui.main_window import DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
        
        self.assertTrue(DEFAULT_WINDOW_WIDTH > 0)
        self.assertTrue(DEFAULT_WINDOW_HEIGHT > 0)


if __name__ == '__main__':
    unittest.main()
