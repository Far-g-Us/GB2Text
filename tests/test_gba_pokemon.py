"""Тесты Pokémon GBA плагина: фикс-таблицы, stub-логика, round-trip."""

import os
import shutil
import tempfile

import pytest

from core.extractor import TextExtractor
from core.injector import TextInjector
from core.plugin_manager import PluginManager
from core.rom import GameBoyROM
from plugins.gba_pokemon import FIXED_TABLES, PokemonGBAPlugin

ROM_DIR = os.path.join(os.path.dirname(__file__), '..', 'test_roms')
US_AND_EU = {
    'emerald': 'Pokemon - Emerald Version (USA, Europe).gba',
    'firered': 'Pokemon - FireRed Version (USA).gba',
    'leafgreen': 'Pokemon - LeafGreen Version (USA).gba',
    'ruby': 'Pokemon - Ruby Version (USA).gba',
    'sapphire': 'Pokemon - Sapphire Version (USA).gba',
}


def _write_mock_rom(path: str, size: int = 0x02000000, game_code: str = 'BPRE',
                    patches: dict[int, bytes] | None = None) -> str:
    """Создаёт минимальный GBA-ROM с game_code в заголовке и патчами данных."""
    data = bytearray(size)
    data[0x0AC:0x0B0] = game_code.encode('ascii')
    for offset, blob in (patches or {}).items():
        data[offset:offset + len(blob)] = blob
    with open(path, 'wb') as f:
        f.write(data)
    return path


def _pokemon_rom_path(file: str) -> str:
    return os.path.join(ROM_DIR, file)


def test_fixed_tables_names_end_equals_attacks_start():
    """Известный sanity-check: names.end == attacks.start для всех версий."""
    for version, tables in FIXED_TABLES.items():
        names = next(t for t in tables if t['name'] == 'names')
        attacks = next(t for t in tables if t['name'] == 'attacks')
        assert names['addr'] + names['width'] * names['count'] == attacks['addr'], version


@pytest.mark.parametrize('code', ('BPEJ', 'AXVJ', 'AXPJ'))
def test_jp_codes_stub(code):
    tmp = os.path.join(tempfile.gettempdir(), f'mock_{code}.gba')
    _write_mock_rom(tmp, game_code=code)
    try:
        rom = GameBoyROM(tmp)
        plugin = PokemonGBAPlugin()
        assert plugin.get_text_segments(rom) == []
        assert getattr(plugin, 'is_stub', plugin._is_stub) is True
    finally:
        os.remove(tmp)


@pytest.mark.parametrize('code', ('BPEJ', 'AXVJ', 'AXPJ'))
def test_jp_codes_stub_via_plugin_manager(code):
    """JP-коды матчатся Pokemon-плагином через PluginManager и уходят в stub."""
    tmp = os.path.join(tempfile.gettempdir(), f'mock_{code}.gba')
    _write_mock_rom(tmp, game_code=code)
    try:
        mgr = PluginManager()
        mgr.plugins = [PokemonGBAPlugin()]
        plugin = mgr.get_plugin(f'GBA_{code}', 'gba')
        assert isinstance(plugin, PokemonGBAPlugin)
        assert plugin.get_text_segments(GameBoyROM(tmp)) == []
        assert plugin.is_stub is True
    finally:
        os.remove(tmp)


@pytest.mark.parametrize('code', ('BPRE', 'BPGE'))
def test_firered_leafgreen_no_longer_stub(code):
    """BPRE/BPGE вышли из stub: возвращают непустые фикс-таблицы."""
    tmp = os.path.join(tempfile.gettempdir(), f'mock_{code}.gba')
    _write_mock_rom(tmp, game_code=code)
    try:
        rom = GameBoyROM(tmp)
        plugin = PokemonGBAPlugin()
        segments = plugin.get_text_segments(rom)
        assert getattr(plugin, 'is_stub', plugin._is_stub) is False
        assert len(segments) > 0
        assert all('fixed_width' in s for s in segments)
    finally:
        os.remove(tmp)


def test_blank_slot_is_skipped():
    """Пустые '?'-слоты пропускаются, реальные записи извлекаются."""
    addr = FIXED_TABLES['ruby'][0]['addr']  # names table
    # '?'*10 + FF  (пустой слот) |  BULBASAUR + FF + 0x00 (charmap-кодировка)
    bulbasaur = bytes.fromhex('BC CF C6 BC BB CD BB CF CC')
    blob = (b'\xac' * 10) + b'\xff' + bulbasaur + b'\xff\x00'
    tmp = os.path.join(tempfile.gettempdir(), 'mock_names.gba')
    _write_mock_rom(tmp, size=0x02000000, game_code='AXVE',
                    patches={addr: blob})
    try:
        rom = GameBoyROM(tmp)
        results = TextExtractor(tmp, rom=rom).extract()
        names = next(v for k, v in results.items() if k.endswith('_names'))
        texts = [m['text'] for m in names]
        assert texts == ['BULBASAUR']
    finally:
        os.remove(tmp)


@pytest.mark.parametrize('version,tname,count,first', [
    ('ruby', 'abilities', 78, 'STENCH'),
    ('ruby', 'types', 18, 'NORMAL'),
    ('sapphire', 'abilities', 78, 'STENCH'),
    ('sapphire', 'types', 18, 'NORMAL'),
    ('leafgreen', 'types', 18, 'NORMAL'),
])
def test_edge_tables_shipped(version, tname, count, first):
    """Ruby/Sapphire abilities+types и LeafGreen types найдены в FIXED_TABLES."""
    tables = FIXED_TABLES[version]
    t = next(t for t in tables if t['name'] == tname)
    assert t['count'] == count


@pytest.mark.parametrize('version,tname,first', [
    ('ruby', 'abilities', 'STENCH'),
    ('ruby', 'types', 'NORMAL'),
    ('sapphire', 'abilities', 'STENCH'),
    ('sapphire', 'types', 'NORMAL'),
    ('leafgreen', 'types', 'NORMAL'),
])
def test_new_tables_real_rom(version, tname, first):
    """Новые таблицы корректно декодируются с реальных ROM."""
    file = US_AND_EU[version]
    path = _pokemon_rom_path(file)
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    seg = next(s for s in PokemonGBAPlugin().get_text_segments(rom)
               if s['name'].endswith(f'_{tname}'))
    messages = TextExtractor(path, rom=rom).extract()[seg['name']]
    assert messages[0]['text'] == first


@pytest.mark.parametrize('version,file', list(US_AND_EU.items()))
def test_real_rom_segments_and_first_names(version, file):
    path = _pokemon_rom_path(file)
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = PokemonGBAPlugin()
    segments = plugin.get_text_segments(rom)
    assert len(segments) >= 2
    names = next(s for s in segments if s['name'].endswith('_names'))
    messages = TextExtractor(path, rom=rom).extract()[names['name']]
    assert messages[0]['text'] == 'BULBASAUR'


@pytest.mark.parametrize('version,file', list(US_AND_EU.items()))
def test_roundtrip_real_rom(version, file):
    """extract → inject (те же тексты) → extract даёт идентичные тексты."""
    src = _pokemon_rom_path(file)
    if not os.path.exists(src):
        pytest.skip('test ROM not present')
    plugin = PokemonGBAPlugin()
    with tempfile.TemporaryDirectory() as td:
        work = os.path.join(td, file)
        shutil.copyfile(src, work)
        rom = GameBoyROM(src)
        before = TextExtractor(src, rom=rom).extract()
        injector = TextInjector(work)
        for seg in plugin.get_text_segments(rom):
            texts = [m['text'] for m in before.get(seg['name'], [])]
            assert injector.inject_segment(seg['name'], texts, plugin)
        injector.save(work)
        after = TextExtractor(work, rom=GameBoyROM(work)).extract()
        for seg in plugin.get_text_segments(rom):
            before_texts = [m['text'] for m in before.get(seg['name'], [])]
            after_texts = [m['text'] for m in after.get(seg['name'], [])]
            assert before_texts == after_texts
