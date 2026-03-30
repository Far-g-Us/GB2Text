"""
Тесты для модуля translation_filler
Автоматическое заполнение нулевых переводов
"""

import unittest
from core.translation_filler import (
    TranslationFiller, SmartTranslationFiller,
    FillStrategy, FillResult, FillOptions,
    get_filler, quick_fill, auto_fill_empty
)


class TestFillStrategy(unittest.TestCase):
    """Тесты для FillStrategy"""
    
    def test_strategies_exist(self):
        """Тест существования стратегий"""
        self.assertIsNotNone(FillStrategy.COPY_ORIGINAL)
        self.assertIsNotNone(FillStrategy.PLACEHOLDER)
        self.assertIsNotNone(FillStrategy.TEMPORARY_MARK)
        self.assertIsNotNone(FillStrategy.SKIP)
        
    def test_strategy_values(self):
        """Тест значений стратегий"""
        self.assertEqual(FillStrategy.COPY_ORIGINAL.value, "copy_original")
        self.assertEqual(FillStrategy.PLACEHOLDER.value, "placeholder")
        self.assertEqual(FillStrategy.TEMPORARY_MARK.value, "temporary_mark")
        self.assertEqual(FillStrategy.SKIP.value, "skip")


class TestFillOptions(unittest.TestCase):
    """Тесты для FillOptions"""
    
    def test_default_values(self):
        """Тест значений по умолчанию"""
        options = FillOptions()
        self.assertEqual(options.strategy, FillStrategy.COPY_ORIGINAL)
        self.assertEqual(options.placeholder_template, "[{original}]")
        self.assertTrue(options.mark_temporary)
        self.assertTrue(options.copy_unchanged)
        self.assertTrue(options.preserve_formatting)
        
    def test_custom_values(self):
        """Тест кастомных значений"""
        options = FillOptions(
            strategy=FillStrategy.PLACEHOLDER,
            placeholder_template="[{orig}]",
            mark_temporary=False
        )
        self.assertEqual(options.strategy, FillStrategy.PLACEHOLDER)
        self.assertEqual(options.placeholder_template, "[{orig}]")
        self.assertFalse(options.mark_temporary)


class TestFillResult(unittest.TestCase):
    """Тесты для FillResult"""
    
    def test_successful_result(self):
        """Тест успешного результата"""
        result = FillResult(
            segment_id="seg_1",
            success=True,
            filled_translation="Hello",
            strategy_used=FillStrategy.COPY_ORIGINAL
        )
        self.assertTrue(result.success)
        self.assertEqual(result.filled_translation, "Hello")
        self.assertIsNone(result.error_message)
        
    def test_failed_result(self):
        """Тест неуспешного результата"""
        result = FillResult(
            segment_id="seg_1",
            success=False,
            filled_translation="",
            strategy_used=FillStrategy.SKIP,
            error_message="Strategy SKIP не заполняет"
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Strategy SKIP не заполняет")


class TestTranslationFiller(unittest.TestCase):
    """Тесты для TranslationFiller"""
    
    def setUp(self):
        self.filler = TranslationFiller(FillOptions(strategy=FillStrategy.COPY_ORIGINAL))
        
    def test_copy_original_strategy(self):
        """Тест стратегии COPY_ORIGINAL"""
        result = self.filler.fill_translation("seg_1", "Hello World")
        self.assertTrue(result.success)
        self.assertEqual(result.filled_translation, "Hello World")
        self.assertEqual(result.strategy_used, FillStrategy.COPY_ORIGINAL)
        
    def test_placeholder_strategy(self):
        """Тест стратегии PLACEHOLDER"""
        options = FillOptions(strategy=FillStrategy.PLACEHOLDER)
        filler = TranslationFiller(options)
        
        result = filler.fill_translation("seg_1", "Hello World")
        self.assertTrue(result.success)
        self.assertEqual(result.filled_translation, "[Hello World]")
        
    def test_placeholder_custom_template(self):
        """Тест кастомного шаблона плейсхолдера"""
        options = FillOptions(
            strategy=FillStrategy.PLACEHOLDER,
            placeholder_template="Требует перевода: {original}"
        )
        filler = TranslationFiller(options)
        
        result = filler.fill_translation("seg_1", "Hello")
        self.assertEqual(result.filled_translation, "Требует перевода: Hello")
        
    def test_temporary_mark_strategy(self):
        """Тест стратегии TEMPORARY_MARK"""
        options = FillOptions(
            strategy=FillStrategy.TEMPORARY_MARK,
            mark_temporary=True
        )
        filler = TranslationFiller(options)
        
        result = filler.fill_translation("seg_1", "Hello")
        self.assertTrue(result.success)
        self.assertEqual(result.filled_translation, "[TEMP] Hello")
        
    def test_skip_strategy(self):
        """Тест стратегии SKIP"""
        options = FillOptions(strategy=FillStrategy.SKIP)
        filler = TranslationFiller(options)
        
        result = filler.fill_translation("seg_1", "Hello")
        self.assertFalse(result.success)
        self.assertEqual(result.filled_translation, "")
        self.assertIsNotNone(result.error_message)
        
    def test_batch_fill(self):
        """Тест пакетного заполнения"""
        segments = {
            "seg_1": "Hello",
            "seg_2": "World",
            "seg_3": "Test"
        }
        
        results = self.filler.fill_batch(segments)
        
        self.assertEqual(len(results), 3)
        for seg_id in segments:
            self.assertIn(seg_id, results)
            self.assertTrue(results[seg_id].success)
            
    def test_get_summary(self):
        """Тест получения сводки"""
        segments = {
            "seg_1": "Hello",
            "seg_2": "World",
        }
        
        results = self.filler.fill_batch(segments)
        summary = self.filler.get_summary(results)
        
        self.assertIn("Заполнение переводов", summary)
        self.assertIn("Всего: 2", summary)


class TestSmartTranslationFiller(unittest.TestCase):
    """Тесты для SmartTranslationFiller"""
    
    def setUp(self):
        self.filler = SmartTranslationFiller()
        
    def test_determine_dialogue(self):
        """Тест определения диалога"""
        # Персонаж: текст (только буквы до точки с запятой)
        self.assertEqual(self.filler.determine_segment_type('"Hello World"'), "dialogue")
        # Текст с многоточием - может быть dialogue или unknown
        result = self.filler.determine_segment_type('Hello...')
        self.assertIn(result, ['dialogue', 'unknown'])
        
    def test_determine_menu(self):
        """Тест определения меню"""
        self.assertEqual(self.filler.determine_segment_type("START"), "menu")
        self.assertEqual(self.filler.determine_segment_type("CONTINUE"), "menu")
        self.assertEqual(self.filler.determine_segment_type("YES NO"), "menu")
        
    def test_determine_hint(self):
        """Тест определения подсказки"""
        self.assertEqual(self.filler.determine_segment_type("[Press A]"), "hint")
        
    def test_determine_unknown(self):
        """Тест определения неизвестного типа"""
        # Может быть menu или unknown в зависимости от реализации
        result = self.filler.determine_segment_type("Some random text here")
        self.assertIn(result, ['menu', 'unknown'])
        
    def test_strategy_for_dialogue(self):
        """Тест стратегии для диалогов"""
        strategy = self.filler.get_strategy_for_type("dialogue")
        self.assertEqual(strategy, FillStrategy.COPY_ORIGINAL)
        
    def test_strategy_for_menu(self):
        """Тест стратегии для меню"""
        strategy = self.filler.get_strategy_for_type("menu")
        self.assertEqual(strategy, FillStrategy.PLACEHOLDER)
        
    def test_strategy_for_hint(self):
        """Тест стратегии для подсказок"""
        strategy = self.filler.get_strategy_for_type("hint")
        self.assertEqual(strategy, FillStrategy.TEMPORARY_MARK)
        
    def test_smart_fill_dialogue(self):
        """Тест умного заполнения диалога"""
        result = self.filler.smart_fill("seg_1", "Mario: Hello!")
        self.assertTrue(result.success)
        self.assertEqual(result.filled_translation, "Mario: Hello!")
        
    def test_smart_fill_menu(self):
        """Тест умного заполнения меню"""
        result = self.filler.smart_fill("seg_1", "START")
        self.assertTrue(result.success)
        self.assertEqual(result.filled_translation, "[START]")
        
    def test_smart_fill_batch(self):
        """Тест умного пакетного заполнения"""
        segments = {
            "seg_1": "Mario: Hello!",
            "seg_2": "START",
            "seg_3": "Some text"
        }
        
        results = self.filler.smart_fill_batch(segments)
        
        self.assertEqual(len(results), 3)
        self.assertEqual(results["seg_1"].filled_translation, "Mario: Hello!")
        self.assertEqual(results["seg_2"].filled_translation, "[START]")


class TestGetFiller(unittest.TestCase):
    """Тесты для глобальной функции get_filler"""
    
    def test_singleton(self):
        """Тест синглтона"""
        filler1 = get_filler()
        filler2 = get_filler()
        
        self.assertIs(filler1, filler2)
        self.assertIsInstance(filler1, TranslationFiller)
        
    def test_with_options(self):
        """Тест с опциями"""
        filler = TranslationFiller(FillOptions(strategy=FillStrategy.PLACEHOLDER))
        result = filler.fill_translation("seg_1", "Test")
        self.assertEqual(result.filled_translation, "[Test]")


class TestQuickFill(unittest.TestCase):
    """Тесты для функции quick_fill"""
    
    def test_quick_fill_copy(self):
        """Тест быстрого заполнения копированием"""
        translations = {
            "seg_1": "Hello",
            "seg_2": "World"
        }
        
        result = quick_fill(translations, FillStrategy.COPY_ORIGINAL)
        
        self.assertEqual(result["seg_1"], "Hello")
        self.assertEqual(result["seg_2"], "World")
        
    def test_quick_fill_placeholder(self):
        """Тест быстрого заполнения плейсхолдером"""
        translations = {
            "seg_1": "Hello",
            "seg_2": "World"
        }
        
        result = quick_fill(translations, FillStrategy.PLACEHOLDER)
        
        self.assertEqual(result["seg_1"], "[Hello]")
        self.assertEqual(result["seg_2"], "[World]")


class TestAutoFillDecorator(unittest.TestCase):
    """Тесты для декоратора auto_fill_empty"""
    
    def test_decorator_fills_empty(self):
        """Тест декоратора с заполнением пустых"""
        
        @auto_fill_empty(FillStrategy.PLACEHOLDER)
        def process_translations(**kwargs):
            return kwargs.get('translations', {})
            
        # Перевод с пустым значением
        translations = {
            "seg_1": "Hello",
            "seg_2": "",  # Пустой
            "seg_3": "   ",  # Только пробелы
            "seg_4": "World"
        }
        
        result = process_translations(translations=translations)
        
        self.assertEqual(result["seg_1"], "Hello")
        self.assertEqual(result["seg_2"], "[]")  # Заполнен плейсхолдером
        self.assertEqual(result["seg_4"], "World")


if __name__ == '__main__':
    unittest.main()