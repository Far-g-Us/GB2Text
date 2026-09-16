import os
import shutil
import tempfile

import pytest

from core.extractor import TextExtractor
from core.injector import TextInjector
from core.rom import GameBoyROM
from plugins.gb_pokemon_gen1 import CHARMAP_GEN1, Gen1TextDecoder
from plugins.gbc_pokemon_gsc import GSC_TABLES, PokemonGSCPlugin

ROM_DIR = os.path.join(os.path.dirname(__file__), '..', 'test_roms')
GOLD = 'Pokemon - Gold Version (USA, Europe) (SGB Enhanced).gbc'


def _gold_rom_path() -> str:
    return os.path.join(ROM_DIR, GOLD)


def _decode_segment(rom, seg):
    """Декодирует сегмент так же, как TextExtractor (fixed_width + split)."""
    dec = seg['decoder']
    data = rom.data[seg['start']:seg['end']]
    if seg.get('fixed_width'):
        msgs = []
        for i in range(seg['record_count']):
            slot = data[i*seg['fixed_width']:(i+1)*seg['fixed_width']]
            text = dec.decode(slot, 0, len(slot))
            if text.strip('-? ') == '':
                continue
            msgs.append(text)
        return msgs
    text = dec.decode(data, 0, len(data))
    return [m for m in text.split('[END]') if m.strip()]


def _write_gb_mock(path: str, title: str, size: int = 0x200000) -> str:
    """Минимальный GB/GBC-ROM с указанным title и размером."""
    data = bytearray(size)
    data[0x134:0x134 + len(title)] = title.encode('ascii')
    with open(path, 'wb') as f:
        f.write(data)
    return path


# ── Уровень конфигурации ───────────────────────────────────────────────────

def test_game_id_pattern():
    import re
    pat = PokemonGSCPlugin().game_id_pattern
    assert re.match(pat, 'GBC_POKEMONGLDAAUE')
    assert re.match(pat, 'GBC_POKEMONSLVAAXE')
    assert re.match(pat, 'GBC_POKEMONSILVER')
    assert re.match(pat, 'GBC_POKEMONCRYSTAL')
    assert re.match(pat, 'GBC_POKEMONGOLD')
    assert re.match(pat, 'GBC_PMCRYSTALBYTE')
    assert re.match(pat, 'GBC_PMCRYSTALBXTJ')
    assert not re.match(pat, 'GBC_POKEMONYEL')


def test_gsc_tables_cover_gold_silver_and_crystal_ue():
    """GSC_TABLES covers verified titles (Gold, Silver, Crystal UE)."""
    assert set(GSC_TABLES) == {
        'POKEMON_GLDAAUE', 'POKEMON_SLVAAXE', 'POKEMON_SILAAUE',
        'PM_CRYSTAL\x00BYTE',
    }
    names = [t['name'] for t in GSC_TABLES['POKEMON_GLDAAUE']]
    assert names == ['item_names', 'trainer_class_names',
                     'monster_names', 'move_names']
    assert GSC_TABLES['POKEMON_SLVAAXE'] == GSC_TABLES['POKEMON_GLDAAUE']
    assert GSC_TABLES['POKEMON_SILAAUE'] == GSC_TABLES['POKEMON_GLDAAUE']


def test_monster_names_range_is_exact_multiple_of_width():
    monster = next(t for t in GSC_TABLES['POKEMON_GLDAAUE']
                    if t['name'] == 'monster_names')
    size = monster['end'] - monster['start']
    assert size % 10 == 0


# ── Уровень декодеров ──────────────────────────────────────────────────────

def test_gsc_reuses_gen1_charmap_and_decoders():
    """Gen2 charmap идентичен Gen1 — переиспользуем без дублирования."""
    assert CHARMAP_GEN1[0x80] == 'A'
    assert CHARMAP_GEN1[0x50] == '@'
    assert CHARMAP_GEN1[0x7F] == ' '
    d = Gen1TextDecoder(CHARMAP_GEN1)
    assert d.decode(bytes([0x8f, 0x8e, 0x93, 0x88, 0x8e, 0x8d, 0x50]),
                    0, 7) == 'POTION[END]'


# ── Уровень синтетических ROM ──────────────────────────────────────────────

def test_silver_has_real_tables():
    """Silver: validate истинно, есть реальные сегменты (не stub)."""
    tmp = os.path.join(tempfile.gettempdir(), 'mock_silver.gb')
    _write_gb_mock(tmp, title='POKEMON_SLVAAXE', size=0x200000)
    try:
        rom = GameBoyROM(tmp)
        plugin = PokemonGSCPlugin()
        assert plugin.validate_rom(rom) is True
        segs = plugin.get_text_segments(rom)
        assert len(segs) == 4
        assert plugin.is_stub is False
    finally:
        os.remove(tmp)


def test_crystal_ue_has_real_tables():
    """Crystal UE (PM_CRYSTAL..BYTE): validate истинно, 4 реальных сегмента."""
    tmp = os.path.join(tempfile.gettempdir(), 'mock_crystal_ue.gb')
    _write_gb_mock(tmp, title='PM_CRYSTAL\x00BYTE', size=0x200000)
    try:
        rom = GameBoyROM(tmp)
        plugin = PokemonGSCPlugin()
        assert plugin.validate_rom(rom) is True
        segs = plugin.get_text_segments(rom)
        assert len(segs) == 4
        assert plugin.is_stub is False
    finally:
        os.remove(tmp)


def test_crystal_jp_is_stub():
    """Crystal JP (PM_CRYSTAL..BXTJ): validate истинно, но сегментов нет."""
    tmp = os.path.join(tempfile.gettempdir(), 'mock_crystal_jp.gb')
    _write_gb_mock(tmp, title='PM_CRYSTAL\x00BXTJ', size=0x200000)
    try:
        rom = GameBoyROM(tmp)
        plugin = PokemonGSCPlugin()
        assert plugin.validate_rom(rom) is True
        assert plugin.get_text_segments(rom) == []
        assert plugin.is_stub is True
    finally:
        os.remove(tmp)


def test_non_gsc_rejected_by_validate():
    tmp = os.path.join(tempfile.gettempdir(), 'mock_zelda.gb')
    _write_gb_mock(tmp, title='ZELDA', size=0x200000)
    try:
        rom = GameBoyROM(tmp)
        plugin = PokemonGSCPlugin()
        assert plugin.validate_rom(rom) is False
    finally:
        os.remove(tmp)


# ── Уровень реального ROM (skip, если нет ROM) ─────────────────────────────

@pytest.mark.rom_required
def test_real_rom_validate_and_extract():
    path = _gold_rom_path()
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = PokemonGSCPlugin()
    assert plugin.validate_rom(rom) is True
    segments = plugin.get_text_segments(rom)
    assert plugin.is_stub is False
    names = {seg['name'] for seg in segments}
    assert names == {'gen2_item_names', 'gen2_trainer_class_names',
                     'gen2_monster_names', 'gen2_move_names'}
    assert all(seg['pad_byte'] == 0x50 for seg in segments)


@pytest.mark.rom_required
def test_real_rom_silver_layout_identical_to_gold():
    """Silver (SLVAAXE) использует те же таблицы, что Gold."""
    path = os.path.join(ROM_DIR,
                        'Pokemon - Silver Version (USA, Europe) '
                        '(SGB Enhanced).gbc')
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = PokemonGSCPlugin()
    assert plugin.validate_rom(rom) is True
    segs = plugin.get_text_segments(rom)
    assert len(segs) == 4
    seg = next(s for s in segs if s['name'] == 'gen2_item_names')
    assert seg['start'] == 0x1B0000 and seg['end'] == 0x1B0955
    msgs = _decode_segment(rom, seg)
    assert msgs[0] == 'MASTER BALL'
    assert 'POTION' in msgs
    seg = next(s for s in segs if s['name'] == 'gen2_move_names')
    msgs = _decode_segment(rom, seg)
    assert msgs[0] == 'POUND'
    assert msgs[-1] == 'BEAT UP'
    seg = next(s for s in segs if s['name'] == 'gen2_monster_names')
    assert seg['start'] == 0x1B0B74 and seg['end'] == 0x1B1574
    msgs = _decode_segment(rom, seg)
    assert msgs[0] == 'BULBASAUR'


@pytest.mark.rom_required
def test_real_rom_crystal_ue_layout():
    """Crystal UE (PM_CRYSTAL..BYTE) использует собственные адреса таблиц."""
    path = os.path.join(ROM_DIR,
                        'Pokemon - Crystal Version (UE) (V1.1) [C][!].gbc')
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = PokemonGSCPlugin()
    assert plugin.validate_rom(rom) is True
    segs = plugin.get_text_segments(rom)
    assert len(segs) == 4
    by_name = {s['name']: s for s in segs}
    assert by_name['gen2_item_names']['start'] == 0x1C8000
    assert by_name['gen2_item_names']['end'] == 0x1C8955
    assert by_name['gen2_trainer_class_names']['start'] == 0x2C1EF
    assert by_name['gen2_trainer_class_names']['end'] == 0x2C41A
    assert by_name['gen2_monster_names']['start'] == 0x53384
    assert by_name['gen2_monster_names']['end'] == 0x53D84
    assert by_name['gen2_move_names']['start'] == 0x1C9F29
    assert by_name['gen2_move_names']['end'] == 0x1CA896
    msgs = _decode_segment(rom, by_name['gen2_item_names'])
    assert msgs[0] == 'MASTER BALL'
    assert 'BICYCLE' in msgs
    msgs = _decode_segment(rom, by_name['gen2_monster_names'])
    assert msgs[0] == 'BULBASAUR'
    assert 'CELEBI' in msgs
    msgs = _decode_segment(rom, by_name['gen2_move_names'])
    assert len(msgs) == 251
    assert msgs[-1] == 'BEAT UP'


@pytest.mark.rom_required
def test_real_rom_crystal_jp_is_stub():
    """Crystal JP: распознаётся, но Japanese charmap не поддерживается."""
    path = os.path.join(ROM_DIR,
                        'Pocket Monsters - Crystal Version (Japan) '
                        '[T-En by Unknown v1.0].gbc')
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = PokemonGSCPlugin()
    assert plugin.validate_rom(rom) is True
    assert plugin.get_text_segments(rom) == []
    assert plugin.is_stub is True


@pytest.mark.rom_required
def test_real_rom_item_names_match_source():
    path = _gold_rom_path()
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = PokemonGSCPlugin()
    seg = plugin.get_text_segments(rom)[0]
    assert seg['name'] == 'gen2_item_names'
    msgs = _decode_segment(rom, seg)
    assert msgs[0] == 'MASTER BALL'
    assert msgs[1] == 'ULTRA BALL'
    assert 'BICYCLE' in msgs
    assert 'POTION' in msgs


@pytest.mark.rom_required
def test_real_rom_monster_names_fixed_slots():
    path = _gold_rom_path()
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = PokemonGSCPlugin()
    seg = next(s for s in plugin.get_text_segments(rom)
               if s['name'] == 'gen2_monster_names')
    assert seg.get('fixed_width') == 10
    msgs = _decode_segment(rom, seg)
    assert msgs[0] == 'BULBASAUR'
    assert msgs[1] == 'IVYSAUR'
    assert msgs[3] == 'CHARMANDER'
    assert 'CELEBI' in msgs


@pytest.mark.rom_required
def test_real_rom_move_names_match_source():
    path = _gold_rom_path()
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = PokemonGSCPlugin()
    seg = next(s for s in plugin.get_text_segments(rom)
               if s['name'] == 'gen2_move_names')
    msgs = _decode_segment(rom, seg)
    assert len(msgs) == 251
    assert msgs[0] == 'POUND'
    assert msgs[1] == 'KARATE CHOP'
    assert msgs[-1] == 'BEAT UP'


GSC_ROM_FILES = {
    'gold': GOLD,
    'silver': 'Pokemon - Silver Version (USA, Europe) (SGB Enhanced).gbc',
    'crystal_ue': 'Pokemon - Crystal Version (UE) (V1.1) [C][!].gbc',
}


@pytest.mark.rom_required
@pytest.mark.parametrize('rom_file', GSC_ROM_FILES.values(),
                         ids=GSC_ROM_FILES.keys())
def test_real_rom_roundtrip(rom_file):
    """extract → inject (те же тексты) → extract: идентичные тексты."""
    src = os.path.join(ROM_DIR, rom_file)
    if not os.path.exists(src):
        pytest.skip('test ROM not present')
    plugin = PokemonGSCPlugin()
    with tempfile.TemporaryDirectory() as td:
        work = os.path.join(td, rom_file)
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

