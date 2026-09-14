import os
import shutil
import tempfile

import pytest

from core.extractor import TextExtractor
from core.injector import TextInjector
from core.rom import GameBoyROM
from plugins.gb_pokemon_gen1 import CHARMAP_GEN1, GEN1_TERMINATORS, Gen1FixedDecoder, Gen1TextDecoder, PokemonGen1Plugin

ROM_DIR = os.path.join(os.path.dirname(__file__), '..', 'test_roms')
RED = 'Pokemon - Red Version (USA, Europe).gb'


def _red_rom_path() -> str:
    return os.path.join(ROM_DIR, RED)


def _decode_segment(plugin, rom, seg):
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


# ── Уровень декодеров ──────────────────────────────────────────────────────

def test_game_id_pattern_matches_gb_pokemon():
    import re
    pat = PokemonGen1Plugin().game_id_pattern
    assert re.search(pat, 'GB_POKEMONRED')
    assert re.search(pat, 'GBC_POKEMONYEL')
    assert not re.search(pat, 'GB_ZELDA')


def test_gen1_text_decoder_roundtrip():
    d = Gen1TextDecoder(CHARMAP_GEN1)
    for s in ['MASTER BALL', 'POKé BALL', "OAK's PARCEL", 'ITEMFINDER', '10F']:
        enc = d.encode(s)
        assert d.decode(enc, 0, len(enc)) == s


def test_gen1_fixed_decoder_stops_at_terminator():
    d = Gen1FixedDecoder(CHARMAP_GEN1)
    # RHYDON (терминатор 0x50) затем следующий слот NIDORAN♂
    data = d.encode('RHYDON') + b'\x50' + d.encode('NIDORAN♂')
    assert d.decode(data, 0, len(data)) == 'RHYDON'


def test_gen1_fixed_decoder_ignores_padding():
    d = Gen1FixedDecoder(CHARMAP_GEN1)
    slot = d.encode('RHYDON') + b'\x50\x50\x50\x50'
    assert d.decode(slot, 0, len(slot)) == 'RHYDON'
    assert d.encode('RHYDON') == bytes([0x91, 0x87, 0x98, 0x83, 0x8e, 0x8d])


# ── Уровень конфигурации ───────────────────────────────────────────────────

def test_gen1_tables_shipped_red():
    assert list(GEN1_TERMINATORS) == [0x50]


def test_monster_names_range_is_exact_multiple_of_width():
    """190 слотов по 10 байт = ровно 1900 байт, без хвоста-мусора."""
    tmp_seg = {'name': 'gen1_monster_names', 'start': 0x1C21E, 'end': 0x1C98A,
               'fixed_width': 10}
    size = tmp_seg['end'] - tmp_seg['start']
    assert size % 10 == 0
    assert size // 10 == 190


# ── Уровень синтетических ROM (stub, Gen2) ────────────────────────────────

def _write_gb_mock(path: str, title: str, size: int = 0x100000) -> str:
    """Минимальный GB/GBC-ROM с указанным title и размером."""
    data = bytearray(size)
    data[0x134:0x134 + len(title)] = title.encode('ascii')
    with open(path, 'wb') as f:
        f.write(data)
    return path


def test_yellow_is_stub():
    """Yellow (другой layout) — stub: validate_rom True, сегментов нет."""
    tmp = os.path.join(tempfile.gettempdir(), 'mock_yellow.gb')
    _write_gb_mock(tmp, title='POKEMON YELLOW', size=0x200000)
    try:
        rom = GameBoyROM(tmp)
        plugin = PokemonGen1Plugin()
        assert plugin.validate_rom(rom) is True
        assert plugin.get_text_segments(rom) == []
        assert plugin.is_stub is True
    finally:
        os.remove(tmp)


def test_blue_is_stub():
    """Blue — stub: validate_rom True, сегментов нет, is_stub True."""
    tmp = os.path.join(tempfile.gettempdir(), 'mock_blue.gb')
    _write_gb_mock(tmp, title='POKEMON BLUE', size=0x100000)
    try:
        rom = GameBoyROM(tmp)
        plugin = PokemonGen1Plugin()
        assert plugin.validate_rom(rom) is True
        assert plugin.get_text_segments(rom) == []
        assert plugin.is_stub is True
    finally:
        os.remove(tmp)


def test_gen2_gold_rejected_by_validate():
    """Gen2 (Gold/Silver/Crystal) НЕ Gen1: validate_rom False."""
    tmp = os.path.join(tempfile.gettempdir(), 'mock_gold.gb')
    _write_gb_mock(tmp, title='POKEMON GOLD', size=0x100000)
    try:
        rom = GameBoyROM(tmp)
        plugin = PokemonGen1Plugin()
        assert plugin.validate_rom(rom) is False
    finally:
        os.remove(tmp)


def test_gen2_crystal_rejected_by_validate():
    """Crystal (2MB) НЕ Gen1: validate_rom False."""
    tmp = os.path.join(tempfile.gettempdir(), 'mock_crystal.gb')
    _write_gb_mock(tmp, title='POKEMON CRYSTAL', size=0x200000)
    try:
        rom = GameBoyROM(tmp)
        plugin = PokemonGen1Plugin()
        assert plugin.validate_rom(rom) is False
    finally:
        os.remove(tmp)


def test_non_pokemon_rejected_by_validate():
    """Не-Pokemon (Zelda) — validate_rom False."""
    tmp = os.path.join(tempfile.gettempdir(), 'mock_zelda.gb')
    _write_gb_mock(tmp, title='ZELDA', size=0x100000)
    try:
        rom = GameBoyROM(tmp)
        plugin = PokemonGen1Plugin()
        assert plugin.validate_rom(rom) is False
    finally:
        os.remove(tmp)


def test_gen1_fixed_decoder_encodes_multi_char_tokens():
    """Fixed-decode→encode round-trip включает multi-char токены charmap."""
    d = Gen1FixedDecoder(CHARMAP_GEN1)
    # è = 0xBA — из контрольных токенов, а имена не используют,
    # но декодер должны быть симметричен переменному.
    for s in ['é', '<PK>', '<MN>']:
        enc = d.encode(s)
        assert d.decode(enc, 0, len(enc)) == s


# ── Уровень реального ROM (skip, если нет ROM) ─────────────────────────────

@pytest.mark.rom_required
def test_real_rom_validate_and_extract():
    path = _red_rom_path()
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = PokemonGen1Plugin()
    assert plugin.validate_rom(rom) is True
    segments = plugin.get_text_segments(rom)
    assert len(segments) == 3
    assert all(seg['pad_byte'] == 0x50 for seg in segments)
    names = {seg['name'] for seg in segments}
    assert names == {'gen1_item_names', 'gen1_monster_names', 'gen1_move_names'}


@pytest.mark.rom_required
def test_real_rom_item_names_match_source():
    path = _red_rom_path()
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    from core.rom import GameBoyROM
    rom = GameBoyROM(path)
    plugin = PokemonGen1Plugin()
    seg = plugin.get_text_segments(rom)[0]
    msgs = _decode_segment(plugin, rom, seg)
    assert msgs[0] == 'MASTER BALL'
    assert msgs[3] == 'POKé BALL'
    assert msgs[-1] == 'B4F'


@pytest.mark.rom_required
def test_real_rom_monster_names_fixed_slots():
    path = _red_rom_path()
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = PokemonGen1Plugin()
    seg = plugin.get_text_segments(rom)[1]
    assert seg.get('fixed_width') == 10
    msgs = _decode_segment(plugin, rom, seg)
    assert len(msgs) == 190
    assert msgs[0] == 'RHYDON'
    assert msgs[1] == 'KANGASKHAN'
    assert msgs[2] == 'NIDORAN♂'
    assert msgs[-1] == 'VICTREEBEL'


@pytest.mark.rom_required
def test_real_rom_move_names_match_source():
    path = _red_rom_path()
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = PokemonGen1Plugin()
    seg = plugin.get_text_segments(rom)[2]
    msgs = _decode_segment(plugin, rom, seg)
    assert len(msgs) == 165
    assert msgs[0] == 'POUND'
    assert msgs[-1] == 'STRUGGLE'


@pytest.mark.rom_required
def test_real_rom_roundtrip():
    """extract → inject (те же тексты) → extract: идентичные тексты."""
    src = _red_rom_path()
    if not os.path.exists(src):
        pytest.skip('test ROM not present')
    plugin = PokemonGen1Plugin()
    with tempfile.TemporaryDirectory() as td:
        work = os.path.join(td, RED)
        shutil.copyfile(src, work)
        # имена в чистом виде (смещения не переносятся между плагинами) —
        # просто проверка симметрии extractor через реальный ROM
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
