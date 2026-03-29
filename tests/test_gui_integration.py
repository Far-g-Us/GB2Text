"""
Интеграционные тесты для GUI компонентов с глубоким мокингом tkinter
"""

import unittest
import unittest.mock as mock
import os
import sys
from unittest.mock import MagicMock, patch, Mock

# Добавляем путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGUIIntegration(unittest.TestCase):
    """Интеграционные тесты GUI с полным мокингом tkinter"""

    def setUp(self):
        """Глобальная настройка моков для всех tkinter компонентов"""
        self.tkinter_mocks = {
            'tkinter.Tk': Mock(),
            'tkinter.ttk.Frame': Mock(),
            'tkinter.ttk.Label': Mock(),
            'tkinter.ttk.Button': Mock(),
            'tkinter.ttk.Entry': Mock(),
            'tkinter.ttk.Combobox': Mock(),
            'tkinter.ttk.Treeview': Mock(),
            'tkinter.ttk.Scrollbar': Mock(),
            'tkinter.ttk.Notebook': Mock(),
            'tkinter.ttk.PanedWindow': Mock(),
            'tkinter.ttk.Checkbutton': Mock(),
            'tkinter.StringVar': Mock(),
            'tkinter.IntVar': Mock(),
            'tkinter.BooleanVar': Mock(),
            'tkinter.Text': Mock(),
            'tkinter.Scrollbar': Mock(),
            'tkinter.Menu': Mock(),
            'tkinter.Canvas': Mock(),
            'tkinter.Listbox': Mock(),
            'tkinter.Message': Mock(),
            'tkinter.filedialog.askopenfilename': Mock(return_value='test.gb'),
            'tkinter.filedialog.asksaveasfilename': Mock(return_value='test.txt'),
            'tkinter.filedialog.askdirectory': Mock(return_value='/tmp'),
            'tkinter.messagebox.showinfo': Mock(),
            'tkinter.messagebox.showerror': Mock(),
            'tkinter.messagebox.showwarning': Mock(),
            'tkinter.messagebox.askyesno': Mock(return_value=True),
            'tkinter.messagebox.askquestion': Mock(return_value='yes'),
        }

        # Применяем все моки
        for mock_target, mock_obj in self.tkinter_mocks.items():
            patcher = mock.patch(mock_target, mock_obj)
            patcher.start()
            self.addCleanup(patcher.stop)

    @mock.patch('gui.main_window.I18N')
    @mock.patch('gui.main_window.PluginManager')
    @mock.patch('gui.main_window.GuideManager')
    @mock.patch('gui.main_window.MachineTranslation')
    @mock.patch('gui.main_window.TMXHandler')
    def test_main_window_initialization_complete(self, mock_tmx, mock_mt, mock_guide, mock_plugin, mock_i18n):
        """Полная инициализация главного окна с моками"""
        from gui.main_window import GBTextExtractorGUI

        # Настройка моков
        mock_root = Mock()
        mock_i18n_instance = Mock()
        mock_i18n_instance.t.return_value = "Test"
        mock_i18n.return_value = mock_i18n_instance

        # Мокаем методы, которые вызывают tkinter компоненты
        with mock.patch.object(GBTextExtractorGUI, '_set_app_icon'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_ui'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_context_menu'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_search'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_drag_drop'), \
             mock.patch.object(GBTextExtractorGUI, 'show_warning_dialog'):

            gui = GBTextExtractorGUI(mock_root, rom_path="test.gb")

            # Проверки
            self.assertIsNotNone(gui)
            self.assertEqual(gui.root, mock_root)
            self.assertEqual(gui.rom_path.get(), "test.gb")
            mock_i18n.assert_called_once()

    @mock.patch('gui.editor.I18N')
    def test_text_editor_initialization(self, mock_i18n):
        """Инициализация текстового редактора"""
        from gui.editor import TextEditorFrame

        # Настройка моков
        mock_parent = Mock()
        mock_i18n_instance = Mock()
        mock_i18n_instance.t.return_value = "Test"
        mock_i18n.return_value = mock_i18n_instance

        # Тестовые данные
        segment_data = [{'text': 'Hello', 'address': 0x1000}]
        rom_path = "test.gb"
        plugin = Mock()

        # Мокаем методы UI
        with mock.patch.object(TextEditorFrame, '_setup_ui'), \
             mock.patch.object(TextEditorFrame, '_create_backup'):

            editor = TextEditorFrame(mock_parent, segment_data, rom_path, plugin)

            # Проверки
            self.assertIsNotNone(editor)
            self.assertEqual(editor.segment_data, segment_data)
            self.assertEqual(editor.rom_path, rom_path)
            self.assertEqual(len(editor.original_texts), 1)
            self.assertEqual(editor.original_texts[0], 'Hello')

    def test_text_editor_text_operations(self):
        """Тест операций с текстом в редакторе"""
        from gui.editor import TextEditorFrame

        # Создаем минимальный мок для тестирования методов
        mock_parent = Mock()
        segment_data = [{'text': 'Hello World', 'address': 0x1000}]
        rom_path = "test.gb"
        plugin = Mock()

        with mock.patch('gui.editor.I18N') as mock_i18n, \
             mock.patch.object(TextEditorFrame, '_setup_ui'), \
             mock.patch.object(TextEditorFrame, '_create_backup'):

            mock_i18n_instance = Mock()
            mock_i18n_instance.t.return_value = "Test"
            mock_i18n.return_value = mock_i18n_instance

            editor = TextEditorFrame(mock_parent, segment_data, rom_path, plugin)

            # Тест undo/redo функциональности
            editor.history = [{'index': 0, 'old_text': 'Hello World', 'new_text': 'Hello Universe'}]
            editor.history_index = 0

            # Мокаем методы undo/redo
            with mock.patch.object(editor, '_update_display'), \
                 mock.patch.object(editor, '_save_history'):

                # Проверяем, что методы существуют
                self.assertTrue(hasattr(editor, '_undo'))
                self.assertTrue(hasattr(editor, '_redo'))
                self.assertTrue(hasattr(editor, 'save_changes'))
                self.assertTrue(hasattr(editor, 'export_translated'))

    @mock.patch('gui.main_window.GBTextExtractorGUI')
    def test_run_gui_function(self, mock_gui_class):
        """Тест функции run_gui"""
        from gui.main_window import run_gui

        mock_gui_instance = Mock()
        mock_gui_class.return_value = mock_gui_instance

        # Мокаем tkinter.Tk и mainloop
        with mock.patch('tkinter.Tk') as mock_tk:
            mock_root = Mock()
            mock_tk.return_value = mock_root

            # Вызываем run_gui
            run_gui()

            # Проверки
            mock_tk.assert_called_once()
            mock_gui_class.assert_called_once_with(mock_root)

    def test_gui_method_existence(self):
        """Тест существования основных методов GUI"""
        from gui.main_window import GBTextExtractorGUI

        # Проверяем наличие основных методов
        expected_methods = [
            'load_rom', 'save_text', 'export_csv', 'import_csv',
            'show_search_dialog', 'show_replace_dialog', 'find_next', 'find_prev',
            'replace_current', 'replace_all', '_undo', '_redo',
            '_setup_batch_tab', '_batch_add_files', '_batch_start',
            'show_about', 'on_closing', '_set_app_icon'
        ]

        for method in expected_methods:
            with self.subTest(method=method):
                self.assertTrue(hasattr(GBTextExtractorGUI, method),
                               f"Method {method} not found in GBTextExtractorGUI")

    def test_editor_method_existence(self):
        """Тест существования основных методов редактора"""
        from gui.editor import TextEditorFrame

        # Проверяем наличие основных методов
        expected_methods = [
            '_setup_ui', '_create_backup', '_undo', '_redo',
            'save_changes', 'export_translated', '_update_display',
            '_save_history', '_load_history', 'navigate_to_segment'
        ]

        for method in expected_methods:
            with self.subTest(method=method):
                self.assertTrue(hasattr(TextEditorFrame, method),
                               f"Method {method} not found in TextEditorFrame")


class TestGUIFunctionality(unittest.TestCase):
    """Тесты функциональности GUI"""

    def setUp(self):
        """Настройка для функциональных тестов"""
        # Мокаем все основные tkinter компоненты
        tkinter_patches = [
            mock.patch('tkinter.Tk'),
            mock.patch('tkinter.ttk.Frame'),
            mock.patch('tkinter.ttk.Button'),
            mock.patch('tkinter.StringVar'),
            mock.patch('tkinter.IntVar'),
            mock.patch('tkinter.BooleanVar'),
            mock.patch('tkinter.filedialog.askopenfilename', return_value='test.gb'),
            mock.patch('tkinter.messagebox.showinfo'),
            mock.patch('gui.main_window.I18N'),
            mock.patch('gui.main_window.PluginManager'),
            mock.patch('gui.main_window.GuideManager'),
            mock.patch('gui.main_window.MachineTranslation'),
            mock.patch('gui.main_window.TMXHandler'),
        ]

        self.patches = []
        for patcher in tkinter_patches:
            patcher.start()
            self.patches.append(patcher)

        self.addCleanup(self._cleanup_patches)

    def _cleanup_patches(self):
        """Очистка патчей"""
        for patcher in self.patches:
            patcher.stop()

    def test_machine_translation_integration(self):
        """Тест интеграции машинного перевода"""
        from gui.main_window import GBTextExtractorGUI

        # Мокаем все зависимости
        with mock.patch.object(GBTextExtractorGUI, '_set_app_icon'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_ui'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_context_menu'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_search'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_drag_drop'), \
             mock.patch.object(GBTextExtractorGUI, 'show_warning_dialog'):

            mock_root = Mock()
            gui = GBTextExtractorGUI(mock_root)

            # Проверяем наличие MT компонентов
            self.assertTrue(hasattr(gui, 'machine_translation'))
            self.assertTrue(hasattr(gui, 'tmx_handler'))
            self.assertIsNotNone(gui.machine_translation)
            self.assertIsNotNone(gui.tmx_handler)

    def test_plugin_system_integration(self):
        """Тест интеграции системы плагинов"""
        from gui.main_window import GBTextExtractorGUI

        # Мокаем все зависимости
        with mock.patch.object(GBTextExtractorGUI, '_set_app_icon'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_ui'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_context_menu'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_search'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_drag_drop'), \
             mock.patch.object(GBTextExtractorGUI, 'show_warning_dialog'):

            mock_root = Mock()
            gui = GBTextExtractorGUI(mock_root)

            # Проверяем наличие компонентов плагинов
            self.assertTrue(hasattr(gui, 'plugin_manager'))
            self.assertTrue(hasattr(gui, 'guide_manager'))
            self.assertIsNotNone(gui.plugin_manager)
            self.assertIsNotNone(gui.guide_manager)


