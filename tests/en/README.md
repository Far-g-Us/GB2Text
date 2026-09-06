# Testing GB2Text

## Why Tests?

Tests provide:
- **Reliability** — verify that code works correctly
- **Safety** — prevent regressions when changes are made
- **Documentation** — show expected code behavior
- **Easier debugging** — quickly find issues

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Running Tests

### All Tests
```bash
pytest tests/ -v
```

### With Code Coverage
```bash
pytest tests/ --cov=core --cov-report=html
```

### Specific File
```bash
pytest tests/test_charset.py -v
```

## Test Structure

```
tests/
├── __init__.py
├── test_analyzer.py           # Text analyzer tests
├── test_auto_detect.py        # Auto-detection tests
├── test_charset.py            # Charset file loading tests
├── test_compression.py        # Compression tests (LZSS, RLE)
├── test_constants.py          # Constants tests
├── test_decoder.py            # Decoder tests
├── test_decoder_extended.py   # Extended decoder tests
├── test_encoding.py           # Encoding tests
├── test_extractor.py          # Text extractor tests
├── test_gba_support.py        # GBA support tests
├── test_generic_plugin.py     # Generic plugin tests
├── test_guide.py              # Guide manager tests
├── test_gui.py                # GUI tests
├── test_gui_edge_cases.py     # GUI edge case tests
├── test_gui_methods.py        # GUI method tests
├── test_gui_real.py           # GUI real scenario tests
├── test_gui_robot.py          # GUI Robot Framework tests
├── test_i18n.py               # Localization tests (i18n)
├── test_injector.py           # Text injector tests
├── test_integration.py        # Integration tests
├── test_integration_extended.py # Extended integration tests
├── test_machine_translation.py # Machine translation tests
├── test_main_window.py        # Main window tests
├── test_mbc.py                # MBC tests
├── test_ml_classifier.py      # ML classifier tests
├── test_multi_charmap.py      # Multi-charmap tests
├── test_plugin.py             # Plugin tests
├── test_plugin_api.py         # Plugin API tests
├── test_plugin_api_extended.py # Extended plugin API tests
├── test_plugin_manager.py     # Plugin manager tests
├── test_rom.py                # ROM tests
├── test_rom_cache.py          # ROM caching tests
├── test_rom_discovery.py      # ROM discovery tests
├── test_rom_validation.py     # ROM validation tests
├── test_roundtrip.py          # Round-trip extract/insert tests
├── test_scanner.py            # Scanner tests
├── test_scanner_extended.py   # Extended scanner tests
├── test_tmx.py                # TMX tests
├── test_translation_filler.py # Translation filler tests
└── test_translation_validator.py # Translation validator tests
```

## Test Types

### 1. Unit Tests
Test individual functions/classes in isolation:
- `test_charset.py` — charset table loading
- `test_decoder.py` — encoding/decoding
- `test_constants.py` — project constants
- `test_i18n.py` — localization (47 tests)
- `test_plugin_manager.py` — plugin manager
- `test_scanner.py` — text scanner

### 2. Integration Tests
Test module interaction:
- `test_integration.py` — working with real ROM files

## Adding New Tests

### Test Example
```python
def test_my_function():
    """Test description"""
    result = my_function(input_data)
    assert result == expected_result
```

### Running a Specific Test
```bash
pytest tests/test_charset.py::TestCharset::test_load_charset_english -v
```

## Continuous Integration

Tests should pass before every commit:
```bash
# Check locally before push
pytest tests/ -v
```

## Coverage

**Target coverage: 80%+ for all core files**

Current coverage see in HTML report after running with `--cov-report=html`
