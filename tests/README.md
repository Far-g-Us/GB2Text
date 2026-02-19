# Тестирование GB2Text

## Зачем нужны тесты?

Тесты обеспечивают:
- **Надёжность** - проверяют, что код работает корректно
- **Безопасность** - предотвращают регрессии при изменениях
- **Документацию** - показывают ожидаемое поведение кода
- **Упрощение отладки** - быстро находят проблемы

## Установка зависимостей

```bash
pip install -r requirements-dev.txt
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
├── test_charset.py     # Тесты загрузки charset файлов
├── test_decoder.py     # Тесты декодера
└── test_constants.py  # Тесты констант
```

## Типы тестов

### 1. Unit-тесты
Тестируют отдельные функции/классы изолированно:
- `test_charset.py` - загрузка таблиц символов
- `test_decoder.py` - кодирование/декодирование
- `test_constants.py` - константы проекта

### 2. Интеграционные тесты
Тестируют взаимодействие модулей (будут добавлены)

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

Целевое покрытие: 70%+ для core модулей

Текущее покрытие см. в отчёте HTML после запуска с `--cov-report=html`
