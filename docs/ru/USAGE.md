# GB2Text Примеры использования

## Пример 1: Извлечение текста из GBA ROM

```python
from core.rom import GameBoyROM
from core.extractor import TextExtractor
from core.plugin_manager import PluginManager
from core.i18n import I18N

# Загрузка ROM
rom = GameBoyROM("Pokemon Ruby.gba")

# Создание экстрактора
extractor = TextExtractor(rom, PluginManager("plugins"), I18N("ru"))

# Извлечение текста
results = extractor.extract()

# Сохранение в JSON
import json
with open("extracted_text.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("Текст успешно извлечён!")
```

## Пример 2: Перевод и внедрение текста

```python
from core.rom import GameBoyROM
from core.injector import TextInjector
from core.plugin_manager import PluginManager

# Загрузка ROM
rom = GameBoyROM("game.gba")

# Создание инъектора
injector = TextInjector("game.gba")

# Получение плагина
pm = PluginManager("plugins")
plugin = pm.get_plugin(rom.get_game_id(), rom.system)

# Перевод (ваши переводы)
translations = ["Привет", "Пока", "Спасибо"]

# Внедрение
injector.inject_segment("dialogs", translations, plugin)

# Сохранение
injector.save("game_translated.gba")
```

## Пример 3: Определение языка

```python
from core.scanner import detect_multiple_languages

# Загрузка ROM
with open("game.gba", "rb") as f:
    rom_data = f.read()

# Определение языка
languages = detect_multiple_languages(rom_data[:2000])

print(f"Обнаруженные языки: {languages}")
```

## Пример 4: Поиск указателей текста

```python
from core.scanner import find_text_pointers

# Загрузка ROM
with open("game.gba", "rb") as f:
    rom_data = f.read()

# Поиск указателей (GBA использует 4-байтные указатели)
pointers = find_text_pointers(rom_data, pointer_size=4)

print(f"Найдено указателей: {len(pointers)}")
```

## Пример 5: Использование GUI

```python
from gui.main_window import GBTextExtractorGUI
import tkinter as tk

root = tk.Tk()
app = GBTextExtractorGUI(root, lang="ru")
root.mainloop()
```

## Пример 6: Создание своего плагина

```python
from core.plugin import BasePlugin

class MyGamePlugin(BasePlugin):
    def get_text_segments(self, rom):
        # Своя логика для игры
        return [
            {"name": "dialogs", "start": 0x10000, "end": 0x20000},
            {"name": "menu", "start": 0x30000, "end": 0x35000}
        ]

# Сохраните плагин в plugins/config/my_game.json
```

## Пример 7: Работа со сжатием

```python
from core.compression import AutoDetectCompressionHandler

handler = AutoDetectCompressionHandler()

# Загрузка ROM
with open("game.gba", "rb") as f:
    rom_data = f.read()

# Поиск сжатых данных по смещению
compressed_data = rom_data[0x1000:0x2000]
decompressed, end_pos = handler.decompress(compressed_data, 0)

print(f"Распаковано {len(decompressed)} байт")
```
