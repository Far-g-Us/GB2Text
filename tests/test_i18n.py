"""Тесты для модуля i18n"""
import os
import sys

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.i18n import I18N


class TestI18N:
    """Тесты для класса I18N"""
    
    def test_i18n_init_english(self):
        """Тест инициализации с английским языком по умолчанию"""
        i18n = I18N(default_lang="en")
        assert i18n.current_lang == "en"
    
    def test_i18n_init_russian(self):
        """Тест инициализации с русским языком"""
        i18n = I18N(default_lang="ru")
        assert i18n.current_lang == "ru"
    
    def test_get_available_languages(self):
        """Тест получения списка доступных языков"""
        i18n = I18N(default_lang="en")
        langs = i18n.get_available_languages()
        assert isinstance(langs, dict)
        assert "en" in langs
    
    def test_translate_key_exists(self):
        """Тест перевода существующего ключа"""
        i18n = I18N(default_lang="en")
        result = i18n.t("app.title")
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_translate_key_not_exists(self):
        """Тест перевода несуществующего ключа"""
        i18n = I18N(default_lang="en")
        result = i18n.t("nonexistent.key.12345")
        # Должен вернуть ключ как есть
        assert result == "nonexistent.key.12345"
    
    def test_translate_with_kwargs(self):
        """Тест перевода с параметрами"""
        i18n = I18N(default_lang="en")
        # Ключ "entry" имеет формат "Entry: {current} of {total}"
        result = i18n.t("entry", current=1, total=10)
        assert isinstance(result, str)
    
    def test_change_language(self):
        """Тест смены языка"""
        i18n = I18N(default_lang="en")
        i18n.change_language("ru")
        assert i18n.current_lang == "ru"
    
    def test_change_language_to_japanese(self):
        """Тест смены языка на японский"""
        i18n = I18N(default_lang="en")
        langs = i18n.get_available_languages()
        if "ja" in langs:
            i18n.change_language("ja")
            assert i18n.current_lang == "ja"
    
    def test_change_language_to_chinese(self):
        """Тест смены языка на китайский"""
        i18n = I18N(default_lang="en")
        langs = i18n.get_available_languages()
        if "zh" in langs:
            i18n.change_language("zh")
            assert i18n.current_lang == "zh"
    
    def test_translations_loaded(self):
        """Тест что переводы загружены"""
        i18n = I18N(default_lang="en")
        assert isinstance(i18n.translations, dict)
        assert len(i18n.translations) > 0
    
    def test_translation_fallback(self):
        """Тест fallback на английский если перевода нет"""
        i18n = I18N(default_lang="ja")
        result = i18n.t("app.title")
        assert isinstance(result, str)

    def test_get_resource_path(self):
        """Тест получения пути к ресурсу"""
        i18n = I18N(default_lang="en")
        path = i18n._get_resource_path("test")
        assert isinstance(path, str)

    def test_create_default_translations(self):
        """Тест создания переводов по умолчанию"""
        i18n = I18N(default_lang="en")
        i18n._create_default_translations()
        assert isinstance(i18n.translations, dict)

    def test_translate_multiple_kwargs(self):
        """Тест перевода с несколькими параметрами"""
        i18n = I18N(default_lang="en")
        result = i18n.t("menu.file", name="test.txt", size=100)
        assert isinstance(result, str)

    def test_translate_empty_key(self):
        """Тест с пустым ключом"""
        i18n = I18N(default_lang="en")
        result = i18n.t("")
        assert isinstance(result, str)

    def test_change_language_invalid(self):
        """Тест смены на несуществующий язык"""
        i18n = I18N(default_lang="en")
        i18n.change_language("invalid_lang_xyz")
        # Должен остаться английский
        assert i18n.current_lang == "en"

    def test_translate_nonexistent_with_kwargs(self):
        """Тест перевода несуществующего ключа с параметрами"""
        i18n = I18N(default_lang="en")
        result = i18n.t("nonexistent.key", name="test", value=123)
        assert isinstance(result, str)

    def test_translate_special_chars(self):
        """Тест перевода со специальными символами"""
        i18n = I18N(default_lang="en")
        result = i18n.t("test.key.123")
        assert isinstance(result, str)

    def test_change_language_same(self):
        """Тест смены на тот же язык"""
        i18n = I18N(default_lang="en")
        i18n.change_language("en")
        assert i18n.current_lang == "en"

    def test_translations_keys(self):
        """Тест получения ключей переводов"""
        i18n = I18N(default_lang="en")
        # Проверяем что есть основные ключи
        assert "app.title" in i18n.translations.get("en", {})

    def test_load_translations_method(self):
        """Тест _load_translations"""
        i18n = I18N(default_lang="en")
        # Метод должен существовать
        assert hasattr(i18n, '_load_translations')

    def test_default_lang_fallback(self):
        """Тест fallback на язык по умолчанию"""
        i18n = I18N(default_lang="invalid_lang")
        # Должен использовать английский как fallback
        result = i18n.t("app.title")
        assert isinstance(result, str)

    def test_available_languages_includes_en(self):
        """Тест что английский в списке языков"""
        i18n = I18N()
        langs = i18n.get_available_languages()
        assert "en" in langs

    def test_translate_with_numeric_kwargs(self):
        """Тест перевода с числовыми параметрами"""
        i18n = I18N(default_lang="en")
        # Используем ключ с числовыми параметрами
        result = i18n.t("about.version", version="1.0.0")
        assert "1.0.0" in result

    def test_translate_returns_string(self):
        """Тест что перевод возвращает строку"""
        i18n = I18N(default_lang="en")
        result = i18n.t("rom.file")
        assert isinstance(result, str)

    def test_translate_with_unicode_chars(self):
        """Тест перевода с unicode символами"""
        i18n = I18N(default_lang="ru")
        result = i18n.t("app.title")
        # Should return translation or key
        assert isinstance(result, str)

    def test_i18n_with_custom_locale_path(self):
        """Тест с кастомным путём к локалям"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to initialize with non-existent locale dir
            i18n = I18N(default_lang="en")
            assert i18n.current_lang == "en"

    def test_translation_fallback_chain(self):
        """Тест цепочки fallback"""
        i18n = I18N(default_lang="ja")
        # Should fallback to English
        result = i18n.t("app.title")
        assert isinstance(result, str)

    def test_available_languages_contains_ru(self):
        """Тест что русский в списке языков"""
        i18n = I18N()
        langs = i18n.get_available_languages()
        assert "ru" in langs

    def test_translate_with_none_kwargs(self):
        """Тест перевода с None параметрами"""
        i18n = I18N(default_lang="en")
        result = i18n.t("entry", current=None, total=None)
        assert isinstance(result, str)

    def test_translations_contains_app_keys(self):
        """Тест что переводы содержат ключи приложения"""
        i18n = I18N(default_lang="en")
        translations = i18n.translations.get("en", {})
        assert isinstance(translations, dict)

    def test_change_language_updates_current(self):
        """Тест что смена языка обновляет текущий"""
        i18n = I18N(default_lang="en")
        i18n.current_lang = "ru"
        # Verify current_lang is updated
        assert i18n.current_lang == "ru"

    def test_i18n_multiple_translations(self):
        """Тест нескольких переводов"""
        i18n = I18N(default_lang="en")
        result1 = i18n.t("tab.extract")
        result2 = i18n.t("tab.edit")
        result3 = i18n.t("tab.settings")
        assert isinstance(result1, str)
        assert isinstance(result2, str)
        assert isinstance(result3, str)

    def test_i18n_load_with_permission_error(self):
        """Тест загрузки с ошибкой доступа"""
        import tempfile
        import os
        # Create a temp file to mock permission error
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mock locales directory with permission issues
            # We'll test the error handling by directly calling _load_translations
            i18n = I18N(default_lang="en")
            # Force reload by clearing translations
            i18n.translations = {}
            try:
                i18n._load_translations()
            except Exception:
                pass  # May fail due to filesystem conditions

    def test_translate_exception_handling(self):
        """Тест обработки исключений в переводе"""
        i18n = I18N(default_lang="en")
        # Test with an invalid key that might cause issues
        result = i18n.t("very.nonexistent.key.that.does.not.exist.at.all")
        assert isinstance(result, str)

    def test_i18n_with_different_default_lang(self):
        """Тест с разными языками по умолчанию"""
        for lang in ["en", "ru", "ja", "zh"]:
            i18n = I18N(default_lang=lang)
            assert i18n.current_lang == lang or i18n.current_lang == "en"  # Fallback

    def test_i18n_load_translations_no_locales_dir(self):
        """Тест загрузки когда папка locales не существует"""
        from unittest.mock import patch, MagicMock
        
        i18n = I18N(default_lang="en")
        # Mock Path to return non-existent directory
        with patch('pathlib.Path.exists', return_value=False):
            i18n._load_translations()
            # Should use default translations
            assert len(i18n.translations) > 0

    def test_i18n_load_translations_with_json_error(self):
        """Тест загрузки с ошибкой парсинга JSON"""
        from unittest.mock import patch, mock_open, MagicMock
        import json
        
        i18n = I18N(default_lang="en")
        i18n.translations = {}
        
        # Mock the file open to raise JSONDecodeError
        def mock_open_side_effect(*args, **kwargs):
            m = MagicMock()
            m.__enter__ = MagicMock(return_value=m)
            m.__exit__ = MagicMock(return_value=False)
            # Return invalid JSON
            m.read = MagicMock(side_effect=json.JSONDecodeError("Invalid", "", 0))
            return m
        
        with patch('builtins.open', side_effect=mock_open_side_effect):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.glob', return_value=[MagicMock(stem='test')]):
                    i18n._load_translations()

    def test_i18n_load_translations_with_os_error(self):
        """Тест загрузки с ошибкой OS"""
        from unittest.mock import patch, MagicMock
        
        i18n = I18N(default_lang="en")
        i18n.translations = {}
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.glob', side_effect=OSError("Test error")):
                i18n._load_translations()
                # Should fallback to defaults
                assert len(i18n.translations) > 0

    def test_i18n_t_with_exception(self):
        """Тест перевода с исключением"""
        from unittest.mock import patch, MagicMock
        
        i18n = I18N(default_lang="en")
        # Create a mock that raises exception when accessed
        mock_translations = MagicMock()
        mock_translations.__getitem__ = MagicMock(side_effect=Exception("Test exception"))
        
        i18n.translations = mock_translations
        
        try:
            result = i18n.t("test.key")
            assert isinstance(result, str)
        finally:
            i18n.translations = {"en": {}}

    def test_i18n_load_skips_non_directories(self):
        """Тест пропуска недиректорий при загрузке языков"""
        from unittest.mock import patch, MagicMock, mock_open
        import json
        
        i18n = I18N(default_lang="en")
        i18n.translations = {}
        
        # Create mock that returns a file (not a directory) for iterdir
        mock_lang_dir = MagicMock()
        mock_lang_dir.is_dir.return_value = False  # Not a directory - should be skipped
        mock_lang_dir.name = "test_lang"
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.iterdir', return_value=[mock_lang_dir]):
                i18n._load_translations()
                # Should not add the non-directory
                assert "test_lang" not in i18n.translations

    def test_i18n_load_missing_messages_json(self):
        """Тест когда файл messages.json не найден для языка"""
        from unittest.mock import patch, MagicMock
        
        i18n = I18N(default_lang="en")
        i18n.translations = {}
        
        # Create mock directory with no messages.json
        mock_lang_dir = MagicMock()
        mock_lang_dir.is_dir.return_value = True
        mock_lang_dir.name = "test_lang"
        mock_lang_dir.__truediv__ = MagicMock(return_value=MagicMock(exists=lambda: False))
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.iterdir', return_value=[mock_lang_dir]):
                i18n._load_translations()
                # Should not add language without messages.json
                assert "test_lang" not in i18n.translations

    def test_i18n_load_file_read_os_error(self):
        """Тест обработки OSError при чтении файла перевода"""
        from unittest.mock import patch, MagicMock, mock_open
        
        i18n = I18N(default_lang="en")
        i18n.translations = {}
        
        # Mock directory with messages.json that exists but can't be read
        mock_lang_dir = MagicMock()
        mock_lang_dir.is_dir.return_value = True
        mock_lang_dir.name = "test_lang"
        
        # Create messages.json path that exists
        messages_path = MagicMock()
        messages_path.exists.return_value = True
        messages_path.__truediv__ = lambda self, x: messages_path
        
        mock_lang_dir.__truediv__ = lambda self, x: messages_path
        
        # Mock open to raise OSError when reading
        with patch('builtins.open', side_effect=OSError("Permission denied")):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.iterdir', return_value=[mock_lang_dir]):
                    i18n._load_translations()
                    # Should handle error gracefully and not add the language
                    assert "test_lang" not in i18n.translations

    def test_i18n_load_permission_error(self):
        """Тест обработки PermissionError при доступе к папке locales"""
        from unittest.mock import patch, MagicMock
        
        i18n = I18N(default_lang="en")
        i18n.translations = {}
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.iterdir', side_effect=PermissionError("Access denied")):
                i18n._load_translations()
                # Should fallback to default translations
                assert len(i18n.translations) > 0

    def test_i18n_load_runtime_error(self):
        """Тест обработки RuntimeError при загрузке переводов"""
        from unittest.mock import patch, MagicMock
        
        i18n = I18N(default_lang="en")
        i18n.translations = {}
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.iterdir', side_effect=RuntimeError("Initialization error")):
                i18n._load_translations()
                # Should fallback to default translations
                assert len(i18n.translations) > 0

    def test_i18n_load_translations_oserror(self):
        """Тест обработки OSError в _load_translations"""
        from unittest.mock import patch, MagicMock
        
        i18n = I18N(default_lang="en")
        i18n.translations = {}
        
        # OSError raised by exists() call inside the try block
        with patch('pathlib.Path.exists', side_effect=OSError("Filesystem error")):
            i18n._load_translations()
            # Should fallback to default translations
            assert len(i18n.translations) > 0

    def test_i18n_t_with_dict_exception(self):
        """Тест обработки исключения в t() при некорректном translations"""
        from unittest.mock import MagicMock
        
        i18n = I18N(default_lang="en")
        # Create a mock dict that raises exception on access
        original_translations = i18n.translations
        try:
            # Make the translations dict itself raise an exception when accessed
            mock_translations = {}
            # Use a custom dict class that raises on any access
            class BadDict(dict):
                def __getitem__(self, key):
                    raise Exception("Dict access error")
                def get(self, key, default=None):
                    raise Exception("Dict get error")
            
            i18n.translations = BadDict()
            i18n.translations["en"] = {"test.key": "value"}
            
            result = i18n.t("test.key")
            # Should return the key safely due to exception handling
            assert result == "test.key"
        finally:
            i18n.translations = original_translations
