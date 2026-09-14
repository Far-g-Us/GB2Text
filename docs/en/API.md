# GB2Text API Documentation

## Core Modules

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

ROM-hack plugins expose a signature gate: when a `rom` object is passed,
candidates must match the game id **and** pass `validate_rom(rom)` (or be a
level-0 plugin). A hack's `validate_rom` must return `False` for incompatible
ROMs. Configurable plugins support a `rom_signature` field instead.

Hack detection only makes sense for games that (a) have a working plugin in
this framework and (b) actually have a ROM-hack scene. The gate never fires
without a candidate plugin, so other games keep falling back to the generic
plugin. Games with a real text-hack scene:

| Game | Game codes | Hack scene |
|------|-----------|------------|
| Pokémon GBA | `BPEE`, `BPRE`, `BPGE`, `AXVE`, `AXPE` | ★★★ huge |
| Fire Emblem GBA (Blazing Blade / Sacred Stones) | `BE7E`, `BE7J`, `AE7Y` / `BE8E`, `BE8J`, `BE8P` | ★★★ large |
| Golden Sun / The Lost Age | `AGSE` / `AGFE` | ★★ moderate |
| Advance Wars | `AWRE` | ★★ moderate |
| Castlevania (Aria of Sorrow / Circle of the Moon / Harmony of Dissonance) | `A2CE`, `AGBJ`, `AGBE` / `AAME`, `AAMJ`, `AAMP` / `ACHP`, `ACHJ`, `ACHI` | ★ small |
| Metroid Fusion | `AMTE`, `AMTP`, `AMTJ` | ★ small |
| FF5 / FF6 Advance | `BZ5E`, `BZ5J`, `BZ5P` / `BZ6E`, `BZ6J`, `BZ6P` | ★ small |
| Mega Man Battle Network 1/2 | `AREP`, `ABKE`, `ABKJ` / `AM2P` | ★ small |
| The Legend of Zelda: The Minish Cap | `BZME` | ★ small |
| Breath of Fire (GBA) | `ABFE` | ★ small |

Reference configs (replace the title pattern with the actual hack title):

Pokémon GBA (Emerald etc.):
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

`title_pattern` is matched with `re.match` (prefix), so anchor it explicitly
(`^...$`) to avoid a hack plugin capturing unrelated ROMs with the same
`game_code`. `min_size`/`max_size` bound the ROM size in bytes
(`min <= size <= max`); an entry without any field matches any ROM.

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

## Plugins

### Generic Plugins
```python
from plugins.generic import GenericGBAPlugin

plugin = GenericGBAPlugin()
segments = plugin.get_text_segments(rom)
```
