"""Wario Land 4 (GBA) decoder + segment round-trip tests.

Unit: decode/encode round-trip for synthetic records.
Integration: 80 known locations (no scan garbage), every window decodes to
readable EN text, extract->inject->re-extract is text-identical.
"""
import os

import pytest

from plugins.gba_wario_land_4 import (
    CHARMAP_WL4,
    WL4_TEXT_LOCATIONS,
    WarioLand4Plugin,
    WL4TextDecoder,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM_DIR = os.path.join(BASE, 'test_roms')
WL4_ROM = os.path.join(ROM_DIR, 'Wario Land 4 (USA, Europe).gba')


@pytest.fixture
def decoder():
    return WL4TextDecoder(CHARMAP_WL4)


# ── Unit: decode ────────────────────────────────────────────────────────────
def test_decode_letters_spaces(decoder):
    # "Mini-Game Shop" using known bytes (0x16='M' 0x2C='i' ... 0xF2='-')
    raw = bytes([
        0x16, 0x2C, 0x31, 0x2C, 0xF2, 0x10, 0x24, 0x30, 0x28,
        0xFF, 0x1C, 0x2B, 0x32, 0x33,
    ])
    assert decoder.decode(raw, 0, len(raw)) == 'Mini-Game Shop'


def test_decode_digit_zero_is_not_terminator(decoder):
    # "40 Below Fridge": 0x04='4', 0x00='0', 0xFF=' '
    raw = bytes([0x04, 0x00, 0xFF, 0x0B, 0x28, 0x2F, 0x32, 0x3A])
    assert decoder.decode(raw, 0, len(raw)) == '40 Below'


def test_decode_punctuation(decoder):
    # "Welcome back!" 0xFF=' ', 0xE7='!'
    raw = bytes([0x20, 0x28, 0x2F, 0x26, 0x32, 0x30, 0x28, 0xFF,
                 0x25, 0x24, 0x26, 0x2E, 0xE7])
    assert decoder.decode(raw, 0, len(raw)) == 'Welcome back!'


def test_decode_stops_at_foreign_byte(decoder):
    # "Entry Passage" then 0x5F (foreign block byte, not in charmap);
    # trailing 0xFF spaces are part of the record and decode to spaces.
    raw = bytes([0x0E, 0x31, 0x37, 0x35, 0x3C, 0xFF,
                 0x19, 0x24, 0x36, 0x36, 0x24, 0x2A, 0x28,
                 0xFF, 0xFF, 0x5F, 0x85, 0x67])
    assert decoder.decode(raw, 0, len(raw)) == 'Entry Passage  '


def test_decode_lowercase_digit_mix(decoder):
    # "Win medals in mini-games." digits only not present, use '.'=0x3E
    raw = bytes([0x20, 0x2C, 0x31, 0xFF, 0x30, 0x28, 0x27, 0x24, 0x2F, 0x36,
                 0xFF, 0x2C, 0x31, 0xFF, 0x30, 0x2C, 0x31, 0x2C, 0xF2,
                 0x2A, 0x24, 0x30, 0x28, 0x36, 0x3E])
    assert decoder.decode(raw, 0, len(raw)) == 'Win medals in mini-games.'


# ── Unit: encode ────────────────────────────────────────────────────────────
def test_encode_plain_text(decoder):
    enc = decoder.encode('ABC')
    assert enc == bytes([0x0A, 0x0B, 0x0C])


def test_encode_space(decoder):
    assert decoder.encode(' ') == bytes([0xFF])


def test_encode_digit_zero(decoder):
    assert decoder.encode('0') == bytes([0x00])


def test_encode_punctuation(decoder):
    assert decoder.encode('!') == bytes([0xE7])
    assert decoder.encode('?') == bytes([0xE8])


def test_encode_ellipsis_uses_multi_char_byte(decoder):
    assert decoder.encode('...') == bytes([0xE6])


def test_encode_ambiguous_dash_roundtrip(decoder):
    # Both 0xE4 and 0xF2 decode to '-'; encode(dash) round-trips via 0xE4
    for byte in (0xE4, 0xF2):
        text = decoder.decode(bytes([byte]), 0, 1)
        assert text == '-'
        assert decoder.decode(decoder.encode(text), 0, 1) == '-'


def test_encode_unknown_char_raises(decoder):
    with pytest.raises(ValueError, match='not in the WL4 charmap'):
        decoder.encode('\u00e9')  # é


def test_encode_uppercase_lowercase(decoder):
    enc = decoder.encode('AaBb')
    assert enc == bytes([0x0A, 0x24, 0x0B, 0x25])


# ── Unit: round-trip ────────────────────────────────────────────────────────
def test_roundtrip_record(decoder):
    raw = bytes([0x16, 0x2C, 0x31, 0x2C, 0xF2, 0x10, 0x24, 0x30, 0x28,
                 0xFF, 0x1C, 0x2B, 0x32, 0x33])
    text = decoder.decode(raw, 0, len(raw))
    enc = decoder.encode(text)
    assert decoder.decode(enc, 0, len(enc)) == text


def test_roundtrip_with_ellipsis(decoder):
    raw = bytes([0x18, 0x2B, 0x28, 0xE6])
    text = decoder.decode(raw, 0, len(raw))
    assert text == 'Ohe...'
    assert decoder.decode(decoder.encode(text), 0, 5) == 'Ohe...'


# ── Integration: segments ───────────────────────────────────────────────────
@pytest.mark.skipif(not os.path.exists(WL4_ROM), reason='WL4 ROM not found')
class TestWL4Integration:

    @pytest.fixture
    def plugin(self):
        from core.rom import GameBoyROM
        rom = GameBoyROM(WL4_ROM)
        return WarioLand4Plugin(), rom

    def test_segments_only_known_locations(self, plugin):
        plug, rom = plugin
        segs = plug.get_text_segments(rom)
        assert len(segs) == len(WL4_TEXT_LOCATIONS), (
            f'Expected {len(WL4_TEXT_LOCATIONS)} segments, got {len(segs)}')
        assert not [s for s in segs if s['name'].startswith('wl4_scan')], (
            'Scan segments must be removed (they were garbage)')

    def test_every_segment_is_single_record_fixed_width(self, plugin):
        plug, rom = plugin
        for s in plug.get_text_segments(rom):
            assert s['fixed_width'] == s['end'] - s['start'], s['name']
            assert s['record_count'] == 1, s['name']
            assert s['max_length'] == s['fixed_width'], s['name']
            assert s['pad_byte'] == 0xFF, s['name']
            assert s['terminators'] == [], s['name']

    def test_every_segment_decodes_clean_en(self, plugin):
        plug, rom = plugin
        bad = []
        for s in plug.get_text_segments(rom):
            data = rom.data[s['start']:s['end']]
            text = s['decoder'].decode(data, 0, len(data))
            alpha = sum(1 for c in text if c.isalpha())
            if len(text) < 3 or alpha < max(3, int(len(text) * 0.4)):
                bad.append((s['name'], text))
        assert not bad, f'Unreadable EN windows: {bad[:5]}'

    def test_corrected_offsets(self, plugin):
        plug, rom = plugin
        segs = {s['name']: s for s in plug.get_text_segments(rom)}
        want = {
            'wl4_want_to_play_more': 0x6F496E,
            'wl4_hall_hieroglyphs': 0x65CEE1,
            'wl4_sound_room': 0x64C8B2,
        }
        for name, off in want.items():
            assert segs[name]['start'] == off, name

    def test_mini_game_shop_offsets(self, plugin):
        plug, rom = plugin
        segs = {s['name']: s for s in plug.get_text_segments(rom)}
        want = {
            'wl4_mini_game_shop': 0x65CF4C,
            'wl4_mini_game_shop_2': 0x65D084,
            'wl4_mini_game_shop_3': 0x65D1BC,
            'wl4_mini_game_shop_4': 0x65D2F4,
            'wl4_mini_game_shop_5': 0x65D42C,
            'wl4_mini_game_shop_6': 0x65D4C8,
        }
        for name, off in want.items():
            assert segs[name]['start'] == off, name
            text = segs[name]['decoder'].decode(
                rom.data, segs[name]['start'], segs[name]['end'] - segs[name]['start'])
            assert text == 'Mini-Game Shop', f'{name}: {text!r}'

    def test_no_window_touches_next_record(self, plugin):
        from itertools import pairwise
        plug, rom = plugin
        segs = sorted(plug.get_text_segments(rom), key=lambda s: s['start'])
        for a, b in pairwise(segs):
            assert a['end'] <= b['start'], (
                f'{a["name"]} window overlaps {b["name"]}')
            assert a['end'] - a['start'] > 0, a['name']

    def test_roundtrip_inject_re_extract(self, plugin):
        import shutil
        import tempfile
        plug, rom = plugin
        segs = plug.get_text_segments(rom)

        texts = [
            s['decoder'].decode(rom.data, s['start'], s['end'] - s['start'])
            for s in segs
        ]

        fd, work = tempfile.mkstemp(suffix='.gba', prefix='wl4_rt_')
        os.close(fd)
        shutil.copy(WL4_ROM, work)

        from core.injector import TextInjector
        inj = TextInjector(work)
        injected = 0
        for s, t in zip(segs, texts, strict=True):
            if inj.inject_segment(s['name'], [t], plug,
                                  skip_long=True, segments=segs):
                injected += 1
        assert injected == len(segs), (
            f'Injected {injected}/{len(segs)} segments')
        inj.save(work)

        from core.rom import GameBoyROM
        rom2 = GameBoyROM(work)
        segs2 = plug.get_text_segments(rom2)
        mismatches = []
        for s, t in zip(segs2, texts, strict=True):
            t2 = s['decoder'].decode(rom2.data, s['start'], s['end'] - s['start'])
            if t2 != t:
                mismatches.append((s['name'], t, t2))
        try:
            os.remove(work)
        except OSError:
            pass
        assert not mismatches, (
            f'Round-trip text mismatch in {len(mismatches)} segments: '
            f'{mismatches[:5]}')

    def test_bytes_outside_windows_untouched(self, plugin):
        import shutil
        import tempfile
        plug, rom = plugin
        segs = plug.get_text_segments(rom)
        windows = [(s['start'], s['end']) for s in segs]

        fd, work = tempfile.mkstemp(suffix='.gba', prefix='wl4_diff_')
        os.close(fd)
        shutil.copy(WL4_ROM, work)

        from core.injector import TextInjector
        inj = TextInjector(work)
        texts = [
            s['decoder'].decode(rom.data, s['start'], s['end'] - s['start'])
            for s in segs
        ]
        for s, t in zip(segs, texts, strict=True):
            inj.inject_segment(s['name'], [t], plug,
                               skip_long=True, segments=segs)
        inj.save(work)

        rom2_data = open(work, 'rb').read()
        try:
            os.remove(work)
        except OSError:
            pass

        orig = bytes(rom.data)
        patched = bytes(rom2_data)
        outside_diffs = [
            i for i in range(len(orig))
            if orig[i] != patched[i]
            and not any(s <= i < e for s, e in windows)
        ]
        assert not outside_diffs, (
            f'Bytes changed outside EN windows at offsets: '
            f'{outside_diffs[:10]}')
