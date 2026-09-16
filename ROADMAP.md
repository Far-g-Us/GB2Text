# GB2Text Roadmap

**Текущая версия:** 1.3

## ✅ Версия 0.9

### Ядро
- [x] Извлечение текста из GB/GBC/GBA ROM
- [x] Автоматическое определение текстовых сегментов
- [x] Автоматическое определение таблиц символов (en/ru/ja)
- [x] Поддержка сжатия LZ77, LZSS, RLE
- [x] Auto-detect сжатия
- [x] Система плагинов для конфигураций
- [x] Ввод текста обратно в ROM

### GUI
- [x] Графический интерфейс на Tkinter
- [x] Редактирование и перевод текста
- [x] Настройка кодировок
- [x] Экспорт в JSON

### Инфраструктура
- [x] Константы в `core/constants.py`
- [x] Локализация (en/ru/ja/zh)
- [x] Файлы charset.json для каждого языка
- [x] Базовая структура тестов
- [x] Документация

---

## ✅ Версия 1.0

### Приоритет 1 - Стабильность
- [x] Расширение покрытия тестами (базовое покрытие core модулей)
- [x] CI/CD для автоматического запуска тестов (.github/workflows/tests.yml)
- [x] Валидация ROM файлов (проверка расширения, размера)
- [x] Тесты для GUI (tests/test_main_window.py)
- [x] **Расширенное тестирование** — Matrix testing (Python 3.10-3.12, Ubuntu, Windows)
- [x] **Бенчмарки производительности** — tests/benchmarks/test_performance.py
- [x] **Интеграционные тесты** — tests/test_integration_extended.py

### Приоритет 2 - Улучшение UX
- [x] Улучшенный GUI — более интуитивный интерфейс
- [x] Предпросмотр изменений перед сохранением
- [x] История изменений (undo/redo) — Ctrl+Z / Ctrl+Y
- [x] Тёмная тема (dark mode)
- [x] Поддержка перетаскивания (drag & drop) файлов
- [x] Копирование/вставка текста между сегментами
- [x] Поиск и замена текста (Ctrl+F, F3, Shift+F3, Ctrl+H)
- [x] Пакетная обработка ROM (выбор нескольких файлов, обработка с прогресс-баром)
- [x] Улучшенные стили Combobox
- [x] Отображение названий языков вместо кодов в UI
- [x] Экспорт/импорт CSV

### Приоритет 3 - Документация
- [x] Базовая документация API
- [x] Примеры использования

### Приоритет 4 - Исправления
- [x] Исправлена загрузка переводов из подпапок locales/{lang}/messages.json
- [x] Добавлены недостающие ключи локализации (settings.theme, mbc.type, load и др.)
- [x] Добавлен китайский язык (zh) в поддерживаемые языки
- [x] Исправлена функция смены темы
- [x] Исправлены диагностические скрипты (diagnostics.bat, diagnostics.sh)
- [x] Добавлен README в test_roms/
- [x] Добавлены константы UI (COMBOBOX_WIDTH, DEFAULT_PADDING и др.)
- [x] Заменены голые исключения (except:) на конкретные типы
- [x] **Добавлено кэширование ROM** — при переключении между вкладками Extract и Edit ROM не перезагружается
- [x] Добавлен модуль core/rom_cache.py с классом ROMCache

---

## ✅ Версия 1.1

### Новые функции
- [x] Пакетная обработка нескольких ROM
- [x] Сравнение текста между версиями ROM
- [x] Интеграция с сервисами машинного перевода (Google Translate, DeepL)
- [x] Экспорт в другие форматы (CSV, XML)
- [x] Экспорт/импорт в формат TMX (Translation Memory eXchange)

### Улучшение анализа
- [x] Улучшенное определение сегментов с ML
- [x] Автоматическое определение типа сжатия
- [x] Поддержка нескольких таблиц символов в одном сегменте
- [x] Улучшенное определение нестандартных кодировок
- [x] Автоматическое определение языка в ROM

### Утилиты
- [x] Валидация перевода (проверка длины текста)
- [x] Автоматическое заполнение нулевых переводов
- [x] **Инструменты разработки** — scripts/debug.py, profiler.py, diagnostics.py
- [x] **Бенчмарки** — tests/benchmarks/test_performance.py
- [x] **Coverage отчёты** — .github/workflows/coverage.yml

### Плагины и расширяемость
- [x] API для создания плагинов
- [x] Шаблоны конфигураций

---

## ✅ Версия 1.2

### Плагины GBA игр
- [x] Поддержка 36 GBA игр (Pokemon, Fire Emblem, FF4/5/6, Zelda TMC, Castlevania и др.)
- [x] FFTA: полное извлечение текста через указательные таблицы + LZSS + CRN
- [x] Huffman декодер для Fire Emblem
- [x] Constant-stride детектор для автоматического поиска таблиц
- [x] DataCrystal TBL таблицы для Castlevania AoS, Wario Land 4, Astro Boy

### Документация
- [x] Двуязычная документация (en/ru): README, CONTRIBUTING, ROADMAP, API
- [x] Тестовое руководство (tests/README.md)
- [x] SUPPORTED_GAMES.md — список поддерживаемых игр
- [x] Юридический guard — нет дистрибуции ROM, disclaimer на месте

### Качество
- [x] 15 plugin contract тестов (все проходят)
- [x] Исправлены ошибки в ROADMAP (CI/CD, API docs, ссылки)

---

## ✅ Версия 1.3

*Незакрытые пункты из версий 1.1 перенесены сюда (помечены «из 1.1»).*

### Приоритет 1 — Доупаковка
- [x] CI/CD: .github/workflows/tests.yml + coverage.yml + lint.yml + security.yml + build.yml
- [x] Pointer relocation после вставки текста (в core/injector.py; для TMC-банков — частично)
- [x] Пересчёт header/global checksum после инъекции (injector.save() → rom.recalculate_checksums; GBA/CGB variants)
- [x] Тесты для FFTA LZSS (tests/test_ffta_lzss.py) и Huffman декодеров (tests/test_golden_sun.py)

### Приоритет 2 — Новые плагины
- [x] Pokemon GBA (Emerald/FireRed/LeafGreen/Ruby/Sapphire USA) — полное покрытие: фикс-таблицы + dialogue pointer-манифесты (guard по заголовку)
- [x] GB/GBC плагины: Pokémon Gen 1 (Red/Blue) — plugin + детекция по заголовку + round-trip тесты
- [x] Metroid Fusion — 1239 dialogue lines via pointer table, 4 ASCII blocks, byte-identical round-trip
- [x] Wario Land 4 — 80 known locations (passages/levels/music/shops), EN-only windows, round-trip verified
- [x] Castlevania AoS — инжектор на уровне языковых блоков (in-place / relocation)
- [x] ROM-хаки: сигнатурный гейт (`get_plugin(..., rom=)`, `rom_signature` в конфигах) — data-driven, без кода под конкретный хак.
- [x] Эталонные конфиги `rom_signature` для игр с хак-сценами (список в docs/en|ru/API.md: Pokémon GBA, Fire Emblem GBA, Golden Sun, Advance Wars; остальные — по мере появления хаков)

### Приоритет 3 — API для агентов
- [x] Модуль `api/` — SDK поверх core: resolve_rom/resolve_output, list_plugins, detect, extract, inject, get_version, load_json_file; контрактные коды SDKError
- [x] `python -m api.cli` — подкоманды plugins/detect/extract/inject/serve; JSON-вывод, коды выхода 0/1/2, конфликт `--json`/`--format json` → ошибка
- [x] HTTP/JSON сервис (`api/server.py`) на stdlib ThreadingHTTPServer — /health /plugins /detect /extract /inject; лимиты Content-Type/размера, таймаут чтения, 503 BUSY семафор, per-output lock на inject, `Connection: close`
- [x] Security-проход (critic + security-critic): `_is_loopback`, нет утечек `str(exc)`, маскировка INTERNAL, mkstemp + os.replace атомарный inject, лимит 1MB у load_json_file
- [x] Тесты: tests/test_api.py + test_api_cli.py + test_api_http.py (~39 кейсов) + синтетические ROM-фикстуры в conftest; полный прогон api+roundtrip зелёный

### Приоритет 4 — UI/UX
- [x] Визуальный редактор таблицы символов (из 1.1) — диалог на вкладке «Настройки»: просмотр/правка charmap, добавление с валидацией дублей, удаление, экспорт в JSON; ROM не модифицируется
- [x] Карта ROM с подсветкой текстовых сегментов (из 1.1) — вкладка «Карта ROM»: блоки по 32KB, подсветка сегментов из current_segments_meta, клик → детали сегмента, перерисовка по смене темы и вкладки
- [x] Многооконный режим (из 1.1) — «Открыть в новом окне»: независимый экземпляр GUI, только главное окно пишет настройки, warning-диалог только в главном
- [x] Предпросмотр изменений в реальном времени (из 1.1) — панель на вкладке «Редактирование»: токены `[TOKEN]` → `<token>`, счётчик символов/оригинала, обновление по `<KeyRelease>`
- [x] Фильтр/поиск по имени сегмента (для 1500+ сегментов) — строка фильтра + счётчик «X / Y» на вкладке «Извлечение»

### Приоритет 5 — Экспорт
- [x] XLIFF формат (CAT-интеграция: memoQ, Trados) (из 1.1) — экспорт + импорт в GUI (`file.import.xliff`, маппинг по индексу trans-unit, `apply_translations`)
- [x] Plugin auto-discovery через entry_points

### Приоритет 6 — Утилиты
- [x] Проверка орфографии (из 1.1) — core/spell_checker.py (pyspellchecker, игнор токенов [XX]/{VAR}/%s/числа), GUI red underline на вкладке «Редактирование», язык auto/ru/en, debounce 500ms

---

## 🚧 Версия 1.4

### Качество
- [ ] Увеличить покрытие тестами
- [x] Довести остальные плагины до состояния stub (детекция + честный пустой результат)

### Инструменты починки (repair tools)
- [ ] CRC/checksum fixer — отдельная CLI-команда для ROM, битых сторонними хекс-редакторами (header + global checksum, GB/GBC/GBA варианты)
- [x] Pointer validator/repair — сканирование таблиц указателей на несогласованность после ручного патчинга, предложение восстановления; core/pointer_validator.py: validate_pointer_table (статусы ok/zero/out_of_bounds/duplicate), problem_summary, repair_pointer_table (LE, база адресации + 2/4-байтные указатели)(может работать неправильно)
- [x] IPS/BPS patch generator — генерация патч-файла вместо дистрибуции патченных ROM (легальная дистрибуция перевода); core/patcher.py: bps_create/bps_apply (CRC32-верифицируемый BPS1, SourceRead/TargetRead/SourceCopy), ips_create/ips_apply (литералы + RLE), create_patch/apply_patch с автоопределением формата; round-trip на реальных ROM в test_roms/(может работать неправильно)
- [ ] Bank-aware pointer scan (из backlog) — честная схема bank_byte + addr для GB/GBC

### Агенты и API
- [ ] MCP-сервер — обёртка над существующим api/-слоем: extract/inject/detect как MCP-инструменты для агентов (контракт SDKError переиспользуется)

### Перевод
- [ ] Line-length / textbox simulator — симуляция переноса строк перевода в реальных границах textbox (max_length/fixed_width) до инъекции
- [ ] DTE-словарь compression helper — автоматический построитель DTE-таблицы по частотному анализу би-грамм под конкретный перевод (GB/GBC, для языков длиннее английского)

### Плагины и платформы
- [x] Community/shared plugin registry — каталог сторонних плагинов (статический JSON на GitHub Pages), установка без форка репо

---

## 🔭 Будущее (backlog)

*Не вошло в v1.4; кандидаты для следующих версий.*

### Перевод
- FE Huffman для Europe ROM (адреса деревьев неизвестны)
- Орфография на этапе инжекта (сейчас — только GUI-предупреждение)

### GB/GBC
- Компрессия GB/GBC (RLE/LZ для Gen1/2)

### Плагины и платформы
- Nintendo DS — плагины для новой платформы
- Сторонние плагины через entry_points — демо-пакет (инфраструктура готова)
- Community/shared plugin registry — каталог сторонних плагинов (статический JSON на GitHub Pages), установка без форка репо

### Визуальные инструменты
- Редактор тайловой графики шрифта — просмотр/правка glyph-tiles (критично для нестандартных алфавитов: кириллица в GB-играх требует перерисовки шрифта под ширину тайла)
- Playtest-ассистент через эмулятор — headless-режим mGBA для авто-прохода по меню/диалогам со скриншотами, проверка что текст не вылезает за рамки

### Инструменты
- Облачная синхронизация — сохранение переводов в облаке
- Save-file repair — починка сохранений, отдельная тема (частый запрос в ромхак-комьюнити)

### API
- Webhook/callback при завершении длительных операций (актуально для больших ROM с 1500+ сегментов)
- Дифф-эндпоинт `/diff` — сравнение текста между версиями ROM (ядро есть с 1.1, но не выведено в API)
- Экспорт метрик (Prometheus-style `/metrics`) — для запуска сервера в CI

### Производительность
- Асинхронная загрузка ROM в отдельном потоке (частично)
- Lazy loading плагинов

---

## 🐛 Известные проблемы

- Некоторые игры с нестандартной кодировкой не распознаются
- FE Huffman декодер не работает для Europe ROMs (неизвестны адреса деревьев)
- Неоднозначность CP866/JIS: чисто русская 8-битная ROM (CP866) без ASCII может
  быть ошибочно определена как японская — обе кодировки разделяют диапазоны
  байтов (0x80-0xDF). Детектор отдаёт приоритет русскому при наличии
  эксклюзивных CP866 байт (0xE0-0xFF); для плагинных игр язык из
  `segment['lang']` плагина имеет приоритет над эвристикой.

---

## 🤝 Как участвовать

1. Проверьте [CONTRIBUTING.md](CONTRIBUTING.md)
2. Создайте issue перед началом работы
3. Напишите тесты для новых функций
4. Обновите документацию

---

*Roadmap обновлён: 2026-09-16*
