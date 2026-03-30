"""
Модуль для автоматического заполнения нулевых переводов

Этот модуль предоставляет функциональность для:
- Автоматического заполнения пустых переводов
- Заполнения переводов на основе оригинального текста
- Пакетного заполнения переводов
"""

import logging
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('gb2text.translation_filler')


class FillStrategy(Enum):
    """Стратегии заполнения переводов"""
    COPY_ORIGINAL = "copy_original"     # Копировать оригинал
    PLACEHOLDER = "placeholder"          # Заполнить плейсхолдером
    TEMPORARY_MARK = "temporary_mark"    # Отметить как временный
    SKIP = "skip"                         # Пропустить


@dataclass
class FillResult:
    """Результат заполнения"""
    segment_id: str
    success: bool
    filled_translation: str
    strategy_used: FillStrategy
    error_message: Optional[str] = None


@dataclass
class FillOptions:
    """Опции для заполнения переводов"""
    strategy: FillStrategy = FillStrategy.COPY_ORIGINAL
    placeholder_template: str = "[{original}]"  # Шаблон для плейсхолдера
    mark_temporary: bool = True                  # Добавлять маркер временного
    copy_unchanged: bool = True                  # Копировать текст без изменений
    preserve_formatting: bool = True            # Сохранять форматирование


class TranslationFiller:
    """
    Заполнитель переводов для пустых сегментов
    
    Позволяет:
    - Автоматически заполнять пустые переводы
    - Использовать различные стратегии заполнения
    - Помечать заполненные переводы как временные
    """
    
    def __init__(self, options: FillOptions = None):
        self.options = options or FillOptions()
        self.logger = logging.getLogger('gb2text.translation_filler')
        
    def fill_translation(self, segment_id: str, original: str) -> FillResult:
        """
        Заполняет один перевод
        
        Args:
            segment_id: ID сегмента
            original: Оригинальный текст
            
        Returns:
            FillResult с результатом заполнения
        """
        try:
            if self.options.strategy == FillStrategy.COPY_ORIGINAL:
                filled = self._fill_copy_original(original)
            elif self.options.strategy == FillStrategy.PLACEHOLDER:
                filled = self._fill_placeholder(original)
            elif self.options.strategy == FillStrategy.TEMPORARY_MARK:
                filled = self._fill_temporary_mark(original)
            else:
                return FillResult(
                    segment_id=segment_id,
                    success=False,
                    filled_translation="",
                    strategy_used=self.options.strategy,
                    error_message="Стратегия SKIP не заполняет переводы"
                )
                
            return FillResult(
                segment_id=segment_id,
                success=True,
                filled_translation=filled,
                strategy_used=self.options.strategy
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка заполнения перевода {segment_id}: {e}")
            return FillResult(
                segment_id=segment_id,
                success=False,
                filled_translation="",
                strategy_used=self.options.strategy,
                error_message=str(e)
            )
            
    def _fill_copy_original(self, original: str) -> str:
        """Копирует оригинальный текст"""
        if self.options.preserve_formatting:
            return original
        return original.strip()
        
    def _fill_placeholder(self, original: str) -> str:
        """Заполняет плейсхолдером"""
        template = self.options.placeholder_template
        return template.format(original=original)
        
    def _fill_temporary_mark(self, original: str) -> str:
        """Заполняет с маркером временного перевода"""
        if self.options.copy_unchanged:
            text = original
        else:
            text = original.strip()
            
        if self.options.mark_temporary:
            return f"[TEMP] {text}"
        return text
        
    def fill_batch(self, segments: Dict[str, str]) -> Dict[str, FillResult]:
        """
        Заполняет партию переводов
        
        Args:
            segments: Словарь {segment_id: original_text}
            
        Returns:
            Словарь {segment_id: FillResult}
        """
        results = {}
        
        for segment_id, original in segments.items():
            result = self.fill_translation(segment_id, original)
            results[segment_id] = result
            
            if result.success:
                self.logger.debug(f"Заполнен перевод: {segment_id}")
            else:
                self.logger.warning(f"Не удалось заполнить: {segment_id} - {result.error_message}")
                
        return results
        
    def get_summary(self, results: Dict[str, FillResult]) -> str:
        """Возвращает сводку результатов заполнения"""
        total = len(results)
        successful = sum(1 for r in results.values() if r.success)
        failed = total - successful
        
        summary = f"Заполнение переводов:\n"
        summary += f"  Всего: {total}\n"
        summary += f"  ✓ Заполнено: {successful}\n"
        summary += f"  ✗ Ошибок: {failed}\n"
        
        if failed > 0:
            summary += "\nОшибки:\n"
            for seg_id, result in results.items():
                if not result.success:
                    summary += f"  - {seg_id}: {result.error_message}\n"
                    
        return summary


class SmartTranslationFiller(TranslationFiller):
    """
    Умный заполнитель переводов
    
    Дополнительно:
    - Анализирует паттерны текста
    - Определяет типы сегментов (диалоги, меню, подсказки)
    - Применяет разные стратегии для разных типов
    """
    
    # Паттерны для определения типов текста
    DIALOGUE_PATTERNS = [
        r'^[А-Яа-я]+:.*',  # Персонаж: текст
        r'^"[^"]+"$',       # Текст в кавычках
        r'\.{3,}',          # Многоточия
    ]
    
    MENU_PATTERNS = [
        r'^(OK|CANCEL|YES|NO|START|CONTINUE)$',  # Кнопки
        r'^[A-Z][A-Z ]+$',                        # Верхний регистр
        r'^\d+\..*',                              # Нумерованные пункты
    ]
    
    HINT_PATTERNS = [
        r'^\[.*\]$',      # В квадратных скобках
        r'^<.*>$',        # В угловых скобках
    ]
    
    def __init__(self, options: FillOptions = None):
        super().__init__(options)
        self.logger = logging.getLogger('gb2text.smart_filler')
        
    def determine_segment_type(self, text: str) -> str:
        """
        Определяет тип сегмента по тексту
        
        Returns:
            Тип: 'dialogue', 'menu', 'hint', или 'unknown'
        """
        import re
        
        for pattern in self.DIALOGUE_PATTERNS:
            if re.match(pattern, text):
                return 'dialogue'
                
        for pattern in self.MENU_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return 'menu'
                
        for pattern in self.HINT_PATTERNS:
            if re.match(pattern, text):
                return 'hint'
                
        return 'unknown'
        
    def get_strategy_for_type(self, segment_type: str) -> FillStrategy:
        """Возвращает стратегию заполнения для типа сегмента"""
        if segment_type == 'dialogue':
            return FillStrategy.COPY_ORIGINAL  # Диалоги лучше копировать
        elif segment_type == 'menu':
            return FillStrategy.PLACEHOLDER     # Меню заполняем плейсхолдером
        elif segment_type == 'hint':
            return FillStrategy.TEMPORARY_MARK  # Подсказки отмечаем
        else:
            return FillStrategy.COPY_ORIGINAL   # По умолчанию копируем
            
    def smart_fill(self, segment_id: str, original: str) -> FillResult:
        """
        Умное заполнение одного перевода
        
        Автоматически выбирает стратегию на основе типа сегмента
        """
        segment_type = self.determine_segment_type(original)
        self.logger.debug(f"Сегмент {segment_id}: тип={segment_type}")
        
        # Сохраняем текущую стратегию
        original_strategy = self.options.strategy
        
        try:
            # Устанавливаем стратегию для типа
            self.options.strategy = self.get_strategy_for_type(segment_type)
            
            # Заполняем
            result = self.fill_translation(segment_id, original)
            
            return result
            
        finally:
            # Восстанавливаем стратегию
            self.options.strategy = original_strategy
            
    def smart_fill_batch(self, segments: Dict[str, str]) -> Dict[str, FillResult]:
        """
        Умное заполнение партии переводов
        """
        results = {}
        
        for segment_id, original in segments.items():
            result = self.smart_fill(segment_id, original)
            results[segment_id] = result
            
        return results


# Глобальный заполнитель
_global_filler: Optional[TranslationFiller] = None

def get_filler(options: FillOptions = None) -> TranslationFiller:
    """Возвращает глобальный экземпляр заполнителя"""
    global _global_filler
    if _global_filler is None:
        _global_filler = TranslationFiller(options)
    return _global_filler


def quick_fill(translations: Dict[str, str], 
              strategy: FillStrategy = FillStrategy.COPY_ORIGINAL) -> Dict[str, str]:
    """
    Быстрое заполнение переводов
    
    Args:
        translations: Словарь {segment_id: original}
        strategy: Стратегия заполнения
        
    Returns:
        Словарь {segment_id: filled_translation}
    """
    options = FillOptions(strategy=strategy)
    filler = TranslationFiller(options)
    
    results = filler.fill_batch(translations)
    return {seg_id: result.filled_translation for seg_id, result in results.items()}


# Декоратор для автоматического заполнения
def auto_fill_empty(strategy: FillStrategy = FillStrategy.COPY_ORIGINAL):
    """
    Декоратор для автоматического заполнения пустых переводов
    
    Пример использования:
    @auto_fill_empty(FillStrategy.PLACEHOLDER)
    def save_translations(translations):
        ...
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # Получаем translations из аргументов
            translations = kwargs.get('translations') or (args[0] if args else {})
            
            # Заполняем пустые
            filled = {}
            for seg_id, text in translations.items():
                if not text or not text.strip():
                    options = FillOptions(strategy=strategy)
                    filler = TranslationFiller(options)
                    result = filler.fill_translation(seg_id, text)
                    filled[seg_id] = result.filled_translation
                else:
                    filled[seg_id] = text
                    
            # Вызываем оригинальную функцию с заполненными данными
            kwargs['translations'] = filled
            return func(*args, **kwargs)
            
        return wrapper
    return decorator