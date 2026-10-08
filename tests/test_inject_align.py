"""Выравнивание extract/inject: inline [XX], trailing-игнор, диагностика (синтетика)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.decoder import CharMapDecoder
from core.extractor import TextExtractor
from core.injector import TextInjector
from tests.test_roundtrip import _build_gb_rom, _make_temp_rom

CHARMAP = {0x41: 'A', 0x42: 'B', 0x20: ' ', 0x43: 'C'}


def _extractor():
    rom_path = _make_temp_rom(_build_gb_rom())
    try:
        yield TextExtractor(rom_path)
    finally:
        os.unlink(rom_path)


def test_split_xx_inline_mid() -> None:
    for ext in _extractor():
        msgs = ext._split_messages("a[01]b", 0)
        assert [m["text"] for m in msgs] == ["a[01]b"]


def test_split_xx_edges_dropped() -> None:
    for ext in _extractor():
        assert [m["text"] for m in ext._split_messages("[01][02]ab", 0)] == ["ab"]
        assert [m["text"] for m in ext._split_messages("ab[01][02]", 0)] == ["ab"]
        assert ext._split_messages("[01][02]", 0) == []
        assert [m["text"] for m in ext._split_messages("ab[01]\ncd[02]", 0)] == ["ab", "cd"]


def test_split_end_and_newline_kept() -> None:
    for ext in _extractor():
        assert [m["text"] for m in ext._split_messages("Hello[END]World", 0)] == ["Hello", "World"]
        assert [m["text"] for m in ext._split_messages("A\nB", 0)] == ["A", "B"]


def test_strip_token_tail() -> None:
    assert TextExtractor._strip_token_tail("ab[01][FF]") == "ab"
    assert TextExtractor._strip_token_tail("[01]") == ""
    assert TextExtractor._strip_token_tail("ab") == "ab"
    assert TextExtractor._strip_token_tail("a[PAGE]") == "a[PAGE]"
    assert TextExtractor._strip_token_tail("aX12]") == "aX12]"
    assert TextExtractor._strip_token_tail("") == ""


def test_drop_junk_windows() -> None:
    rom_path = _make_temp_rom(_build_gb_rom())
    try:
        inj = TextInjector(rom_path)
        mapped, dropped = inj._drop_junk_windows([{"text": "[82]"}, {"text": "AB"}, {"text": "[03]"}])
        assert mapped is not None
        assert [w["text"] for w in mapped] == ["AB"]
        assert dropped == 2
        mapped, dropped = inj._drop_junk_windows([{"text": "   "}, {"text": "AB"}])
        assert mapped is not None
        assert len(mapped) == 2 and dropped == 0
        assert inj._drop_junk_windows([{"text": None}]) == (None, 0)
        assert inj._drop_junk_windows([]) == ([], 0)
    finally:
        os.unlink(rom_path)


class _TokenDecoder:
    """Stub: известные байты — символы, остальные — [HH] токены (1 байт)."""

    def __init__(self, charmap):
        self.charmap = charmap
        self.last_unmapped_chars: list = []

    def decode(self, data, start, length):
        out = []
        for byte in bytes(data[start:start + length]):
            if byte == 0xFF:
                break
            if byte in self.charmap:
                out.append(self.charmap[byte])
            else:
                out.append(f"[{byte:02X}]")
        return "".join(out)

    def encode(self, text):
        import re
        out = bytearray()
        rev = {v: k for k, v in self.charmap.items()}
        pos = 0
        for match in re.finditer(r"\[([0-9A-Fa-f]{2})\]", text):
            for char in text[pos:match.start()]:
                out.append(rev[char])
            out.append(int(match.group(1), 16))
            self.last_unmapped_chars.append(match.group(0))
            pos = match.end()
        for char in text[pos:]:
            out.append(rev[char])
        return bytes(out)


def _token_plugin(charmap):
    class _Plugin:
        game_id_pattern = r'^TEST'

        def get_text_segments(self, rom):
            return [{
                'name': 'seg',
                'start': 0x4000,
                'end': 0x4010,
                'decoder': _TokenDecoder(charmap),
                'compression': None,
            }]

    return _Plugin()


def test_inject_preserves_leading_controls() -> None:
    rom_data = _build_gb_rom({0x4000: b'\x01\x02AB\x00'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        plugin = _token_plugin({0x41: 'A', 0x42: 'B'})
        injector = TextInjector(rom_path)
        assert injector.inject_segment('seg', ['AB'], plugin) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4005] == b'\x01\x02AB\x00'
        dec = injector._get_segments(plugin)[0]['decoder']
        assert dec.last_unmapped_chars == []
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_preserves_trailing_controls() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\x01\x00'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_segment('seg', ['AB'], _token_plugin({0x41: 'A', 0x42: 'B'})) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4004] == b'AB\x01\x00'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_head_junk_windows() -> None:
    rom_data = _build_gb_rom({0x4000: b'\x01\x00AB\x00'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_segment('seg', ['AB'], _token_plugin({0x41: 'A', 0x42: 'B'})) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4005] == b'\x01\x00AB\x00'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_empty_translation_skips_without_wipe() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\x00CD\x00'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_segment('seg', ['AB', ''], _junk_plugin()) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4006] == b'AB\x00CD\x00'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def _fixed_token_plugin():
    class _Plugin:
        game_id_pattern = r'^TEST'

        def get_text_segments(self, rom):
            return [{
                'name': 'fixed',
                'start': 0x4000,
                'end': 0x4009,
                'decoder': _TokenDecoder({0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D'}),
                'compression': None,
                'fixed_width': 3,
                'record_count': 3,
            }]

    return _Plugin()


def test_inject_fixed_token_slots_untouched() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\xff\x01\xff\xffCD\xff'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_segment('fixed', ['AB', '[01]', 'CD'], _fixed_token_plugin()) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4009] == b'AB\xff\x01\xff\xffCD\xff'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_partial_affix_consumed() -> None:
    rom_data = _build_gb_rom({0x4000: b'\x01\x02AB\x00'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_segment('seg', ['[01]AB'], _token_plugin({0x41: 'A', 0x42: 'B'})) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4005] == b'\x01\x02AB\x00'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_affix_case_insensitive() -> None:
    rom_data = _build_gb_rom({0x4000: b'\xabCD\x00'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_segment('seg', ['[ab]CD'], _token_plugin({0x43: 'C', 0x44: 'D'})) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4004] == b'\xabCD\x00'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_dropped_mid_token_refuses() -> None:
    rom_data = _build_gb_rom({0x4000: b'A\x01B\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_segment('seg', ['AB'], _token_plugin({0x41: 'A', 0x42: 'B'})) is False
        assert open(rom_path, 'rb').read()[0x4000:0x4004] == b'A\x01B\x00'
    finally:
        os.unlink(rom_path)


def test_inject_middle_junk_window_skipped() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\x00\x01\x00CD\x00'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_segment('seg', ['AB', 'CD'], _token_plugin({0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D'})) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4008] == b'AB\x00\x01\x00CD\x00'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_trailing_empty_translations_trimmed() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_segment('seg', ['AB', ''], _junk_plugin()) is True
    finally:
        os.unlink(rom_path)


def test_inject_none_translation_refuses() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        translations: list = ['AB', None]
        assert injector.inject_segment('seg', translations, _junk_plugin()) is False
    finally:
        os.unlink(rom_path)


def test_inject_non_string_extra_no_crash() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        translations: list = ['AB', 123]
        assert injector.inject_segment('seg', translations, _junk_plugin()) is False
        assert injector.last_align_report['extra_translations'] == ['123']
    finally:
        os.unlink(rom_path)


def test_inject_duplicate_hole_refuses() -> None:
    rom_data = _build_gb_rom({0x4000: b'\x01A\x01B\x02\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        plugin = _token_plugin({0x41: 'A', 0x42: 'B'})
        assert injector.inject_segment('seg', ['[01]AB[02]'], plugin) is False
        assert open(rom_path, 'rb').read()[0x4000:0x4006] == b'\x01A\x01B\x02\x00'
    finally:
        os.unlink(rom_path)


def test_inject_pointer_none_translation() -> None:
    rom_data = _build_gb_rom({0x4000: b'Hi\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)

        class _Plugin:
            game_id_pattern = r'^TEST'

            def get_text_segments(self, rom):
                return [{
                    'name': 'dlg',
                    'kind': 'pointer_dialogues',
                    'start': 0x4000,
                    'end': 0x4010,
                    'decoder': CharMapDecoder({0x48: 'H', 0x69: 'i'}),
                    'manifest': [{'target': 0x4000, 'free_after': 8}],
                }]

        translations: list = [None]
        assert injector.inject_segment('dlg', translations, _Plugin()) is False
    finally:
        os.unlink(rom_path)


def test_inject_bank_non_string_translation(monkeypatch) -> None:
    rom_data = _build_gb_rom({0x4000: b'A\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)

        class _Plugin:
            game_id_pattern = r'^TEST'

            def get_text_segments(self, rom):
                return [{
                    'name': 'bank',
                    'start': 0x4000,
                    'end': 0x4010,
                    'decoder': CharMapDecoder({0x41: 'A'}),
                    'bank_meta': {},
                }]

        plugin = _Plugin()
        monkeypatch.setattr(TextInjector, '_extract_bank_messages',
                            lambda self, segment: [{'offset': 0, 'length': 2, 'text': 'A'}])
        translations: list = [None]
        assert injector.inject_segment('bank', translations, plugin) is False
    finally:
        os.unlink(rom_path)


def test_safe_inject_message_guards() -> None:
    rom_path = _make_temp_rom(_build_gb_rom())
    try:
        injector = TextInjector(rom_path)
        assert injector._safe_inject_message(0x4000, b'AB', 2, 0x20) is True
        assert injector._safe_inject_message(0x8000 + 100, b'AB', 2, 0x20) is False
        assert injector._safe_inject_message('x', b'AB', 2, 0x20) is False
        assert injector._safe_inject_message(0x4000, 'AB', 2, 0x20) is False
    finally:
        os.unlink(rom_path)


def test_inject_language_block_non_string() -> None:
    rom_data = _build_gb_rom({0x0100: (0x08000200).to_bytes(4, 'little'),
                              0x0200: b'Hi\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)

        class _Encoder:
            def encode(self, text):
                return text.encode('ascii')

        class _Plugin:
            game_id_pattern = r'^TEST'

            def get_pointer_table_meta(self):
                return {'table': 0x0100, 'count': 1, 'blocks': [(0, 1, 'en')]}

            def make_text_encoder(self):
                return _Encoder()

            def get_text_segments(self, rom):
                return [{'name': 'cvas_en_0', 'start': 0x0200, 'end': 0x0210}]

        plugin = _Plugin()
        translations: list = [None]
        assert injector.inject_language_block('en', translations, plugin) is False
    finally:
        os.unlink(rom_path)


def test_inject_translations_not_list_refuses() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        bad_inputs: list = ['AB', None]
        for bad in bad_inputs:
            assert injector.inject_segment('seg', bad, _junk_plugin()) is False
    finally:
        os.unlink(rom_path)


def test_inject_pointer_bad_entry_refuses() -> None:
    rom_data = _build_gb_rom({0x4000: b'Hi\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)

        class _Plugin:
            game_id_pattern = r'^TEST'

            def get_text_segments(self, rom):
                return [{
                    'name': 'dlg',
                    'kind': 'pointer_dialogues',
                    'start': 0x4000,
                    'end': 0x4010,
                    'decoder': CharMapDecoder({0x48: 'H', 0x69: 'i'}),
                    'manifest': ['oops'],
                }]

        assert injector.inject_segment('dlg', ['Hi'], _Plugin()) is False
    finally:
        os.unlink(rom_path)


def test_inject_pointer_oob_refuses() -> None:
    rom_data = _build_gb_rom({0x4000: b'Hi\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)

        class _Plugin:
            game_id_pattern = r'^TEST'

            def get_text_segments(self, rom):
                return [{
                    'name': 'dlg',
                    'kind': 'pointer_dialogues',
                    'start': 0x4000,
                    'end': 0x4010,
                    'decoder': CharMapDecoder({0x48: 'H', 0x69: 'i'}),
                    'manifest': [{'target': 0x8000 + 100, 'free_after': 8}],
                }]

        assert injector.inject_segment('dlg', ['Hi'], _Plugin()) is False
    finally:
        os.unlink(rom_path)


def test_inject_fixed_token_slot_rename() -> None:
    rom_data = _build_gb_rom({0x4000: b'\x65\xff\xff'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        plugin = _fixed_token_plugin()
        injector = TextInjector(rom_path)
        assert injector.inject_segment('fixed', ['[65]', 'AB', 'CD'], plugin) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4009] == b'\x65\xff\xffAB\xffCD\xff'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_reordered_tokens_refuses() -> None:
    rom_data = _build_gb_rom({0x4000: b'A\x01B\x02C\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        plugin = _token_plugin({0x41: 'A', 0x42: 'B', 0x43: 'C'})
        assert injector.inject_segment('seg', ['A[02]B[01]C'], plugin) is False
        assert open(rom_path, 'rb').read()[0x4000:0x4006] == b'A\x01B\x02C\x00'
    finally:
        os.unlink(rom_path)


def test_inject_trailing_trim_strict_refuses() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_segment('seg', ['AB', ''], _junk_plugin(), skip_long=False) is False
    finally:
        os.unlink(rom_path)


def test_inject_fixed_mid_token_drop_is_explicit() -> None:
    rom_data = _build_gb_rom({0x4000: b'A\x01BCD\xff'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        plugin = _fixed_token_plugin()
        injector = TextInjector(rom_path)
        assert injector.inject_segment('fixed', ['AB', 'CD', '[00][00][00]'], plugin) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4009] == b'AB\xffCD\xff\x00\x00\x00'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_content_on_junk_window_refuses() -> None:
    rom_data = _build_gb_rom({0x4000: b'\x01\x00AB\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        ok = injector.inject_segment('seg', ['AB', 'CD'], _token_plugin({0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D'}))
        assert ok is False
        assert injector.last_align_report['segment'] == 'seg'
    finally:
        os.unlink(rom_path)


def test_inject_more_translations_than_windows() -> None:
    rom_data = _build_gb_rom({0x4000: b'A\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        ok = injector.inject_segment('seg', ['A', 'B'], _junk_plugin())
        assert ok is False
        assert injector.last_align_report['extra_translations'] == ['B']
        assert injector.last_align_report['extra'] == []
    finally:
        os.unlink(rom_path)


def test_inject_empty_translations_nonempty_windows() -> None:
    rom_data = _build_gb_rom({0x4000: b'A\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_segment('seg', [], _junk_plugin()) is False
        assert injector.last_align_report['translations'] == 0
        assert injector.last_align_report['windows'] == 1
    finally:
        os.unlink(rom_path)


def _junk_plugin():
    class _Plugin:
        game_id_pattern = r'^TEST'

        def get_text_segments(self, rom):
            return [{
                'name': 'seg',
                'start': 0x4000,
                'end': 0x4010,
                'decoder': CharMapDecoder(CHARMAP),
                'compression': None,
            }]

    return _Plugin()


def test_inject_trailing_junk_windows() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\x00\x01\x02'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        injector = TextInjector(rom_path)
        ok = injector.inject_segment('seg', ['AB'], _junk_plugin())
        assert ok is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4005] == b'AB\x00\x01\x02'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_content_extra_refuses_with_report() -> None:
    rom_data = _build_gb_rom({0x4000: b'A\x00BC'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        ok = injector.inject_segment('seg', ['A'], _junk_plugin())
        assert ok is False
        report = injector.last_align_report
        assert report['segment'] == 'seg'
        assert report['translations'] == 1
        assert report['windows'] == 2
        assert report['extra'] == ['BC']
    finally:
        os.unlink(rom_path)


def test_inject_malformed_segments_refuses() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)
        bad_segments: list = [[None], 'nope']
        for bad in bad_segments:
            assert injector.inject_segment('seg', ['AB'], _junk_plugin(), segments=bad) is False
        bad_windows = injector._extract_original_messages({'start': 'x', 'end': 0x4010, 'decoder': None})
        assert bad_windows == []
    finally:
        os.unlink(rom_path)


def test_inject_language_block_guards() -> None:
    rom_data = _build_gb_rom({0x0100: (0x08000200).to_bytes(4, 'little'),
                              0x0200: b'Hi\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)

        class _Encoder:
            def encode(self, text):
                return text.encode('ascii')

        class _Plugin:
            game_id_pattern = r'^TEST'

            def __init__(self, blocks):
                self._blocks = blocks

            def get_pointer_table_meta(self):
                return {'table': 0x0100, 'count': 1, 'blocks': self._blocks}

            def make_text_encoder(self):
                return _Encoder()

            def get_text_segments(self, rom):
                return [{'name': 'cvas_en_0', 'lang': 'en', 'start': 0x0200, 'end': 0x0210}]

        bad_texts: list = [None]
        assert injector.inject_language_block('en', bad_texts, _Plugin([(0, 1, 'en')])) is False
        assert injector.inject_language_block('en', ['Hi'], _Plugin([None])) is False
        assert injector.inject_language_block('en', ['Hi'], _Plugin([(0, 1, 'en')])) is True
    finally:
        os.unlink(rom_path)


def test_inject_translations_routes_record_to_block() -> None:
    rom_data = _build_gb_rom({0x0100: (0x08000200).to_bytes(4, 'little'),
                              0x0200: b'Hi\x00'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        injector = TextInjector(rom_path)

        class _Encoder:
            def encode(self, text):
                return text.encode('ascii')

        class _Plugin:
            game_id_pattern = r'^TEST'

            def get_pointer_table_meta(self):
                return {'table': 0x0100, 'count': 1, 'blocks': [(0, 1, 'xx')]}

            def make_text_encoder(self):
                return _Encoder()

            def get_text_segments(self, rom):
                return [{'name': 'rec_xx_0', 'kind': 'record', 'lang': 'xx',
                         'start': 0x0200, 'end': 0x0210, 'raw_text': 'Hi'}]

        plugin = _Plugin()
        segs = plugin.get_text_segments(None)
        results = {'rec_xx_0': [{'text': 'Hi'}]}
        assert injector.inject_translations('rec_xx_0', ['Yo'], plugin,
                                            segments=segs, results=results) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x0202:0x0204] == b'Yo'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_translations_record_needs_sibling_text() -> None:
    rom_data = _build_gb_rom({0x0100: (0x08000200).to_bytes(4, 'little')})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)

        class _Plugin:
            game_id_pattern = r'^TEST'

            def get_pointer_table_meta(self):
                return {'table': 0x0100, 'count': 1, 'blocks': [(0, 1, 'xx')]}

            def get_text_segments(self, rom):
                return [{'name': 'rec_xx_0', 'kind': 'record', 'lang': 'xx',
                         'start': 0x0200, 'end': 0x0210},
                        {'name': 'rec_xx_1', 'kind': 'record', 'lang': 'xx',
                         'start': 0x0210, 'end': 0x0220}]

        plugin = _Plugin()
        segs = plugin.get_text_segments(None)
        assert injector.inject_translations('rec_xx_0', ['Yo'], plugin,
                                            segments=segs, results=None) is False
    finally:
        os.unlink(rom_path)


def test_inject_translations_plain_segment_legacy() -> None:
    rom_data = _build_gb_rom({0x4000: b'AB\x00'})
    rom_path = _make_temp_rom(rom_data)
    out_path = rom_path + ".out.gbc"
    try:
        injector = TextInjector(rom_path)
        assert injector.inject_translations('seg', ['AB'], _junk_plugin()) is True
        injector.save(out_path)
        assert open(out_path, 'rb').read()[0x4000:0x4002] == b'AB'
    finally:
        for p in (rom_path, out_path):
            if os.path.exists(p):
                os.unlink(p)


def test_inject_pointer_missing_target_refuses() -> None:
    rom_data = _build_gb_rom({0x4000: b'Hi\x00'})
    rom_path = _make_temp_rom(rom_data)
    try:
        injector = TextInjector(rom_path)

        class _Plugin:
            game_id_pattern = r'^TEST'

            def get_text_segments(self, rom):
                return [{
                    'name': 'dlg',
                    'kind': 'pointer_dialogues',
                    'start': 0x4000,
                    'end': 0x4010,
                    'decoder': CharMapDecoder({0x48: 'H', 0x69: 'i'}),
                    'manifest': [{'free_after': 8}],
                }]

        assert injector.inject_segment('dlg', ['Hi'], _Plugin()) is False
    finally:
        os.unlink(rom_path)
