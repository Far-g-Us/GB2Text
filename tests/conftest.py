"""Pytest configuration and shared fixtures for GB2Text tests."""

from pathlib import Path

import pytest


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
    config.addinivalue_line(
        "markers", "rom_required: marks tests requiring real ROM files"
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


@pytest.fixture
def api_rom_bytes() -> bytes:
    """Синтетический валидный GB ROM (cartridge type 0x00 → GAME_00)."""
    size = 0x8000
    data = bytearray(size)

    nintendo_logo = bytes([
        0xCE, 0xED, 0x66, 0x66, 0xCC, 0x0D, 0x00, 0x0B,
        0x03, 0x73, 0x00, 0x83, 0x00, 0x0C, 0x00, 0x0D,
        0x00, 0x08, 0x19, 0x16, 0x83, 0x00, 0x73, 0x00,
        0x8B, 0x00, 0xD6, 0x00, 0xDC, 0x00, 0x2E, 0x00,
        0xE1, 0x00, 0x47, 0x18, 0x1F, 0x88, 0x89, 0x00,
        0x0E, 0xDC, 0xCC, 0x6E, 0xE6, 0xDD, 0xDD, 0xD9,
        0x99, 0xBB, 0xBB, 0x67, 0x63, 0x6E, 0x0E, 0xEC,
        0xCC, 0xDD, 0xDC, 0x99, 0x9F, 0xBB, 0xB9, 0x33,
        0x3E, 0x3C, 0x42, 0x79, 0xAB, 0x60, 0x3B, 0x89,
        0x43, 0x4E, 0x98, 0x56, 0x53, 0x4E, 0x4E, 0x7F,
        0x01, 0x2C, 0x58, 0x3A, 0x56, 0xC2, 0x49, 0x86,
        0x34, 0x50, 0x71, 0x62, 0x4F, 0x56, 0x6F, 0x41,
        0x4F, 0x29, 0x4C, 0x6F, 0x52, 0x53, 0x44, 0x53,
        0x47, 0x4D, 0x3A, 0x44, 0x5A, 0x47, 0x43, 0x20,
        0x01, 0x2C, 0x58, 0x3A, 0x56, 0xC2, 0x49, 0x86,
    ])
    data[0x104:0x133] = nintendo_logo[:0x2F]
    data[0x134:0x143] = b'TEST-TITLE-API'.ljust(15, b'\x00')
    data[0x143] = 0x00  # CGB flag = 0 (DMG)
    data[0x147] = 0x00  # Cartridge type = ROM ONLY
    data[0x149] = 0x00  # RAM size = None

    data[0x4000:0x400B] = b'HELLO WORLD'
    data[0x400B] = 0x00

    checksum = 0
    for addr in range(0x0134, 0x014D):
        checksum = (checksum - data[addr] - 1) & 0xFF
    data[0x14D] = checksum

    global_checksum = 0
    for i in range(len(data)):
        if i not in (0x14E, 0x14F):
            global_checksum = (global_checksum + data[i]) & 0xFFFF
    data[0x14E] = (global_checksum >> 8) & 0xFF
    data[0x14F] = global_checksum & 0xFF

    return bytes(data)


@pytest.fixture
def api_rom_file(tmp_path, api_rom_bytes):
    """Записывает api_rom_bytes в .gb файл, возвращает путь."""
    rom_file = tmp_path / "test_api.gb"
    rom_file.write_bytes(api_rom_bytes)
    return str(rom_file)


@pytest.fixture
def empty_plugin_dir(tmp_path) -> str:
    """Несуществующий каталог плагинов → безопасный fallback (generic-плагины)."""
    return str(tmp_path / "no_plugins")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add skip markers."""
    import os

    # Skip GUI tests if no display available
    if not os.environ.get('DISPLAY') and os.name != 'nt':
        skip_gui = pytest.mark.skip(reason="GUI tests require display")
        for item in items:
            if "gui" in item.keywords:
                item.add_marker(skip_gui)
