"""
Тесты для модуля translation_validator
Валидация переводов (проверка длины текста)
"""

import unittest

from core.translation_validator import (
    BatchTranslationValidator,
    TranslationValidator,
    ValidationError,
    ValidationLevel,
    ValidationResult,
    get_validator,
)


class TestValidationError(unittest.TestCase):
    """Тесты для класса ValidationError"""

    def test_creation(self):
        """Тест создания ошибки"""
        error = ValidationError(
            ValidationLevel.ERROR,
            "Test error",
            field="test",
            segment_id="seg_1"
        )
        self.assertEqual(error.level, ValidationLevel.ERROR)
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.field, "test")
        self.assertEqual(error.segment_id, "seg_1")

    def test_repr(self):
        """Тест строкового представления"""
        error = ValidationError(ValidationLevel.WARNING, "Test message")
        repr_str = repr(error)
        self.assertIn("WARNING", repr_str)
        self.assertIn("Test message", repr_str)


class TestValidationResult(unittest.TestCase):
    """Тесты для класса ValidationResult"""

    def test_valid_result(self):
        """Тест валидного результата"""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            max_length=255,
            original_length=100,
            translated_length=120
        )
        self.assertTrue(result.is_valid)
        self.assertFalse(result.has_critical_errors())
        self.assertFalse(result.has_errors())

    def test_critical_error(self):
        """Тест с критической ошибкой"""
        errors = [ValidationError(ValidationLevel.CRITICAL, "Critical error")]
        result = ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=[],
            max_length=255,
            original_length=100,
            translated_length=300
        )
        self.assertFalse(result.is_valid)
        self.assertTrue(result.has_critical_errors())

    def test_summary(self):
        """Тест сводки результата"""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            max_length=255,
            original_length=100,
            translated_length=120
        )
        summary = result.get_summary()
        self.assertIn("Валидация пройдена", summary)


class TestTranslationValidator(unittest.TestCase):
    """Тесты для класса TranslationValidator"""

    def setUp(self):
        self.validator = TranslationValidator(max_length=50)

    def test_empty_translation(self):
        """Тест пустого перевода"""
        result = self.validator.validate("Hello", "")
        self.assertFalse(result.is_valid)
        self.assertTrue(result.has_errors())

    def test_whitespace_only_translation(self):
        """Тест перевода только с пробелами"""
        result = self.validator.validate("Hello", "   ")
        self.assertFalse(result.is_valid)

    def test_valid_translation(self):
        """Тест валидного перевода"""
        result = self.validator.validate("Hello", "Привет")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.translated_length, 6)

    def test_exceeds_max_length(self):
        """Тест превышения максимальной длины"""
        long_text = "A" * 100
        result = self.validator.validate("Original", long_text)
        self.assertFalse(result.is_valid)
        self.assertTrue(result.has_critical_errors())

    def test_control_characters(self):
        """Тест управляющих символов"""
        text = "Hello\x00World"
        result = self.validator.validate("Hello", text)
        self.assertFalse(result.is_valid)
        self.assertTrue(result.has_errors())

    def test_multiple_spaces(self):
        """Тест множественных пробелов"""
        text = "Hello   World"
        result = self.validator.validate("Hello World", text)
        # Должно пройти с предупреждением
        self.assertTrue(result.is_valid)

    def test_trailing_spaces(self):
        """Тест концевых пробелов"""
        text = "Hello World  "
        result = self.validator.validate("Hello World", text)
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)

    def test_pointer_references(self):
        """Тест ссылок на указатели"""
        text = "Hello [0x1234] World"
        result = self.validator.validate("Hello World", text)
        # Ссылки на указатели не должны вызывать ошибок
        self.assertTrue(result.is_valid)

    def test_custom_allowed_glyphs(self):
        """Тест кастомных разрешённых глифов"""
        validator = TranslationValidator(max_length=100, check_glyphs=True)
        validator.set_allowed_glyphs({'A', 'B', 'C', 'А', 'Б', 'В', ' '})

        result = validator.validate("Hello", "ABC АБВ")
        self.assertTrue(result.is_valid)

        # С другими символами
        result = validator.validate("Hello", "ABC АБВ田中")
        self.assertFalse(result.is_valid)


class TestBatchTranslationValidator(unittest.TestCase):
    """Тесты для класса BatchTranslationValidator"""

    def setUp(self):
        self.batch = BatchTranslationValidator(max_length=50)

    def test_validate_batch(self):
        """Тест пакетной валидации"""
        translations = {
            "seg_1": ("Hello", "Привет"),
            "seg_2": ("World", "Мир"),
            "seg_3": ("Test", "Тест"),
        }

        results = self.batch.validate_batch(translations)

        self.assertEqual(len(results), 3)
        self.assertTrue(results["seg_1"].is_valid)
        self.assertTrue(results["seg_2"].is_valid)
        self.assertTrue(results["seg_3"].is_valid)

    def test_batch_with_invalid(self):
        """Тест пакета с невалидными переводами"""
        translations = {
            "seg_1": ("Hello", "Привет"),
            "seg_2": ("World", "A" * 100),  # Слишком длинный
        }

        results = self.batch.validate_batch(translations)

        self.assertTrue(results["seg_1"].is_valid)
        self.assertFalse(results["seg_2"].is_valid)

    def test_get_summary(self):
        """Тест получения сводки"""
        translations = {
            "seg_1": ("Hello", "Привет"),
            "seg_2": ("World", "A" * 100),
        }

        results = self.batch.validate_batch(translations)
        summary = self.batch.get_summary(results)

        self.assertIn("Проверено", summary)
        self.assertIn("Валидных", summary)


class TestValidatorTokens(unittest.TestCase):
    """Токены перевода: сохранение контрольных кодов оригинала."""

    def setUp(self):
        self.validator = TranslationValidator(max_length=50)

    def test_tokens_preserved(self):
        result = self.validator.validate("Hi [PLAYER]!", "Привет [PLAYER]!")
        self.assertTrue(result.is_valid)

    def test_tokens_missing_is_error(self):
        result = self.validator.validate("Hi [PLAYER]!", "Привет!")
        self.assertFalse(result.is_valid)
        self.assertTrue(any('tokens' in (e.field or '') for e in result.errors))

    def test_tokens_extra_is_warning(self):
        result = self.validator.validate("Hi!", "Привет [WAIT]!")
        self.assertTrue(result.is_valid)
        self.assertTrue(any('tokens' in (w.field or '') for w in result.warnings))

    def test_prose_brackets_not_blocking(self):
        result = self.validator.validate("Box [sic]", "Коробка.")
        self.assertTrue(result.is_valid)
        self.assertFalse(any(e.level.value == 'error' and 'tokens' in (e.field or '')
                             for e in result.errors))
        text = " ".join(w.message for w in result.warnings)
        self.assertIn("[sic]", text)
        self.assertNotIn("[siC]", text)

    def test_uppercase_prose_not_blocking(self):
        result = self.validator.validate("Note [Hello World]", "Заметка.")
        self.assertTrue(result.is_valid)

    def test_game_token_forms_strict(self):
        for token in ('[G:15]', '[FF 0B]', '[40_3C]', '{NL}', '[PLAYER]', '[65]', '[0x1234]'):
            with self.subTest(token=token):
                result = self.validator.validate(f"A {token} B", "A B")
                self.assertFalse(result.is_valid)

    def test_hex_case_insensitive_both_ways(self):
        for src, dst in (("A [FF] B", "A [ff] B"),
                         ("A [FF 0B] B", "A [ff 0b] B"),
                         ("A [40_3C] B", "A [40_3c] B"),
                         ("A [0x1234] B", "A [0X1234] B"),
                         ("A [G:AB] B", "A [G:ab] B"),
                         ("A [0X 12] B", "A [0x 12] B")):
            with self.subTest(src=src, dst=dst):
                for a, b in ((src, dst), (dst, src)):
                    result = self.validator.validate(a, b)
                    self.assertTrue(result.is_valid)
                    self.assertFalse(any('tokens' in (w.field or '')
                                         for w in result.warnings))

    def test_hex_token_loss_single_error(self):
        for spelling in ("[0x1234]", "[0X1234]"):
            with self.subTest(spelling=spelling):
                result = self.validator.validate(f"A {spelling} B", "A B")
                self.assertFalse(result.is_valid)
                self.assertFalse(any('tokens' in (w.field or '')
                                     for w in result.warnings))

    def test_loose_case_only_change_no_warning(self):
        result = self.validator.validate("A [G:ab] B", "A [G:aB] B")
        self.assertTrue(result.is_valid)
        self.assertFalse(any('tokens' in (w.field or '')
                             for w in result.warnings))

    def test_case_is_strict(self):
        for src, dst in (("A [G:15] B", "A [g:15] B"),
                         ("A [PLAYER] B", "A [player] B"),
                         ("A {Chocobo} B", "A {chocobo} B"),
                         ("A [123AB] B", "A [123ab] B")):
            with self.subTest(src=src, dst=dst):
                result = self.validator.validate(src, dst)
                self.assertFalse(result.is_valid)

    def test_bare_and_lowercase_lead_are_loose(self):
        for token in ("[12abc]", "[0x]", "[G:]", "[1g]"):
            with self.subTest(token=token):
                result = self.validator.validate(f"A {token} B", "A B")
                self.assertTrue(result.is_valid)
                self.assertTrue(any('tokens' in (w.field or '')
                                    for w in result.warnings))

    def test_digit_lead_upper_gate_is_strict(self):
        result = self.validator.validate("A [1G] B", "A B")
        self.assertFalse(result.is_valid)

    def test_brace_name_preserved(self):
        result = self.validator.validate("A {Chocobo} B", "A {Chocobo} B")
        self.assertTrue(result.is_valid)

    def test_leading_spaces_warning(self):
        result = self.validator.validate("Hi", "  Hi")
        self.assertTrue(result.is_valid)
        self.assertTrue(any(w.field == 'formatting' for w in result.warnings))

    def test_reorder_is_warning(self):
        result = self.validator.validate("A [X] B [Y]", "A [Y] B [X]")
        self.assertTrue(result.is_valid)
        self.assertTrue(any('tokens' in (w.field or '') for w in result.warnings))

    def test_duplicate_extra_single_warning(self):
        result = self.validator.validate("A", "A [X] [X]")
        warnings = [w for w in result.warnings if 'tokens' in (w.field or '')]
        self.assertEqual(len(warnings), 1)


class TestGetValidator(unittest.TestCase):
    """Тесты для глобальной функции get_validator"""

    def test_singleton(self):
        """Тест синглтона"""
        validator1 = get_validator()
        validator2 = get_validator()

        self.assertIs(validator1, validator2)
        self.assertIsInstance(validator1, TranslationValidator)


if __name__ == '__main__':
    unittest.main()
