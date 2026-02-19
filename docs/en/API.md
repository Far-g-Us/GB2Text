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
```

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
