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
├── test_analyzer.py           # Тесты анализатора текста
├── test_auto_detect.py        # Тесты автоопределения
├── test_charset.py            # Тесты загрузки charset файлов
├── test_compression.py        # Тесты сжатия (LZSS, RLE)
├── test_constants.py          # Тесты констант
├── test_decoder.py            # Тесты декодера
├── test_decoder_extended.py   # Расширенные тесты декодера
├── test_encoding.py           # Тесты кодирования
├── test_extractor.py          # Тесты экстрактора текста
├── test_gba_support.py        # Тесты GBA поддержки
├── test_generic_plugin.py     # Тесты.generic плагина
├── test_guide.py              # Тесты менеджера гайдов
├── test_gui.py                # Тесты GUI
├── test_gui_edge_cases.py     # Тесты GUI (edge cases)
├── test_gui_methods.py        # Тесты GUI методов
├── test_gui_real.py           # Тесты GUI (реальные сценарии)
├── test_gui_robot.py          # Тесты GUI (Robot Framework)
├── test_i18n.py               # Тесты локализации (i18n)
├── test_injector.py           # Тесты инжектора текста
├── test_integration.py        # Интеграционные тесты
├── test_integration_extended.py # Расширенные интеграционные тесты
├── test_machine_translation.py # Тесты машинного перевода
├── test_main_window.py        # Тесты главного окна
├── test_mbc.py                # Тесты MBC
├── test_ml_classifier.py      # Тесты ML классификатора
├── test_multi_charmap.py      # Тесты мульти-чармапов
├── test_plugin.py             # Тесты плагинов
├── test_plugin_api.py         # Тесты API плагинов
├── test_plugin_api_extended.py # Расширенные тесты API плагинов
├── test_plugin_manager.py     # Тесты менеджера плагинов
├── test_rom.py                # Тесты ROM
├── test_rom_cache.py          # Тесты кэширования ROM
├── test_rom_discovery.py      # Тесты обнаружения ROM
├── test_rom_validation.py     # Тесты валидации ROM
├── test_roundtrip.py          # Тесты round-trip извлечения/вставки
├── test_scanner.py            # Тесты сканера
├── test_scanner_extended.py   # Расширенные тесты сканера
├── test_tmx.py                # Тесты TMX
├── test_translation_filler.py # Тесты заполнения переводов
└── test_translation_validator.py # Тесты валидации переводов
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

Текущее покрытие см. в отчёте HTML после запуска с `--cov-report=html`
