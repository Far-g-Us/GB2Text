# Тестирование GB2Text

## Зачем нужны тесты?

Тесты обеспечивают:
- **Надёжность** - проверяют, что код работает корректно
- **Безопасность** - предотвращают регрессии при изменениях
- **Документацию** - показывают ожидаемое поведение кода
- **Упрощение отладки** - быстро находят проблемы

## Установка зависимостей

```bash
pip install -r requirements.txt
```

## Запуск тестов

### Все тесты
```bash
pytest tests/ -v
```

### С покрытием кода
```bash
pytest tests/ --cov=core --cov-report=html
```

### Конкретный файл
```bash
pytest tests/test_charset.py -v
```

## Структура тестов

```
tests/
├── __init__.py
├── test_analyzer.py        # Тесты анализатора текста
├── test_auto_detect.py    # Тесты автоопределения
├── test_charset.py        # Тесты загрузки charset файлов
├── test_compression.py    # Тесты сжатия (LZSS, RLE)
├── test_constants.py      # Тесты констант
├── test_decoder.py        # Тесты декодера
├── test_encoding.py       # Тесты кодирования
├── test_extractor.py      # Тесты экстрактора текста
├── test_gba_support.py    # Тесты GBA поддержки
├── test_guide.py         # Тесты менеджера гайдов
├── test_i18n.py           # Тесты локализации (i18n)
├── test_injector.py      # Тесты инжектора текста
├── test_integration.py   # Интеграционные тесты
├── test_mbc.py           # Тесты MBC
├── test_plugin.py        # Тесты плагинов
├── test_plugin_manager.py # Тесты менеджера плагинов
├── test_rom.py           # Тесты ROM
├── test_rom_cache.py     # Тесты кэширования ROM
├── test_rom_validation.py # Тесты валидации ROM
└── test_scanner.py       # Тесты сканера
```

## Типы тестов

### 1. Unit-тесты
Тестируют отдельные функции/классы изолированно:
- `test_charset.py` - загрузка таблиц символов
- `test_decoder.py` - кодирование/декодирование
- `test_constants.py` - константы проекта
- `test_i18n.py` - локализация (47 тестов)
- `test_plugin_manager.py` - менеджер плагинов
- `test_scanner.py` - сканер текста

### 2. Интеграционные тесты
Тестируют взаимодействие модулей:
- `test_integration.py` - работа с реальными ROM файлами

## Добавление новых тестов

### Пример теста
```python
def test_my_function():
    """Описание теста"""
    result = my_function(input_data)
    assert result == expected_result
```

### Запуск конкретного теста
```bash
pytest tests/test_charset.py::TestCharset::test_load_charset_english -v
```

## Непрерывная интеграция

Тесты должны проходить перед каждым commit:
```bash
# Проверьте локально перед push
pytest tests/ -v
```

## Coverage

**Целевое покрытие: 80%+ для всех файлов core**

Текущее покрытие (2026-03-01):
- **Общее покрытие: 88%**
- Все файлы core/ имеют ≥80% покрытия

### Покрытие по файлам
| Файл | Покрытие |
|------|----------|
| core/analyzer.py | 89% |
| core/charset.py | 100% |
| core/compression.py | 81% |
| core/constants.py | 100% |
| core/database.py | 86% |
| core/decoder.py | 91% |
| core/encoding.py | 95% |
| core/extractor.py | 85% |
| core/gba_support.py | 86% |
| core/guide.py | 100% |
| core/i18n.py | 100% |
| core/injector.py | 90% |
| core/mbc.py | 82% |
| core/plugin.py | 89% |
| core/plugin_manager.py | 84% |
| core/rom.py | 84% |
| core/rom_cache.py | 93% |
| core/scanner.py | 86% |

Текущее покрытие см. в отчёте HTML после запуска с `--cov-report=html`
