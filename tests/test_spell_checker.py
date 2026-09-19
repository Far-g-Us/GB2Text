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
        # Кэш работает — ключ закэширован; отдаются равные копии,
        # а не один объект (мутация caller'ом кэш не травит)
        self.assertEqual(len(svc._cache), 1)
        self.assertIsNot(first, second)

    @pytest.mark.slow
    def test_performance_many_words(self):
        """Проверка 1000 слов должна укладываться в секунду."""
        svc = SpellCheckService()
        text = " ".join(["correct"] * 1000)
        start = time.time()
        svc.check_text(text)
        elapsed = time.time() - start
        self.assertLess(elapsed, 1.0, f"Медленная проверка: {elapsed:.2f}c")

    @pytest.mark.slow
    def test_suggestions_default_on(self):
        """По умолчанию подсказки для короткой опечатки считаются."""
        errors = check_text("wrord", lang="en")
        self.assertTrue(errors)
        self.assertTrue(errors[0][3])
        self.assertIn("word", errors[0][3])

    @pytest.mark.slow
    def test_without_suggestions_still_detects(self):
        """with_suggestions=False: опечатка находится, подсказок нет."""
        errors = check_text(
            "This is a wrord example", lang="en", with_suggestions=False)
        words = [w for _, _, w, _ in errors]
        self.assertIn("wrord", words)
        self.assertTrue(all(sug == [] for _, _, _, sug in errors))

    @pytest.mark.slow
    def test_long_words_have_no_suggestions(self):
        """Для очень длинных слов подсказки не считаются (защита от взрыва)."""
        errors = check_text("qwertyuiopasdf", lang="en")
        self.assertTrue(errors)
        self.assertEqual(errors[0][3], [])

    @pytest.mark.slow
    def test_cache_distinguishes_suggestions(self):
        """Кэш различает режимы with_suggestions True/False."""
        svc = SpellCheckService()
        with_sug = svc.check_text("превет", lang="ru")
        without_sug = svc.check_text(
            "превет", lang="ru", with_suggestions=False)
        self.assertIsNot(with_sug, without_sug)
        self.assertEqual(svc.check_text("превет", lang="ru"), with_sug)
        self.assertIsNot(svc.check_text("превет", lang="ru"), with_sug)
        self.assertTrue(with_sug[0][3])
        self.assertEqual(without_sug[0][3], [])

    @pytest.mark.slow
    def test_hex_literal_ignored(self):
        """Hex-литерал 0xFF целиком в игноре (без ложного 'xFF')."""
        errors = check_text("set value 0xFF and 0x1A", lang="en")
        words = [w for _, _, w, _ in errors]
        self.assertNotIn("xFF", words)
        self.assertNotIn("x1A", words)

    @pytest.mark.slow
    def test_unknown_lang_falls_back_to_auto(self):
        """Явный lang вне (ru,en) → fallback 'auto' без исключений."""
        errors = check_text("wrord", lang="xx")
        words = [w for _, _, w, _ in errors]
        self.assertIn("wrord", words)

    @pytest.mark.slow
    def test_cache_overflow_clears(self):
        """Переполнение кэша (_CACHE_MAX) чистит его."""
        from core.spell_checker import _CACHE_MAX

        svc = SpellCheckService()
        svc._cache.update({(f"k{i}", "en", False): [] for i in range(_CACHE_MAX + 5)})
        svc.check_text("wrord", lang="en")
        self.assertLessEqual(len(svc._cache), 2)

    @pytest.mark.slow
    def test_clear_cache(self):
        """clear_cache() опустошает кэш."""
        svc = SpellCheckService()
        svc.check_text("wrord", lang="en")
        self.assertTrue(svc._cache)
        svc.clear_cache()
        self.assertEqual(svc._cache, {})

    @pytest.mark.slow
    def test_cache_returns_copies(self):
        """Мутация результата caller'ом не травит кэш."""
        svc = SpellCheckService()
        first = svc.check_text("wrord mistake", lang="en")
        self.assertTrue(first)
        first.append((0, 1, "zzz", []))
        first[0][3].append("MUT")
        second = svc.check_text("wrord mistake", lang="en")
        self.assertEqual([w for _, _, w, _ in second], [w for _, _, w, _ in first if w != "zzz"])
        self.assertTrue(all("MUT" not in sg for _, _, _, sg in second))


if __name__ == "__main__":
    unittest.main()
