# Changelog

All notable changes to the GB2Text project.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Font core F1 (`core/font_tiles.py`, EXPERIMENTAL).** 1/2/4bpp tile
  decode/encode (GBA 4bpp low-nibble-first), strict `bpp` validation
  (no silent fallback), `validate_font_meta` + layout gates, PNG
  import/export + char→tile manifest + VWF widths, `preview_font_block`
  dry-run and `inject_font_block` (explicit `confirm=True`,
  compressed-font refusal, candidate gate, atomic writes), Layer 1
  integration test (checksums + no-touch-outside). 100% coverage.
  Real-ROM pilot still required.
- **Font GUI tab F2 (`gui/font_tab.py`, `gui/glyph_editor.py`).**
  Glyph-grid preview (composite Canvas + pagination), PNG import,
  per-pixel glyph editor (modal, paint/cycle/erase + palette),
  write-through-`TextInjector` with confirm, undo/redo zone-snapshot
  stacks, five view states, `en`/`ru` locales. No GUI for playtest yet.
- **Headless playtest (`core/playtest.py`, PyBoy-first).**
  Strictly validated input scripts (button allowlist, frame caps),
  per-frame SHA-256, stuck/dark markers, screenshots on marks,
  structural `compare_reports` (round-trip only), `MGBABackend` as an
  honest stub; mGBA v1 adds a pinned-API (0.10.x) Lua driver generator
  + manual-run shot collector. 100% coverage on fake cores; emulator
  pilot on a real ROM still required. `pyboy==2.7.1` in requirements-dev.
- **DTE v3 (`core/dte.py`, EXPERIMENTAL).** Atomic `TextCoder`
  (strict ASCII default), byte-level table builder with loud disjoint
  checks, masked-pair encode, `build_for_translation` with mandatory
  `extra_used` and honest post-assignment savings stats, in-memory
  Cyrillic pilot. Injector writes stay a follow-up.
- **Community dialog sorting + portable specs + build fixes.**
  Clickable Treeview headers (name/author/version/status/type, asc/desc
  with ▲▼ marks, semantic version order, selection preserved,
  i18n-safe column autosize); both `.spec` files portable (relative
  paths, `--specpath` into `build/specs`); build scripts ship a single
  `HIDDEN_IMPORTS` list incl. Pillow (previously excluded → silent
  onefile death) and new modules; debug wrapper runs `main()` with
  cp1251-safe output.

## [1.4.0] — 2026-09-23

### Added
- **Spellcheck gate on injection.** Every translation is checked through
  `spell_checker.check_text` before being written to ROM; detected errors are
  accumulated in `TextInjector.last_spellcheck_report` (same pattern as
  `last_overflow_report`). The gate is always soft — writing is never blocked.
  It covers all write paths: `inject_segment`
  (plain/compressed/bank/fixed_width/pointer_dialogues),
  `inject_language_block` (including slot-interleaved) and
  `inject_pointer_dialogues`.
- **Lazy plugin loading.** Specific plugins are imported for the first time
  only on the first match in `get_plugin`; generic plugins
  (`GenericGBPlugin`, `GenericGBCPlugin`, `GenericGBAPlugin`,
  `AutoDetectPlugin`) stay eager. The allowlist gate is preserved: a module
  outside the allowlist is imported neither at startup nor lazily.
  `.plugins`/`list_plugins` still return the full list, and thread safety is
  provided by a lock and a `CancellationToken`.
- **Textbox simulator (`core/textbox.py`).** Character-based fit check for
  translations: word wrap that keeps `[XX]`/`{VAR}`/`%s` tokens unsplit
  at word boundaries (hard-cut only when a token itself exceeds the width),
  per-message report `{index, ok, overflow_chars, lines_used}` from segment
  `max_length`/`fixed_width`. Wired as soft `TextInjector.last_fit_report`
  (reset in every entry point, never blocks writing, coexists with
  overflow/spellcheck reports).
- **Font tiles phase 0/1 (`core/font_tiles.py`, `scripts_roms/`).**
  GB 2bpp tile decode/encode round-trip + ASCII-art preview for review
  without an emulator; blind-heuristic font scan of two ROMs
  (`scripts_roms/font_scan.py`, 1bpp/2bpp) did not positively identify
  a font — findings, candidates and ROM/VRAM addressing documented in
  `scripts_roms/FONT_RESEARCH.md`. Glyph injection (phase 2) gated
  behind review.
- **DTE dictionary builder (`core/dte.py`).** Automatic byte-pair table
  builder from bigram frequencies with NET-profit ranking
  (`freq - table_entry_cost`), token/newline hard-breaks, deterministic
  tie-break, greedy codec + `DTEHandler` (subclass of
  `CompressionHandler`, per-segment instances, registry untouched).
- **`POST /diff` endpoint + `core/diff_text.py`.** Compares extracted text
  of two ROM versions: `added`/`removed` as sorted key diffs, `changed` as
  keyed pairs of GUI-style summaries (`_summarize_text`, 40 chars, ASCII
  `...`), stats included. Contract mirrors `/extract`; missing `rom2`
  yields 400, invalid `rom1` type yields 200 `ok:false VALIDATION_ERROR`,
  GET yields 405. Read-only: no inject locks touched.
- **Font glyph injection (`inject_glyphs`, `get_font_meta`).**
  In-place writes of 2bpp glyphs (raw bytes or 8x8 grids) with
  two-phase validation (no partial writes on error), per-tile report,
  free-space search delegated to the caller (e.g.
  `pointer_table.find_free_space`); optional `GamePlugin.get_font_meta`
  hook (default None, no existing plugin changes). Real-ROM demo
  replaced by synthetic end-to-end test (font not positively identified
  in researched ROMs — see `scripts_roms/FONT_RESEARCH.md`).

### Changed
- **BREAKING: auto-detect Russian charmap is now real CP866.**
  `_setup_russian_charmap` previously shipped a game-specific example table
  (e.g. 0x80='Ё') with duplicate values that made `encode` non-deterministic.
  It now matches the CP866 (DOS Russian) codec byte-for-byte for 0x80-0xFE
  (letters, box drawing, Ё/ё, ЄєЇїЎў, °∙·√№¤■); values are unique
  (first-wins reverse-map). Game-specific overrides via plugin `charmap`
  keep working. 0xFF stays a message terminator (`'\n'`), not NBSP.
  Re-extract Russian ROMs analyzed with older versions.
- Hiragana auto-table deduplicated: bytes 0xB8/0xB9/0xC7 duplicated
  0x84 '゛', 0x85 '゜', 0x86 'ー' (non-deterministic encode reverse-map).
  They now decode as unknown; first occurrences win.
- `spell_checker.check_text` gained an optional `with_suggestions` parameter
  (`True` by default); suggestions for very long words are not computed. The
  injection gate checks with `with_suggestions=False` — on large corpora this
  removes ~99% of the check time.
- `VERSION` = `1.4`, `pyproject.toml` version = `1.4.0`.
