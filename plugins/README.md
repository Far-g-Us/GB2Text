# Plugins

Каталог с плагинами игр для фреймворка извлечения текста (GB/GBC/GBA).

## Что такое плагин

Плагин — это Python-модуль, определяющий класс-наследник `GamePlugin`
(см. `core/plugin.py`). Плагин отвечает за:

- **детекцию** конкретного ROM по game code (`game_id_pattern`);
- **извлечение** текстовых сегментов из ROM (`get_text_segments(rom)`);
- опционально — декодер/чиармап, обработчик сжатия, терминаторы и т.д.

`PluginManager` автоматически находит все классы-наследники `GamePlugin`
в этой директории и регистрирует их. Специфичные плагины проверяются
до generic-фоллбеков и `AutoDetect`.

## Минимальный плагин

```python
import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.example')


class ExamplePlugin(GamePlugin):
    @property
    def game_id_pattern(self) -> str:
        return r'^GBA_(ABCD)$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        return []
```

## Stub-плагины (`is_stub = True`)

Если структура текста игры ещё не изучена, плагин должен быть честным
stub: детектировать игру по game code, возвращать пустой список и
помечать себя `is_stub = True`. Это блокирует мусорные сегменты от
`auto_detect`-фоллбека и даёт тестам/GUI корректный статус.

```python
class ExamplePlugin(GamePlugin):
    _is_stub = True

    @property
    def game_id_pattern(self) -> str:
        return r'^GBA_(ABCD)$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        return []
```

## Список плагинов

Полный список плагинов, статусы и известные факты по каждой игре —
в `SUPPORTED_GAMES.md` (корень проекта).

## Конфигурационные плагины

JSON-конфиги (без Python-кода) лежат в `plugins/config/`.
См. `plugins/config/README.md`.

## Добавление новой игры

1. Создать `plugins/gba_<game_name>.py`.
2. Унаследоваться от `GamePlugin`, задать `game_id_pattern` и
   `get_text_segments(rom)`.
3. Валидировать детекцию и извлечение на реальном ROM из `test_roms/`.
4. Обновить `SUPPORTED_GAMES.md` (включая Region-колонку).

Подробнее — `docs/en/CONTRIBUTING.md` и `docs/ru/CONTRIBUTING.md`.