"""
Тесты для модуля spell_checker
Проверка орфографии переводов (pyspellchecker, ignore токенов)
"""

import time
import unittest

import pytest

from core.spell_checker import SpellCheckService, check_text


class TestSpellCheckService(unittest.TestCase):
    """Тесты сервиса проверки орфографии"""

    @pytest.mark.slow
    def test_initialization_is_lazy(self):
        """Словарь pyspellchecker подгружается только при первом вызове."""
        svc = SpellCheckService()
        self.assertFalse(svc.initialized)
        svc.check_text("Hello world")
        self.assertTrue(svc.initialized)

    @pytest.mark.slow
    def test_typo_ru_detected(self):
        """Опечатка на русском обнаруживается."""
        errors = check_text("Это превет мир!", lang="auto")
        words = [w for _, _, w, _ in errors]
        self.assertIn("превет", words)

    @pytest.mark.slow
    def test_typo_en_detected(self):
        """Опечатка на английском обнаруживается."""
        errors = check_text("This is a wrord example", lang="en")
        words = [w for _, _, w, _ in errors]
        self.assertIn("wrord", words)

    def test_tokens_ignored(self):
        """Управляющие токены не считаются опечатками."""
        errors = check_text("[END] [LINE] %s {PLAYER} 12345")
        self.assertEqual(errors, [])

    @pytest.mark.slow
    def test_correct_text_no_errors(self):
        """Правильный текст без ошибок."""
        self.assertEqual(check_text("Привет мир, как дела?", lang="ru"), [])
        self.assertEqual(check_text("Hello world, how are you?", lang="en"), [])

    @pytest.mark.slow
    def test_positions_with_tokens(self):
        """Позиции корректны при наличии токенов в тексте."""
        text = "[END] превет [LINE]"
        errors = check_text(text)
        start, end, word, _ = errors[0]
        self.assertEqual(word, "превет")
        # индексы в исходной строке с учётом токена [END]
        self.assertEqual(text[start:end], "превет")

    @pytest.mark.slow
    def test_lang_auto_prefers_cyrillic(self):
        """Автоопределение языка: кириллица -> ru."""
        errors = check_text("Это helo тест")
        words = [w for _, _, w, _ in errors]
        # ru-словарь содержит "это"; "тест" — тоже известное
        self.assertTrue(words)

    def test_short_words_ignored(self):
        """Односимвольные фрагменты (буквы) не считаются словами."""
        errors = check_text("а b x")
        self.assertEqual(errors, [])

    @pytest.mark.slow
    def test_empty_and_whitespace(self):
        """Пустой текст и пробелы -> нет ошибок."""
        self.assertEqual(check_text(""), [])
        self.assertEqual(check_text("   \n  "), [])

    @pytest.mark.slow
    def test_lazy_cache(self):
        """Кэш сокращает повторные проверки без пересоздания словаря."""
        svc = SpellCheckService()
        first = svc.check_text("превет", lang="ru")
        second = svc.check_text("превет", lang="ru")
        self.assertEqual(first, second)
        # Кэш работает — тот же объект списка
        self.assertIs(first, second)

    @pytest.mark.slow
    def test_performance_many_words(self):
        """Проверка 1000 слов должна укладываться в секунду."""
        svc = SpellCheckService()
        text = " ".join(["correct"] * 1000)
        start = time.time()
        svc.check_text(text)
        elapsed = time.time() - start
        self.assertLess(elapsed, 1.0, f"Медленная проверка: {elapsed:.2f}c")


if __name__ == "__main__":
    unittest.main()
