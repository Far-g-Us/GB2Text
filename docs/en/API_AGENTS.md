# Agent API Plan — GB2Text

Internal plan: give agents and scripts programmatic access to core without GUI.
Three interfaces: Python module (REPL/Jupyter), CLI commands, HTTP/JSON (stdlib).
The core contract (`get_plugin(..., rom=)`, `TextExtractor(..., rom=)`, etc.) is
NOT changed; the GUI is untouched. This document incorporates the results of the
critic and security-critic pre-reviews (mode B).

## 1. Current state

- A CLI already exists in `main.py` (extract text/json/csv, inject via
  --translations, --lang en|ru|ja), but: not JSON-consistent, no list/detect,
  `--lang` without zh, hardcoded plugin-dir in inject, errors via `print` with no
  exit code.
- Core API is mature: `TextExtractor(rom).extract() -> dict[str, list[dict]]`,
  `TextInjector(rom).inject_segment(name, texts, plugin)`, `get_safe_plugin_manager(dir)`.
- The project runs from repo root (no package install); GUI tests use real ROMs
  in test_roms/ (skipped if missing). Pre-existing: ruff 56 / mypy 360 repo-wide
  errors — acceptance criteria are scoped to our files only.
- Known pre-existing (documented, not fixed): main.py --lang without zh;
  `PluginManager(plugins_dir)` creates the dir and example.json on construction —
  api isolates from this. `injector.save()` does recompute header/global checksums
  (rom.recalculate_checksums: GBA — complement byte 0x0BD, GB/GBC — header
  0x14D + global sum over the whole ROM).

## 2. Goals

1. One Python module `api/` (REPL/Jupyter-first): clean functions with
   dataclass/JSON results, CancellationToken for long operations.
2. `python -m api.cli` subcommands: `plugins`, `detect`, `extract`, `inject`,
   `serve` — JSON-compatible output, stable exit codes (0/1/2).
3. HTTP/JSON service on stdlib (`ThreadingHTTPServer`), default bind 127.0.0.1,
   endpoints /health /plugins /detect /extract /inject.
4. Stable response contract: `{"ok": bool, "data": ...|"error": {...}}`.
5. Tests in-process (api/HTTP handler) + subprocess (CLI); round-trip and the
   existing suite are not broken.

## 3. Contract

Response (all interfaces):

```
HTTP/CLI --json: {"ok": true, "data": ...}
                 {"ok": false, "error": {"code": "...", "message": "..."}}
REPL: Python values (dataclasses), SDKError exceptions as-is.
```

Error codes: PLUGIN_NOT_FOUND, UNSUPPORTED_SYSTEM, ROM_ERROR, IO_ERROR,
VALIDATION_ERROR, INTERNAL, PAYLOAD_TOO_LARGE, TIMEOUT, BUSY, METHOD_NOT_ALLOWED.

HTTP wire errors (400 malformed JSON, 404 endpoint, 405 method, 408 timeout,
413 payload, 415 content-type) are NOT masked as `ok:false` — only contract
errors (PLUGIN_NOT_FOUND etc.) are returned as `200 {"ok":false}`.

CLI: exit 0 = ok; 1 = runtime/validation (contract error on stdout);
2 = argparse parse error. JSON goes to stdout (not stderr), utf-8
(`sys.stdout.reconfigure(encoding='utf-8')` with `--json`).
`--format json` (raw extract results, as in main.py) and `--json` (contract
wrapper) are mutually exclusive: if both are given, argparse raises an error
(exit code 2).

## 4. api/ module

Files:
```
api/
  __init__.py    # public functions + result dataclasses
  _core.py       # thin wrappers over core: error mapping + safe paths
  cli.py         # argparse subcommands; main(); serve via api.server
  server.py      # http.server ThreadingHTTPServer + handler (contract+wire errors)
```

Public functions:

- `list_plugins(plugin_dir=None) -> list[PluginInfo]` — read-only: MUST NOT
  create the dir/example.json (check dir existence before PluginManager).
- `detect(rom_path, *, plugin_dir=None) -> GameInfo` (game_id, system, plugin,
  hack-signature).
- `extract(rom_path, *, plugin_dir=None, max_segments=None, language="en",
  progress=None) -> ExtractionResult` — segments: dict[name, list[Message]],
  stats. Message: `text`, `offset` (+ extra pointer_dialogues fields from core);
  `decoder_name` is synthesized by the api layer from `segment['decoder']`
  (core does not return it). `language` — segment filter by config `lang`
  (no separate core parameter; if segments are unmarked the option is a no-op).
- `inject(rom_path, translations, *, output_path=None, plugin_dir=None) -> InjectionResult`
  — translations: `dict[segment_name, list[dict]]` with `translation` key
  (COMPATIBLE with main.py:172), in extract order. `output_path` default — next
  to the rom (`rom_path` + `_translated` suffix). Per-segment report; checksum is
  recomputed in `injector.save()` (rom.recalculate_checksums), final value reported.
- `serve(host="127.0.0.1", port=8765, *, plugin_dir=None, max_workers=4)` —
  starts the server (blocking); invoked from `cli.main()`. A non-loopback host
  prints a warning to stderr («no authentication, trusted network only»).

Safe paths (P0, security review):
- Every function taking `rom_path`: `Path(rom).resolve()`, `not is_symlink()`,
  `validate_rom_file()` (core/rom.py:36) — extension .gb/.gbc/.gba, existence,
  MAX_ROM_SIZE. Otherwise `IO_ERROR`/`UNSUPPORTED_SYSTEM`.
- `inject`: `output_path=None` -> next to ROM; explicit -> `resolve()`,
  `not is_symlink()` and `parent(output) == parent(rom)` (else IO_ERROR).
  Atomic write via `tempfile.mkstemp` in the same dir + `os.replace` (no
  partial files, no predictable tmp path).
- Symlinked ROMs are rejected (the real file is checked by the same validate).
  32MB ROM: ~3× in memory (GameBoyROM + original + modified) — explicit
  `del injector` after `save()`, limitation documented.

## 5. CLI (python -m api.cli)

```
api.cli plugins [--plugin-dir DIR] [--json]
api.cli detect ROM [--plugin-dir DIR] [--json]
api.cli extract ROM -o OUT [--format json|text|csv]
                [--plugin-dir DIR] [--max-segments N] [--lang en|ru|ja|zh] [--json]
api.cli inject ROM --translations T.json [--output-rom OUT] [--plugin-dir DIR] [--json]
api.cli serve [--host 127.0.0.1] [--port 8765] [--plugin-dir DIR]
```

- `--json` — machine-readable contract (§3); without it — human-readable like main.py.
- inject accepts the main.py format (`list[dict]` with `translation`); a mismatch
  is VALIDATION_ERROR with a clear message.
- `--lang`: interface/text language — documented as segment filter in extract,
  no-op elsewhere.

## 6. HTTP (stdlib)

`api/server.py`: `ThreadingHTTPServer` + `BaseHTTPRequestHandler`.

- Bind: default 127.0.0.1; `--host 0.0.0.0/non-loopback` -> WARNING to stderr
  (no authentication, trusted network only).
- Endpoints:
  - GET  /health   -> {"ok": true, "data": {"version": ..., "status": "ok"}}
  - GET  /plugins  -> list_plugins
  - POST /detect   -> body {"rom": "/abs/path"}
  - POST /extract  -> body {"rom", "max_segments", "lang"}
  - POST /inject   -> body {"rom", "translations", "output"}
- Content-Type: `application/json` only, otherwise 415 (browser form-POST/CSRF
  rejected without CORS handling).
- Body limit: per-endpoint. /detect,/extract: 1 MB; /inject: MAX_ROM_SIZE +
  margin. If Content-Length exceeds the limit -> 413 PAYLOAD_TOO_LARGE before
  reading the body. Missing Content-Length — read with a hard limit.
- Timeout: `timeout_read_body = 10s` ONLY on body read (after reading,
  `settimeout(None)` before processing so a slow extract is not killed) -> 408
  TIMEOUT.
- Concurrency: `threading.Semaphore(max_workers)` (default 4), exhausted -> 503
  BUSY. No RLock needed (request thread), but output writes use a per-path lock
  (`dict[resolved_path, threading.Lock]` in server) so parallel /inject into the
  same file do not race.
- Error handling: try/except, mapping to contract; traceback NEVER in responses.
  Malformed JSON -> 400 (wire). Unknown endpoint -> 404.
- Logging: replace `BaseHTTPRequestHandler.log_message` default with a custom one:
  method, URL-path (not the body's file path), status, latency. body fields
  (rom/output) and headers are NEVER logged.
- Memory: explicit `del injector` after per-request extract/inject; note that
  4 concurrent 32MB ROM extracts ≈ 400MB peak.

## 7. Testing

- `tests/conftest.py`: fixture `api_rom_bytes` — synthetic GB ROM following the
  `_build_gb_rom` pattern from test_roundtrip.py:35-84 (valid logo + checksum),
  explicit ConfigurablePlugin config with charmap (determinism), placeholder text
  only (legal guard — no real game text).
- `tests/test_api.py`: REPL — detect/extract/list_plugins/mini inject round-trip,
  IO_ERROR/UNSUPPORTED_SYSTEM/PLUGIN_NOT_FOUND/output-parent validation.
- `tests/test_api_cli.py`: subprocess via `sys.executable -m api.cli`, temp dir
  with a config, check JSON/exit codes 0/1/2, --format/--json mutual exclusion.
- `tests/test_api_http.py`: ThreadingHTTPServer on an ephemeral port, http.client:
  /health, /detect ok, bad-rom -> contract error, /inject bad translations ->
  ok:false, 415 on form POST, 413 on oversized body, 503 BUSY (semaphore), 404/405.
- Guarantees: no test_roms (portable); tests do not depend on the network.

## 8. Out of scope

- No new dependencies (stdlib: http.server, json, argparse, threading).
- No core/GUI/plugins contract changes; no pre-existing fixes.
- No auth/tokens (documented limitation, local bind + WSAD).
- No auto-start of the server on GUI launch.
- No cross-endpoint transactions: /inject writes immediately, no rollback.

## 9. Documentation

- `docs/en/API_AGENTS.md` + `docs/ru/API_AGENTS.md` (sync pair): REPL quickstart,
  CLI reference, HTTP endpoints + curl, error contract, security notes (local
  bind, Content-Type, limits, no auth = known limitation).
- ROADMAP (RU+EN): add an "Agent/CLI/HTTP interfaces" item.
- README "Automation" section + link to API_AGENTS (run gbx-docs-sync).

## 10. Acceptance criteria

- `pytest tests/test_api.py tests/test_api_cli.py tests/test_api_http.py` — green.
- Key existing groups (i18n, extractor, roundtrip) unaffected.
- `python -m api.cli extract <synthetic> --json` valid per the contract schema.
- HTTP /inject on synthetic: output written next to ROM (default) or into the
  allowed parent dir; re-extract matches.
- Scoped static checks: `ruff check api/ tests/test_api*.py` and `mypy api/`
  clean; NOT `mypy .`/`ruff check .` (pre-existing baseline 360/56).
- HTTP responses carry text/metadata only: zero ROM/hex dumps.
- Security lives in the api layer (path sanitization) without core changes.