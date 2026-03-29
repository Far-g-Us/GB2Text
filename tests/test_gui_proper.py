"""
Правильные интеграционные тесты для GUI компонентов с глубоким мокингом
Использует pytest-xvfb для headless тестирования
"""

import unittest
import unittest.mock as mock
import os
import sys
from unittest.mock import MagicMock, Mock, patch

# Добавляем путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGUIProperIntegration(unittest.TestCase):
    """Правильные интеграционные тесты GUI без конфликтов метаклассов"""

    def setUp(self):
        """Настройка моков для всех проблемных импортов"""
        # Мокаем все импорты, которые вызывают проблемы
        self.patches = [
            mock.patch('tkinterdnd2', Mock()),
            mock.patch('tkinterdnd2.Tk', Mock()),
            mock.patch.dict('sys.modules', {
                'tkinterdnd2': Mock(),
                'tkinterdnd2.Tk': Mock(),
            })
        ]

        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self._cleanup_patches)

    def _cleanup_patches(self):
        """Очистка патчей"""
        for patcher in self.patches:
            patcher.stop()

    @mock.patch('tkinter.Tk')
    @mock.patch('tkinter.ttk.Frame')
    @mock.patch('tkinter.ttk.Button')
    @mock.patch('tkinter.ttk.Label')
    @mock.patch('tkinter.ttk.Entry')
    @mock.patch('tkinter.StringVar')
    @mock.patch('tkinter.IntVar')
    @mock.patch('tkinter.BooleanVar')
    @mock.patch('gui.main_window.I18N')
    @mock.patch('gui.main_window.PluginManager')
    @mock.patch('gui.main_window.GuideManager')
    @mock.patch('gui.main_window.MachineTranslation')
    @mock.patch('gui.main_window.TMXHandler')
    def test_main_window_minimal_init(self, mock_tmx, mock_mt, mock_guide,
                                      mock_plugin, mock_i18n, mock_boolvar,
                                      mock_intvar, mock_stringvar, mock_entry,
                                      mock_label, mock_button, mock_frame, mock_tk):
        """Минимальная инициализация главного окна"""
        from gui.main_window import GBTextExtractorGUI

        # Настройка моков
        mock_root = Mock()
        mock_tk.return_value = mock_root

        mock_i18n_instance = Mock()
        mock_i18n_instance.t.return_value = "Test"
        mock_i18n.return_value = mock_i18n_instance

        # Мокаем все методы, которые могут вызывать tkinter
        methods_to_mock = [
            '_set_app_icon', '_setup_ui', '_setup_context_menu',
            '_setup_search', '_setup_drag_drop', 'show_warning_dialog',
            'load_saved_settings', '_init_default_settings'
        ]

        for method in methods_to_mock:
            with mock.patch.object(GBTextExtractorGUI, method):
                pass

        # Создаем экземпляр с моками
        with mock.patch.object(GBTextExtractorGUI, '_set_app_icon'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_ui'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_context_menu'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_search'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_drag_drop'), \
             mock.patch.object(GBTextExtractorGUI, 'show_warning_dialog'), \
             mock.patch.object(GBTextExtractorGUI, 'load_saved_settings'), \
             mock.patch.object(GBTextExtractorGUI, '_init_default_settings'):

            gui = GBTextExtractorGUI(mock_root)

            # Базовые проверки
            self.assertIsNotNone(gui)
            self.assertEqual(gui.root, mock_root)

    def test_gui_component_imports(self):
        """Тест импорта GUI компонентов с мокингом"""
        # Мокаем проблемные импорты на уровне модуля
        with mock.patch.dict('sys.modules', {
            'tkinterdnd2': Mock(),
            'tkinterdnd2.Tk': Mock(),
        }):
            # Теперь можно импортировать без ошибок
            from gui.main_window import GBTextExtractorGUI
            from gui.editor import TextEditorFrame

            # Проверяем что классы существуют
            self.assertTrue(callable(GBTextExtractorGUI))
            self.assertTrue(callable(TextEditorFrame))

    @mock.patch.dict('sys.modules', {
        'tkinterdnd2': Mock(),
        'tkinterdnd2.Tk': Mock(),
    })
    def test_editor_frame_creation(self):
        """Тест создания фрейма редактора"""
        from gui.editor import TextEditorFrame

        # Мокаем все tkinter компоненты
        with mock.patch('tkinter.ttk.Frame') as mock_frame, \
             mock.patch('tkinter.ttk.Button'), \
             mock.patch('tkinter.ttk.Label'), \
             mock.patch('tkinter.Text'), \
             mock.patch('tkinter.Scrollbar'), \
             mock.patch('tkinter.Menu'), \
             mock.patch('gui.editor.I18N') as mock_i18n:

            mock_parent = Mock()
            mock_frame_instance = Mock()
            mock_frame.return_value = mock_frame_instance

            mock_i18n_instance = Mock()
            mock_i18n_instance.t.return_value = "Test"
            mock_i18n.return_value = mock_i18n_instance

            # Тестовые данные
            segment_data = [{'text': 'Hello', 'address': 0x1000}]
            plugin = Mock()

            # Мокаем методы
            with mock.patch.object(TextEditorFrame, '_setup_ui'), \
                 mock.patch.object(TextEditorFrame, '_create_backup'):

                editor = TextEditorFrame(mock_parent, segment_data, "test.gb", plugin)

                # Проверки
                self.assertIsNotNone(editor)
                self.assertEqual(editor.segment_data, segment_data)
                self.assertEqual(len(editor.original_texts), 1)

    def test_method_existence_without_import(self):
        """Тест существования методов без проблемных импортов"""
        # Мокаем на уровне sys.modules
        with mock.patch.dict('sys.modules', {
            'tkinterdnd2': Mock(),
            'tkinterdnd2.Tk': Mock(),
        }):
            from gui.main_window import GBTextExtractorGUI
            from gui.editor import TextEditorFrame

            # Проверяем наличие ключевых методов
            main_window_methods = [
                'load_rom', 'save_text', 'export_csv', 'show_about',
                'on_closing', '_undo', '_redo'
            ]

            editor_methods = [
                '_setup_ui', 'save_changes', '_undo', '_redo'
            ]

            for method in main_window_methods:
                self.assertTrue(hasattr(GBTextExtractorGUI, method),
                               f"GBTextExtractorGUI missing method: {method}")

            for method in editor_methods:
                self.assertTrue(hasattr(TextEditorFrame, method),
                               f"TextEditorFrame missing method: {method}")


class TestGUIFunctionalityHeadless(unittest.TestCase):
    """Тесты функциональности GUI в headless режиме"""

    def setUp(self):
        """Headless настройка для GUI тестов"""
        # Мокаем все проблемные импорты
        self.patches = [
            mock.patch.dict('sys.modules', {
                'tkinterdnd2': Mock(),
                'tkinterdnd2.Tk': Mock(),
            }),
            mock.patch('tkinter.Tk'),
            mock.patch('tkinter.ttk.Frame'),
            mock.patch('tkinter.StringVar'),
            mock.patch('tkinter.IntVar'),
            mock.patch('tkinter.BooleanVar'),
        ]

        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self._cleanup_patches)

    def _cleanup_patches(self):
        """Очистка патчей"""
        for patcher in self.patches:
            patcher.stop()

    def test_machine_translation_component(self):
        """Тест компонента машинного перевода"""
        from gui.main_window import GBTextExtractorGUI

        # Мокаем все зависимости
        with mock.patch('gui.main_window.I18N'), \
             mock.patch('gui.main_window.PluginManager'), \
             mock.patch('gui.main_window.GuideManager'), \
             mock.patch('gui.main_window.MachineTranslation') as mock_mt, \
             mock.patch('gui.main_window.TMXHandler'), \
             mock.patch.object(GBTextExtractorGUI, '_set_app_icon'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_ui'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_context_menu'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_search'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_drag_drop'), \
             mock.patch.object(GBTextExtractorGUI, 'show_warning_dialog'), \
             mock.patch.object(GBTextExtractorGUI, 'load_saved_settings'), \
             mock.patch.object(GBTextExtractorGUI, '_init_default_settings'):

            mock_mt_instance = Mock()
            mock_mt.return_value = mock_mt_instance

            mock_root = Mock()
            gui = GBTextExtractorGUI(mock_root)

            # Проверяем что MT компонент инициализирован
            self.assertIsNotNone(gui.machine_translation)
            self.assertEqual(gui.machine_translation, mock_mt_instance)

    def test_plugin_manager_component(self):
        """Тест компонента управления плагинами"""
        from gui.main_window import GBTextExtractorGUI

        # Мокаем все зависимости
        with mock.patch('gui.main_window.I18N'), \
             mock.patch('gui.main_window.PluginManager') as mock_pm, \
             mock.patch('gui.main_window.GuideManager'), \
             mock.patch('gui.main_window.MachineTranslation'), \
             mock.patch('gui.main_window.TMXHandler'), \
             mock.patch.object(GBTextExtractorGUI, '_set_app_icon'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_ui'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_context_menu'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_search'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_drag_drop'), \
             mock.patch.object(GBTextExtractorGUI, 'show_warning_dialog'), \
             mock.patch.object(GBTextExtractorGUI, 'load_saved_settings'), \
             mock.patch.object(GBTextExtractorGUI, '_init_default_settings'):

            mock_pm_instance = Mock()
            mock_pm.return_value = mock_pm_instance

            mock_root = Mock()
            gui = GBTextExtractorGUI(mock_root)

            # Проверяем что PM компонент инициализирован
            self.assertIsNotNone(gui.plugin_manager)
            self.assertEqual(gui.plugin_manager, mock_pm_instance)

    def test_tmx_handler_component(self):
        """Тест компонента TMX обработчика"""
        from gui.main_window import GBTextExtractorGUI

        # Мокаем все зависимости
        with mock.patch('gui.main_window.I18N'), \
             mock.patch('gui.main_window.PluginManager'), \
             mock.patch('gui.main_window.GuideManager'), \
             mock.patch('gui.main_window.MachineTranslation'), \
             mock.patch('gui.main_window.TMXHandler') as mock_tmx, \
             mock.patch.object(GBTextExtractorGUI, '_set_app_icon'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_ui'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_context_menu'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_search'), \
             mock.patch.object(GBTextExtractorGUI, '_setup_drag_drop'), \
             mock.patch.object(GBTextExtractorGUI, 'show_warning_dialog'), \
             mock.patch.object(GBTextExtractorGUI, 'load_saved_settings'), \
             mock.patch.object(GBTextExtractorGUI, '_init_default_settings'):

            mock_tmx_instance = Mock()
            mock_tmx.return_value = mock_tmx_instance

            mock_root = Mock()
            gui = GBTextExtractorGUI(mock_root)

            # Проверяем что TMX компонент инициализирован
            self.assertIsNotNone(gui.tmx_handler)
            self.assertEqual(gui.tmx_handler, mock_tmx_instance)


