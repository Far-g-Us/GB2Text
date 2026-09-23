# Agent API Plan — GB2Text

Внутренний план: дать агентам и скриптам программный доступ к core без GUI.
Три интерфейса: Python-модуль (REPL/Jupyter), CLI-команды, HTTP/JSON (stdlib).
Контракт core (`get_plugin(..., rom=)`, `TextExtractor(..., rom=)` и т.д.) НЕ
меняется; GUI не трогаем. Документ учитывает результаты пре-ревью критика и
security-критика (режим B).

## 1. Текущее состояние

- CLI уже есть в `main.py` (extract text/json/csv, inject через --translations,
  --lang en|ru|ja), но: не JSON-согласован, без list/detect, `--lang` без zh,
  hardcode plugin-dir'а в inject, ошибки через `print` без кода возврата.
- core API зрелый: `TextExtractor(rom).extract() -> dict[str, list[dict]]`,
  `TextInjector(rom).inject_segment(name, texts, plugin)`, `get_safe_plugin_manager(dir)`.
- Проект запускается из корня (no package install), GUI-тесты на реальных ROM
  в test_roms/ (skip, если нет). Pre-existing: ruff 56 / mypy 360 ошибок по
  проекту — критерии приёмки scoped на наши файлы.
- Известные pre-existing (document, не фиксим): main.py --lang без zh;
  `PluginManager(plugins_dir)` создаёт каталог и example.json при создании —
  api изолирует от этого. `injector.save()` пересчитывает header/global
  checksum (rom.recalculate_checksums: GBA — complement 0x0BD, GB/GBC —
  header 0x14D + глобальный по всему ROM).

## 2. Цели

1. Единый Python-модуль `api/` (REPL/Jupyter-first): чистые функции с dataclass/JSON
   результатами, CancellationToken для длинных операций.
2. `python -m api.cli` subcommands: `plugins`, `detect`, `extract`, `inject`,
   `serve` — JSON-совместимый вывод, стабильные коды возврата (0/1/2).
3. HTTP/JSON сервис на stdlib (`ThreadingHTTPServer`), bind по умолчанию
   127.0.0.1, эндпоинты /health /plugins /detect /extract /inject.
4. Стабильный контракт ответов: `{"ok": bool, "data": ...|"error": {...}}`.
5. Тесты in-process (api/HTTP handler) + subprocess (CLI); round-trip и
   существующие тесты не ломаем.

## 3. Контракт

Ответ (все интерфейсы):

```
HTTP/CLI --json: {"ok": true, "data": ...}
                 {"ok": false, "error": {"code": "...", "message": "..."}}
REPL: Python-значения (dataclass), исключения SDKError как есть.
```

Коды ошибок: PLUGIN_NOT_FOUND, UNSUPPORTED_SYSTEM, ROM_ERROR, IO_ERROR,
VALIDATION_ERROR, INTERNAL, PAYLOAD_TOO_LARGE, TIMEOUT, BUSY, METHOD_NOT_ALLOWED.

HTTP wire-ошибки (400 malformed JSON, 404 endpoint, 405 метод, 408 timeout,
413 payload, 415 content-type) НЕ маскируются под `ok:false`-контракт — только
contract-ошибки (PLUGIN_NOT_FOUND и т.п.) отдаются как `200 {"ok":false}`.

CLI: exit 0 = ok; 1 = runtime/validation (contract-ошибка на stdout);
2 = parse-ошибка argparse. JSON-ответы на stdout (не stderr), utf-8
(`sys.stdout.reconfigure(encoding='utf-8')` при `--json`).
`--format json` (сырые результаты extract, как main.py) и `--json`
(contract-обёртка) взаимоисключающие: если оба указаны — argparse выдаёт
ошибку (код выхода 2).

## 4. Модуль api/

Файлы:
```
api/
  __init__.py    # публичные функции + dataclass'ы результата
  _core.py       # тонкие обёртки над core: маппинг ошибок + безопасные пути
  cli.py         # argparse подкоманды; main(); serve via api.server
  server.py      # http.server ThreadingHTTPServer + handler (contract+wire-ошибки)
```

Публичные функции:

- `list_plugins(plugin_dir=None) -> list[PluginInfo]` — read-only: НЕ создаём
  каталог/example.json (проверяем существование dir до PluginManager).
- `detect(rom_path, *, plugin_dir=None) -> GameInfo` (game_id, system, plugin,
  hack-signature).
- `extract(rom_path, *, plugin_dir=None, max_segments=None, language="en",
  progress=None) -> ExtractionResult` — segments: dict[name, list[Message]],
  stats. Message: `text`, `offset` (+ доп. поля pointer_dialogues из core);
  `decoder_name` — синтезируется api-слоем из `segment['decoder']` явно
  (core его не отдаёт). `language` — фильтр сегментов по `lang` конфига
  (в core нет отдельного параметра; если сегменты не помечены — опция no-op).
- `inject(rom_path, translations, *, output_path=None, plugin_dir=None) -> InjectionResult`
  — translations: `dict[segment_name, list[dict]]` с ключом `translation`
  (СОВМЕСТИМО с main.py:172), в порядке extract. `output_path` по умолчанию —
  рядом с rom (`rom_path` + `_translated` суффикс). Отчёт по сегментам; checksum
  пересчитывается в `injector.save()` (rom.recalculate_checksums), итоговое значение
  сообщается в отчёте.
- `serve(host="127.0.0.1", port=8765, *, plugin_dir=None, max_workers=4)` —
  запускает сервер (blocking); вызывается из `cli.main()`. При host не loopback
  печатает предупреждение в stderr («no authentication, trusted network only»).

Безопасные пути (P0, security-ревью):
- Все функции, принимающие `rom_path`: `Path(rom).resolve()`, `not is_symlink()`,
  `validate_rom_file()` (core/rom.py:36) — расширение>.gb/.gbc/.gba, existence,
  MAX_ROM_SIZE. Иначе `IO_ERROR`/`UNSUPPORTED_SYSTEM`.
- `inject`: `output_path=None` -> рядом с ROM; явный -> `resolve()`, `not is_symlink()`
  и `parent(output) == parent(rom)` (иначе IO_ERROR). Запись атомарная через
  `tempfile.mkstemp` в том же каталоге + `os.replace` (не остаётся частичных
  файлов, нет предсказуемого tmp-пути).
- Симлинки на ROM не принимаются (реальный файл проверяется тем же validate).
  32MB-ROM: 3× в памяти (GameBoyROM + original + modified) — после `save()`
  явный `del injector`, документируем ограничение.

## 5. CLI (python -m api.cli)

```
api.cli plugins [--plugin-dir DIR] [--json]
api.cli detect ROM [--plugin-dir DIR] [--json]
api.cli extract ROM -o OUT [--format json|text|csv]
                [--plugin-dir DIR] [--max-segments N] [--lang en|ru|ja|zh] [--json]
api.cli inject ROM --translations T.json [--output-rom OUT] [--plugin-dir DIR] [--json]
api.cli serve [--host 127.0.0.1] [--port 8765] [--plugin-dir DIR]
```

- `--json` — машиночитаемый контракт (§3); без него — человекочитаемо как main.py.
- inject принимает формат main.py (`list[dict]` c `translation`); несовпадение —
  VALIDATION_ERROR с понятным сообщением.
- `--lang`: выбор языка интерфейса/текста — задокументировать что в extract
  это фильтр по конфигу сегментов, в остальных командах no-op.

## 6. HTTP (stdlib)

`api/server.py`: `ThreadingHTTPServer` + `BaseHTTPRequestHandler`.

- Bind: по умолчанию 127.0.0.1; `--host 0.0.0.0/non-loopback` -> WARNING в stderr
  (нет авторизации, только trusted network).
- Эндпоинты:
  - GET  /health   -> {"ok": true, "data": {"version": ..., "status": "ok"}}
  - GET  /plugins  -> list_plugins
  - POST /detect   -> body {"rom": "/abs/path"}
  - POST /extract  -> body {"rom", "max_segments", "lang"}
  - POST /inject   -> body {"rom", "translations", "output"}
  - POST /diff     -> body {"rom1", "rom2"} (read-only сравнение текста двух ROM)
- Content-Type: только `application/json` (413->нет, 415 VOID), иначе 415.
  Browser form-POST (CSRF) отклоняется без CORS-разборов.
- Body limit: `max_content_length = 50 MB` (покрывает MAX_ROM_SIZE 64MB? НЕТ —
  поэтому дробью: для /detect,/extract,/diff дефолт 1MB+path, для /inject до MAX_ROM_SIZE
  ограничение отдельно). UB: если Content-Length > лимита -> 413 PAYLOAD_TOO_LARGE
  до чтения body. Без Content-Length — читать с лимитом.
- Таймаут: `timeout_read_body = 10s` ТОЛЬКО на чтение body (после чтения
  `settimeout(None)` перед обработкой, чтобы долгий extract не убился) ->
  408 TIMEOUT.
- Параллелизм: `threading.Semaphore(max_workers)` (default 4), при исчерпании —
  503 BUSY. RLock не нужен (запрос-поток), но для записи output — per-path lock
  (`dict[resolved_path, threading.Lock]` в server), чтобы параллельные /inject
  в один файл не гонялись.
- Обработка ошибок: try/except, маппинг в contract; traceback НИКОГДА в ответ.
  Malformed JSON -> 400 (wire, отдельно). Неизвестный endpoint -> 404.
- Логирование: access log по умолчанию из `BaseHTTPRequestHandler.log_message`
  ЗАМЕНА на кастомный: метод, URL-path (не файловый путь тела), status, latency.
  body fields (rom/output) и заголовки НЕ логируются.
- Memory: после extract/inject в потоке — явный `del injector`; документируем,
  что concurrent 4×extract 32MB ROM ≈ 400MB пик.

## 7. Тестирование

- `tests/conftest.py`: фикстура `api_rom_bytes` — синтетический GB ROM по
  паттерну `_build_gb_rom` из test_roundtrip.py:35-84 (валидный logo + checksum),
  явный ConfigurablePlugin-конфиг с charmap (детерминизм), текст плейсхолдеры
  (legal guard — никакого реального игрового текста).
- `tests/test_api.py`: REPL — detect/extract/list_plugins/inject round-trip mini,
  IO_ERROR/UNSUPPORTED_SYSTEM/PLUGIN_NOT_FOUND/валидация output родителя.
- `tests/test_api_cli.py`: subprocess через `sys.executable -m api.cli`,
  temp dir с конфигом, проверка JSON/кодов 0/1/2, взаимоисключение --format/--json.
- `tests/test_api_http.py`: ThreadingHTTPServer на ephemeral порт, http.client:
  /health, /detect ok, bad-rom -> contract-ошибка, /inject bad translations ->
  ok:false, 415 на form POST, 413 на большой body, 503 BUSY (сем-фор), 404/405.
- Гарантии: никаких test_roms (portable); тесты не зависят от сети.

## 8. Вне скоупа

- Без новых зависимостей (stdlib: http.server, json, argparse, threading).
- Без изменения контрактов core/GUI/plugins; без pre-existing фиксов.
- Без авторизации/токенов (documented limitation, local bind + WSAD).
- Без auto-запуска сервера при старте GUI.
- Cross-endpoint транзакций нет: /inject пишет сразу, отката нет (xml).

## 9. Документация

- `docs/en/API_AGENTS.md` + `docs/ru/API_AGENTS.md` (sync pair): REPL quickstart,
  CLI reference, HTTP endpoints + curl, контракт ошибок, security-замечания
  (local bind, Content-Type, лимиты, no auth=known limitation).
- ROADMAP (RU+EN): пункт «Agent/CLI/HTTP-интерфейсы».
- README «Automation» + ссылка на API_AGENTS (запустить gbx-docs-sync).

## 10. Критерии приёмки

- `pytest tests/test_api.py tests/test_api_cli.py tests/test_api_http.py` — green.
- Key-группы существующих тестов (i18n, extractor, roundtrip) не сломаны.
- `python -m api.cli extract <synthetic> --json` валиден по схеме контракта.
- HTTP /inject на синтетике: выход записан рядом с ROM (по умолчанию) или в
  указанный каталог разрешённого родителя; повторное extract совпало.
- Scoped-статика: `ruff check api/ tests/test_api*.py` и `mypy api/` чистые;
  НЕ запускаем `mypy .`/`ruff check .` (pre-existing baseline 360/56).
- В ответах HTTP только текст/метаданные: ни одного ROM/hex-дампа.
- Security делается на слое api (санитизация путей) без правок core.