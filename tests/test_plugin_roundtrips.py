"""Plugin round-trip fixes: FF5 aliases, GS credits codec, FFTA forms, record kind."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict

from core.decoder import CharMapDecoder
from core.extractor import TextExtractor
from core.injector import TextInjector
from plugins import gba_ff5_advance as ff5
from plugins.gba_fft_advance import FFTATextDecoder
from tests.test_roundtrip import _build_gb_rom, _make_temp_rom


def test_ff5_no_single_double_aliases() -> None:
    by_char: dict[str, list[int]] = defaultdict(list)
    for code, char in ff5.CHARMAP_FF5.items():
        by_char[char].append(code)
    bad = {char: codes for char, codes in by_char.items()
           if len(codes) > 1 and any(c < 0x100 for c in codes)
           and not any(c in ff5.FF5_CONTROL_CODES for c in codes)}
    assert bad == {}


def test_ff5_alias_roundtrip() -> None:
    dec = ff5.FF5TextDecoder(ff5.CHARMAP_FF5)
    assert dec.decode(bytes([0xC3, 0x87]), 0, 2) == '[C387]'
    assert dec.encode('[C387]') == bytes([0xC3, 0x87])


def test_ffta_force_multi_default_off() -> None:
    assert FFTATextDecoder().force_multi is False
    assert FFTATextDecoder(force_multi=True).force_multi is True


def test_ffta_multi_form_reproduced() -> None:
    dec = FFTATextDecoder(force_multi=True)
    raw = bytes([0x80, 0xC4, 0x80, 0xD5])
    text = dec.decode(raw, 0, len(raw))
    assert dec.encode(text) == raw


def test_gs_credits_ascii_codec() -> None:
    from plugins.gba_golden_sun import _ASCII_CHARMAP
    dec = CharMapDecoder(dict(_ASCII_CHARMAP))
    assert dec.encode('Staff Coordination') == b'Staff Coordination'
    assert dec.decode(b'Staff Coordination', 0, 18) == 'Staff Coordination'


def test_record_kind_no_split() -> None:
    rom_path = _make_temp_rom(_build_gb_rom({0x4000: b'AB\x00'}))
    try:
        ext = TextExtractor(rom_path)

        class _Plugin:
            game_id_pattern = r'^TEST'

            def get_text_segments(self, rom):
                return [{
                    'name': 'rec',
                    'start': 0x4000,
                    'end': 0x4010,
                    'decoder': CharMapDecoder({0x41: 'A', 0x42: 'B'}),
                    'kind': 'record',
                    'lang': 'xx',
                    'raw_text': 'A\nB\nC',
                }]

        from core.plugin_manager import PluginManager

        class _PM(PluginManager):
            def get_plugin(self, game_id, system=None, cancellation_token=None, rom=None):
                return _Plugin()

        ext = TextExtractor(rom_path, plugin_manager=_PM())
        results = ext.extract()
        assert [m['text'] for m in results['rec']] == ['A\nB\nC']
    finally:
        os.unlink(rom_path)


def test_inject_translations_unknown_kind_falls_back() -> None:
    rom_path = _make_temp_rom(_build_gb_rom({0x4000: b'AB\x00'}))
    try:
        injector = TextInjector(rom_path)

        class _Plugin:
            game_id_pattern = r'^TEST'

            def get_text_segments(self, rom):
                return [{
                    'name': 'seg',
                    'start': 0x4000,
                    'end': 0x4010,
                    'decoder': CharMapDecoder({0x41: 'A', 0x42: 'B'}),
                }]

        assert injector.inject_translations('seg', ['AB'], _Plugin()) is True
        assert injector.inject_translations('missing', ['AB'], _Plugin()) is False
    finally:
        os.unlink(rom_path)
