# Руководства по извлечению текста

Пошаговые инструкции для извлечения текста из конкретных игр.

## Структура гайда

```json
{
  "game_id": "GBA_FF5_ADVANCE",
  "description": "Извлечение текста из Final Fantasy V Advance",
  "platform": "GBA",
  "game_codes": ["BZ5E"],
  "difficulty": "medium",
  "steps": [
    {
      "title": "Поиск указателей",
      "description": "Поиск 4-байтовых GBA-указателей (0x08XXXXXX) в ROM",
      "details": "Сканировать ROM на наличие значений 0x08000000-0x09000000"
    }
  ],
  "charmap_reference": {
    "0x00": "space",
    "0x41-0x5A": "A-Z",
    "0x61-0x7A": "a-z",
    "0xFF": "END"
  },
  "tips": [
    "Используйте pointer_table_scan для автоматического поиска"
  ],
  "warnings": [
    "Некоторые игры используют LZ77-сжатие"
  ]
}
```

## Поля

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `game_id` | string | ✅ | ID игры (совпадает с именем плагина) |
| `description` | string | ✅ | Краткое описание |
| `platform` | string | ✅ | Платформа: GB, GBC, GBA |
| `game_codes` | array | ✅ | Коды игры из заголовка ROM |
| `difficulty` | string | ✅ | easy / medium / hard |
| `steps` | array | ✅ | Массив шагов |
| `charmap_reference` | object | ❌ | Ссылка на таблицу символов |
| `tips` | array | ❌ | Полезные советы |
| `warnings` | array | ❌ | Предупреждения |

## Типичные паттерны извлечения

### 1. ASCII текст (простой)
**Примеры:** Sonic Advance, KH:CoM, Phoenix Wright

```python
# Сканирование на ASCII строки
i = start_addr
while i < end:
    if 0x20 <= rom.data[i] <= 0x7E:
        str_start = i
        while i < end and 0x20 <= rom.data[i] <= 0x7E:
            i += 1
        text = rom.data[str_start:i].decode('ascii')
        # Минимальная длина для фильтрации мусора
        if len(text) >= 20:
            segments.append(...)
    i += 1
```

### 2. ASCII + control codes
**Примеры:** Castlevania AoS, Metroid Fusion

```python
# ASCII + специальные коды
terminators = [0x0D, 0x0A, 0xFF]  # Завершающие коды
control_codes = {0x06: '\n', 0x0A: '\n', 0x50: '\n'}  # Коды команд

while i < end and rom.data[i] not in terminators:
    byte = rom.data[i]
    if 0x20 <= byte <= 0x7E:
        result.append(chr(byte))
    elif byte in control_codes:
        result.append(control_codes[byte])
    i += 1
```

### 3. Multi-byte encoding (японский)
**Примеры:** FF5/FF4 Advance, FFTA

```python
# Двухбайтовые символы (кандзи/хира)
while i < end:
    byte = rom.data[i]
    if byte == 0xFF:  # END
        break
    elif 0xC2 <= byte <= 0xD6:  # Многобайтовый символ
        key = f"0x{byte:02X}{rom.data[i+1]:02X}"
        char = charmap.get(key, f'[{key}]')
        result.append(char)
        i += 2
    elif 0x20 <= byte <= 0x7E:  # ASCII
        result.append(chr(byte))
        i += 1
    else:
        result.append(f'[{byte:02X}]')
        i += 1
```

### 4. Pointer table extraction
**Примеры:** FF5 Advance, FF4 Advance, Castlevania AoS

```python
# Поиск указателей в известном диапазоне
POINTER_BASE = 0x08000000
TEXT_START = 0x36DD64
TEXT_END = 0x3A4B64

pointers = []
for i in range(TEXT_START, TEXT_END, 4):
    val = int.from_bytes(rom.data[i:i+4], 'little')
    if POINTER_BASE <= val < POINTER_BASE + len(rom.data):
        target = val - POINTER_BASE
        if target < len(rom.data):
            pointers.append((i, target))
```

### 5. LZ77 decompression (сжатые данные)
**Примеры:** Pokemon Gen 3

```python
from core.compression import GBALZ77Handler

handler = GBALZ77Handler()
# Поиск LZ77-заголовков (0x10 XX XX XX)
for i in range(start, end):
    if rom.data[i] == 0x10:
        try:
            decompressed = handler.decompress(rom.data, i)
            if decompressed:
                # Разбиение на строки по 0xFF
                strings = decompressed.split(b'\xFF')
                for s in strings:
                    if len(s) >= 5:
                        segments.append(...)
        except:
            pass
```

### 6. Pointer-based multi-language
**Примеры:** Castlevania AoS

```python
# Разные языка в разных диапазонах ROM
LANGUAGES = {
    'EN': (0x0F0000, 0x100000),
    'FR': (0x100000, 0x110000),
    'DE': (0x110000, 0x120000),
}

for lang, (start, end) in LANGUAGES.items():
    # Поиск указателей в這個 диапазоне
    for i in range(0, len(rom.data) - 4, 4):
        val = int.from_bytes(rom.data[i:i+4], 'little')
        target = val - 0x08000000
        if start <= target < end:
            # Указатель в这个 диапазоне = этот язык
            pass
```

## Процесс создания плагина

1. **Анализ заголовка ROM** — определить game_code, platform
2. **Поиск паттернов** — определить тип текста (ASCII / multi-byte / compressed)
3. **Определение указателей** — найти таблицу указателей или способ поиска
4. **Создание charmap** — составить таблицу соответствия кодов и символов
5. **Реализация `get_text_segments()`** — вернуть список сегментов с текстом
6. **Тестирование** — проверить извлечение на реальной ROM
