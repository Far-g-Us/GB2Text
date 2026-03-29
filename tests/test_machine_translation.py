"""
Tests for machine translation functionality
"""

import pytest
from unittest.mock import Mock, patch
from core.machine_translation import MachineTranslation, GoogleTranslator, DeepLTranslator, BingTranslator


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