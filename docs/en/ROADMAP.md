# GB2Text Roadmap

**Current version:** 1.2

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
- [ ] CI/CD for automated test runs (.github/workflows/tests.yml)
- [x] ROM file validation (extension, size checks)
- [x] GUI tests (tests/test_main_window.py)
- [ ] **Extended testing** — Matrix testing (Python 3.10-3.12, Ubuntu, Windows)
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
- [ ] CAT tool integration (memoQ, Trados)

### Analysis Improvements
- [x] ML-based segment detection
- [x] Automatic compression type detection
- [x] Multiple charset tables per segment support
- [x] Improved non-standard encoding detection
- [x] Automatic language detection in ROM

### UI/UX Improvements
- [ ] Visual charset table editor
- [ ] ROM map with highlighted text segments
- [ ] Customizable dark theme (color scheme)
- [ ] Multi-window mode
- [ ] Real-time preview of changes

### Utilities
- [x] Translation validation (text length check)
- [x] Automatic null translation filling
- [ ] Spell checking
- [x] **Developer tools** — scripts/debug.py, profile.py, diagnostics.py
- [x] **Benchmarks** — tests/benchmarks/test_performance.py
- [ ] **Coverage reports** — .github/workflows/coverage.yml

### Plugins & Extensibility
- [x] Plugin creation API
- [ ] Plugins for specific homebrew games
- [x] Configuration templates

---

## 🆕 Version 1.2

### GBA Game Plugins
- [x] 20+ GBA games supported (Pokemon, Fire Emblem, FF4/5/6, Zelda TMC, Castlevania, etc.)
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

## 🔮 Version 1.3 (planned)

### Priority 1 — Packaging
- [ ] CI/CD: .github/workflows/tests.yml + coverage.yml
- [ ] Pointer relocation after text reinsertion
- [ ] Header/global checksum recalculation after injection
- [ ] Tests for FFTA LZSS and Huffman decoders

### Priority 2 — New Plugins
- [ ] GB/GBC plugins (currently GBA only)
- [ ] Metroid Fusion — dialogue pointer tables
- [ ] Castlevania AoS — pointer table brute-force

### Priority 3 — UI/UX
- [ ] Visual charset table editor
- [ ] ROM map with highlighted text segments
- [ ] Segment name filter/search (for 1500+ segments)

### Priority 4 — Export
- [ ] XLIFF format (CAT integration)
- [ ] Plugin auto-discovery via entry_points

---

## 🐛 Known Issues

- Some games with non-standard encodings are not recognized
- FE Huffman decoder doesn't work for Europe ROMs (tree addresses unknown)
- Castlevania AoS — pointer tables not found

---

## 🤝 How to Contribute

1. Check [CONTRIBUTING.md](CONTRIBUTING.md)
2. Create an issue before starting work
3. Write tests for new features
4. Update documentation

---

## 📄 Additional Documentation

- [IMPROVEMENTS.md](../../IMPROVEMENTS.md) — Improvement suggestions

---

*Roadmap updated: 2026-09-06*
