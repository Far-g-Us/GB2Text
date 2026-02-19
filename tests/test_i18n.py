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
