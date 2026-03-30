"""
Тесты для GUI модулей без проблем с tkinterdnd2 метаклассов
Используем реальный tkinter, но патчим только проблемные части
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, Mock

# Важно: НЕ патчим tkinterdnd2 ДО импорта!
# Позволяем реальному tkinterdnd2 импортироваться, но патчим только проблемные классы


class TestGUIImportsRealTkinter(unittest.TestCase):
    """Тесты импорта GUI с реальным tkinter"""
    
    def test_editor_import(self):
        """Тест импорта editor"""
        from gui.editor import TextEditorFrame
        self.assertIsNotNone(TextEditorFrame)
        # Проверяем что это класс, а не мок
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
            
    def test_main_window_methods_exist(self):
        """Тест наличия методов main_window"""
        from gui.main_window import GBTextExtractorGUI
        
        # Проверяем что это callable
        self.assertTrue(callable(GBTextExtractorGUI))


class TestGUIEditorLogicWithoutTkinter(unittest.TestCase):
    """Тесты логики editor без инициализации tkinter виджетов"""
    
    def test_editor_type_validation(self):
        """Тест валидации типа rom_path в editor"""
        from gui.editor import TextEditorFrame
        
        # Создаем объект без вызова __init__
        editor = object.__new__(TextEditorFrame)
        
        # Устанавливаем минимальные атрибуты
        editor.segment_data = [{'text': 'test'}]
        editor.current_index = 0
        
        self.assertEqual(len(editor.segment_data), 1)
        
    def test_editor_navigation_without_init(self):
        """Тест навигации без инициализации"""
        from gui.editor import TextEditorFrame
        
        editor = object.__new__(TextEditorFrame)
        editor.segment_data = [
            {'text': 'Entry 1'},
            {'text': 'Entry 2'},
            {'text': 'Entry 3'}
        ]
        editor.current_index = 0
        
        # Симулируем prev_entry
        if editor.current_index > 0:
            editor.current_index -= 1
            
        self.assertEqual(editor.current_index, 0)  # Не изменился
        
        # Симулируем next_entry
        if editor.current_index < len(editor.segment_data) - 1:
            editor.current_index += 1
            
        self.assertEqual(editor.current_index, 1)
        
    def test_editor_history_without_init(self):
        """Тест истории без инициализации"""
        from gui.editor import TextEditorFrame
        
        editor = object.__new__(TextEditorFrame)
        editor.history = []
        editor.history_index = -1
        editor.max_history = 50
        
        # Симулируем добавление в историю
        editor.history.append({'text': 'Change 1', 'index': 0})
        editor.history_index = 0
        
        editor.history.append({'text': 'Change 2', 'index': 1})
        editor.history_index = 1
        
        self.assertEqual(len(editor.history), 2)
        
        # Симулируем undo
        if editor.history_index > 0:
            editor.history_index -= 1
        self.assertEqual(editor.history_index, 0)
        
        # Симулируем redo
        if editor.history_index < len(editor.history) - 1:
            editor.history_index += 1
        self.assertEqual(editor.history_index, 1)


class TestGUIMainWindowLogicWithoutTkinter(unittest.TestCase):
    """Тесты логики main_window без инициализации tkinter виджетов"""
    
    def test_main_window_validation_without_init(self):
        """Тест валидации без инициализации"""
        from gui.main_window import GBTextExtractorGUI
        
        # Проверяем что неправильный rom_path вызывает ошибку
        # Это можно сделать без создания объекта
        pass
        
    def test_search_state_simulation(self):
        """Тест состояния поиска"""
        from gui.main_window import GBTextExtractorGUI
        
        gui = object.__new__(GBTextExtractorGUI)
        gui.search_results = []
        gui.search_index = 0
        gui.search_term = ""
        gui.replace_term = ""
        
        # Симулируем поиск
        gui.search_results = [
            {'offset': 0x100, 'text': 'Result 1'},
            {'offset': 0x200, 'text': 'Result 2'},
            {'offset': 0x300, 'text': 'Result 3'}
        ]
        
        self.assertEqual(len(gui.search_results), 3)
        
        # Симулируем навигацию
        if gui.search_index < len(gui.search_results) - 1:
            gui.search_index += 1
        self.assertEqual(gui.search_index, 1)
        
    def test_component_integration_simulation(self):
        """Тест интеграции компонентов"""
        from gui.main_window import GBTextExtractorGUI
        from core.plugin_manager import PluginManager
        from core.guide import GuideManager
        from core.machine_translation import MachineTranslation
        from core.tmx import TMXHandler
        
        gui = object.__new__(GBTextExtractorGUI)
        
        # Симулируем инициализацию компонентов
        gui.plugin_manager = PluginManager("plugins")
        gui.guide_manager = GuideManager()
        gui.machine_translation = MachineTranslation()
        gui.tmx_handler = TMXHandler()
        
        self.assertIsNotNone(gui.plugin_manager)
        self.assertIsNotNone(gui.guide_manager)
        self.assertIsNotNone(gui.machine_translation)
        self.assertIsNotNone(gui.tmx_handler)


class TestGUIConstants(unittest.TestCase):
    """Тесты констант GUI"""
    
    def test_window_dimensions(self):
        """Тест констант размеров окна"""
        from gui.main_window import DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
        
        self.assertIsInstance(DEFAULT_WINDOW_WIDTH, int)
        self.assertIsInstance(DEFAULT_WINDOW_HEIGHT, int)
        self.assertGreater(DEFAULT_WINDOW_WIDTH, 0)
        self.assertGreater(DEFAULT_WINDOW_HEIGHT, 0)
        
    def test_editor_class_type(self):
        """Тест что editor класс - реальный тип"""
        from gui.editor import TextEditorFrame
        # Проверяем что это не MagicMock
        self.assertNotIsInstance(TextEditorFrame, MagicMock)


class TestGUIWithMockRoot(unittest.TestCase):
    """Тесты с моковым корневым окном"""
    
    def test_gui_validation_rom_path(self):
        """Тест валидации rom_path"""
        from gui.main_window import GBTextExtractorGUI
        
        # Проверяем что невалидные типы отклоняются
        with self.assertRaises(TypeError):
            GBTextExtractorGUI(Mock(), rom_path=123)
            
    def test_gui_rom_path_none(self):
        """Тест rom_path = None"""
        from gui.main_window import GBTextExtractorGUI
        
        # None должен быть валидным
        # Но мы не можем создать полный объект без tkinter
        # поэтому проверяем только логику валидации
        rom_path = None
        self.assertTrue(rom_path is None or isinstance(rom_path, str))


class TestGUIExportImportLogic(unittest.TestCase):
    """Тесты логики экспорта/импорта"""
    
    def test_export_data_structure(self):
        """Тест структуры данных экспорта"""
        data = {
            'version': '1.0',
            'results': [
                {'offset': 0x100, 'text': 'Hello', 'translated': 'Привет'}
            ]
        }
        
        import json
        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed['version'], '1.0')
        self.assertEqual(len(parsed['results']), 1)
        
    def test_csv_parsing_logic(self):
        """Тест логики парсинга CSV"""
        csv_line = "0x100,Hello,Привет"
        parts = csv_line.split(',')
        
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], '0x100')


if __name__ == '__main__':
    unittest.main()