# Конфигурации плагинов

JSON-конфигурации для поддержки конкретных игр.

## Шаблоны

| Файл | Платформа | Описание |
|------|-----------|----------|
| `_template_game.json` | Любая | Минимальный шаблон |
| `_template_gba.json` | GBA | Полный шаблон с паттернами |
| `_template_gb_basic.json` | GB/GBC | Базовый шаблон |
| `_template_gbc.json` | GBC | С расширенной кодировкой |
| `example.json` | GBA | Рабочий пример |

## Режимы извлечения

### ASCII (простой)
```json
{
  "encoding": "ascii",
  "terminators": ["0x00"],
  "min_length": 20
}
```
**Игры:** Sonic Advance, KH:CoM, Phoenix Wright

### ASCII + control codes
```json
{
  "encoding": "ascii_with_control_codes",
  "terminators": ["0x0D", "0x0A", "0xFF"],
  "control_codes": {"0x06": "\n", "0x0A": "\n"}
}
```
**Игры:** Castlevania AoS, Metroid Fusion

### Multi-byte (японский)
```json
{
  "encoding": "multi_byte",
  "primary_range": ["0xC2-0xD6"],
  "terminators": ["0x0D", "0xFF"]
}
```
**Игры:** FF5/FF4 Advance, FFTA

### Pointer table
```json
{
  "encoding": "pointer_table",
  "pointer_base": 134217728,
  "pointer_size": 4
}
```
**Игры:** FF5/FF4 Advance, Castlevania AoS

### Compressed (LZ77)
```json
{
  "encoding": "compressed",
  "header_byte": "0x10",
  "handler": "GBALZ77Handler"
}
```
**Игры:** Pokemon Gen 3

## Как создать плагин

1. Скопируйте шаблон
2. Определите `game_id_pattern` (regex для Game ID из заголовка ROM)
3. Выберите режим извлечения
4. Укажите адреса сегментов
5. Создайте charmap (таблицу символов)

## Как найти game_id

Откройте ROM в hex-редакторе:
- **GBA:** offset 192 (4 байта), например `BZ5E` = FF5 Advance
- **GB:** offset 308 (11 байт) = название, offset 304 (4 байта) = код

## Как найти текстовые сегменты

1. Запустите `python main.py` с ROM
2. Включите "Debug mode" для просмотра найденных сегментов
3. Определите терминатор (0x00, 0xFF, 0x0D, 0x50)
4. Проверьте min_length для фильтрации мусора

## Валидация

Параметры проверки качества извлечения:

```json
{
  "validation": {
    "min_alpha_ratio": 0.3,
    "max_unknown_bytes": 0.2,
    "check_terminators": true
  }
}
```

- `min_alpha_ratio` — минимальная доля букв (0.0-1.0)
- `max_unknown_bytes` — максимальная доля неизвестных байтов
