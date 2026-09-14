"""Metroid Fusion (GBA) 16-bit dialogue decoder round-trip tests.

Unit: encode(decode(raw)) == raw for synthetic and real ROM data.
Integration: manifest building, pointer_dialogues segment creation.
"""
import os
import struct

import pytest

from plugins.gba_metroid_fusion import (
    CHARMAP_METROID_FUSION,
    MetroidFusionAsciiDecoder,
    MetroidFusionDialogueDecoder,
    MetroidFusionPlugin,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM_DIR = os.path.join(BASE, 'test_roms')
MF_ROM = os.path.join(ROM_DIR, 'Metroid Fusion (USA).gba')


@pytest.fixture
def decoder():
    return MetroidFusionDialogueDecoder(CHARMAP_METROID_FUSION)


def _encode_word(word: int) -> bytes:
    return struct.pack('<H', word)


def _make_words(*words: int) -> bytes:
    return b''.join(_encode_word(w) for w in words)


# ── Unit: decode ────────────────────────────────────────────────────────────
def test_decode_plain_text(decoder):
    # "A " = 0x81 0x00 0x40 0x00
    raw = _make_words(0x81, 0x40)
    assert decoder.decode(raw, 0, len(raw)) == 'A '


def test_decode_control_word(decoder):
    # "A" + control 0xB003 + "B"
    raw = _make_words(0x81, 0xB003, 0x82)
    text = decoder.decode(raw, 0, len(raw))
    assert text.startswith('A')
    assert '[B003]' in text
    assert text.endswith('B')


def test_decode_end_terminator(decoder):
    # "A" + END(0xFF00) + "B" — should stop at END
    raw = _make_words(0x81, 0xFF00, 0x82)
    text = decoder.decode(raw, 0, len(raw))
    assert text == 'A'


def test_decode_truncated_no_end(decoder):
    # Truncated: no END, should decode what's available
    raw = _make_words(0x81, 0x82)
    text = decoder.decode(raw, 0, len(raw))
    assert text == 'AB'


def test_decode_unknown_low_byte(decoder):
    # Unknown low byte (not in charmap, not ASCII)
    raw = _make_words(0x10)  # 0x10 not in charmap
    text = decoder.decode(raw, 0, len(raw))
    assert text == '[0010]'


def test_decode_ascii_low_byte(decoder):
    # 'a' = 0x61 in ASCII range
    raw = _make_words(0x61, 0x62)
    text = decoder.decode(raw, 0, len(raw))
    assert text == 'ab'


# ── Unit: encode ────────────────────────────────────────────────────────────
def test_encode_plain_text(decoder):
    enc = decoder.encode('A')
    assert enc == _make_words(0x81)


def test_encode_control_token(decoder):
    enc = decoder.encode('[B003]B')
    assert enc == _make_words(0xB003, 0x82)


def test_encode_space(decoder):
    enc = decoder.encode(' ')
    assert enc == _make_words(0x40)


def test_encode_ascii_char(decoder):
    enc = decoder.encode('z')
    assert enc == _make_words(0xDA)


def test_encode_literal_bracket(decoder):
    # Char '[' (0x9B) decodes from ROM; literal '[' must NOT be parsed as a
    # control-code token. "A[!" round-trips (no ']' in MF charmap).
    raw = _make_words(0x81, 0x9B, 0x41)
    text = decoder.decode(raw, 0, len(raw))
    assert text == 'A[!'
    enc = decoder.encode(text)
    assert enc == raw


def test_encode_token_precedence_over_literal(decoder):
    # A proper '[XXXX]' token still takes precedence over a literal '['.
    raw = _make_words(0xB003, 0x82)
    assert decoder.encode('[B003]B') == raw


def test_encode_unknown_char_raises(decoder):
    with pytest.raises(ValueError, match='not in Metroid Fusion'):
        decoder.encode('\u00e9')  # é — not in charmap, not ASCII


# ── Unit: round-trip ────────────────────────────────────────────────────────
def test_roundtrip_plain(decoder):
    raw = _make_words(0x81, 0x82, 0x83)
    text = decoder.decode(raw, 0, len(raw))
    enc = decoder.encode(text)
    assert enc == raw


def test_roundtrip_with_control(decoder):
    raw = _make_words(0x81, 0xB003, 0x82, 0xFD00, 0x83)
    text = decoder.decode(raw, 0, len(raw))
    enc = decoder.encode(text)
    assert enc == raw


def test_roundtrip_with_unknown_token(decoder):
    raw = _make_words(0x81, 0x10, 0x82)  # 0x0010 unknown
    text = decoder.decode(raw, 0, len(raw))
    enc = decoder.encode(text)
    assert enc == raw


def test_roundtrip_mixed_all(decoder):
    raw = _make_words(0x81, 0x40, 0xB003, 0x7E, 0x10, 0xFD00, 0x82)
    text = decoder.decode(raw, 0, len(raw))
    enc = decoder.encode(text)
    assert enc == raw


# ── Integration: manifest + segment ─────────────────────────────────────────
@pytest.mark.skipif(not os.path.exists(MF_ROM), reason='MF ROM not found')
class TestMFDialogueIntegration:

    def test_manifest_structure(self):
        rom_data = open(MF_ROM, 'rb').read()
        from plugins.gba_metroid_fusion import _BASE_ADDR, _DIALOGUE_PTR_TABLE
        off = _DIALOGUE_PTR_TABLE
        raw = struct.unpack_from('<I', rom_data, off)[0]
        target = raw - _BASE_ADDR
        assert 0x6CE8B0 <= target < 0x740000, (
            f'First target 0x{target:X} outside expected range')

    def test_segments_include_dialogue(self):
        from core.rom import GameBoyROM
        rom = GameBoyROM(MF_ROM)
        plugin = MetroidFusionPlugin()
        segs = plugin.get_text_segments(rom)
        dialogue = [s for s in segs if s.get('kind') == 'pointer_dialogues']
        assert len(dialogue) == 1, 'Expected exactly one dialogue segment'
        seg = dialogue[0]
        assert seg['name'] == 'metroid_fusion_dialogue'
        assert seg['terminator'] == b'\x00\xff'
        assert seg['max_decode_len'] == 5000
        assert len(seg['manifest']) > 1000, (
            f'Expected >1000 records, got {len(seg["manifest"])}')

    def test_manifest_entries_have_required_keys(self):
        from core.rom import GameBoyROM
        rom = GameBoyROM(MF_ROM)
        plugin = MetroidFusionPlugin()
        segs = plugin.get_text_segments(rom)
        dialogue = next(s for s in segs if s.get('kind') == 'pointer_dialogues')
        for entry in dialogue['manifest']:
            assert 'target' in entry and 'free_after' in entry, (
                f'Missing keys in entry: {entry}')
            assert entry['free_after'] >= 4
            assert 0x6CE8B0 <= entry['target'] < 0x739D58

    def test_manifest_targets_in_zone(self):
        from core.rom import GameBoyROM
        rom = GameBoyROM(MF_ROM)
        plugin = MetroidFusionPlugin()
        segs = plugin.get_text_segments(rom)
        dialogue = next(s for s in segs if s.get('kind') == 'pointer_dialogues')
        targets = [e['target'] for e in dialogue['manifest']]
        # Duplicates are allowed (game references the same string from
        # multiple contexts). All must lie in the text zone.
        assert all(0x6CE8B0 <= t < 0x739D58 for t in targets)

    def test_manifest_every_entry_roundtrips(self):
        from core.rom import GameBoyROM
        rom = GameBoyROM(MF_ROM)
        plugin = MetroidFusionPlugin()
        segs = plugin.get_text_segments(rom)
        dialogue = next(s for s in segs if s.get('kind') == 'pointer_dialogues')
        data = rom.data
        bad = []
        for entry in dialogue['manifest']:
            target = entry['target']
            slot = entry['free_after']
            seg = data[target:target + slot]
            text = plugin._dialogue_decoder.decode(seg, 0, len(seg))
            reencoded = plugin._dialogue_decoder.encode(text)
            if reencoded + b'\x00\xff' != seg:
                bad.append((target, len(seg), len(reencoded)))
        assert not bad, f'Round-trip failed for {len(bad)} entries: {bad[:5]}'


@pytest.mark.skipif(not os.path.exists(MF_ROM), reason='MF ROM not found')
def test_real_rom_decode_first_entry(decoder):
    from plugins.gba_metroid_fusion import _BASE_ADDR, _DIALOGUE_PTR_TABLE
    rom_data = open(MF_ROM, 'rb').read()
    raw = struct.unpack_from('<I', rom_data, _DIALOGUE_PTR_TABLE)[0]
    target = raw - _BASE_ADDR
    # Decode first string, should be readable text
    text = decoder.decode(rom_data, target, 5000)
    assert len(text) > 5, f'First entry too short: {text!r}'
    # Must contain at least one charmap character (A-Z / a-z)
    assert any(c.isalpha() for c in text), (
        f'No alphabetic chars in first entry: {text[:80]!r}')


@pytest.mark.skipif(not os.path.exists(MF_ROM), reason='MF ROM not found')
def test_real_rom_roundtrip_first_entry(decoder):
    from plugins.gba_metroid_fusion import _BASE_ADDR, _DIALOGUE_PTR_TABLE
    rom_data = open(MF_ROM, 'rb').read()
    raw = struct.unpack_from('<I', rom_data, _DIALOGUE_PTR_TABLE)[0]
    target = raw - _BASE_ADDR
    # Read until END
    i = target
    while i + 1 < len(rom_data):
        if rom_data[i] == 0x00 and rom_data[i + 1] == 0xFF:
            break
        i += 2
    slot = i + 2 - target
    seg = rom_data[target:target + slot]
    text = decoder.decode(seg, 0, len(seg))
    reencoded = decoder.encode(text) + b'\x00\xff'
    assert reencoded == seg, (
        f'Round-trip failed for first entry at 0x{target:X}:\n'
        f' original:  {seg.hex(" ")}\n'
        f' reencoded: {reencoded.hex(" ")}\n'
        f' text:      {text[:120]!r}')


def test_ascii_decoder_keeps_s_0x53():
    dec = MetroidFusionAsciiDecoder()
    raw = b'SAMUS DESIGN\x00\x00\x00\x00\x00\x00'
    assert dec.decode(raw, 0, len(raw)) == 'SAMUS DESIGN'


def test_ascii_decoder_roundtrip():
    dec = MetroidFusionAsciiDecoder()
    for text in ('SAMUS DESIGN', 'SAMUS ORIGINAL DESIGN',
                 'SAVE_ENDMetroidEpisode4A'):
        assert dec.decode(dec.encode(text) + b'\x00', 0, len(text) + 1) == text
        assert dec.encode(text) == text.encode('ascii')


def test_ascii_decoder_hex_escape_decode():
    dec = MetroidFusionAsciiDecoder()
    raw = b'A\x82B'
    text = dec.decode(raw, 0, len(raw))
    assert '[82]' in text
    assert dec.decode(dec.encode(text), 0, len(text)) == text


@pytest.mark.skipif(not os.path.exists(MF_ROM), reason='MF ROM not found')
def test_fixed_ascii_blocks_decode_nonempty():
    from core.rom import GameBoyROM
    from plugins.gba_metroid_fusion import MetroidFusionPlugin
    rom = GameBoyROM(MF_ROM)
    plugin = MetroidFusionPlugin()
    segs = plugin.get_text_segments(rom)
    ascii_segs = [s for s in segs if s.get('kind') != 'pointer_dialogues']
    assert len(ascii_segs) == 4, (
        f'Expected 4 fixed ASCII blocks, got {len(ascii_segs)}')
    for seg in ascii_segs:
        text = seg['decoder'].decode(
            rom.data, seg['start'], seg['end'] - seg['start'])
        assert text.strip(), (
            f"Block '{seg['name']}' decoded empty (0x{seg['start']:X})")
        assert 'SAMUS' in text or 'SAVE_END' in text
