# GB2Text Usage Examples

## Example 1: Extract Text from GBA ROM

```python
from core.rom import GameBoyROM
from core.extractor import TextExtractor
from core.plugin_manager import PluginManager
from core.i18n import I18N

# Load ROM
rom = GameBoyROM("Pokemon Ruby.gba")

# Create extractor
extractor = TextExtractor(rom, PluginManager("plugins"), I18N("en"))

# Extract text
results = extractor.extract()

# Save to JSON
import json
with open("extracted_text.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("Text extracted successfully!")
```

## Example 2: Translate and Inject Text

```python
from core.rom import GameBoyROM
from core.injector import TextInjector
from core.plugin_manager import PluginManager

# Load ROM
rom = GameBoyROM("game.gba")

# Create injector
injector = TextInjector("game.gba")

# Get plugin
pm = PluginManager("plugins")
plugin = pm.get_plugin(rom.get_game_id(), rom.system)

# Translate (your translations)
translations = ["Привет", "Пока", "Спасибо"]

# Inject
injector.inject_segment("dialogs", translations, plugin)

# Save
injector.save("game_translated.gba")
```

## Example 3: Detect Language

```python
from core.scanner import detect_multiple_languages

# Load ROM
with open("game.gba", "rb") as f:
    rom_data = f.read()

# Detect language
languages = detect_multiple_languages(rom_data[:2000])

print(f"Detected languages: {languages}")
```

## Example 4: Find Text Pointers

```python
from core.scanner import find_text_pointers

# Load ROM
with open("game.gba", "rb") as f:
    rom_data = f.read()

# Find pointers (GBA uses 4-byte pointers)
pointers = find_text_pointers(rom_data, pointer_size=4)

print(f"Found {len(pointers)} text pointers")
```

## Example 5: Use GUI

```python
from gui.main_window import GBTextExtractorGUI
import tkinter as tk

root = tk.Tk()
app = GBTextExtractorGUI(root, lang="ru")
root.mainloop()
```

## Example 6: Create Custom Plugin

```python
from core.plugin import BasePlugin

class MyGamePlugin(BasePlugin):
    def get_text_segments(self, rom):
        # Custom logic for your game
        return [
            {"name": "dialogs", "start": 0x10000, "end": 0x20000},
            {"name": "menu", "start": 0x30000, "end": 0x35000}
        ]

# Register and use
pm = PluginManager("plugins")
# Save plugin to plugins/config/my_game.json
```

## Example 7: Work with Compression

```python
from core.compression import AutoDetectCompressionHandler

handler = AutoDetectCompressionHandler()

# Decompress data
with open("game.gba", "rb") as f:
    rom_data = f.read()

# Find compressed data at specific offset
compressed_data = rom_data[0x1000:0x2000]
decompressed, end_pos = handler.decompress(compressed_data, 0)

print(f"Decompressed {len(decompressed)} bytes")
```
