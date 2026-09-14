"""Диалоговый pointer-пайплайн Pokemon GBA (Этап 2).

Unit: грамматика контрольных токенов декодера/энкодера round-trip.
rom_required: extracted dialogue strings обязаны (а) декодироваться обратно
в тот же текст, (б) влезать в свой free_after (безопасность in-place),
(в) внедрённые ссылки перечитываются в исходный текст.

Нарушение (а)/(б) означает: либо энкодер теряет информацию, либо манифест
даёт небезопасную комнату — оба случая блокируют Этап 2.
"""
import os

import pytest

from core.injector import TextInjector
from plugins.gba_pokemon import (
    CHARMAP_FIRERED,
    CHARMAP_POKEMON_GBA,
    PokemonTextDecoder,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM_DIR = os.path.join(BASE, 'test_roms')

GAME_ROMS = {
    'BPEE': 'Pokemon - Emerald Version (USA, Europe).gba',
    'BPRE': 'Pokemon - FireRed Version (USA).gba',
    'BPGE': 'Pokemon - LeafGreen Version (USA).gba',
    'AXVE': 'Pokemon - Ruby Version (USA).gba',
    'AXPE': 'Pokemon - Sapphire Version (USA).gba',
}
VERSIONS = {'BPEE': 'emerald', 'BPRE': 'firered', 'BPGE': 'leafgreen',
            'AXVE': 'ruby', 'AXPE': 'sapphire'}


@pytest.fixture
def rse_decoder():
    return PokemonTextDecoder(CHARMAP_POKEMON_GBA)


@pytest.fixture
def fr_decoder():
    return PokemonTextDecoder(CHARMAP_FIRERED)


def _rt(decoder, raw: bytes) -> bool:
    text = decoder.decode(raw, 0, len(raw))
    enc = decoder.encode(text)
    return decoder.decode(enc, 0, len(enc)) == text


# ── Unit: грамматика ────────────────────────────────────────────────────────
def test_scroll_para_distinct_tokens(rse_decoder):
    assert rse_decoder.decode(b'\xBB\xFE\xBC\xFF', 0, 4) == 'A\nB'
    assert rse_decoder.decode(b'\xBB\xFA\xFF', 0, 3) == 'A[SCROLL]'
    assert rse_decoder.decode(b'\xBB\xFB\xFF', 0, 3) == 'A[PARA]'


def test_encoder_ctrl_roundtrip(rse_decoder):
    raws = [
        b'\xBB\xBC\xBD\xFF',                       # plain
        b'\xFC\x06\x01\xBB\xFF',                   # set font NORMAL
        b'\xFC\x01\x04\xBB\xFF',                   # color RED
        b'\xFC\x02\x02\xBB\xFF',                   # highlight DARK_GRAY
        b'\xFC\x03\x08\xBB\xFF',                   # shadow BLUE
        b'\xFC\x04\x12\x34\x56\xFF',               # CHS
        b'\xFC\x09\xFF',                           # PAUSE_UNTIL_PRESS
        b'\xFC\x0B\xFF',                           # PLAY_BGM
        b'\xF8\x04\xFF',                           # [START]
        b'\xF8\x00\xFF',                           # [A]
        b'\xF9\x0A\xFF',                           # ①
        b'\xF9\xDF\xFF',                           # 🌀
        b'\xFD\x01\xFF',                           # {PLAYER}
        b'\xFD\x02\xFF',                           # {STR_VAR_1}
        b'\xF7\xFF',                               # [DYN]
        b'\x53\x54\xFF',                           # PKMN glyphs
        b'\x20\x16\x17\xFF',                       # accents round-trip
    ]
    for raw in raws:
        assert _rt(rse_decoder, raw), f'round-trip failed for {raw!r}'


def test_fr_multichar_glyphs(fr_decoder):
    raw = b'\xB5\xB6\xFF'                          # |m| |w|
    text = fr_decoder.decode(raw, 0, len(raw))
    assert text.startswith('|m|')
    enc = fr_decoder.encode(text)
    assert fr_decoder.decode(enc, 0, len(enc)) == text


def test_unknown_char_maps_to_space(rse_decoder):
    enc = rse_decoder.encode('A{')
    assert enc == b'\xBB\x00'
    assert rse_decoder.decode(enc, 0, len(enc)) == 'A '


# ── rom_required: интеграция экстракции/вставки ─────────────────────────────
@pytest.mark.rom_required
@pytest.mark.parametrize('game_code', sorted(GAME_ROMS))
def test_dialogues_roundtrip_and_fit(game_code):
    rom_path = os.path.join(ROM_DIR, GAME_ROMS[game_code])
    if not os.path.exists(rom_path):
        pytest.skip(f'Нет ROM: {os.path.basename(rom_path)}')
    from core.extractor import TextExtractor
    from core.plugin_manager import PluginManager
    from core.rom import GameBoyROM

    rom = GameBoyROM(rom_path)
    version = VERSIONS[game_code]
    charmap = CHARMAP_FIRERED if version in ('firered', 'leafgreen') \
        else CHARMAP_POKEMON_GBA
    decoder = PokemonTextDecoder(charmap)

    ex = TextExtractor(rom_path, rom=rom,
                       plugin_manager=PluginManager())
    results = ex.extract()
    name = f'pokemon_{version}_dialogues'
    messages = results[name]
    assert messages, f'{game_code}: пустой диалог-сегмент'

    for m in messages:
        assert 0 <= m['target_addr'] < len(rom.data)
        assert m['length'] >= 3
        enc = decoder.encode(m['text'])
        back = decoder.decode(enc, 0, len(enc))
        assert back == m['text'], f'{game_code}: потеря текста 0x{m["target_addr"]:X}'
        assert len(enc) + 1 <= m['length'], \
            f'{game_code}: строка 0x{m["target_addr"]:X} не влезает в комнату'


@pytest.mark.rom_required
@pytest.mark.parametrize('game_code', sorted(GAME_ROMS))
def test_dialogues_in_place_inject_roundtrip(game_code):
    rom_path = os.path.join(ROM_DIR, GAME_ROMS[game_code])
    if not os.path.exists(rom_path):
        pytest.skip(f'Нет ROM: {os.path.basename(rom_path)}')
    from core.extractor import TextExtractor
    from core.plugin_manager import PluginManager
    from core.rom import GameBoyROM

    rom = GameBoyROM(rom_path)
    version = VERSIONS[game_code]
    charmap = CHARMAP_FIRERED if version in ('firered', 'leafgreen') \
        else CHARMAP_POKEMON_GBA
    decoder = PokemonTextDecoder(charmap)

    ex = TextExtractor(rom_path, rom=rom, plugin_manager=PluginManager())
    results = ex.extract()
    name = f'pokemon_{version}_dialogues'
    messages = results[name]
    texts = [m['text'] for m in messages]
    plugin = ex.plugin

    injector = TextInjector(rom_path)
    assert injector.inject_segment(name, texts, plugin, skip_long=False)

    seg = next(s for s in plugin.get_text_segments(injector.rom)
               if s['name'] == name)
    for entry in seg['manifest']:
        addr = entry['target']
        room = entry['free_after']
        back = decoder.decode(injector.modified_data, addr, room)
        want = decoder.decode(rom.data, addr, min(room, 320))
        assert back == want, \
            f'{game_code}: вставка испортила 0x{addr:X}'
    assert injector.last_overflow_report == []


@pytest.mark.rom_required
def test_dialogue_overflow_reported(game_code='BPEE'):
    rom_path = os.path.join(ROM_DIR, GAME_ROMS[game_code])
    if not os.path.exists(rom_path):
        pytest.skip('Нет ROM Emerald')
    from core.extractor import TextExtractor
    from core.plugin_manager import PluginManager
    from core.rom import GameBoyROM

    rom = GameBoyROM(rom_path)
    ex = TextExtractor(rom_path, rom=rom, plugin_manager=PluginManager())
    results = ex.extract()
    name = 'pokemon_emerald_dialogues'
    messages = results[name]
    plugin = ex.plugin

    big = 'X' * (max(m['length'] for m in messages) + 10)
    overflow_texts = [big] * len(messages)

    injector = TextInjector(rom_path)
    injector.inject_segment(name, overflow_texts, plugin, skip_long=True)
    assert injector.last_overflow_report
    first = injector.last_overflow_report[0]
    assert 'target' in first and 'free_after' in first and 'text' in first
