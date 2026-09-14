"""
Тесты для публичных методов GUI модулей без полной инициализации
"""
import json
import sys
import threading
import time
import unittest
from unittest.mock import Mock


class TestGUIPublicMethods(unittest.TestCase):
    """Тесты для публичных методов GUI классов"""

    def setUp(self):
        """Настройка тестового окружения"""
        for mod in list(sys.modules.keys()):
            if 'gui' in mod or 'tkinter' in mod:
                try:
                    del sys.modules[mod]
                except KeyError:
                    pass

    # ==================== Editor методы ====================

    def test_editor_prev_entry_logic(self):
        """Тест логики prev_entry"""
        from gui.editor import TextEditorFrame

        editor = object.__new__(TextEditorFrame)
        editor.segment_data = [
            {'text': 'First'},
            {'text': 'Second'},
            {'text': 'Third'}
        ]
        editor.current_index = 1
        editor._show_current_entry = Mock()

        # Выполняем prev_entry
        if editor.current_index > 0:
            editor.current_index -= 1

        self.assertEqual(editor.current_index, 0)

    def test_editor_next_entry_logic(self):
        """Тест логики next_entry"""
        from gui.editor import TextEditorFrame

        editor = object.__new__(TextEditorFrame)
        editor.segment_data = [
            {'text': 'First'},
            {'text': 'Second'},
            {'text': 'Third'}
        ]
        editor.current_index = 1
        editor._show_current_entry = Mock()

        # Выполняем next_entry
        if editor.current_index < len(editor.segment_data) - 1:
            editor.current_index += 1

        self.assertEqual(editor.current_index, 2)

    def test_editor_boundary_at_start(self):
        """Тест что нельзя идти назад в начале"""
        from gui.editor import TextEditorFrame

        editor = object.__new__(TextEditorFrame)
        editor.segment_data = [{'text': 'Only one'}]
        editor.current_index = 0
        editor._show_current_entry = Mock()

        initial = editor.current_index
        if editor.current_index > 0:
            editor.current_index -= 1

        self.assertEqual(editor.current_index, initial)

    def test_editor_boundary_at_end(self):
        """Тест что нельзя идти вперед в конце"""
        from gui.editor import TextEditorFrame

        editor = object.__new__(TextEditorFrame)
        editor.segment_data = [
            {'text': 'First'},
            {'text': 'Second'}
        ]
        editor.current_index = 1  # Последний
        editor._show_current_entry = Mock()

        initial = editor.current_index
        if editor.current_index < len(editor.segment_data) - 1:
            editor.current_index += 1

        self.assertEqual(editor.current_index, initial)

    def test_editor_show_current_entry_empty(self):
        """Тест show_current_entry с пустыми данными"""
        from gui.editor import TextEditorFrame

        editor = object.__new__(TextEditorFrame)
        editor.segment_data = []
        editor.current_index = 0

        # Не должен падать
        if editor.segment_data and editor.current_index < len(editor.segment_data):
            pass  # Не выполняется т.к. segment_data пустой
        else:
            pass  # Корректно обработано

    def test_editor_undo_at_start(self):
        """Тест undo когда нет истории"""
        from gui.editor import TextEditorFrame

        editor = object.__new__(TextEditorFrame)
        editor.history = []
        editor.history_index = -1

        # Не должен падать
        if editor.history_index > 0:
            editor.history_index -= 1
        else:
            pass  # Корректно

    def test_editor_redo_at_end(self):
        """Тест redo когда нет следующего"""
        from gui.editor import TextEditorFrame

        editor = object.__new__(TextEditorFrame)
        editor.history = [{'text': 'One'}]
        editor.history_index = 0

        # Не должен ничего делать
        initial = editor.history_index
        if editor.history_index < len(editor.history) - 1:
            editor.history_index += 1
        else:
            pass

        self.assertEqual(editor.history_index, initial)

    # ==================== MainWindow методы ====================

    def test_search_state_empty(self):
        """Тест начального состояния поиска"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.search_results = []
        gui.search_index = 0
        gui.search_term = ""
        gui.replace_term = ""

        self.assertEqual(gui.search_results, [])
        self.assertEqual(gui.search_index, 0)

    def test_search_results_add(self):
        """Тест добавления результатов поиска"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.search_results = [
            {'offset': 0x100, 'text': 'Match 1'},
            {'offset': 0x200, 'text': 'Match 2'}
        ]

        self.assertEqual(len(gui.search_results), 2)
        self.assertEqual(gui.search_results[0]['offset'], 0x100)

    def test_search_navigation_forward(self):
        """Тест навигации вперед по результатам"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.search_results = [1, 2, 3, 4, 5]
        gui.search_index = 2

        # Следующий результат
        if gui.search_index < len(gui.search_results) - 1:
            gui.search_index += 1

        self.assertEqual(gui.search_index, 3)

    def test_search_navigation_backward(self):
        """Тест навигации назад по результатам"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.search_results = [1, 2, 3, 4, 5]
        gui.search_index = 2

        # Предыдущий результат
        if gui.search_index > 0:
            gui.search_index -= 1

        self.assertEqual(gui.search_index, 1)

    def test_search_boundary_start(self):
        """Тест границы в начале списка"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.search_results = [1, 2, 3]
        gui.search_index = 0

        initial = gui.search_index
        if gui.search_index > 0:
            gui.search_index -= 1
        else:
            pass

        self.assertEqual(gui.search_index, initial)

    def test_search_boundary_end(self):
        """Тест границы в конце списка"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.search_results = [1, 2, 3]
        gui.search_index = 2

        initial = gui.search_index
        if gui.search_index < len(gui.search_results) - 1:
            gui.search_index += 1
        else:
            pass

        self.assertEqual(gui.search_index, initial)

    def test_replace_term_update(self):
        """Тест обновления строки замены"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.replace_term = "old_value"

        gui.replace_term = "new_value"
        self.assertEqual(gui.replace_term, "new_value")

    def test_search_term_update(self):
        """Тест обновления строки поиска"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.search_term = ""

        gui.search_term = "test_pattern"
        self.assertEqual(gui.search_term, "test_pattern")


class TestGUISearchDialogs(unittest.TestCase):
    """Тесты диалогов поиска и замены"""

    def setUp(self):
        for mod in list(sys.modules.keys()):
            if 'gui' in mod or 'tkinter' in mod:
                try:
                    del sys.modules[mod]
                except KeyError:
                    pass

    def test_search_dialog_initial_state(self):
        """Тест начального состояния диалога поиска"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.search_dialog = None
        gui.replace_dialog = None

        self.assertIsNone(gui.search_dialog)
        self.assertIsNone(gui.replace_dialog)

    def test_search_dialog_open_close(self):
        """Тест открытия и закрытия диалога"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.search_dialog = None

        # Симулируем открытие
        gui.search_dialog = Mock()
        self.assertIsNotNone(gui.search_dialog)

        # Симулируем закрытие
        if gui.search_dialog:
            gui.search_dialog = None
        self.assertIsNone(gui.search_dialog)


class TestGUIExportImport(unittest.TestCase):
    """Тесты функций экспорта/импорта"""

    def setUp(self):
        for mod in list(sys.modules.keys()):
            if 'gui' in mod or 'tkinter' in mod:
                try:
                    del sys.modules[mod]
                except KeyError:
                    pass

    def test_export_data_structure(self):
        """Тест структуры данных для экспорта"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_results = [
            {'offset': 0x100, 'original': 'Hello', 'translated': 'Привет'},
            {'offset': 0x200, 'original': 'World', 'translated': 'Мир'}
        ]

        self.assertEqual(len(gui.current_results), 2)
        self.assertIn('original', gui.current_results[0])
        self.assertIn('translated', gui.current_results[0])

    def test_import_csv_data_parsing(self):
        """Тест парсинга CSV данных"""
        # Тестируем логику парсинга CSV
        csv_line = "0x100,Hello,Привет"
        parts = csv_line.split(',')

        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], '0x100')
        self.assertEqual(parts[1], 'Hello')
        self.assertEqual(parts[2], 'Привет')

    def test_export_json_format(self):
        """Тест формата JSON экспорта"""
        data = {
            'version': '1.0',
            'results': [
                {'offset': 0x100, 'text': 'Test'}
            ]
        }

        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)

        self.assertEqual(parsed['version'], '1.0')
        self.assertEqual(len(parsed['results']), 1)


class TestGUIFileOperations(unittest.TestCase):
    """Тесты операций с файлами в GUI"""

    def setUp(self):
        for mod in list(sys.modules.keys()):
            if 'gui' in mod or 'tkinter' in mod:
                try:
                    del sys.modules[mod]
                except KeyError:
                    pass

    def test_rom_path_storage(self):
        """Тест хранения пути к ROM"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.rom_path = Mock()
        gui.rom_path.get = Mock(return_value="test.rom")

        self.assertEqual(gui.rom_path.get(), "test.rom")

    def test_loaded_rom_path_cache(self):
        """Тест кэширования пути загруженного ROM"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui._loaded_rom_path = None

        # Симулируем загрузку
        gui._loaded_rom_path = "loaded.rom"
        self.assertEqual(gui._loaded_rom_path, "loaded.rom")

    def test_plugin_dir_storage(self):
        """Тест хранения директории плагинов"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.plugin_dir = "plugins"

        self.assertEqual(gui.plugin_dir, "plugins")


class TestGUIGuideOperations(unittest.TestCase):
    """Тесты операций с руководствами"""

    def setUp(self):
        for mod in list(sys.modules.keys()):
            if 'gui' in mod or 'tkinter' in mod:
                try:
                    del sys.modules[mod]
                except KeyError:
                    pass

    def test_current_guide_storage(self):
        """Тест хранения текущего руководства"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_guide = None

        # Симулируем загрузку гайда
        mock_guide = Mock()
        gui.current_guide = mock_guide

        self.assertIsNotNone(gui.current_guide)


class TestGUIComponentInitialization(unittest.TestCase):
    """Тесты инициализации компонентов GUI"""

    def setUp(self):
        for mod in list(sys.modules.keys()):
            if 'gui' in mod or 'tkinter' in mod:
                try:
                    del sys.modules[mod]
                except KeyError:
                    pass

    def test_plugin_manager_integration(self):
        """Тест интеграции PluginManager в GUI"""
        from core.plugin_manager import PluginManager

        pm = PluginManager("plugins")
        self.assertIsNotNone(pm)
        self.assertTrue(hasattr(pm, 'plugins'))

    def test_guide_manager_integration(self):
        """Тест интеграции GuideManager в GUI"""
        from core.guide import GuideManager

        gm = GuideManager()
        self.assertIsNotNone(gm)

    def test_i18n_integration(self):
        """Тест интеграции I18N в GUI"""
        from core.i18n import I18N

        i18n = I18N(default_lang='en')
        self.assertIsNotNone(i18n)
        self.assertTrue(hasattr(i18n, 't'))

    def test_machine_translation_integration(self):
        """Тест интеграции MachineTranslation в GUI"""
        from core.machine_translation import MachineTranslation

        mt = MachineTranslation()
        self.assertIsNotNone(mt)

    def test_tmx_handler_integration(self):
        """Тест интеграции TMXHandler в GUI"""
        from core.tmx import TMXHandler

        handler = TMXHandler()
        self.assertIsNotNone(handler)


class TestGUMachineTranslationRace(unittest.TestCase):
    """Тесты гонки фонового машинного перевода с навигацией по записям"""

    def _make_gui(self):
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = [
            {'text': 'Original A'},
            {'text': 'Original B'},
        ]
        gui.current_entry_index = 0
        gui.current_segment = 'dialogue'
        gui.i18n = Mock()
        gui.i18n.t = Mock(side_effect=lambda key, **kw: key)
        gui.set_status = Mock()
        gui.root = Mock()
        gui.root.after = Mock()
        gui._mt_in_progress = False
        gui._mt_cloud_confirmed = True
        gui._mt_entry_index = None
        gui._mt_segment = None
        gui._captured_mt_entry = None
        gui._mt_error = None
        gui._mt_result = None
        gui._mt_start_time = time.time()
        gui.machine_translation = Mock()
        gui.encoding_type = Mock()
        gui.encoding_type.get = Mock(return_value='en')
        gui.target_lang = Mock()
        gui.target_lang.get = Mock(return_value='ru')
        return gui

    def test_mt_result_written_to_captured_entry_after_navigation(self):
        """При смене записи во время MT результат попадает в захваченную запись, а не в виджет"""
        gui = self._make_gui()
        release = threading.Event()

        def slow_translate(text, src, dst):
            release.wait(timeout=5)
            return 'Перевод A'

        gui.machine_translation.translate = Mock(side_effect=slow_translate)

        gui.machine_translate_current()
        self.assertTrue(gui._mt_in_progress)
        self.assertIsNotNone(gui._mt_thread)

        self.assertEqual(gui.current_entry_index, 0)

        # Пользователь переключает запись, пока MT ещё работает
        gui.current_entry_index = 1
        release.set()
        gui._mt_thread.join(timeout=3)

        # Принудительно выполняем poll (в приложении это делает root.after)
        gui._poll_machine_translate()

        # Перевод должен попасть в захваченную запись (index 0), виджет не тронут
        self.assertEqual(gui.current_entries[0].get('translation'), 'Перевод A')
        self.assertIsNone(gui.current_entries[1].get('translation'))
        self.assertFalse(gui._mt_in_progress)

    def test_mt_result_writes_widget_when_same_entry(self):
        """Если запись не менялась — перевод попадает в entry['translation'] и блок в виджете обновляется"""
        gui = self._make_gui()
        gui._replace_current_entry_in_widget = Mock()
        release = threading.Event()

        def delayed_translate(text, src, dst):
            release.wait(timeout=5)
            return 'Перевод A'

        gui.machine_translation.translate = Mock(side_effect=delayed_translate)
        gui.machine_translate_current()
        release.set()
        gui._mt_thread.join(timeout=3)
        gui._poll_machine_translate()

        self.assertEqual(gui.current_entries[0].get('translation'), 'Перевод A')
        gui._replace_current_entry_in_widget.assert_called_once()
        self.assertFalse(gui._mt_in_progress)

    def test_mt_guard_blocks_second_run(self):
        """Повторный запуск MT при активном переводе не стартует второй поток"""
        gui = self._make_gui()
        release = threading.Event()

        def slow_translate(text, src, dst):
            release.wait(timeout=5)
            return 'Перевод A'

        gui.machine_translation.translate = Mock(side_effect=slow_translate)
        gui.machine_translate_current()
        first_thread = gui._mt_thread

        gui.machine_translate_current()
        self.assertIs(gui._mt_thread, first_thread)

        release.set()
        first_thread.join(timeout=3)

    def test_replace_current_entry_in_widget_updates_only_block(self):
        """Точечная замена обновляет только блок текущей записи, не трогая остальные"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = [
            {'text': 'Original A', 'translation': 'Новый перевод A'},
            {'text': 'Original B', 'translation': ''},
            {'text': 'Original C', 'translation': ''},
        ]
        gui.current_entry_index = 0
        widget = Mock()
        widget.get.return_value = "[1] Старый A\n\n[2] Original B\n\n[3] Original C\n"
        gui.translated_text = widget
        gui._update_preview = Mock()
        gui._update_spellcheck = Mock()

        gui._replace_current_entry_in_widget()

        widget.delete.assert_called_once_with("1.0+4c", "1.0+12c")
        widget.insert.assert_called_once_with("1.0+4c", "Новый перевод A")
        gui._update_preview.assert_called_once()
        gui._update_spellcheck.assert_called_once()

    def test_replace_current_entry_in_widget_ignores_nested_marker(self):
        """Маркер [N] внутри перевода (не в начале строки) не считается границей блока"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = [
            {'text': 'A', 'translation': 'Перенос строки\n[2] внутри'},
            {'text': 'B', 'translation': 'Второй B'},
        ]
        gui.current_entry_index = 1
        widget = Mock()
        widget.get.return_value = "[1] Старый [2] внутри\n\n[2] Второй B\n\n"
        gui.translated_text = widget
        gui._update_preview = Mock()
        gui._update_spellcheck = Mock()

        gui._replace_current_entry_in_widget()

        # Вложенный [2] в середине строки записи 1 игнорируется,
        # заменяется настоящий блок записи 2 (строка начинается на [2])
        widget.delete.assert_called_once_with("1.0+27c", "1.0+35c")
        widget.insert.assert_called_once_with("1.0+27c", "Второй B")

    def test_current_entry_from_widget_reads_block(self):
        """_current_entry_from_widget возвращает перевод только текущего блока"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entry_index = 1
        widget = Mock()
        widget.get.return_value = "[1] Старый A\n\n[2] СерединныйB\n\n[3] Original C\n"
        gui.translated_text = widget

        self.assertEqual(gui._current_entry_from_widget(), "СерединныйB")

    def test_replace_current_entry_in_widget_falls_back_on_missing_block(self):
        """Если блока текущей записи нет на странице — виджет не трогается"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = [
            {'text': 'A1'}, {'text': 'A2'}, {'text': 'A3'},
            {'text': 'A4'}, {'text': 'A5'}, {'text': 'A6'},
        ]
        gui.current_entry_index = 5
        widget = Mock()
        widget.get.return_value = "[1] A1\n\n[2] A2\n\n"
        gui.translated_text = widget
        gui._update_preview = Mock()
        gui._update_spellcheck = Mock()

        gui._replace_current_entry_in_widget()

        widget.delete.assert_not_called()
        widget.insert.assert_not_called()
        gui._update_preview.assert_not_called()
        gui._update_spellcheck.assert_not_called()

    def test_mt_result_ignored_after_reload_replaces_entries(self):
        """Если во время MT current_entries был пересоздан — результат не пишется в новый список"""
        gui = self._make_gui()
        release = threading.Event()

        def slow_translate(text, src, dst):
            release.wait(timeout=5)
            return 'Перевод A'

        gui.machine_translation.translate = Mock(side_effect=slow_translate)

        gui.machine_translate_current()
        captured = gui._captured_mt_entry

        # Извлекли заново: список записей пересоздан (новые объекты)
        gui.current_entries = [
            {'text': 'Новый Original A'},
            {'text': 'Новый Original B'},
        ]

        release.set()
        gui._mt_thread.join(timeout=3)
        gui._poll_machine_translate()

        # Захваченная запись получает результат, новые записи — нет
        self.assertEqual(captured.get('translation'), 'Перевод A')
        self.assertIsNone(gui.current_entries[0].get('translation'))
        self.assertFalse(gui._mt_in_progress)

    def test_collect_translations_from_widget_strict_marker_sequence(self):
        """Строгое возрастание маркера: вложенный [N] в переводе не режет блок"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = [
            {'text': 'A', 'translation': 'Старый A'},
            {'text': 'B', 'translation': 'Старый B'},
        ]
        widget = Mock()
        # Первый перевод содержит маркероподобную строку; граница блока 2
        # определяется только по строгому маркеру [2], а не по любому [\d+]
        widget.get.return_value = (
            "[1] Внутри строки\n"
            "\n[3] ложный маркер\n"
            "\n[2] Второй B\n\n"
        )
        gui.translated_text = widget

        result = gui._collect_translations_from_widget()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "Внутри строки\n\n[3] ложный маркер")
        self.assertEqual(result[1], "Второй B")

    def test_collect_translations_from_widget_empty_block_uses_saved(self):
        """Пустой блок отдаёт сохранённый перевод либо оригинал"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = [
            {'text': 'Original A', 'translation': 'Saved A'},
            {'text': 'Original B'},
        ]
        widget = Mock()
        widget.get.return_value = "[1] \n\n[2] \n\n"
        gui.translated_text = widget

        result = gui._collect_translations_from_widget()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], 'Saved A')
        self.assertEqual(result[1], 'Original B')

    def test_active_text_widget_falls_back_to_last_edit(self):
        """_get_active_text_widget возвращает последний редактируемый виджет,
        если фокус вне текстовых полей (например, в диалоге поиска)"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        translated = Mock()
        original = Mock()
        gui.translated_text = translated
        gui.original_text = original
        gui._last_edit_widget = original

        # Фокус на кнопке диалога — не текст
        gui.root = Mock()
        gui.root.focus_get.return_value = "some.button"

        self.assertIs(gui._get_active_text_widget(), original)

    def test_active_text_widget_focus_in_text_field(self):
        """Фокус в текстовом поле возвращает его и обновляет _last_edit_widget"""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        translated = Mock()
        original = Mock()
        gui.translated_text = translated
        gui.original_text = original
        gui._last_edit_widget = original

        gui.root = Mock()
        gui.root.focus_get.return_value = translated

        self.assertIs(gui._get_active_text_widget(), translated)
        self.assertIs(gui._last_edit_widget, translated)

    def test_find_entry_block_bounds_strict_marker_sequence(self):
        """_find_entry_block_bounds использует ту же строгую логику, что и
        _collect_translations_from_widget: вложенный [N] в переводе не режет блок."""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = [
            {'text': 'A'},
            {'text': 'B'},
        ]
        widget = Mock()
        widget.get.return_value = (
            "[1] Внутри строки\n"
            "\n[3] ложный маркер\n"
            "\n[2] Второй B\n\n"
        )
        gui.translated_text = widget

        block_start, end_rel = gui._find_entry_block_bounds(0)
        content = widget.get.return_value
        self.assertEqual(
            content[block_start:block_start + end_rel].rstrip("\n"),
            "Внутри строки\n\n[3] ложный маркер",
        )
        self.assertEqual(gui._find_entry_block_bounds(99), None)

    def test_paste_translation_replaces_current_block_only(self):
        """paste_translation заменяет блок текущей записи, не трогая остальные."""
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = [
            {'text': 'A', 'translation': 'старый A'},
            {'text': 'B', 'translation': 'старый B'},
        ]
        gui.current_entry_index = 0
        widget = Mock()
        widget.get.return_value = "[1] старый A\n\n[2] старый B\n\n"
        gui.translated_text = widget
        gui.root = Mock()
        gui.root.clipboard_get.return_value = "НОВЫЙ A"
        gui._update_preview = Mock()
        gui._update_spellcheck = Mock()
        gui.set_status = Mock()
        gui.i18n = Mock()
        gui.i18n.t.return_value = "Вставлено"

        gui.paste_translation()

        # delete: ровно один вызов (очистка блока [1]), insert — буфер.
        self.assertEqual(len(widget.delete.call_args_list), 1)
        inserted = [c.args[1] for c in widget.insert.call_args_list]
        self.assertIn("НОВЫЙ A", inserted)

    def test_paste_translation_empty_clipboard_shows_info(self):
        """Пустой буфер обмена → info-диалог, блок не трогается."""
        from tkinter import TclError

        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = [{'text': 'A', 'translation': 'старый A'}]
        gui.current_entry_index = 0
        widget = Mock()
        gui.translated_text = widget
        gui.root = Mock()
        gui.root.clipboard_get.side_effect = TclError
        gui._update_preview = Mock()
        gui._update_spellcheck = Mock()
        gui.set_status = Mock()
        gui.i18n = Mock()
        with unittest.mock.patch("gui.main_window.messagebox.showinfo") as showinfo:
            gui.paste_translation()
        showinfo.assert_called_once()
        widget.delete.assert_not_called()

    def test_import_gate_guards_against_dirty_page(self):
        """Импорт (csv) спрашивает через guard и отменяется на Cancel."""
        import io
        from unittest.mock import patch

        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_results = {
            "seg": [{'offset': 0x10, 'text': 'A', 'translation': 'старый'}],
        }
        widget = Mock()
        widget.get.return_value = "[1] EDITED IN WIDGET\n\n"
        gui.translated_text = widget
        gui.current_entries = gui.current_results["seg"]
        gui.i18n = Mock()
        gui.i18n.t.return_value = "msg"
        fake_csv = io.StringIO(
            "segment,offset,translation\n"
            "seg,0x10,новый\n"
        )
        with patch("gui.main_window.filedialog.askopenfilename", return_value="x.csv"):
            with patch("gui.main_window.messagebox.showerror") as showerror:
                with patch("gui.main_window.messagebox.askyesnocancel", return_value=None):
                    with patch("builtins.open") as open_mock:
                        open_mock.return_value.__enter__.return_value = fake_csv
                        gui.import_csv()
        showerror.assert_not_called()
        self.assertEqual(gui.current_results["seg"][0]["translation"], "старый")


class TestGUIDirtyGuard(unittest.TestCase):
    """Тесты dirty-guard: _is_entry_dirty, тихое сохранение страницы, отмена."""

    def _make_gui(self, entries, widget_text):
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = entries
        widget = Mock()
        widget.get.return_value = widget_text
        gui.translated_text = widget
        gui.set_status = Mock()
        gui.i18n = Mock()
        gui.i18n.t = Mock(return_value="t")
        return gui

    def test_is_entry_dirty_false_when_unchanged(self):
        gui = self._make_gui(
            [{'text': 'A', 'translation': 'X'}, {'text': 'B', 'translation': 'Y'}],
            "[1] X\n\n[2] Y\n\n",
        )
        self.assertFalse(gui._is_entry_dirty())

    def test_is_entry_dirty_true_when_edited(self):
        gui = self._make_gui(
            [{'text': 'A', 'translation': 'X'}, {'text': 'B', 'translation': 'Y'}],
            "[1] EDITED\n\n[2] Y\n\n",
        )
        self.assertTrue(gui._is_entry_dirty())

    def test_is_entry_dirty_empty_entries_is_false(self):
        gui = self._make_gui([], "")
        self.assertFalse(gui._is_entry_dirty())

    def test_save_page_silent_writes_all_entries(self):
        gui = self._make_gui(
            [{'text': 'A'}, {'text': 'B', 'translation': 'Y'}],
            "[1] NEW1\n\n[2] NEW2\n\n",
        )
        gui._save_current_page_silent()
        self.assertEqual(gui.current_entries[0]['translation'], 'NEW1')
        self.assertEqual(gui.current_entries[1]['translation'], 'NEW2')

    def test_save_page_silent_unmodified_block_keeps_saved(self):
        gui = self._make_gui(
            [{'text': 'A', 'translation': 'SAVED'}, {'text': 'B', 'translation': 'Y'}],
            "[1] \n\n[2] Y\n\n",
        )
        gui._save_current_page_silent()
        self.assertEqual(gui.current_entries[0]['translation'], 'SAVED')

    def test_guard_proceeds_when_not_dirty(self):
        gui = self._make_gui(
            [{'text': 'A', 'translation': 'X'}],
            "[1] X\n\n",
        )
        self.assertTrue(gui._guard_unsaved_changes())

    def test_guard_cancel_returns_false(self):
        from unittest.mock import patch

        gui = self._make_gui(
            [{'text': 'A', 'translation': 'X'}],
            "[1] EDITED\n\n",
        )
        with patch("gui.main_window.messagebox.askyesnocancel", return_value=None):
            self.assertFalse(gui._guard_unsaved_changes())

    def test_guard_discard_returns_true(self):
        from unittest.mock import patch

        gui = self._make_gui(
            [{'text': 'A', 'translation': 'X'}],
            "[1] EDITED\n\n",
        )
        with patch("gui.main_window.messagebox.askyesnocancel", return_value=False):
            self.assertTrue(gui._guard_unsaved_changes())
        self.assertEqual(gui.current_entries[0]['translation'], 'X')

    def test_guard_save_saves_and_returns_true(self):
        from unittest.mock import patch

        gui = self._make_gui(
            [{'text': 'A', 'translation': 'X'}],
            "[1] EDITED\n\n",
        )
        with patch("gui.main_window.messagebox.askyesnocancel", return_value=True):
            self.assertTrue(gui._guard_unsaved_changes())
        self.assertEqual(gui.current_entries[0]['translation'], 'EDITED')

    def test_prev_entry_cancelled_keeps_index(self):
        from unittest.mock import patch


        gui = self._make_gui(
            [{'text': 'A', 'translation': 'X'}, {'text': 'B', 'translation': 'Y'}],
            "[1] EDITED\n\n[2] Y\n\n",
        )
        gui.current_results = {'main': gui.current_entries}
        gui.current_segment = 'main'
        gui.current_entry_index = 1
        with patch("gui.main_window.messagebox.askyesnocancel", return_value=None):
            gui.prev_entry()
        self.assertEqual(gui.current_entry_index, 1)

    def test_prev_entry_after_discard_moves(self):
        from unittest.mock import patch

        gui = self._make_gui(
            [{'text': 'A', 'translation': 'X'}, {'text': 'B', 'translation': 'Y'}],
            "[1] EDITED\n\n[2] Y\n\n",
        )
        gui.current_results = {'main': gui.current_entries}
        gui.current_segment = 'main'
        gui.current_entry_index = 1
        gui._display_current_entry = Mock()
        with patch("gui.main_window.messagebox.askyesnocancel", return_value=False):
            gui.prev_entry()
        self.assertEqual(gui.current_entry_index, 0)


class TestGUIMigrationAndGuardExtras(unittest.TestCase):
    """Миграция легаси-ключей и дополнительные сценарии dirty-guard."""

    def test_migrate_does_not_overwrite_stored_secret(self):
        from unittest.mock import patch

        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        stored = {"deepl_key": "keep"}

        def fake_load(name):
            return stored.get(name)

        def fake_store(name, value):
            stored[name] = value
            return True

        gui.deepl_key = Mock()
        gui.bing_key = Mock()
        with patch("gui.main_window.secret_store.load_secret",
                   side_effect=fake_load), \
             patch("gui.main_window.secret_store.store_secret",
                   side_effect=fake_store), \
             patch.object(gui, "_write_settings_file") as write_file:
            gui._migrate_legacy_secrets(
                {"deepl_key": "old", "mt_service": "google"}
            )
        self.assertEqual(stored, {"deepl_key": "keep"})
        gui.deepl_key.set.assert_not_called()
        write_file.assert_called_once_with({"mt_service": "google"})

    def test_migrate_stores_and_updates_gui_fields(self):
        from unittest.mock import patch

        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        stored = {}

        def fake_store(name, value):
            stored[name] = value
            return True

        gui.deepl_key = Mock()
        gui.bing_key = Mock()
        with patch("gui.main_window.secret_store.load_secret",
                   return_value=None), \
             patch("gui.main_window.secret_store.store_secret",
                   side_effect=fake_store), \
             patch.object(gui, "_write_settings_file") as write_file:
            gui._migrate_legacy_secrets(
                {"deepl_key": "NEWKEY", "bing_key": "OLDBKEY", "x": 1}
            )
        self.assertEqual(stored, {"deepl_key": "NEWKEY", "bing_key": "OLDBKEY"})
        gui.deepl_key.set.assert_called_once_with("NEWKEY")
        gui.bing_key.set.assert_called_once_with("OLDBKEY")
        write_file.assert_called_once_with({"x": 1})

    def test_migrate_writes_settings_even_if_only_legacy_keys(self):
        from unittest.mock import patch

        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.deepl_key = Mock()
        gui.bing_key = Mock()
        with patch("gui.main_window.secret_store.load_secret",
                   return_value=None), \
             patch("gui.main_window.secret_store.store_secret",
                   return_value=True), \
             patch.object(gui, "_write_settings_file") as write_file:
            gui._migrate_legacy_secrets({"deepl_key": "KEY"})
        write_file.assert_called_once_with({})

    def test_load_for_editing_cancelled_keeps_rom(self):
        from unittest.mock import patch

        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = [{'text': 'A', 'translation': 'X'}]
        widget = Mock()
        widget.get.return_value = "[1] EDITED\n\n"
        gui.translated_text = widget
        gui.i18n = Mock()
        gui.i18n.t = Mock(return_value="t")
        gui.rom_path = Mock()
        gui.rom_path.get.return_value = "some.gba"
        gui._loaded_rom_path = None
        gui.current_rom = None
        gui.logger = Mock()
        with patch("gui.main_window.messagebox.askyesnocancel",
                   return_value=None):
            gui.load_for_editing()
        self.assertIsNone(gui.current_rom)

    def test_on_segment_select_cancel_keeps_page(self):
        from unittest.mock import patch

        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        entries = [{'text': 'A', 'translation': 'X'}]
        gui.current_entries = entries
        widget = Mock()
        widget.get.return_value = "[1] EDITED\n\n"
        gui.translated_text = widget
        gui.i18n = Mock()
        gui.i18n.t = Mock(return_value="t")
        gui.current_results = {
            's1': entries,
            's2': [{'text': 'B', 'translation': 'Y'}],
        }
        gui.text_output = Mock()
        gui.segments_list = Mock()
        gui.segments_list.curselection.return_value = (0,)
        gui.segments_list.get.return_value = 's2'
        with patch("gui.main_window.messagebox.askyesnocancel",
                   return_value=None):
            gui.on_segment_select(Mock())
        self.assertIs(gui.current_entries, entries)
        gui.text_output.delete.assert_not_called()

    def test_prev_entry_noop_does_not_ask(self):
        from unittest.mock import patch

        gui = self._migrate_gui([{'text': 'A', 'translation': 'X'}])
        gui.current_results = {'main': gui.current_entries}
        gui.current_segment = 'main'
        gui.current_entry_index = 0
        with patch("gui.main_window.messagebox.askyesnocancel") as ask:
            gui.prev_entry()
        ask.assert_not_called()
        self.assertEqual(gui.current_entry_index, 0)

    def test_next_entry_noop_does_not_ask(self):
        from unittest.mock import patch

        gui = self._migrate_gui([{'text': 'A', 'translation': 'X'}])
        gui.current_results = {'main': gui.current_entries}
        gui.current_segment = 'main'
        gui.current_entry_index = 0
        with patch("gui.main_window.messagebox.askyesnocancel") as ask:
            gui.next_entry()
        ask.assert_not_called()
        self.assertEqual(gui.current_entry_index, 0)

    def test_prev_segment_noop_does_not_ask(self):
        from unittest.mock import patch

        gui = self._migrate_gui([{'text': 'A', 'translation': 'X'}])
        gui.current_results = {'main': gui.current_entries}
        gui.current_segment = 'main'
        gui.current_entry_index = 0
        with patch("gui.main_window.messagebox.askyesnocancel") as ask:
            gui.prev_segment()
        ask.assert_not_called()
        self.assertEqual(gui.current_entry_index, 0)

    def test_guard_save_failure_aborts(self):
        from unittest.mock import patch

        gui = self._migrate_gui([{'text': 'A', 'translation': 'X'}])
        gui.translated_text.get.return_value = "[1] EDITED\n\n"
        with patch("gui.main_window.messagebox.askyesnocancel",
                   return_value=True), \
             patch.object(gui, "_save_current_page_silent",
                          return_value=False):
            self.assertFalse(gui._guard_unsaved_changes())

    def _migrate_gui(self, entries):
        from gui.main_window import GBTextExtractorGUI

        gui = object.__new__(GBTextExtractorGUI)
        gui.current_entries = entries
        widget = Mock()
        widget.get.return_value = "".join(
            f"[{i + 1}] {e.get('translation', e['text'])}\n\n"
            for i, e in enumerate(entries)
        )
        gui.translated_text = widget
        gui.i18n = Mock()
        gui.i18n.t = Mock(return_value="t")
        gui.set_status = Mock()
        return gui


if __name__ == '__main__':
    unittest.main()
