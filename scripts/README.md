# GB2Text Development Tools

Набор инструментов для разработки, тестирования и отладки GB2Text.

## Структура

```
scripts/
├── diagnostics.py   # Диагностика окружения и зависимостей
├── debug.py        # Отладочные инструменты
├── profile.py      # Профилирование производительности
├── diagnostics.bat # Windows batch-скрипт
└── diagnostics.sh  # Linux/Mac shell-скрипт
```

## Быстрый старт

### Диагностика

```bash
# Полная диагностика окружения
python scripts/diagnostics.py --full

# Быстрая проверка
python scripts/diagnostics.py --quick
```

### Профилирование

```bash
# Профилирование загрузки ROM
python scripts/profile.py --module rom-loading --input test.gb

# Профилирование сканирования текста
python scripts/profile.py --module scanning --input test.gb

# Профилирование полного цикла
python scripts/profile.py --module full-workflow --input test.gb --iterations 5

# Генерация отчёта о производительности
python scripts/profile.py --module benchmark --input test.gb --output benchmark.json
```

### Отладка

```bash
# Дамп заголовка ROM
python scripts/debug.py --rom test.gb --action dump-header

# Сканирование текстовых блоков
python scripts/debug.py --rom test.gb --action scan-blocks --limit 20

# Декодирование блока по адресу
python scripts/debug.py --rom test.gb --action decode-block --address 0x4000

# Включение режима трассировки
python scripts/debug.py --rom test.gb --action trace --verbose

# Детальная инспекция ROM
python scripts/debug.py --rom test.gb --action inspect
```

## Инструменты

### diagnostics.py

Проверяет конфигурацию окружения разработки:

- Версия Python и платформа
- Установленные зависимости
- Модули GB2Text
- Система плагинов
- Конфигурационные файлы
- GitHub workflows
- Тестовая среда
- Производительность импорта модулей

### profile.py

Профилирует производительность ключевых операций:

- `rom-loading` - Загрузка ROM файлов
- `scanning` - Сканирование текста
- `decoding` - Декодирование текста
- `encoding` - Кодирование текста
- `full-workflow` - Полный цикл извлечения
- `benchmark` - Комплексный бенчмарк

### debug.py

Отладочные инструменты для анализа ROM:

- `dump-header` - Информация о заголовке ROM
- `scan-blocks` - Найденные текстовые блоки
- `decode-block` - Декодирование блока по адресу
- `trace` - Режим трассировки
- `inspect` - Детальная структура ROM

## Тесты производительности

### Бенчмарки

Тесты производительности находятся в `tests/benchmarks/`:

```bash
# Запуск только бенчмарков
pytest tests/benchmarks/ --benchmark-only

# Запуск с сохранением результатов
pytest tests/benchmarks/ --benchmark-only --benchmark-save=latest

# Сравнение результатов
pytest tests/benchmarks/ --benchmark-compare=baseline
```

### Интеграционные тесты

Расширенные интеграционные тесты:

```bash
# Все интеграционные тесты
pytest tests/test_integration_extended.py -v

# Тест полного цикла
pytest tests/test_integration_extended.py::TestFullExtractionWorkflow -v

# Пакетная обработка
pytest tests/test_integration_extended.py::TestBatchProcessing -v
```

## CI/CD

Workflow файлы находятся в `.github/workflows/`:

- `tests.yml` - Основные тесты (matrix testing)
- `coverage.yml` - Покрытие кода
- `lint.yml` - Линтинг
- `security.yml` - Безопасность
- `build.yml` - Сборка

## Зависимости для разработки

```bash
# Установка зависимостей разработки
pip install -r requirements-dev.txt
```

Основные пакеты:
- pytest-xdist - Параллельное выполнение тестов
- pytest-cov - Покрытие кода
- pytest-benchmark - Бенчмарки
- memory-profiler - Профилирование памяти
- line-profiler - Профилирование построчно