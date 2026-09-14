# GB2Text API Документация

## Основные модули

### GameBoyROM
```python
from core.rom import GameBoyROM

# Загрузка ROM файла
rom = GameBoyROM("game.gba")

# Основные свойства
rom.system        # 'gb', 'gbc', или 'gba'
rom.data          # байты ROM файла
rom.header        # заголовок ROM

# Методы
game_id = rom.get_game_id()    # Получить ID игры
```

### TextExtractor
```python
from core.extractor import TextExtractor
from core.plugin_manager import PluginManager
from core.i18n import I18N

# Создание экстрактора
extractor = TextExtractor(rom, PluginManager(), I18N())

# Извлечение текста
results = extractor.extract()
```

### TextInjector
```python
from core.injector import TextInjector

# Создание инъектора
injector = TextInjector("game.gba")

# Внедрение перевода
injector.inject_segment("segment_name", ["translated text"], plugin)

# Сохранение
injector.save("output.gba")
```

### PluginManager
```python
from core.plugin_manager import PluginManager

pm = PluginManager("plugins")

# Получение плагина для игры
plugin = pm.get_plugin(game_id, system)

# Получение плагина по сигнатуре ROM (для хаков)
plugin = pm.get_plugin(game_id, system, rom=rom)
```

Плагины-хаки имеют сигнатурный гейт: когда передан объект `rom`, кандидаты
должны подходить по game id **и** проходить `validate_rom(rom)` (либо быть
уровня 0). Хак-плагин обязан возвращать `False` на несовместимый ROM.
Конфигурируемые плагины вместо этого поддерживают поле `rom_signature`.

Детект хаков имеет смысл только для игр, у которых (а) есть рабочий плагин
в этом фреймворке и (б) реально существует хак-сцена. Гейт не сработает без
плагина-кандидата, поэтому у остальных игр остаётся fallback на generic.
Игры с реальной хак-сценой:

| Игра | Коды игр | Хак-сцена |
|------|----------|-----------|
| Pokémon GBA | `BPEE`, `BPRE`, `BPGE`, `AXVE`, `AXPE` | ★★★ огромная |
| Fire Emblem GBA (Blazing Blade / Sacred Stones) | `BE7E`, `BE7J`, `AE7Y` / `BE8E`, `BE8J`, `BE8P` | ★★★ большая |
| Golden Sun / The Lost Age | `AGSE` / `AGFE` | ★★ заметная |
| Advance Wars | `AWRE` | ★★ заметная |
| Castlevania (Aria of Sorrow / Circle of the Moon / Harmony of Dissonance) | `A2CE`, `AGBJ`, `AGBE` / `AAME`, `AAMJ`, `AAMP` / `ACHP`, `ACHJ`, `ACHI` | ★ точечная |
| Metroid Fusion | `AMTE`, `AMTP`, `AMTJ` | ★ точечная |
| FF5 / FF6 Advance | `BZ5E`, `BZ5J`, `BZ5P` / `BZ6E`, `BZ6J`, `BZ6P` | ★ точечная |
| Mega Man Battle Network 1/2 | `AREP`, `ABKE`, `ABKJ` / `AM2P` | ★ точечная |
| The Legend of Zelda: The Minish Cap | `BZME` | ★ точечная |
| Breath of Fire (GBA) | `ABFE` | ★ точечная |

Эталонные конфиги (паттерн title замени на название конкретного хака):

Pokémon GBA (Emerald и др.):
```json
{
  "game_id_pattern": "^GBA_(BPEE|BPRE|BPGE|AXVE|AXPE)$",
  "rom_signature": [
    { "title_pattern": "^POKEMON HACK$", "min_size": 16777216 }
  ]
}
```
Fire Emblem GBA:
```json
{
  "game_id_pattern": "^GBA_(BE7E|BE7J|AE7Y|BE8E|BE8J|BE8P)$",
  "rom_signature": [
    { "title_pattern": "^FEMAKER", "min_size": 16777216 }
  ]
}
```

`title_pattern` матчится через `re.match` (префикс) — добавляй явные якоря
(`^...$`), иначе хак-плагин перехватит все ROM с тем же `game_code`.
`min_size`/`max_size` ограничивают размер ROM в байтах
(`min <= размер <= max`); запись без полей подходит любому ROM.

### Scanner Functions
```python
from core.scanner import find_text_pointers, detect_multiple_languages

# Поиск указателей
pointers = find_text_pointers(rom_data, pointer_size=4)

# Определение языка
languages = detect_multiple_languages(rom_data)
```

### Encoder/Decoder
```python
from core.decoder import CharMapDecoder
from core.encoding import get_generic_english_charmap

# Декодирование
decoder = CharMapDecoder(get_generic_english_charmap())
text = decoder.decode(rom_data)
```

## GUI

### GBTextExtractorGUI
```python
from gui.main_window import GBTextExtractorGUI
import tkinter as tk

root = tk.Tk()
app = GBTextExtractorGUI(root, lang="ru")
root.mainloop()
```

## Плагины

### Generic Plugins
```python
from plugins.generic import GenericGBAPlugin

plugin = GenericGBAPlugin()
segments = plugin.get_text_segments(rom)
```
