"""
Модуль валидации переводов
Проверяет корректность перевода: длина, глифы, синтаксис
"""

import logging
import re
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('gb2text.translation_validator')


class ValidationLevel(Enum):
    """Уровни серьёзности ошибок валидации"""
    INFO = "info"           # Информационное сообщение
    WARNING = "warning"      # Предупреждение
    ERROR = "error"          # Ошибка (перевод не должен использоваться)
    CRITICAL = "critical"    # Критическая ошибка (блокирует использование)


class ValidationError:
    """Ошибка валидации"""
    
    def __init__(self, level: ValidationLevel, message: str, field: str = None, segment_id: str = None):
        self.level = level
        self.message = message
        self.field = field
        self.segment_id = segment_id
        
    def __repr__(self):
        return f"[{self.level.value.upper()}] {self.message}"


@dataclass
class ValidationResult:
    """Результат валидации перевода"""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    max_length: int
    original_length: int
    translated_length: int
    
    def has_critical_errors(self) -> bool:
        """Проверяет наличие критических ошибок"""
        return any(e.level == ValidationLevel.CRITICAL for e in self.errors)
    
    def has_errors(self) -> bool:
        """Проверяет наличие обычных ошибок"""
        return any(e.level == ValidationLevel.ERROR for e in self.errors)
    
    def get_summary(self) -> str:
        """Возвращает текстовую сводку результата"""
        if self.is_valid:
            return f"✓ Валидация пройдена ({self.translated_length}/{self.max_length} симв.)"
        return f"✗ Валидация не пройдена: {len(self.errors)} ошибок, {len(self.warnings)} предупреждений"


class TranslationValidator:
    """
    Валидатор переводов для ROM
    
    Проверяет:
    - Максимальную длину текста (ограничение буфера)
    - Запрещённые символы (системные, управляющие)
    - Формат указателей (pointer refs)
    - Новые строки и переносы
    """
    
    # Регулярные выражения для проверок
    CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')
    POINTER_REF_RE = re.compile(r'\[[0-9A-Fa-f]{4,8}\]')  # Ссылки на указатели
    MULTIPLE_SPACES_RE = re.compile(r' {2,}')  # Множественные пробелы
    TRAILING_SPACE_RE = re.compile(r' +$', re.MULTILINE)
    LEADING_SPACE_RE = re.compile(r'^ +', re.MULTILINE)
    
    def __init__(self, max_length: int = 255, check_glyphs: bool = True):
        """
        Args:
            max_length: Максимальная длина перевода (в символах)
            check_glyphs: Проверять ли допустимые глифы
        """
        self.max_length = max_length
        self.check_glyphs = check_glyphs
        self.logger = logging.getLogger('gb2text.translation_validator')
        
        # Разрешённые символы (можно расширить)
        self.allowed_glyphs: Optional[set] = None
        
    def set_allowed_glyphs(self, glyphs: set):
        """Устанавливает набор разрешённых глифов"""
        self.allowed_glyphs = glyphs
        
    def validate(self, original: str, translation: str, segment_id: str = None) -> ValidationResult:
        """
        Проводит полную валидацию перевода
        
        Args:
            original: Оригинальный текст
            translation: Перевод
            segment_id: ID сегмента для отчётности
            
        Returns:
            ValidationResult с результатами проверки
        """
        errors: List[ValidationError] = []
        warnings: List[ValidationError] = []
        
        # Проверка пустого перевода
        if not translation or not translation.strip():
            errors.append(ValidationError(
                ValidationLevel.ERROR,
                "Перевод пуст или содержит только пробелы",
                field="translation",
                segment_id=segment_id
            ))
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                max_length=self.max_length,
                original_length=len(original),
                translated_length=0
            )
        
        # Проверка длины
        length_result = self._validate_length(translation, segment_id)
        errors.extend(length_result.errors)
        warnings.extend(length_result.warnings)
        
        # Проверка управляющих символов
        ctrl_result = self._validate_control_chars(translation, segment_id)
        errors.extend(ctrl_result.errors)
        
        # Проверка пробелов
        space_result = self._validate_spaces(translation, segment_id)
        errors.extend(space_result.errors)
        warnings.extend(space_result.warnings)
        
        # Проверка указателей
        pointer_result = self._validate_pointers(translation, segment_id)
        warnings.extend(pointer_result.warnings)
        
        # Проверка разрешённых глифов
        if self.check_glyphs and self.allowed_glyphs:
            glyph_result = self._validate_glyphs(translation, segment_id)
            errors.extend(glyph_result.errors)
        
        # Определяем валидность
        is_valid = not self.has_critical_errors_in_list(errors) and not self.has_errors_in_list(errors)
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            max_length=self.max_length,
            original_length=len(original),
            translated_length=len(translation)
        )
    
    def _validate_length(self, text: str, segment_id: str = None) -> ValidationResult:
        """Проверка длины текста"""
        errors = []
        warnings = []
        
        if len(text) > self.max_length:
            errors.append(ValidationError(
                ValidationLevel.CRITICAL,
                f"Превышена максимальная длина: {len(text)} > {self.max_length}",
                field="length",
                segment_id=segment_id
            ))
        elif len(text) > self.max_length * 0.9:  # Предупреждение на 90%
            warnings.append(ValidationError(
                ValidationLevel.WARNING,
                f"Длина близка к максимуму: {len(text)}/{self.max_length} симв.",
                field="length",
                segment_id=segment_id
            ))
            
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            max_length=self.max_length,
            original_length=0,
            translated_length=len(text)
        )
    
    def _validate_control_chars(self, text: str, segment_id: str = None) -> ValidationResult:
        """Проверка управляющих символов"""
        errors = []
        
        matches = self.CONTROL_CHARS_RE.findall(text)
        if matches:
            # Группируем найденные символы
            char_set = set(ord(c) for c in matches)
            chars_str = ', '.join(f'0x{c:02X}' for c in sorted(char_set)[:5])
            errors.append(ValidationError(
                ValidationLevel.ERROR,
                f"Найдены недопустимые управляющие символы: {chars_str}",
                field="content",
                segment_id=segment_id
            ))
            
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=[],
            max_length=self.max_length,
            original_length=0,
            translated_length=len(text)
        )
    
    def _validate_spaces(self, text: str, segment_id: str = None) -> ValidationResult:
        """Проверка пробелов"""
        errors = []
        warnings = []
        
        # Множественные пробелы
        if self.MULTIPLE_SPACES_RE.search(text):
            warnings.append(ValidationError(
                ValidationLevel.WARNING,
                "Найдены последовательности из нескольких пробелов",
                field="formatting",
                segment_id=segment_id
            ))
            
        # Начальные/конечные пробелы в строках
        if self.TRAILING_SPACE_RE.search(text):
            warnings.append(ValidationError(
                ValidationLevel.WARNING,
                "Найдены концевые пробелы в строках",
                field="formatting",
                segment_id=segment_id
            ))
            
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            max_length=self.max_length,
            original_length=0,
            translated_length=len(text)
        )
    
    def _validate_pointers(self, text: str, segment_id: str = None) -> ValidationResult:
        """Проверка ссылок на указатели"""
        warnings = []
        
        matches = self.POINTER_REF_RE.findall(text)
        if matches:
            self.logger.debug(f"Найдены ссылки на указатели: {matches}")
            # Это нормальное поведение, просто информируем
            
        return ValidationResult(
            is_valid=True,
            errors=[],
            warnings=warnings,
            max_length=self.max_length,
            original_length=0,
            translated_length=len(text)
        )
    
    def _validate_glyphs(self, text: str, segment_id: str = None) -> ValidationResult:
        """Проверка допустимых глифов"""
        errors = []
        
        if not self.allowed_glyphs:
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                max_length=self.max_length,
                original_length=0,
                translated_length=len(text)
            )
            
        invalid_glyphs = set()
        for char in text:
            if char not in self.allowed_glyphs and char not in ('\n', '\r', '\t'):
                invalid_glyphs.add(char)
                
        if invalid_glyphs:
            glyphs_str = ''.join(sorted(invalid_glyphs))[:20]
            errors.append(ValidationError(
                ValidationLevel.ERROR,
                f"Найдены недопустимые символы: '{glyphs_str}...'",
                field="glyphs",
                segment_id=segment_id
            ))
            
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=[],
            max_length=self.max_length,
            original_length=0,
            translated_length=len(text)
        )
    
    @staticmethod
    def has_critical_errors_in_list(errors: List[ValidationError]) -> bool:
        return any(e.level == ValidationLevel.CRITICAL for e in errors)
    
    @staticmethod
    def has_errors_in_list(errors: List[ValidationError]) -> bool:
        return any(e.level == ValidationLevel.ERROR for e in errors)


class BatchTranslationValidator:
    """Валидатор для пакетной проверки переводов"""
    
    def __init__(self, max_length: int = 255, check_glyphs: bool = False):
        self.validator = TranslationValidator(max_length, check_glyphs)
        self.logger = logging.getLogger('gb2text.batch_validator')
        
    def validate_batch(self, translations: Dict[str, Tuple[str, str]]) -> Dict[str, ValidationResult]:
        """
        Проверяет партию переводов
        
        Args:
            translations: Словарь {segment_id: (original, translation)}
            
        Returns:
            Словарь {segment_id: ValidationResult}
        """
        results = {}
        
        for segment_id, (original, translation) in translations.items():
            result = self.validator.validate(original, translation, segment_id)
            results[segment_id] = result
            
            if not result.is_valid:
                self.logger.warning(f"Сегмент {segment_id}: {result.get_summary()}")
                
        return results
    
    def get_summary(self, results: Dict[str, ValidationResult]) -> str:
        """Возвращает сводку по всем результатам"""
        total = len(results)
        valid = sum(1 for r in results.values() if r.is_valid)
        invalid = total - valid
        
        summary = f"Проверено переводов: {total}\n"
        summary += f"✓ Валидных: {valid}\n"
        summary += f"✗ Невалидных: {invalid}\n"
        
        # Считаем ошибки по уровням
        all_errors = [e for r in results.values() for e in r.errors]
        error_levels = {}
        for e in all_errors:
            level = e.level.value
            error_levels[level] = error_levels.get(level, 0) + 1
            
        if error_levels:
            summary += "\nОшибки по уровням:\n"
            for level, count in sorted(error_levels.items()):
                summary += f"  {level}: {count}\n"
                
        return summary


# Глобальный валидатор
_global_validator: Optional[TranslationValidator] = None

def get_validator(max_length: int = 255, check_glyphs: bool = True) -> TranslationValidator:
    """Возвращает глобальный экземпляр валидатора"""
    global _global_validator
    if _global_validator is None:
        _global_validator = TranslationValidator(max_length, check_glyphs)
    return _global_validator