# GB2Text Roadmap

**Current version:** 1.4

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

## ✅ Version 1.0

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
- [x] Added test_game/ README
- [x] Added UI constants (COMBOBOX_WIDTH, DEFAULT_PADDING, etc.)
- [x] Replaced bare exceptions (except:) with specific types
- [x] **ROM caching** — ROM not reloaded when switching between Extract/Edit tabs
- [x] Added core/rom_cache.py module with ROMCache class

---

## ✅ Version 1.1

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
- [x] Pokemon GBA (Emerald/FireRed/LeafGreen/Ruby/Sapphire USA) — full coverage: fixed tables + dialogue pointer manifests (guard by header)
- [x] Configuration templates

---

## ✅ Version 1.2

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
- [x] Security pass: `_is_loopback`, no `str(exc)` leaks, masked INTERNAL, mkstemp + os.replace atomic inject, 1MB load_json_file limit
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
- [ ] Test coverage — last measured **97.38 %** (11,365 statements, 4,466 branches); 14 files below 100 %, of which `core/injector.py` is 84.55 % (231 lines, 166 branches). The figure is stale relative to earlier measurements and needs a re-run after the latest batches of tests. Measured with `pytest tests/ -n 4 --cov` (scope and omit come from `.coveragerc`: `core, plugins`). Progress: clusters 1618-1680, 1198-1218, 433-450, 380-455, 949-1000 and 2681-2702 are closed; 1050-1066, 1918-1934, 541-549, 1243-1267, 1794-1806, 1829-1838 and the small ones remain.
- [x] Bring the remaining plugins up to stub state (detection + honest empty result)
- [x] Docs-consistency CI — auto-check of links/routers/legal canon/ru-en parity (`scripts/check_docs_consistency.py`, hard gate; the `parity` mode compares the item count, order, nesting and state of the KNOWN_ISSUES and ROADMAP pairs)
- [x] Fixed-segment contract for plugin authors: `fixed_width`, `pad_byte` and `has_mid_alias` are documented in `plugins/config/README.md` ("Segment fields that change the WRITE" section) — what each field does, its default, and why `has_mid_alias` is mandatory when a foreign pointer looks into the tail (cost measured: 561 of 646 FF4 records cannot be shortened). NO automatic check was added to `_valid_segments`, and that was measured rather than overlooked: both candidates were rejected on the real corpus. A `pad_byte` outside 0..255 is rolled back to a default by `_resolve_pad`, and rejecting the segment is worse than padding with the default byte; `has_mid_alias` without `fixed_width` is not a contradiction but a working combination (FF4: 561 of 1762 segments), so a check would reject live records. Whether a foreign pointer actually looks into a slot's tail cannot be checked without parsing pointers — that stays with the plugin author, and the contract says so though the injector now treats them differently. For a fixed segment `has_mid_alias` is mandatory: without it the tail of the slot that a foreign pointer looks into gets overwritten with `pad_byte`, which is silent corruption. Either document the fields or validate them in `_validated()`.

### Repair tools
- [x] CRC/checksum fixer — `core/checksum_fix.py` + CLI `api.cli fixsum ROM (--check|--fix)`: `inspect()` writes nothing, `repair()` writes atomically (`.chksum.tmp` + `replace`) and only when there is something to fix, and the result is verified in memory BEFORE the write. GB/GBC: header checksum (0x14D) + global checksum (0x14E-0x14F); GBA: complement byte 0xBD only. **Two decisions measured on 60 ROMs rather than taken from a spec:** a GBA ROM has no global checksum (0x14E-0x14F hold values from an internal register; 40/40 GBA ROMs differ from the byte sum) — checking them would declare every commercial GBA ROM broken; the reserved 0x0BE-0x0BF should be 0x0000 per GBATEK, but `Moemon Fire Red ruRevival` holds 0x3C/0x2A there with a matching complement — they are neither checked nor overwritten. CLI exit codes: 0 matched, **3 broken** (separate from 1 "error", or CI cannot tell a broken ROM from "wrong path"); the path goes through `resolve_rom`, so `.sav`/`.txt` are refused rather than overwritten. 17 + 14 tests
- [x] Pointer validator/repair — scan pointer tables for inconsistencies after manual patching, offer recovery; core/pointer_validator.py: validate_pointer_table (statuses ok/zero/out_of_bounds/duplicate), problem_summary, repair_pointer_table (LE, addressing base + 2/4-byte pointers) (may work incorrectly)
- [x] IPS/BPS patch generator — produce a patch file instead of distributing patched ROMs (legal translation distribution); core/patcher.py: bps_create/bps_apply (CRC32-verified BPS1, SourceRead/TargetRead/SourceCopy), ips_create/ips_apply (literals + RLE), create_patch/apply_patch with format auto-detection; round-trip verified on real ROMs in test_game/
- [x] Bank-aware pointer scan — `core/gb_banks.py`: an honest `(bank_byte, addr16)` pair and the real bank mapping (`N * 0x4000 + (addr - 0x4000)`, NOT `bank * 0x4000 + addr`, which would shift every reference by a whole bank). Clipped last bank, NULL/VRAM/RAM/BANK0 classification, 16-bit pointer search, bank+addr16 row tables (3 bytes per row), stride-based table grouping. `tests/test_gb_banks.py` — 42 tests (plus 19 refusal-path tests in `tests/test_gb_coverage_gaps.py` and 11 in `tests/test_write_guard_gaps.py`)

### Translation
- [x] Spell checking at the injection stage — soft gate: every translation passes `spell_checker.check_text` before writing to ROM (core/injector.py), report in `last_spellcheck_report`, writing is never blocked
- [x] Line-length / textbox simulator — simulate real textbox rendering (max_length/fixed_width) before injection (core/textbox.py + `last_fit_report`, writing is never blocked)
- [x] Genuine CP866 auto-Russian table (**breaking in 1.4**: was a game-specific sample table with duplicates; detector ranges synced, see CHANGELOG)
- [x] Hiragana table dedup (0xB8/0xB9/0xC7 duplicated 0x84/0x85/0x86; encode is deterministic now)
- [x] DTE dictionary compression helper (EXPERIMENTAL — test-only, synthetic + in-memory pilot): per-translation byte DTE table builder with atomic coder contract, disjoint/compression-refusal gates and savings estimate; injector writes — follow-up

### Fonts (EXPERIMENTAL — everything needs tests on real ROMs)
- [x] Phase 0/1: font format research and basic tile operations (decoding, preview)
- [x] F1 core: 1/2/4 bits-per-pixel depths, image import/export, strict metadata validation, safe-write gates
- [x] Phase 2: glyph embedding mechanism with confirmations and refusals (compressed data, out-of-bounds, candidates)
- [ ] Pilot: full pipeline run on real ROMs with emulator verification

### Plugins & Platforms
- [x] Community/shared plugin registry — third-party plugin catalog (static JSON on GitHub Pages), install without forking the repo

### Performance
- [x] Lazy plugin loading — specific plugins are imported on first access (allowlist gate preserved), generic stay eager

---

## 🚧 Version 1.5

### Fonts: F1 testing + GUI editor
- [ ] F1 pilot on real ROMs (legally-owned): candidate-gate + inject + emulator verification, dropping the experimental status
- [x] F2 GUI editor, MR1: “Font” tab — glyph-grid preview, PNG import, write via TextInjector (read-only without ROM, undo until save, dark theme) — code done, pilot needed
- [x] F2 GUI editor, MR2: per-pixel glyph editing + undo/redo stacks — code done, pilot needed

### Playtest assistant (after F2, in order)
- [x] `core/playtest.py`: PlaytestRunner protocol + PyBoyBackend (GB/GBC) — strictly validated input scripts, per-frame hashes, stuck/dark markers, screenshots on marks, structural diff (roundtrip only), 100% coverage on fake core — code done, pilot on a real ROM needed
- [ ] MGBABackend (GBA): Lua driver + screenshot collector ready (API pin 0.10.x, PyBoy frame contract, pilot-gated); auto-run — second increment after pilot

---

- [ ] Defects and limitations moved to `KNOWN_ISSUES.md` — check status there, not here.

## 🔭 Future (backlog)

*Not part of v1.4; candidates for future versions.*

### Translation
- [ ] FE Huffman for Europe ROMs (tree addresses unknown)

### GB/GBC
- [x] GB/GBC compression (RLE/LZ for Gen1/2) — `core/gb_compression.py`: two formats with an exact specification and a matching `compress`, so the round-trip is real: control-byte RLE (`ctrl < 0x80` is a literal run of `ctrl + 1`; `ctrl >= 0x80` repeats the next byte `(ctrl & 0x7F) + 3` times) and flag-byte LZ with a two-byte reference (12-bit offset, 4-bit length). `core/compression.py` used to hold "looks compressed" heuristics with no writer and a 64 KiB output cut. A broken LZ reference stops the stream instead of emitting zeros. `tests/test_gb_compression.py` — 53 tests including round-trip
- [ ] Plugins now exist for every game listed before (the list was wrong):
  plugins are present and detected for Zelda LA/LA-DX/Seasons/TMC, Harvest Moon
  1-3, Resident Evil Gaiden, Super Mario Bros. Deluxe, Fire Emblem (GBA and
  Reincarnation), Breath of Fire, SMT Devil Children and Mario & Luigi. What
  is actually broken is that most of them yield **0 segments**: Breath of Fire,
  Fire Emblem (GBA and Reincarnation), Harvest Moon 1-3, Resident Evil Gaiden,
  SMT Devil Children, Super Mario Bros. Deluxe. So the plugin loads and finds
  its own block - the scanner does not. Checked against their own revisions
  (`MLSS` 5120 segments, TMC 70, Zelda 7/6/2).
Both modules are **not wired to any plugin** and live in `core/` as a tool.
Wiring them up before the RE is done is not possible:

- [ ] The compression formats are verified against no game in `test_game/` —
  there is no GB/GBC ROM there with confirmed compression, so `guess_format`
  stays a heuristic (after the fix it answers `none` almost everywhere on 5 real
  ROMs, which is honest: it does not invent a format)
- [x] False-positive filter in `scan_banked_rows` (`_plausible_run`): without it
  arbitrary 3 bytes yielded ~24% plausible "pointers", and the RE script would
  have dragged the header region into a table. It checks consecutive accepted
  rows (`min_rows`), the number of distinct banks (`max_banks`) and the step
  between addresses (`max_addr_step`). Measured on Pokémon Gold: accepted rows
  10.3% → **0.2%**. The filter checks geometry, not text: a text check needs the
  game's charmap and stays a separate task
- [x] `guess_format(data, start, charmap=...)` takes the game's charmap, and
  without one honestly falls back to ASCII and says so through `.likeness`.
  Real Gen1 text (letters in 0x80..0x99) scored 0.018 against a foreign ASCII
  map and 1.000 against the game's own; without an explicit map the criterion
  remains a heuristic, and the docstring says so
- [x] `looks_like_text` + `verify_table` + `scan_text_table`: text verification
  against the game's charmap plus address monotonicity. Measured on a Pokémon
  Gold copy (`scripts_roms/out/gb_gold_tables.txt`, `gb_gold_tables.json`): 419
  monotonic series by geometry, 63 of them 8 rows or longer, and **not one**
  contains Gen1 text — the longest (251 rows, bank 109) turned out to be a tile
  table. Conclusion: in Pokémon Gen1 the text lives inside scripts rather than in
  a flat pointer table, so insertion must not be built on such a scan.
  `scan_for_text_pointers` is not the tool for this either: it groups repeats of
  a *single* value and yields 2-8 row fragments on a real table. For the
  "separate bank byte + addr16" layout the same script found 56 candidates that
  pass the full check (6-8 rows, text share 0.50-0.67) — those are candidates in
  bank 1, not in the header

### Plugins & Platforms
- [ ] Nintendo DS — plugins for a new platform
- [ ] Third-party plugins via entry_points — demo package (infrastructure ready)

### Visual tools
- [x] Text baked into graphics (title logos as tiles) — tool pi.cli picture ROM {preview,apply} --offset --bpp --count, core core/tile_picture.py: renders a tile block to PNG and writes a NEW ROM from an edited PNG (the source ROM is never touched, the write is atomic). Automatic block discovery was dropped on measured evidence (positive control: the criterion fires 552 times on the FireRed font and 630 times on noise — it does not discriminate), so the block is operator-supplied: the title-screen asset address lives in ARM code, not in the data. The round-trip is LOSSLESS: a dedicated sampler reconciles against the PNG palette (the stock image_to_grids turned out irreversible — it ignored the preview scale and returned 60 foreign pixels out of 64), so an unchanged picture comes back byte-for-byte; verified across 120 regions of a FireRed copy and on font 0x1FF2F0. The graphics-vs-code gate exists precisely because the round trip is flawless for ANY 32 bytes: its threshold is calibrated by measurement (font median 76 / min 68, ARM code 19 / max 56, data 17, threshold 60 — a narrow margin, so the gate rejects "looks like noise" rather than proving graphics), the refusal names the remedy --force. Also found and fixed during review: refusal when the output would overwrite the source ROM, refusals for PNGs without metadata or with a foreign bpp, the gray ramp instead of zero for RGB/RGBA/L previews, bpp=8 dropped from the CLI, a preview ceiling. 31 tests, including 64 random tiles at each depth

### Tools
- [ ] Cloud sync — translations stored in the cloud
- [ ] Save-file repair — fixing saves, separate topic (frequent request in the romhacking community)

### API
- [ ] MCP server (deferred from 1.4) — wrapper over the api/ layer: extract/inject/detect as MCP tools for agents
- [ ] Webhook/callback on completion of long operations (relevant for large ROMs with 1500+ segments)
- [x] `/diff` endpoint — compare text between ROM versions (implemented in 1.4: `core/diff_text.py` + `POST /diff`)
- [ ] Metrics export (Prometheus-style `/metrics`) — for running the server in CI

### Performance
- [ ] Async ROM loading in a separate thread (partial)

---


- **OPEN: the free-space measurement above is limited by its model and needs
  re-checking.** Free space was counted only as runs of `0xFF` and `0x00`.
  That model ignores what GBC translators actually rely on: code caves at the
  end of banks filled with something other than `0x00`/`0xFF`; mixed filler
  (`0x00`, `0xFF`, `0xAA` interleaved), which the count ignores entirely; text
  compression, since the ~24 bytes-per-record estimate that yields 44,400 bytes
  does not reflect one- or two-byte tokens and shortened lines; and ROM
  expansion, as several GBC games ship official larger versions. So "there is
  nowhere to relocate" is **stronger than what was measured** and should be
  read as "within the `0x00`/`0xFF` run model there is no room". Separate task:
  re-measure free space with a wider model and revisit the conclusion instead
  of treating it as a property of the format.

- **FIXED: race and corrupt span in the MLSS catalog cache.** The
  `_CLASS_CATALOG_SPANS` cache was a check-then-act on shared class state while
  `get_text_segments` runs from background threads (`gui/main_window.py`,
  `api/server.py` with ThreadingHTTPServer), so two concurrent parses of two
  different MLSS ROMs interleaved and one received the other's spans. Second defect
  of the same class: a foreign span with `upper > len(data)` crashed the parse with
  IndexError in `_make_segment`, because the catalog branch overwrote `target`
  from the span after the only bounds check.
  **Fix:** a module-level `_CATALOG_CACHE_LOCK`; the scan builds spans into a local
  dict published with a single assignment (the shared dict is never mutated); the
  detection threshold is part of the cache key, so patching it triggers a rescan
  instead of reusing stale spans; `_make_segment` now checks
  `start < upper <= len(data)`, so a corrupt span is dropped (the record stays an
  ordinary one) instead of decoding as a 12 MB catalog or crashing. A public
  `reset_class_cache()` was added for tests.
  **Verified:** three new tests (`test_stale_span_out_of_rom_is_dropped`,
  `test_detection_knob_invalidates_cache`, `test_reset_class_cache_clears_state`),
  26 MLSS tests pass.
  The race was not in publication but in reading: the lock and the publication order
  did not close it, because `_make_segment` read the shared ClassVar after
  publishing. The snapshot is now taken under the lock in `get_text_segments` and
  passed into `_make_segment` as an explicit parameter, so another ROM cannot
  republish spans into this read. The lock is a ClassVar on the plugin class, not a
  module-level variable. Covered by the deterministic test
  `test_reader_does_not_use_republished_spans`, which replaces the shared attribute
  with foreign spans while the first thread is blocked and fails on the old code.
- **Oracle of Seasons: 16-bit banked relocation is IMPLEMENTED, but the format
  leaves no room for it.** `_relocate_dialogue` now handles 16-bit
  bank-relative GB/GBC pointers as well as the 32-bit `0x08 + addr` (GBA) ones,
  and the plugin reports the win in KNOWN_ISSUES. What remains is that a
  shortened record still does not fit its original window, so it is written in
  place truncated rather than relocated - the mechanism exists, the format does
  not admit it.
  a catalogue.** The earlier guess (that `find_free_space` failed to exclude the
  catalogue blob) was wrong: there is no overlap with the catalogue at all, the
  record is written correctly (656 bytes at dest 0x1DF5F4) and its pointer is
  updated and re-read by the scan.
  **Cause:** the classification in `_scan_catalogs`, not the free-space search.
  The window's upper bound came from the next pointer of the same column
  (`lst[idx+1]`), and everything between the relocated record and that pointer is the
  whole dialogue pool, full of `FF 0A`. So `sub > 1` and the record was decoded as
  a catalog spanning `(0x1DF5F4, 0x3F1054)` = 2,169,440 bytes and 10,198,969 characters.
  **Fix:** the sub-record window is cut at the first run of zeros longer than
  `_CATALOG_MAX_ZERO_RUN` (64) - catalog sub-records are physically contiguous while
  free space runs for thousands of zeros (measured: the maximum inside the real
  catalogs' structural windows is 5, in free space 1000+). A size-based fail-safe
  was implemented and removed: it made any relocated record of 0x800 bytes or more
  read-only, so a longer translation was silently dropped by an `inject()` that still
  returned `True`.
  **Verified:** on a clean ROM the catalog dictionary is byte-identical (nine
  entries, same bounds); 27 MLSS tests pass; disabling the cut as a mutation fails
  four tests including `test_relocated_record_is_not_a_catalog`, parametrized over
  600 and 2500 characters so it crosses the 0x800 threshold.

- **FF4/FF5 multilingual support has not been started.** The core exists
  (`core/font_tiles.py`, `core/font_ui.py`) but `get_font_meta` exists only in
  `plugins/gba_pokemon.py`; FF4, FF5, TMC, FFTA, Golden Sun and ~15 other
  games have none. This is real font-table/asset work, not a charmap tweak,
  and it was in neither Known Issues nor the Backlog
- **The shortening round-trip is suppressed on 3 games (`_SHORTENING_SCOPE`).** `_SHORTENING_SCOPE`
  is limited to FF4/FF5/WL4 (`tests/test_realrom_pipeline.py:509`) although the
  shortening run is red on other games too. Closed within this item: Wario Land 4
  (earlier), Golden Sun — segments emitted over machine code, Metroid Fusion
  — a printable `pad_byte` tail in the credits, and FFTA `CRN_*` — the chained
  scan — by `tests/test_ffta_crn_chain.py`. The visible `pad_byte` tail in
  Golden Sun credits is **also closed**: the earlier claim that the pad cannot
  be switched to `0x00` "because the credits-region boundary is found by record
  length" turned out to be wrong — it described a side effect of segment
  selection sharing the `_CREDITS_MIN_RUN` threshold with the density probe.
  Done: selection got its own minimum (`_CREDITS_WALK_MIN_RUN` = 1), `_CREDITS_GAP`
  = 0x100, the region start is pinned by per-revision constants (`_CREDITS_AT` =
  0x0F0AE4, `TLA_CREDITS_AT` = 0x1A1A10) guarded by `_looks_like_credits`, and
  `pad_byte` = 0x00. Measured: 109 of 109 GS credits and 101 TLA credits, loss 0,
  `pad_visible` = 0 across the corpus. Details, including the rejected variants,
  are in `KNOWN_ISSUES.md`. Separately: Golden Sun: The Lost Age credits are now
  extracted, 101 records at `0x1A1A10..0x1A2058` (see
  `plugins/gba_golden_sun_tla.py`, `TLA_CREDITS_AT`). Still open: the Metroid
  Fusion item has no automated anchor, since no coverage for it exists.
  The Oracle and Pokémon debt is real, but its **scale is not established**: the
  measurement under-reports corruption where record matching stops being
  provable (address shift, changed record count) — see `KNOWN_ISSUES.md`
- **The parallel run is non-deterministic.** Two consecutive
  `pytest tests/ -n 4 --cov` runs failed differently (both `@pytest.mark.slow`,
  both pass in isolation); the lazy `SpellChecker` in
  `core/spell_checker.py` is the suspect, no `ru` dictionary is installed

## 🐛 Known Issues

- [x] ~~**FF5: the record `in[F6]a!` loses its control code with a parameter when shortened**~~ CLOSED, and the cause was diagnosed wrong. `0xF6` is not a control code with a parameter — it is an *unknown* byte the decoder renders as the raw token `[F6]`, so accounting for parameterised control codes in the FF5 encoder was beside the point. The real cause is the extractor's display rule: a trailing token-only run is dropped, which makes `in[F6]` unrepresentable (the window `08 05 f6 0d` would read back as `in`, silently losing characters). The injector now REFUSES such a translation (`last_affix_report`, reason `trailing_raw_token`) and leaves the bytes. Measured cost: 1 record of 5241 on FF5, 0 of 1761 on FF4, 0 under the `_mutate` transform on both ROMs. Pinned by `tests/test_injector_trailing_token.py`
- [x] ~~**FFTA: CRN names are parsed with a chained scan from 0x55128C**~~ CLOSED.
  The records sit back to back, separated by exactly one `0x00`, and the scan
  skipped the separator with `offset += 1`. The injector pads a shortened
  record with `pad_byte=0x00` up to its former length, so a run of zeros
  follows it, and each of those zeros consumed a whole iteration of the fixed
  107-step loop: the scan never reached the end of the area and only 21 of 107
  names came back. The whole zero run is now skipped, losses are 0; pinned by
  `tests/test_ffta_crn_chain.py`
- **Byte ownership at the boundary between the Pokémon GBA catalogues and the
  dialogue manifest is ambiguous.** Entries of `core/manifests/BPRE.json`
  sometimes point *inside* the fixed-width name/ability/attack tables:
  `0x24FD03` is ability slot 15 (`'INSOMNIA'`, free_after 13), `0x247024` is
  `'  REGICE'`, `0x247404` is `'    COUNTER'`, `0x250026` is `'   AIR LOCK'` —
  i.e. the dialogue decoder false-positives there. Giving the catalogue
  priority (a fixed-width table is a strict grid) was implemented and
  REVERTED: it restores 40 records on FireRed and 37 on Emerald, but on Odyssey
  that same `0x250026` entry *is* a real dialogue and the catalogue write
  overwrote it (`'AW'` instead of the translation). The symmetric block
  (neither side writes) is kept: corruption is worse than an untranslated
  string. Measured: FireRed 38 of 2123 records (1.8%), Odyssey 19 of 1685
  (1.1%) stay untranslated. MEASURED in more detail: of 1289 manifest records exactly 10 have NOT ONE slot pointing at their `target`, and 9 of those lie inside the fixed-width catalogue tables; only one of them (`0x24FD03` = slot 15, `free_after` 13 = exactly the slot width) is provably a duplicate of a catalogue slot, while the other 8 start mid-slot and run 2-3 slots long — and FireRed and Odyssey hold DIFFERENT bytes there, so on Odyssey at least some of them are real dialogues. They cannot be dropped automatically: that would delete real speech. DIRECTION: regenerate the manifest with an "is there a slot pointing at target" check and split the hacks into separate manifests, so false records are filtered by data rather than by heuristic
- **Relocating a record that has SEVERAL pointers loses the translation
  (Odyssey v4.1).** The injector patches only the slots that point at `target`; the rest
  land in `skipped_pointers`.
  `_relocated_dialogue_addr` takes the FIRST slot whose value differs from
  `target` — which is usually one of the unpatched ones — and decodes a foreign
  block: measured on 6 records out of 1163 (e.g. `0x417E50` really moves to
  `0x135F389` while the extractor resolves `0x1064B74`). This is the same class
  of defect marked closed above, but for multi-pointer records. DIRECTION (revised after
  measuring): patching ALL slots is NOT possible — some of them hold real ARM
  code. For record `0x417E50` the slot at `0x3E02B8` contains `0x09064B74`,
  i.e. an instruction rather than a pointer, and overwriting it would break the
  game. The actual cause is manifest quality: on clean FireRed 134 of 1700
  slots point elsewhere and 10 records have no valid slot at all; on Odyssey it
  is 296 and 113. The item is therefore closed only for records with correct
  slots. DIRECTION: regenerate the manifests with a validated slot scanner,
  plus separate manifests per hack — that addresses both this and the false
  catalogue records below
- [x] ~~**FF4: records one character long**~~ CLOSED: not a defect but data. The ROM really contains `55 0C 52 0C 49 0C 45 0C` = 5,4,3,2,1 as separate 0x0C-terminated records (from `0x2EA56B`). The old check decoded whole segment windows, walked into these records and demanded they be dropped — acting on that would have deleted real text. The test now asserts the records exist and that each is a genuine charset glyph. Dropping them by length is not allowed for a translator either: the junk filter decides on the TRANSLATION, and a record translated into a couple of characters would vanish from the manifest (`/`, `:`, `3`…). Dropping
  them by length is not allowed: the junk filter decides on the TRANSLATION,
  and a record translated into a couple of characters would vanish from the
  manifest and become untranslatable. A translation-invariant criterion is
  needed — e.g. evidence that the pointer table does not reference the
  address, or a check that the record does not continue the previous one.
  Asserted directly (no xfail: the records are real data) in
  `tests/test_gba_ff4_ff5_quality.py::test_no_single_glyphs`
- [x] ~~**The `test_roms/` directory was renamed to `test_game/` only in the tests**~~ CLOSED: the path is updated everywhere — in `tests/`, `test_run.py`, `script_game/` (109 files), `scripts/`, `plugins/gbc_pokemon_gsc.py`, `.coveragerc`, `tests/gui_tests.robot`, `.opencode/rules.md` and in both ROADMAPs. That also brought 180 previously silently skipped tests back to life (skips 182 → 2), which is why their thresholds and invariants had never been checked. Remaining mentions live only in `.agent/tasks/` — historical artefacts of past tasks, not instructions.
- **`inject_language_block` / `inject_interleaved_language` are not checked
  against foreign windows.** The overlap guard now exists in the ordinary
  generic path, the pointer path, `_inject_bank_segment` (Zelda TMC) and the
  compressed branch, but NOT in the language block: there the block
  legitimately spans its own segments, and the first version of the guard
  produced false positives on Castlevania (`inject_language_block` returned
  False on a valid insertion). Reverted; the debt remains and needs a filter
  that tells the block's own segments apart from foreign ones. Not verified;
  no live cases were looked for
- [x] ~~**`_foreign_overlap` is linear in the number of foreign windows**~~ CLOSED:
  the method no longer exists — it had no caller in `core/` once the write paths
  moved to `_foreign_hit`. The underlying cost is gone with it: foreign windows
  are indexed once (`_foreign_index`, prefix-max-of-ends) and queried by bisect,
  so a game with 10k dialogue records no longer means ~100M Python iterations.
  The real ROM suite went from 644 s to 85-92 s. `_foreign_ranges` survives only
  as the pre-index reference implementation used by `_relocate_dialogue` and as
  the oracle in `test_index_matches_full_scan_oracle`.
- **Zeroing the old block after a dialogue relocation is a deliberate trade with
  debt.** The old block is zeroed entirely per `room_old`. The window is safe
  by construction (`free_after` abuts the next target and the scanner requires
  0x00/0xFF padding), but the manifest validator only checks that `slots` is a
  list of ints, not that it is complete. A pointer the scanner missed will read
  an empty string after zeroing instead of the previous English text. Cheaper
  to zero only up to `min(room_old, next_record_target - addr)` — the in-place
  path preserves the tail, zeroing destroys it
- [x] ~~**The compressed generic segment does not consult the overlap guard**~~ CLOSED: the compressed branch now checks `_check_write_overlap` and `_foreign_ranges` against the width actually written and skips the write on overlap, reporting it in `last_overlap_report` (`foreign: True`). The same defect was closed in the ordinary generic path, the pointer path and `_inject_bank_segment`
- **Dialogue records receive a FOREIGN translation (Odyssey v4.1, critical).**
  CLOSED: the cause was not translation-to-record matching but the ability
  segment window `[0x24FC40, 0x250036)` covering dialogue record 607 at
  `0x250026`. The generic path wrote from its own base without consulting other
  segments and wiped 13 bytes of that record (`d1 c9 c8 cd 00 c1 c8 c3 c8 cc bb
  d1 ff` — the tail of 'WATER LABYRINTH' with a shifted start). The generic path
  now checks foreign ranges and skips an overlapping write, marking it
  `foreign: True` in `last_overlap_report`; dialogue manifests contribute
  PER-RECORD windows rather than one coarse block, otherwise every neighbouring
  segment would be rejected as a whole.
  REMAINS: ~2 of 411 names, ~6 of 77 abilities and ~7 of 1179 dialogues on
  Odyssey stay untranslated — their windows physically overlap foreign segments
  and cannot be written without relocating the tables themselves. This is a
  report the translator can see, not a silent loss. Also still to do: split
  Odyssey and Radical Red into separate manifests/profiles — detection is shared
  for now
- [x] ~~A relocated Pokémon dialogue loses the block's last character~~ CLOSED: the
  post-relocation parse is cut at the terminator rather than at the static
  `free_after`, which is what dropped the final byte. Pinned by
  `test_relocated_dialogues_roundtrip` — it compares the translation AFTER the
  relocation in full, last character included
- [x] ~~Odyssey v4.1: after a dialogue relocation, extraction returns a foreign text
  (`NG` → we expect `GN`, we get `AW`)~~ CLOSED: that was the same corruption
  described above (the ability window overwriting a dialogue record), not a
  relocation problem. Pinned by `test_changed_text_roundtrip` and
  `test_relocated_dialogues_roundtrip`. REMAINS: split Odyssey and Radical Red
  into separate manifests/profiles with their own `guard` — on a hack the slots
  already disagree with the manifest on a CLEAN ROM, so the main plugin has to
  rely on two relocation signals at once for the 4 clean ROMs

---

## 🤝 How to Contribute

1. Check [CONTRIBUTING.md](CONTRIBUTING.md)
2. Create an issue before starting work
3. Write tests for new features
4. Update documentation

---

