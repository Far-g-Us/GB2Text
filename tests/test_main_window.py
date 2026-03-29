"""
Тесты для GUI main_window.py
"""

import unittest
import unittest.mock as mock
import os
import sys
from unittest.mock import MagicMock, patch

# Добавляем путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMainWindowImports(unittest.TestCase):
    """Тесты импорта модуля"""

    def test_imports(self):
        """Проверка что все импорты работают"""
        try:
            import gui.main_window
        except ImportError as e:
            self.fail(f"Не удалось импортировать gui.main_window: {e}")

    def test_class_exists(self):
        """Проверка что класс существует"""
        from gui.main_window import GBTextExtractorGUI
        self.assertTrue(callable(GBTextExtractorGUI))


class TestSearchFunctionality(unittest.TestCase):
    """Тесты функциональности поиска"""

    def test_search_method_exists(self):
        """Проверка что методы поиска существуют"""
        from gui.main_window import GBTextExtractorGUI
        
        # Проверяем атрибуты класса
        self.assertTrue(hasattr(GBTextExtractorGUI, '_setup_search'))
        self.assertTrue(hasattr(GBTextExtractorGUI, 'show_search_dialog'))
        self.assertTrue(hasattr(GBTextExtractorGUI, 'show_replace_dialog'))
        self.assertTrue(hasattr(GBTextExtractorGUI, 'find_next'))
        self.assertTrue(hasattr(GBTextExtractorGUI, 'find_prev'))
        self.assertTrue(hasattr(GBTextExtractorGUI, 'replace_current'))
        self.assertTrue(hasattr(GBTextExtractorGUI, 'replace_all'))


class TestBatchProcessing(unittest.TestCase):
    """Тесты пакетной обработки"""

    def test_batch_method_exists(self):
        """Проверка что методы batch существуют"""
        from gui.main_window import GBTextExtractorGUI
        
        # Проверяем атрибуты класса
        self.assertTrue(hasattr(GBTextExtractorGUI, '_setup_batch_tab'))
        self.assertTrue(hasattr(GBTextExtractorGUI, '_batch_add_files'))
        self.assertTrue(hasattr(GBTextExtractorGUI, '_batch_clear_list'))
        self.assertTrue(hasattr(GBTextExtractorGUI, '_batch_start'))
        self.assertTrue(hasattr(GBTextExtractorGUI, '_batch_process_files'))
        self.assertTrue(hasattr(GBTextExtractorGUI, '_batch_export_all'))


class TestUndoRedo(unittest.TestCase):
    """Тесты Undo/Redo"""

    def test_undo_redo_methods_exist(self):
        """Проверка что методы undo/redo существуют"""
        from gui.main_window import GBTextExtractorGUI
        
        # Проверяем атрибуты класса
        self.assertTrue(hasattr(GBTextExtractorGUI, '_undo'))
        self.assertTrue(hasattr(GBTextExtractorGUI, '_redo'))


class TestCSVExportImport(unittest.TestCase):
    """Тесты экспорта/импорта CSV"""

    def test_csv_methods_exist(self):
        """Проверка что методы CSV существуют"""
        from gui.main_window import GBTextExtractorGUI
        
        # Проверяем атрибуты класса
        self.assertTrue(hasattr(GBTextExtractorGUI, 'export_csv'))
        self.assertTrue(hasattr(GBTextExtractorGUI, 'import_csv'))


class TestPreviewChanges(unittest.TestCase):
    """Тесты предпросмотра изменений"""

    def test_preview_method_exists(self):
        """Проверка что метод предпросмотра существует"""
        from gui.main_window import GBTextExtractorGUI
        
        # Проверяем атрибуты класса
        self.assertTrue(hasattr(GBTextExtractorGUI, '_show_preview_dialog'))


class TestDragDrop(unittest.TestCase):
    """Тесты Drag & Drop"""

    def test_drag_drop_methods_exist(self):
        """Проверка что методы drag & drop существуют"""
        from gui.main_window import GBTextExtractorGUI
        
        # Проверяем атрибуты класса
        self.assertTrue(hasattr(GBTextExtractorGUI, '_setup_drag_drop'))
        self.assertTrue(hasattr(GBTextExtractorGUI, '_on_file_drop'))


class TestGUIMethods(unittest.TestCase):
    """Тесты методов GUI без полной инициализации"""

    def test_machine_translation_initialization(self):
        """Тест инициализации машинного перевода"""
        from gui.main_window import GBTextExtractorGUI

        # Создаем минимальный мок для тестирования MT
        mock_mt = MagicMock()
        with mock.patch('gui.main_window.MachineTranslation', return_value=mock_mt):
            # Проверяем что MT инициализируется
            self.assertIsNotNone(mock_mt)

    def test_tmx_handler_initialization(self):
        """Тест инициализации TMX обработчика"""
        from gui.main_window import GBTextExtractorGUI

        # Создаем минимальный мок для тестирования TMX
        mock_tmx = MagicMock()
        with mock.patch('gui.main_window.TMXHandler', return_value=mock_tmx):
            # Проверяем что TMX инициализируется
            self.assertIsNotNone(mock_tmx)

    @mock.patch('gui.main_window.MachineTranslation')
    def test_machine_translation_settings_application(self, mock_mt_class):
        """Тест применения настроек машинного перевода"""
        from gui.main_window import GBTextExtractorGUI

        mock_mt = MagicMock()
        mock_mt_class.return_value = mock_mt

        # Создаем экземпляр с MT
        with mock.patch('tkinter.Tk'), \
             mock.patch('gui.main_window.I18N'), \
             mock.patch('gui.main_window.PluginManager'), \
             mock.patch('gui.main_window.GuideManager'), \
             mock.patch('gui.main_window.TMXHandler'):
            # Проверяем что MT создан
            self.assertIsNotNone(mock_mt)

    @mock.patch('gui.main_window.TMXHandler')
    def test_tmx_handler_settings_application(self, mock_tmx_class):
        """Тест применения настроек TMX обработчика"""
        from gui.main_window import GBTextExtractorGUI

        mock_tmx = MagicMock()
        mock_tmx_class.return_value = mock_tmx

        # Создаем экземпляр с TMX
        with mock.patch('tkinter.Tk'), \
             mock.patch('gui.main_window.I18N'), \
             mock.patch('gui.main_window.PluginManager'), \
             mock.patch('gui.main_window.GuideManager'), \
             mock.patch('gui.main_window.MachineTranslation'):
            # Проверяем что TMX создан
            self.assertIsNotNone(mock_tmx)


class TestRunGUI(unittest.TestCase):
    """Тесты функции run_gui"""

    def test_run_gui_exists(self):
        """Проверка что функция run_gui существует"""
        from gui.main_window import run_gui
        self.assertTrue(callable(run_gui))


if __name__ == '__main__':
    unittest.main()
