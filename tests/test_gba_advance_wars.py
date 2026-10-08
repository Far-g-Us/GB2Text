"""Advance Wars: extract/insert round-trip on synthetic ROMs."""

from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.extractor import TextExtractor
from core.injector import TextInjector
from core.plugin_manager import PluginManager
from plugins import gba_advance_wars as aw
from plugins.gba_advance_wars import AdvanceWarsPlugin, AdvanceWarsTextDecoder
from tests.test_roundtrip import _make_temp_rom

BASE = 0x08000000
TABLE = 0x1000
POOL = 0x2000


def _build_aw_rom(strings: list[bytes]) -> bytes:
    size = 0x8000
    data = bytearray(size)
    data[0x0AC:0x0B0] = b'AWRE'
    addr = POOL
    targets = []
    for s in strings:
        blob = s + b'\x00\x00\x00\x00'
        data[addr:addr + len(blob)] = blob
        targets.append(addr)
        addr += len(blob)
    for i, target in enumerate(targets):
        struct.pack_into('<I', data, TABLE + 4 * i, BASE + target)
    data[0x0BD] = (0 - sum(data[0x0A0:0x0BD]) - 0x19) & 0xFF
    return bytes(data)


def _safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture()
def synth(monkeypatch):
    strings = [b'SYNTH ALPHA MESSAGE ONE', b'SYNTH SECOND LINE HERE']
    monkeypatch.setattr(aw, 'TABLES', [(TABLE, len(strings))])
    path = _make_temp_rom(_build_aw_rom(strings), suffix='.gba')
    try:
        yield path, [s.decode('ascii') for s in strings]
    finally:
        _safe_unlink(path)


class _PM(PluginManager):
    def get_plugin(self, game_id, system=None, cancellation_token=None, rom=None):
        return AdvanceWarsPlugin()


def _extract(path):
    ext = TextExtractor(path, plugin_manager=_PM())
    results = ext.extract()
    return ext, [m['text'] for m in results['advance_wars_dialogues']]


def test_synthetic_extract(synth):
    path, strings = synth
    _, texts = _extract(path)
    assert texts == strings


def test_synthetic_identity_roundtrip(synth):
    import shutil
    import tempfile
    path, strings = synth
    ext, texts = _extract(path)
    assert texts == strings
    tmp = tempfile.mkdtemp()
    try:
        work = os.path.join(tmp, 'w.gba')
        shutil.copy(path, work)
        inj = TextInjector(work)
        assert inj.inject_segment(
            'advance_wars_dialogues', texts, ext.plugin, relocate=True) is True
        out = os.path.join(tmp, 'o.gba')
        inj.save(out)
        _, back = _extract(out)
        assert back == strings
        assert open(path, 'rb').read() == open(out, 'rb').read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_synthetic_changed_text_roundtrip(synth):
    import shutil
    import tempfile
    path, _strings = synth
    ext, texts = _extract(path)
    rev = [t[::-1] for t in texts]
    tmp = tempfile.mkdtemp()
    try:
        work = os.path.join(tmp, 'w.gba')
        shutil.copy(path, work)
        inj = TextInjector(work)
        assert inj.inject_segment(
            'advance_wars_dialogues', rev, ext.plugin, relocate=True) is True
        out = os.path.join(tmp, 'o.gba')
        inj.save(out)
        _, back = _extract(out)
        assert back == rev
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_synthetic_long_translation_relocates(synth):
    import shutil
    import tempfile
    path, _strings = synth
    ext, texts = _extract(path)
    long = [t + ' ' + t + ' ' + t for t in texts]
    tmp = tempfile.mkdtemp()
    try:
        work = os.path.join(tmp, 'w.gba')
        shutil.copy(path, work)
        inj = TextInjector(work)
        assert inj.inject_segment(
            'advance_wars_dialogues', long, ext.plugin, relocate=True) is True
        assert len(inj.last_relocate_report) > 0
        assert len(inj.last_overflow_report) == 0
        out = os.path.join(tmp, 'o.gba')
        inj.save(out)
        _, back = _extract(out)
        assert sorted(back) == sorted(long)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_synthetic_unencodable_skipped_without_corruption(synth):
    import shutil
    import tempfile
    path, _strings = synth
    ext, texts = _extract(path)
    bad = ['\u00c9DIT' + texts[0][4:], texts[1]]
    tmp = tempfile.mkdtemp()
    try:
        work = os.path.join(tmp, 'w.gba')
        shutil.copy(path, work)
        inj = TextInjector(work)
        inj.inject_segment(
            'advance_wars_dialogues', bad, ext.plugin, relocate=True)
        out = os.path.join(tmp, 'o.gba')
        inj.save(out)
        _, back = _extract(out)
        assert back[1] == texts[1]
        assert back[0] == texts[0]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_zero_rom_stays_stub(monkeypatch):
    from core.rom import GameBoyROM
    monkeypatch.setattr(aw, 'TABLES', [(TABLE, 2)])
    rom = GameBoyROM.__new__(GameBoyROM)
    rom.data = bytearray(0x8000)
    rom.header = {'game_code': 'AWRE'}
    plugin = AdvanceWarsPlugin()
    assert plugin.get_text_segments(rom) == []
    assert plugin.is_stub is True


def test_decoder_roundtrip():
    dec = AdvanceWarsTextDecoder()
    for text in ('HELLO WORLD', 'LINE ONE\rLINE TWO', 'A\nB'):
        raw = dec.encode(text)
        assert dec.decode(raw, 0, len(raw)) == text
    with pytest.raises(ValueError):
        dec.encode('\u00c9')
    assert dec.decode(b'AB\x00CD', 0, 4) == 'AB'


def test_decode_at_rejects_unterminated():
    from plugins.gba_advance_wars import _decode_at
    assert _decode_at(b'A' * 320, 0) is None
    assert _decode_at(b'AB', 0) is None
    assert _decode_at(b'\x00AB', 0) is None
    assert _decode_at(b'ABC\x00', 0) == 'ABC'
    assert _decode_at(b'ABC\x00', 99) is None


def test_entries_clamp_suffix_overlap(monkeypatch):
    from plugins.gba_advance_wars import _entries_for_rom
    size = 0x8000
    data = bytearray(size)
    outer = b'OUTER SUFFIX TEST'
    data[POOL:POOL + len(outer)] = outer
    data[POOL + len(outer)] = 0x00
    inner_target = POOL + 6
    monkeypatch.setattr(aw, 'TABLES', [(TABLE, 2)])
    struct.pack_into('<I', data, TABLE, BASE + POOL)
    struct.pack_into('<I', data, TABLE + 4, BASE + inner_target)
    entries = _entries_for_rom(bytes(data))
    assert len(entries) == 1
    assert entries[0]['target'] == inner_target
    assert entries[0]['free_after'] == 320


def test_entries_merge_slots_for_shared_target(monkeypatch):
    from plugins.gba_advance_wars import _entries_for_rom
    data = bytearray(0x8000)
    blob = b'SHARED TARGET TEXT\x00\x00\x00\x00'
    data[POOL:POOL + len(blob)] = blob
    monkeypatch.setattr(aw, 'TABLES', [(TABLE, 1), (TABLE + 0x100, 1)])
    struct.pack_into('<I', data, TABLE, BASE + POOL)
    struct.pack_into('<I', data, TABLE + 0x100, BASE + POOL)
    entries = _entries_for_rom(bytes(data))
    assert len(entries) == 1
    assert sorted(entries[0]['slots']) == [TABLE, TABLE + 0x100]


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
