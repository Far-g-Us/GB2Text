import os
import shutil
import tempfile

import pytest

from core.extractor import TextExtractor
from core.injector import TextInjector
from core.rom import GameBoyROM
from plugins.gb_zelda_awakening import (
    ZELDA_SEGMENTS_GB,
    ZeldaAwakeningPlugin,
)
from plugins.gbc_zelda_awakening_dx import (
    ZELDA_SEGMENTS_DX,
    ZeldaAwakeningDXPlugin,
)
from plugins.zelda_awakening_common import (
    ZELDA_ARROWS,
    ZELDA_TERMINATORS,
    ZeldaTextDecoder,
)

ROM_DIR = os.path.join(os.path.dirname(__file__), '..', 'test_roms')
GB = 'Legend of Zelda, The - Link\'s Awakening (USA, Europe).gb'
DX = 'Legend of Zelda, The - Link\'s Awakening DX (USA, Europe).gbc'


def _rogue_path():
    return os.path.join(ROM_DIR, GB)


def _dx_path():
    return os.path.join(ROM_DIR, DX)


def _decode_segment(plugin, rom, seg):
    dec = seg['decoder']
    data = rom.data[seg['start']:seg['end']]
    text = dec.decode(data, 0, len(data))
    return [m for m in text.split('[END]') if m.strip()]


# ── Уровень декодера ────────────────────────────────────────────────────────

def test_decoder_roundtrip():
    d = ZeldaTextDecoder()
    for s in ["You've got a Golden Leaf!", 'Full Moon Cello',
              '[NEXT]', '[UP][DOWN][LEFT][RIGHT]']:
        enc = d.encode(s)
        assert d.decode(enc, 0, len(enc)) == s


def test_decoder_ascii_roundtrip():
    d = ZeldaTextDecoder()
    phrase = "It will reduce the damage you take by half!"
    assert d.decode(d.encode(phrase), 0, len(phrase)) == phrase


def test_decoder_terminators_and_next():
    d = ZeldaTextDecoder()
    raw = b'Yes  No\xfeHi there!'
    decoded = d.decode(raw, 0, len(raw))
    assert decoded == 'Yes  No[NEXT]Hi there!'
    assert d.encode(decoded) == raw


def test_decoder_arrows():
    d = ZeldaTextDecoder()
    raw = bytes([0xF0, 0xF1, 0xF2, 0xF3])
    decoded = d.decode(raw, 0, len(raw))
    assert decoded == '[UP][DOWN][LEFT][RIGHT]'
    assert d.encode(decoded) == raw


def test_decoder_icons_safe_tokens():
    """Глифы должны декодироваться НЕ в [XX]-вид, чтобы не разрывать записи."""
    d = ZeldaTextDecoder()
    for byte in ZELDA_ARROWS:
        assert f'[{byte:02X}]' not in d.decode(bytes([byte]), 0, 1)


def test_decoder_escape_zero():
    d = ZeldaTextDecoder()
    assert d.decode(b'\x00', 0, 1) == '[CTL_00]'


def test_decoder_icon_token_roundtrip():
    d = ZeldaTextDecoder()
    raw = bytes([0xE2, 0xAF, 0xC9, 0xE0, 0xA5, 0xC9, 0xA5, 0xAF])
    decoded = d.decode(raw, 0, len(raw))
    assert '[IC_E2]' in decoded and '[IC_AF]' in decoded
    assert d.encode(decoded) == raw
    # повторный колл не должен висеть (регрессия бесконечного цикла encode)
    assert d.encode(decoded) == raw


def test_decoder_inserted_end_token_is_dropped():
    """[END] в середине перевода — ошибка переводчика: дропается с warning."""
    d = ZeldaTextDecoder()
    half = d.encode('Hi![END]Bye!')
    assert half == b'Hi!Bye!'


def test_decoder_caret_encodes_to_apostrophe_byte():
    d = ZeldaTextDecoder()
    assert d.encode("Don't") == b"Don\x5Et"


def test_decoder_malformed_brackets_are_literal():
    d = ZeldaTextDecoder()
    for token in ('[IC_4', '[CTL_ZZ]', '[IC]', '[', 'IC_E2]'):
        enc = d.encode('word ' + token)
        assert d.decode(enc, 0, len(enc)) == 'word ' + token


def test_decoder_fe_at_end_of_record():
    d = ZeldaTextDecoder()
    raw = b'Yes  No\xfe'  # запись заканчивается на 0xFE
    decoded = d.decode(raw, 0, len(raw))
    assert decoded == 'Yes  No[NEXT]'
    assert d.encode(decoded) == raw


def test_decoder_double_ff_splits_to_empty_message():
    d = ZeldaTextDecoder()
    raw = b'One!\xff\xffTwo!'
    decoded = d.decode(raw, 0, len(raw))
    assert decoded == 'One![END][END]Two!'


# ── Уровень конфигурации ───────────────────────────────────────────────────

def test_terminators_only_ff():
    assert ZELDA_TERMINATORS == [0xFF]


def test_gb_segments_exact():
    assert len(ZELDA_SEGMENTS_GB) == 7
    names = [s[0] for s in ZELDA_SEGMENTS_GB]
    assert names == ['zelda_gb_dialog_a', 'zelda_gb_dialog_b',
                     'zelda_gb_dialog_c', 'zelda_gb_dialog_d',
                     'zelda_gb_credits', 'zelda_gb_dialog_e',
                     'zelda_gb_dialog_f']


def test_dx_segments_exact():
    assert len(ZELDA_SEGMENTS_DX) == 6
    names = [s[0] for s in ZELDA_SEGMENTS_DX]
    assert names == ['zelda_dx_dialog_a', 'zelda_dx_dialog_b',
                     'zelda_dx_dialog_c', 'zelda_dx_credits',
                     'zelda_dx_dialog_d', 'zelda_dx_dialog_e']
    # Старты — с начала EN-записей, энды — перед французскими хвостами
    # и без захвата примыкающего исполняемого кода.
    bounds = [(s[1], s[2]) for s in ZELDA_SEGMENTS_DX]
    assert bounds == [
        (0x2668E, 0x27D42),
        (0x51931, 0x53F48),
        (0x59701, 0x5BFA9),
        (0x5C095, 0x5C48B),
        (0x70B2A, 0x73EB3),
        (0x74000, 0x77FCC),
    ]


# ── Уровень синтетических ROM (stub-чеки на моках) ─────────────────────────

def _write_gb_mock(path: str, title: str, size: int = 0x100000) -> str:
    data = bytearray(size)
    data[0x134:0x134 + len(title)] = title.encode('ascii')
    with open(path, 'wb') as f:
        f.write(data)
    return path


def test_gb_plugin_game_id():
    import re
    pat = ZeldaAwakeningPlugin().game_id_pattern
    assert re.match(pat, 'GB_ZELDA')
    assert re.match(pat, 'GBC_ZELDAAZLE') is None


def test_dx_plugin_game_id():
    import re
    pat = ZeldaAwakeningDXPlugin().game_id_pattern
    assert re.match(pat, 'GBC_ZELDAAZLE')
    assert re.match(pat, 'GB_ZELDA') is None


def test_mock_gb_too_small_gives_no_segments():
    tmp = os.path.join(tempfile.gettempdir(), 'mock_zelda_small.gb')
    _write_gb_mock(tmp, title='ZELDA', size=0x1000)
    try:
        rom = GameBoyROM(tmp)
        plugin = ZeldaAwakeningPlugin()
        assert plugin.get_text_segments(rom) == []
    finally:
        os.remove(tmp)


def test_mock_gb_full_segments():
    tmp = os.path.join(tempfile.gettempdir(), 'mock_zelda.gb')
    _write_gb_mock(tmp, title='ZELDA', size=0x80000)
    try:
        rom = GameBoyROM(tmp)
        plugin = ZeldaAwakeningPlugin()
        segs = plugin.get_text_segments(rom)
        assert len(segs) == 7
        assert all(seg['pad_byte'] == 0xFF for seg in segs)
        assert all(seg['terminators'] == [0xFF] for seg in segs)
        assert plugin.is_stub is False
    finally:
        os.remove(tmp)


def test_mock_dx_full_segments():
    tmp = os.path.join(tempfile.gettempdir(), 'mock_zelda_dx.gb')
    _write_gb_mock(tmp, title='ZELDA', size=0x100000)
    data = bytearray(0x100000)
    data[0x134:0x144] = b'ZELDA\x00\x00\x00\x00\x00\x00AZLE\x80'
    with open(tmp, 'wb') as f:
        f.write(data)
    try:
        rom = GameBoyROM(tmp)
        plugin = ZeldaAwakeningDXPlugin()
        segs = plugin.get_text_segments(rom)
        assert len(segs) == 6
        assert plugin.is_stub is False
    finally:
        os.remove(tmp)


# ── Уровень реального ROM (skip, если нет ROM) ─────────────────────────────

@pytest.mark.rom_required
def test_real_gb_validate_and_extract():
    path = _rogue_path()
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = ZeldaAwakeningPlugin()
    segments = plugin.get_text_segments(rom)
    assert len(segments) == 7
    texts = _decode_segment(plugin, rom, segments[0])
    assert 'Golden Leaf' in texts[0]
    assert 'Guardian Acorn' in texts[2]
    # Титры: запись не обрезана на старте и не захватывает мусор в конце.
    credits = _decode_segment(plugin, rom, segments[4])
    assert len(credits) == 1
    assert 'THE  END' in credits[0]
    assert not credits[0].startswith('[IC_FA]')
    assert not credits[0].endswith(('[IC_', '[CTL_'))


@pytest.mark.rom_required
def test_real_dx_validate_and_extract():
    path = _dx_path()
    if not os.path.exists(path):
        pytest.skip('test ROM not present')
    rom = GameBoyROM(path)
    plugin = ZeldaAwakeningDXPlugin()
    segments = plugin.get_text_segments(rom)
    assert len(segments) == 6
    # Первая запись dialog_a — с начала EN-записи, а не обрезка в её середине.
    texts = _decode_segment(plugin, rom, segments[0])
    def norm(t):
        return ' '.join(t.split())
    assert any('Have you heard of the Flying Rooster' in norm(t)
               for t in texts[:3])
    # Запись "Ahhh!  It's her!" включена целиком (а не 's her!...').
    assert any("Ahhh!  It's her!" in t for t in texts)
    assert all(not m.startswith("'s her!") for m in texts)
    assert not any(t.lower().startswith('si tu vois') for t in texts)
    # Старт dialog_a — с текста записи, без захваченного кода перед ним.
    assert not texts[0].startswith(('[IC_', '[CTL_'))
    texts = _decode_segment(plugin, rom, segments[2])
    assert any('Golden Leaf' in t for t in texts)
    assert any('Full Moon Cello' in t for t in texts)
    # Энд сегментов — до французских хвостов (в этих зонах DX — En+Fr).
    assert not any('cristal bleu' in t for t in texts)
    # dialog_b / dialog_d — стартуют с текста, а не с хвоста кода
    # (раньше захватывались байты E0 DF C9 / C9 перед записями).
    for seg in (segments[1], segments[4]):
        t = _decode_segment(plugin, rom, seg)
        assert not t[0].startswith('[IC_')
        assert not t[0].startswith('[CTL_')
    # Титры DX — заканчиваются текстом 'THE END', без мусора кода после.
    credits = _decode_segment(plugin, rom, segments[3])
    assert len(credits) == 1
    assert 'THE  END' in credits[0]
    assert not credits[0].endswith('[IC_FA]')


@pytest.mark.rom_required
def test_real_gb_roundtrip():
    src = _rogue_path()
    if not os.path.exists(src):
        pytest.skip('test ROM not present')
    plugin = ZeldaAwakeningPlugin()
    with tempfile.TemporaryDirectory() as td:
        work = os.path.join(td, GB)
        shutil.copyfile(src, work)
        rom = GameBoyROM(src)
        before = TextExtractor(src, rom=rom).extract()
        injector = TextInjector(work)
        for seg in plugin.get_text_segments(rom):
            if seg['end'] > len(rom.data):
                continue
            texts = [m['text'] for m in before.get(seg['name'], [])]
            assert injector.inject_segment(seg['name'], texts, plugin)
        injector.save(work)
        after = TextExtractor(work, rom=GameBoyROM(work)).extract()
        for seg in plugin.get_text_segments(rom):
            before_texts = [m['text'] for m in before.get(seg['name'], [])]
            after_texts = [m['text'] for m in after.get(seg['name'], [])]
            assert before_texts == after_texts


@pytest.mark.rom_required
def test_real_dx_roundtrip():
    src = _dx_path()
    if not os.path.exists(src):
        pytest.skip('test ROM not present')
    plugin = ZeldaAwakeningDXPlugin()
    with tempfile.TemporaryDirectory() as td:
        work = os.path.join(td, DX)
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
