"""Pytest configuration and shared fixtures for GB2Text tests."""

import pytest
from pathlib import Path


# ROM system types for parametrized tests
@pytest.fixture(params=['GB', 'GBC', 'GBA'])
def rom_system(request):
    """Parametrized fixture for ROM system types."""
    return request.param


# Language fixtures for i18n testing
@pytest.fixture(params=['en', 'ru', 'ja', 'zh'])
def language(request):
    """Parametrized fixture for supported languages."""
    return request.param


# ROM file fixtures
@pytest.fixture
def test_roms_dir():
    """Return the test ROMs directory path."""
    return Path(__file__).parent.parent / 'test_roms'


@pytest.fixture
def guides_dir():
    """Return the guides directory path."""
    return Path(__file__).parent.parent / 'guides'


@pytest.fixture
def config_dir():
    """Return the plugins config directory path."""
    return Path(__file__).parent.parent / 'plugins' / 'config'


@pytest.fixture
def locales_dir():
    """Return the locales directory path."""
    return Path(__file__).parent.parent / 'locales'


# Core module fixtures
@pytest.fixture
def core_modules():
    """Return list of core modules to test."""
    return [
        'analyzer',
        'charset',
        'compression',
        'decoder',
        'encoding',
        'extractor',
        'injector',
        'mbc',
        'plugin',
        'plugin_manager',
        'rom',
        'scanner',
    ]


# Skip GUI tests on headless systems
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "gui: marks tests as requiring GUI display"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


# Optional display fixture for GUI tests
@pytest.fixture(scope='session')
def gui_available():
    """Check if GUI display is available."""
    import os
    return os.environ.get('DISPLAY') is not None or os.name == 'nt'


@pytest.fixture(autouse=True)
def reset_test_env(monkeypatch, tmp_path):
    """Reset environment for each test."""
    # Set temp directory for test artifacts
    monkeypatch.setenv('TEMP', str(tmp_path))
    monkeypatch.setenv('TMP', str(tmp_path))
    return tmp_path


@pytest.fixture
def sample_rom_bytes():
    """Return sample ROM bytes for testing."""
    return bytes([
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ])


@pytest.fixture
def sample_text_data():
    """Return sample text data for testing."""
    return {
        'hello': 'world',
        'test': 'data',
        'numbers': [1, 2, 3],
        'nested': {'key': 'value'}
    }


@pytest.fixture
def charset_sample():
    """Return a sample charset mapping for testing."""
    return {
        0x00: 'A', 0x01: 'B', 0x02: 'C', 0x03: 'D',
        0x04: '0', 0x05: '1', 0x06: '2', 0xFF: '\n'
    }


@pytest.fixture
def mock_rom_file(tmp_path):
    """Create a mock ROM file for testing."""
    rom_file = tmp_path / 'test.gb'
    rom_file.write_bytes(bytes([0x00] * 32768))
    return rom_file


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add skip markers."""
    import os
    
    # Skip GUI tests if no display available
    if not os.environ.get('DISPLAY') and os.name != 'nt':
        skip_gui = pytest.mark.skip(reason="GUI tests require display")
        for item in items:
            if "gui" in item.keywords:
                item.add_marker(skip_gui)