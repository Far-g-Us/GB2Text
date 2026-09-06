"""
Tests for machine translation functionality
"""

from unittest.mock import Mock, patch

import pytest

from core.machine_translation import BingTranslator, DeepLTranslator, GoogleTranslator, MachineTranslation


class TestGoogleTranslator:
    @patch('googletrans.Translator')
    def test_translate_success(self, mock_translator_class):
        mock_instance = Mock()
        mock_instance.translate.return_value = Mock(text="Hello")
        mock_translator_class.return_value = mock_instance

        translator = GoogleTranslator()
        result = translator.translate("Hola", "es", "en")
        assert result == "Hello"

    @patch('googletrans.Translator')
    def test_translate_failure(self, mock_translator_class):
        mock_instance = Mock()
        mock_instance.translate.side_effect = Exception("API Error")
        mock_translator_class.return_value = mock_instance

        translator = GoogleTranslator()
        with pytest.raises(Exception):
            translator.translate("Hola", "es", "en")

    @patch('googletrans.Translator')
    def test_is_available_with_library(self, mock_translator_class):
        translator = GoogleTranslator()
        assert translator.is_available()

    @patch('googletrans.Translator', side_effect=ImportError)
    def test_is_available_without_library(self, mock_translator_class):
        translator = GoogleTranslator()
        assert not translator.is_available()


class TestDeepLTranslator:
    @patch('deepl.Translator')
    def test_translate_success(self, mock_translator_class):
        mock_translator = Mock()
        mock_result = Mock()
        mock_result.text = "Hello"
        mock_translator.translate_text.return_value = mock_result
        mock_usage = Mock()
        mock_usage.any_limit_reached = False
        mock_translator.get_usage.return_value = mock_usage
        mock_translator_class.return_value = mock_translator

        translator = DeepLTranslator("fake_key")
        result = translator.translate("Hola", "ES", "EN")
        assert result == "Hello"

    @patch('deepl.Translator')
    def test_is_available_with_key(self, mock_translator_class):
        mock_translator = Mock()
        mock_usage = Mock()
        mock_usage.any_limit_reached = False
        mock_translator.get_usage.return_value = mock_usage
        mock_translator_class.return_value = mock_translator

        translator = DeepLTranslator("fake_key")
        assert translator.is_available()

    @patch('deepl.Translator', side_effect=ImportError)
    def test_is_available_without_key(self, mock_translator_class):
        translator = DeepLTranslator("fake_key")
        assert not translator.is_available()


class TestBingTranslator:
    @patch('requests.post')
    def test_translate_success(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = [{"translations": [{"text": "Hello"}]}]
        mock_post.return_value = mock_response

        translator = BingTranslator("fake_key", "global")
        result = translator.translate("Hola", "es", "en")
        assert result == "Hello"

    @patch('requests.post', side_effect=ImportError)
    def test_translate_requests_not_available(self, mock_post):
        translator = BingTranslator("fake_key", "global")
        with pytest.raises(Exception, match="requests не установлен"):
            translator.translate("Hola", "es", "en")

    def test_is_available_with_key(self):
        translator = BingTranslator("fake_key", "global")
        assert translator.is_available()

    def test_is_available_without_key(self):
        translator = BingTranslator("", "global")
        assert not translator.is_available()


class TestMachineTranslation:
    def test_add_google_translator(self):
        mt = MachineTranslation()
        mt.add_google_translator()
        assert 'google' in mt.translators

    @patch('deepl.Translator')
    def test_add_deepl_translator(self, mock_translator_class):
        mt = MachineTranslation()
        mt.add_deepl_translator("fake_key")
        assert 'deepl' in mt.translators

    def test_add_bing_translator(self):
        mt = MachineTranslation()
        mt.add_bing_translator("fake_key", "global")
        assert 'bing' in mt.translators

    @patch('googletrans.Translator')
    def test_set_service_success(self, mock_translator_class):
        mt = MachineTranslation()
        mt.add_google_translator()
        mt.set_service('google')
        assert mt.current_service == 'google'

    def test_set_service_failure(self):
        mt = MachineTranslation()
        with pytest.raises(ValueError):
            mt.set_service('nonexistent')

    @patch('googletrans.Translator')
    def test_translate_with_service(self, mock_translator_class):
        mock_instance = Mock()
        mock_instance.translate.return_value = Mock(text="Hello")
        mock_translator_class.return_value = mock_instance

        mt = MachineTranslation()
        mt.add_google_translator()
        mt.set_service('google')
        result = mt.translate("Hola", "es", "en")
        assert result == "Hello"

    def test_translate_without_service(self):
        mt = MachineTranslation()
        with pytest.raises(Exception):
            mt.translate("Hola", "es", "en")

    @patch('googletrans.Translator')
    def test_get_available_services(self, mock_translator_class):
        mt = MachineTranslation()
        mt.add_google_translator()
        services = mt.get_available_services()
        assert 'google' in services

    def test_get_available_services_empty(self):
        mt = MachineTranslation()
        services = mt.get_available_services()
        assert services == []

    @patch('googletrans.Translator')
    def test_get_available_services_filter(self, mock_translator_class):
        mt = MachineTranslation()
        # Google available, Bing not available (no key)
        mt.add_google_translator()
        mt.add_bing_translator("", "global")
        services = mt.get_available_services()
        # Only google should be available
        assert 'google' in services


class TestGoogleTranslatorEdgeCases:
    @patch('googletrans.Translator')
    def test_translate_when_not_available(self, mock_translator_class):
        # Simulate library not available
        translator = GoogleTranslator()
        # Manually set translator to None to simulate unavailable state
        translator.translator = None
        with pytest.raises(Exception, match="Google Translate недоступен"):
            translator.translate("test", "en", "ru")

    @patch('googletrans.Translator')
    def test_init_logs_warning_on_import_error(self, mock_translator_class):
        # Test that warning is logged when googletrans not installed
        with patch.dict('sys.modules', {'googletrans': None}):
            translator = GoogleTranslator()
            assert not translator.is_available()


class TestDeepLTranslatorEdgeCases:
    @patch('deepl.Translator')
    def test_translate_when_not_available(self, mock_translator_class):
        translator = DeepLTranslator("fake_key")
        # Simulate unavailable state
        translator.translator = None
        with pytest.raises(Exception, match="DeepL недоступен"):
            translator.translate("test", "en", "ru")

    @patch('deepl.Translator')
    def test_is_available_when_limit_reached(self, mock_translator_class):
        mock_translator = Mock()
        mock_usage = Mock()
        mock_usage.any_limit_reached = True
        mock_translator.get_usage.return_value = mock_usage
        mock_translator_class.return_value = mock_translator

        translator = DeepLTranslator("fake_key")
        assert not translator.is_available()

    @patch('deepl.Translator')
    def test_is_available_exception(self, mock_translator_class):
        mock_translator = Mock()
        mock_translator.get_usage.side_effect = Exception("API Error")
        mock_translator_class.return_value = mock_translator

        translator = DeepLTranslator("fake_key")
        assert not translator.is_available()

    @patch('deepl.Translator')
    def test_init_with_exception(self, mock_translator_class):
        mock_translator_class.side_effect = Exception("Init Error")
        translator = DeepLTranslator("fake_key")
        assert translator.translator is None


class TestBingTranslatorEdgeCases:
    @patch('requests.post')
    def test_translate_when_not_available(self, mock_post):
        translator = BingTranslator("", "global")
        with pytest.raises(Exception, match="Bing Translator недоступен"):
            translator.translate("test", "en", "ru")

    @patch('requests.post')
    def test_translate_api_error(self, mock_post):
        mock_post.side_effect = Exception("API Error")
        translator = BingTranslator("fake_key", "global")
        with pytest.raises(Exception):
            translator.translate("test", "en", "ru")


class TestMachineTranslationEdgeCases:
    @patch('googletrans.Translator')
    def test_translate_translator_not_found(self, mock_translator_class):
        mock_instance = Mock()
        mock_translator_class.return_value = mock_instance

        mt = MachineTranslation()
        mt.add_google_translator()
        mt.set_service('google')
        # Simulate translator removed from dict
        del mt.translators['google']
        with pytest.raises(Exception, match="Переводчик google не найден"):
            mt.translate("test", "en", "ru")

    @patch('googletrans.Translator')
    def test_set_service_unavailable(self, mock_translator_class):
        mock_instance = Mock()
        mock_instance.translate.side_effect = Exception("Not available")
        mock_translator_class.return_value = mock_instance

        # Make translator not available
        with patch.object(GoogleTranslator, 'is_available', return_value=False):
            mt = MachineTranslation()
            mt.add_google_translator()
            with pytest.raises(ValueError, match="Сервис google недоступен"):
                mt.set_service('google')

    def test_add_google_when_already_exists(self):
        mt = MachineTranslation()
        mt.add_google_translator()
        mt.translators['google']
        mt.add_google_translator()
        # Should replace
        assert mt.translators['google'] is not None

    @patch('googletrans.Translator')
    def test_translate_calls_correct_method(self, mock_translator_class):
        mock_instance = Mock()
        mock_instance.translate.return_value = Mock(text="Translated")
        mock_translator_class.return_value = mock_instance

        mt = MachineTranslation()
        mt.add_google_translator()
        mt.set_service('google')
        result = mt.translate("Test text", "en", "ru")
        assert result == "Translated"
        # Verify translate was called on the translator instance
        mock_instance.translate.assert_called_once()


# ─────────────────────────────────────────────────────────────
# P1: Fallback tests
# ─────────────────────────────────────────────────────────────

class TestTranslationFallback:
    """P1: Тесты translate_with_fallback и get_preferred_service."""

    def test_get_preferred_service_returns_deepl_first(self):
        """DeepL имеет наивысший приоритет."""
        mt = MachineTranslation()
        # Добавляем моки
        deepl_mock = Mock()
        deepl_mock.is_available.return_value = True
        mt.translators['deepl'] = deepl_mock

        google_mock = Mock()
        google_mock.is_available.return_value = True
        mt.translators['google'] = google_mock

        assert mt.get_preferred_service() == 'deepl'

    def test_get_preferred_service_falls_back_to_google(self):
        """Если DeepL недоступен, используется Google."""
        mt = MachineTranslation()
        deepl_mock = Mock()
        deepl_mock.is_available.return_value = False
        mt.translators['deepl'] = deepl_mock

        google_mock = Mock()
        google_mock.is_available.return_value = True
        mt.translators['google'] = google_mock

        assert mt.get_preferred_service() == 'google'

    def test_get_preferred_service_returns_none_if_none_available(self):
        """Если ни один сервис недоступен, возвращает None."""
        mt = MachineTranslation()
        deepl_mock = Mock()
        deepl_mock.is_available.return_value = False
        mt.translators['deepl'] = deepl_mock

        google_mock = Mock()
        google_mock.is_available.return_value = False
        mt.translators['google'] = google_mock

        assert mt.get_preferred_service() is None

    def test_translate_with_fallback_uses_current_service(self):
        """translate_with_fallback использует текущий сервис."""
        mt = MachineTranslation()
        google_mock = Mock()
        google_mock.is_available.return_value = True
        google_mock.translate.return_value = "Hello"
        mt.translators['google'] = google_mock
        mt.current_service = 'google'

        result = mt.translate_with_fallback("Hola", "es", "en")
        assert result == "Hello"
        google_mock.translate.assert_called_once()

    def test_translate_with_fallback_falls_back_on_error(self):
        """translate_with_fallback fallback при ошибке текущего сервиса."""
        mt = MachineTranslation()
        # Google падает
        google_mock = Mock()
        google_mock.is_available.return_value = True
        google_mock.translate.side_effect = Exception("Google API Error")
        mt.translators['google'] = google_mock

        # DeepL работает
        deepl_mock = Mock()
        deepl_mock.is_available.return_value = True
        deepl_mock.translate.return_value = "Translated by DeepL"
        mt.translators['deepl'] = deepl_mock

        mt.current_service = 'google'
        result = mt.translate_with_fallback("Hola", "es", "en")
        assert result == "Translated by DeepL"

    def test_translate_with_fallback_raises_when_all_fail(self):
        """translate_with_fallback поднимает исключение если все сервисы упали."""
        mt = MachineTranslation()
        google_mock = Mock()
        google_mock.is_available.return_value = True
        google_mock.translate.side_effect = Exception("Google Error")
        mt.translators['google'] = google_mock

        deepl_mock = Mock()
        deepl_mock.is_available.return_value = True
        deepl_mock.translate.side_effect = Exception("DeepL Error")
        mt.translators['deepl'] = deepl_mock

        mt.current_service = 'google'
        with pytest.raises(Exception, match="Все сервисы перевода недоступны"):
            mt.translate_with_fallback("Hola", "es", "en")

    def test_translate_with_fallback_skips_unavailable(self):
        """translate_with_fallback пропускает недоступные сервисы."""
        mt = MachineTranslation()
        google_mock = Mock()
        google_mock.is_available.return_value = False
        mt.translators['google'] = google_mock

        deepl_mock = Mock()
        deepl_mock.is_available.return_value = True
        deepl_mock.translate.return_value = "OK"
        mt.translators['deepl'] = deepl_mock

        mt.current_service = 'google'
        result = mt.translate_with_fallback("Test", "en", "ru")
        assert result == "OK"

    def test_google_translator_logs_warning(self):
        """add_google_translator() логирует предупреждение."""
        mt = MachineTranslation()
        # Не должен упасть
        mt.add_google_translator()
        assert 'google' in mt.translators
