# GB2Text Roadmap

**Current version:** 1.3

## ✅ Version 0.9

### Core
- [x] Text extraction from GB/GBC/GBA ROMs
- [x] Automatic text segment detection
- [x] Automatic charset table detection (en/ru/ja)
- [x] LZ77, LZSS, RLE compression support
- [x] Auto-detect compression
- [x] Plugin system for game-specific configurations
- [x] Text reinsertion into ROM

### GUI
- [x] Tkinter-based graphical interface
- [x] Text editing and translation
- [x] Encoding configuration
- [x] JSON export

### Infrastructure
- [x] Constants in `core/constants.py`
- [x] Localization (en/ru/ja/zh)
- [x] charset.json files for each language
- [x] Basic test structure
- [x] Documentation

---

## 🎯 Version 1.0

### Priority 1 — Stability
- [x] Expanded test coverage (core module basics)
- [x] CI/CD for automated test runs (.github/workflows/tests.yml)
- [x] ROM file validation (extension, size checks)
- [x] GUI tests (tests/test_main_window.py)
- [x] **Extended testing** — Matrix testing (Python 3.10-3.12, Ubuntu, Windows)
- [x] **Performance benchmarks** — tests/benchmarks/test_performance.py
- [x] **Integration tests** — tests/test_integration_extended.py

### Priority 2 — UX Improvements
- [x] Improved GUI — more intuitive interface
- [x] Preview changes before saving
- [x] Change history (undo/redo) — Ctrl+Z / Ctrl+Y
- [x] Dark mode
- [x] Drag & drop file support
- [x] Copy/paste text between segments
- [x] Find and replace text (Ctrl+F, F3, Shift+F3, Ctrl+H)
- [x] Batch ROM processing (multi-file selection, progress bar)
- [x] Improved Combobox styles
- [x] Language name display instead of codes in UI
- [x] CSV export/import

### Priority 3 — Documentation
- [x] Basic API documentation
- [x] Usage examples

### Priority 4 — Fixes
- [x] Fixed translation loading from locales/{lang}/messages.json subfolders
- [x] Added missing localization keys (settings.theme, mbc.type, load, etc.)
- [x] Added Chinese language (zh) support
- [x] Fixed theme switching function
- [x] Fixed diagnostic scripts (diagnostics.bat, diagnostics.sh)
- [x] Added test_roms/ README
- [x] Added UI constants (COMBOBOX_WIDTH, DEFAULT_PADDING, etc.)
- [x] Replaced bare exceptions (except:) with specific types
- [x] **ROM caching** — ROM not reloaded when switching between Extract/Edit tabs
- [x] Added core/rom_cache.py module with ROMCache class

---

## 🔮 Version 1.1

### New Features
- [x] Batch processing of multiple ROMs
- [x] Text comparison between ROM versions
- [x] Machine translation integration (Google Translate, DeepL, Bing)
- [x] Export to other formats (CSV, XML)
- [x] TMX (Translation Memory eXchange) export/import

### Analysis Improvements
- [x] ML-based segment detection
- [x] Automatic compression type detection
- [x] Multiple charset tables per segment support
- [x] Improved non-standard encoding detection
- [x] Automatic language detection in ROM

### Utilities
- [x] Translation validation (text length check)
- [x] Automatic null translation filling
- [x] **Developer tools** — scripts/debug.py, profiler.py, diagnostics.py
- [x] **Benchmarks** — tests/benchmarks/test_performance.py
- [x] **Coverage reports** — .github/workflows/coverage.yml

### Plugins & Extensibility
- [x] Plugin creation API
- [x] Configuration templates

---

## 🆕 Version 1.2

### GBA Game Plugins
- [x] 36 GBA games supported (Pokemon, Fire Emblem, FF4/5/6, Zelda TMC, Castlevania, etc.)
- [x] FFTA: full text extraction via pointer tables + LZSS + CRN
- [x] Huffman decoder for Fire Emblem
- [x] Constant-stride detector for automatic table discovery
- [x] DataCrystal TBL tables for Castlevania AoS, Wario Land 4, Astro Boy

### Documentation
- [x] Bilingual docs (en/ru): README, CONTRIBUTING, ROADMAP, API
- [x] Testing guide (tests/README.md)
- [x] SUPPORTED_GAMES.md — supported games list
- [x] Legal guard — no ROM distribution, disclaimer present

### Quality
- [x] 15 plugin contract tests (all passing)
- [x] Fixed roadmap inaccuracies (CI/CD, API docs, broken links)

---

## ✅ Version 1.3

### Priority 1 — Packaging
- [x] CI/CD: .github/workflows/tests.yml + coverage.yml + lint.yml + security.yml + build.yml
- [x] Pointer relocation after text reinsertion (in core/injector.py; partial for TMC banks)
- [x] Header/global checksum recalculation after injection (injector.save() → rom.recalculate_checksums; GBA/CGB variants)
- [x] Tests for FFTA LZSS (tests/test_ffta_lzss.py) and Huffman decoders (tests/test_golden_sun.py)

### Priority 2 — New Plugins
- [x] Pokemon GBA (Emerald/FireRed/LeafGreen/Ruby/Sapphire USA) — full coverage: fixed tables + dialogue pointer manifests (guard by header)
- [x] GB/GBC plugins: Pokémon Gen 1 (Red/Blue) — plugin + header detection + round-trip tests
- [x] Metroid Fusion — 1239 dialogue lines via pointer table, 4 ASCII blocks, byte-identical round-trip
- [x] Wario Land 4 — 80 known locations (passages/levels/music/shops), EN-only windows, round-trip verified
- [x] Castlevania AoS — injector at language-block level (in-place / relocation)
- [x] ROM hacks: signature gate (`get_plugin(..., rom=)`, `rom_signature` in configs) — data-driven, no code per hack
- [x] Reference `rom_signature` configs for games with hack scenes (list in docs/en|ru/API.md: Pokémon GBA, Fire Emblem GBA, Golden Sun, Advance Wars; others as hacks appear)

### Priority 3 — Agent API
- [x] `api/` module — SDK over core: resolve_rom/resolve_output, list_plugins, detect, extract, inject, get_version, load_json_file; SDKError contract codes
- [x] `python -m api.cli` — subcommands plugins/detect/extract/inject/serve; JSON output, exit codes 0/1/2, `--json`/`--format json` conflict → error
- [x] HTTP/JSON service (`api/server.py`) on stdlib ThreadingHTTPServer — /health /plugins /detect /extract /inject; Content-Type/body-size limits, read timeout, 503 BUSY semaphore, per-output inject lock, `Connection: close`
- [x] Security pass (critic + security-critic): `_is_loopback`, no `str(exc)` leaks, masked INTERNAL, mkstemp + os.replace atomic inject, 1MB load_json_file limit
- [x] Tests: tests/test_api.py + test_api_cli.py + test_api_http.py (~39 cases) + conftest synthetic ROM fixtures; full api+roundtrip run green

### Priority 4 — UI/UX
- [x] Visual charset table editor — dialog on the Settings tab: view/edit charmap, add entries with duplicate validation, remove, export to JSON; ROM is never modified
- [x] ROM map with highlighted text segments — "ROM Map" tab: 32KB blocks, segments highlighted from current_segments_meta, click → segment details, redraw on theme change and tab switch
- [x] Multi-window mode — "Open in New Window": independent GUI instance; only the primary window saves settings; warning dialog only in the primary window
- [x] Realtime translation preview — panel on the Edit tab: `[TOKEN]` → `<token>`, char/original counters, updates on `<KeyRelease>`
- [x] Segment name filter/search (for 1500+ segments) — filter entry + "X / Y" counter on the Extract tab

### Priority 5 — Export
- [x] XLIFF format (CAT integration: memoQ, Trados) (from 1.1) — export + GUI import (`file.import.xliff`, trans-unit index mapping, `apply_translations`)
- [x] Plugin auto-discovery via entry_points

### Priority 6 — Utilities
- [x] Spell checking (from 1.1) — core/spell_checker.py (pyspellchecker, ignores [XX]/{VAR}/%s/numbers), GUI red underline on Edit tab, language auto/ru/en, 500ms debounce

---

## 🚧 Version 1.4

### Quality
- [ ] Increase test coverage
- [ ] Bring the remaining plugins up to stub state (detection + honest empty result)

### Repair tools
- [ ] CRC/checksum fixer — standalone CLI command for ROMs corrupted by third-party hex editors (header + global checksum, GB/GBC/GBA variants)
- [ ] Pointer validator/repair — scan pointer tables for inconsistencies after manual patching, offer recovery
- [x] IPS/BPS patch generator — produce a patch file instead of distributing patched ROMs (legal translation distribution); core/patcher.py: bps_create/bps_apply (CRC32-verified BPS1, SourceRead/TargetRead/SourceCopy), ips_create/ips_apply (literals + RLE), create_patch/apply_patch with format auto-detection; round-trip verified on real ROMs in test_roms/
- [ ] Bank-aware pointer scan (from backlog) — proper bank_byte + addr scheme for GB/GBC

### Agents & API
- [ ] MCP server — wrapper over the existing api/ layer: extract/inject/detect as MCP tools for agents (reuses the SDKError contract)

### Translation
- [ ] Line-length / textbox simulator — simulate real textbox rendering (max_length/fixed_width) before injection
- [ ] DTE dictionary compression helper — automatic DTE table builder via bigram frequency analysis for a given translation (GB/GBC, for languages longer than English)

---

## 🔭 Future (backlog)

*Not part of v1.4; candidates for future versions.*

### Translation
- FE Huffman for Europe ROMs (tree addresses unknown)
- Spell checking at the injection stage (currently a GUI warning only)

### GB/GBC
- GB/GBC compression (RLE/LZ for Gen1/2)
- Plugins for Zelda: Link's Awakening (GB/DX), Oracle of Seasons, Harvest Moon, Resident Evil Gaiden, Super Mario Bros. Deluxe, SMT Devil Children, Fire Emblem (ROMs are already in test_roms/)

### Plugins & Platforms
- Nintendo DS — plugins for a new platform
- Third-party plugins via entry_points — demo package (infrastructure ready)
- Community/shared plugin registry — third-party plugin catalog (static JSON on GitHub Pages), install without forking the repo

### Visual tools
- Font tile graphics editor — view/edit glyph tiles (critical for non-standard alphabets: Cyrillic in GB games requires font redrawing to fit tile width)
- Playtest assistant via emulator — mGBA headless mode for auto-walking menus/dialogs with screenshots, checking that text doesn't overflow

### Tools
- Cloud sync — translations stored in the cloud
- Save-file repair — fixing saves, separate topic (frequent request in the romhacking community)

### API
- Webhook/callback on completion of long operations (relevant for large ROMs with 1500+ segments)
- `/diff` endpoint — compare text between ROM versions (core exists since 1.1, not exposed in the API)
- Metrics export (Prometheus-style `/metrics`) — for running the server in CI

### Performance
- Async ROM loading in a separate thread (partial)
- Lazy plugin loading

---

## 🐛 Known Issues

- Some games with non-standard encodings are not recognized
- FE Huffman decoder doesn't work for Europe ROMs (tree addresses unknown)
- CP866/JIS ambiguity: a pure 8-bit Russian (CP866) ROM without ASCII may be
  misdetected as Japanese — both encodings share the same byte ranges
  (0x80-0xDF). The detector prefers Russian when CP866-exclusive bytes
  (0xE0-0xFF) are present; for plugin-driven games the plugin's `segment['lang']`
  takes precedence over the heuristic.

---

## 🤝 How to Contribute

1. Check [CONTRIBUTING.md](CONTRIBUTING.md)
2. Create an issue before starting work
3. Write tests for new features
4. Update documentation

---

*Roadmap updated: 2026-09-14*
