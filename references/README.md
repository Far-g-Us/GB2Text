# References

Исходные материалы, использованные при разработке плагинов и компонентов GB2Text.

## FFTA LZSS Decompressor

**Файл:** `ffta_lzss_myguyz.py`

**Источник:** [MyGuyz/Final-Fantasy-Tactics-Advance](https://github.com/MyGuyz/Final-Fantasy-Tactics-Advance) — `tools/lzss01.py`

**Использование:** Референсная реализация FFTA LZSS декомпрессора (тег 0x01, 8 типов команд). Использована для верификации нашего `FFTA_LZSSHandler` в `core/compression.py`.

## FFTA Character Definitions

**Файл:** `ffta_character_definitions.py`

**Источник:** [LeonarthCG/FFTA_Engine_Hacks](https://github.com/LeonarthCG/FFTA_Engine_Hacks) — `Text/Text Character Definitions.event`

**Использование:** Справочные определения символов FFTA для Event Assembler. Двухбайтовая кодировка (0x80 XX, 0x81 XX). Верифицировано против нашего плагина `gba_fft_advance.py` — совпадает.
