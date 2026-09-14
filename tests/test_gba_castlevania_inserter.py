"""Тесты вставки (encode + релокация) Castlevania: Aria of Sorrow"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.injector import TextInjector
from core.pointer_table import assemble_block, find_free_space, patch_pointer_range
from core.rom import GameBoyROM
from plugins.gba_castlevania import (
    CHARMAP_CVAS,
    CastlevaniaGBAPlugin,
    CVASTextDecoder,
)

ROM_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'test_roms',
    'Castlevania - Aria of Sorrow (USA).gba',
)


@pytest.fixture(scope="module")
def cvas_rom() -> GameBoyROM:
    if not os.path.exists(ROM_PATH):
        pytest.skip("Отсутствует test_roms/Castlevania - Aria of Sorrow (USA).gba")
    return GameBoyROM(ROM_PATH)


@pytest.fixture(scope="module")
def plugin() -> CastlevaniaGBAPlugin:
    return CastlevaniaGBAPlugin()


@pytest.fixture(scope="module")
def segments(plugin, cvas_rom):
    return plugin.get_text_segments(cvas_rom)


def _lang(seg: dict) -> str:
    name = seg['name']
    return str(name).removeprefix('cvas_').rsplit('_', 1)[0]


def _lang_texts(segments, lang: str) -> list[str]:
    return [s['raw_text'] for s in segments if _lang(s) == lang]


class TestCVASTextEncoder:
    def test_encoder_basic(self, plugin):
        enc = plugin.make_text_encoder()
        assert enc.encode('[PAGE][SOMA]A') == b'\x01\x00\x07\x01A'
        assert enc.encode('[PAGE]A\nB') == b'\x01\x00' + b'A' + b'\x06' + b'B'
        assert enc.encode('[PAGEBREAK]X') == b'\x01X'

    def test_encoder_raw_byte_notation(self, plugin):
        enc = plugin.make_text_encoder()
        assert enc.encode('#[13] while') == b'#' + b'\x13' + b' while'
        assert enc.encode('[0701]') == b'\x07\x01'

    def test_encoder_rejects_bad_tokens(self, plugin):
        enc = plugin.make_text_encoder()
        with pytest.raises(ValueError):
            enc.encode('[00]')
        with pytest.raises(ValueError):
            enc.encode('[0003]')
        with pytest.raises(ValueError):
            enc.encode('Сомā')

    def test_encoder_extended_latin(self, plugin):
        enc = plugin.make_text_encoder()
        assert enc.encode('Œ') == b'\x90'
        assert enc.encode('é') == b'\xe9'

    def test_encoder_preserves_literal_brackets(self, plugin):
        enc = plugin.make_text_encoder()
        assert enc.encode('Hello [you]!') == b'Hello [you]!'


class TestCVASRoundTrip:
    def test_text_roundtrip_all_records(self, plugin, segments):
        enc = plugin.make_text_encoder()
        dec = CVASTextDecoder(CHARMAP_CVAS)
        for seg in segments:
            assert dec.decode(enc.encode(seg['raw_text']), 0, 10**6) == seg['raw_text']

    def test_byte_lengths_all_records(self, plugin, segments, cvas_rom):
        enc = plugin.make_text_encoder()
        for seg in segments:
            raw = cvas_rom.data[seg['start']:seg['end']]
            assert len(enc.encode(seg['raw_text'])) == len(raw)

    def test_byte_roundtrip_no_newline(self, plugin):
        enc = plugin.make_text_encoder()
        dec = CVASTextDecoder(CHARMAP_CVAS)
        raw = b'\x01\x00\x03\x00\x07\x01Hello.'
        assert enc.encode(dec.decode(raw, 0, len(raw))) == raw

    def test_pagebreak_byte_roundtrip(self, plugin):
        """Inline одиночный 0x01 (разрыв страницы) без 0x00 — байт-в-байт."""
        enc = plugin.make_text_encoder()
        dec = CVASTextDecoder(CHARMAP_CVAS)
        raw = b'\x01\x00\x03\x00\x07\x01First\x01\x02Second\x01Third'
        assert enc.encode(dec.decode(raw, 0, len(raw))) == raw


class TestCVASInject:
    def test_inject_en_block_roundtrip(self, plugin, segments, cvas_rom):
        texts = _lang_texts(segments, 'en')
        injector = TextInjector(ROM_PATH)
        assert injector.inject_language_block('en', texts, plugin, segments=segments)
        patched = cvas_rom.__class__(ROM_PATH)
        patched.data = bytes(injector.modified_data)
        re = _lang_texts(plugin.get_text_segments(patched), 'en')
        assert re == texts
        diffs = [
            i for i in range(2895)
            if injector.modified_data[0x506B38 + 4 * i:0x506B38 + 4 * i + 4]
            != injector.original_data[0x506B38 + 4 * i:0x506B38 + 4 * i + 4]
        ]
        assert diffs and all(40 <= i < 1013 for i in diffs)
        assert injector.modified_data[0x1001B8:0x110004] == injector.original_data[0x1001B8:0x110004]
        assert injector.modified_data[0x0EA72C:0x0F01C4] == injector.original_data[0x0EA72C:0x0F01C4]

    def test_inject_en_ui_block_roundtrip(self, plugin, segments, cvas_rom):
        texts = _lang_texts(segments, 'en_ui')
        injector = TextInjector(ROM_PATH)
        assert injector.inject_language_block('en_ui', texts, plugin, segments=segments)
        patched = cvas_rom.__class__(ROM_PATH)
        patched.data = bytes(injector.modified_data)
        re = _lang_texts(plugin.get_text_segments(patched), 'en_ui')
        assert re == texts
        assert injector.modified_data[0x0F01C4:0x1001B8] == injector.original_data[0x0F01C4:0x1001B8]

    def test_inject_relocates_on_overflow(self, plugin, segments, cvas_rom):
        texts = _lang_texts(segments, 'en_ui')
        texts = [texts[0] + '[PAGEBREAK]' + 'X' * 30000, *texts[1:]]
        injector = TextInjector(ROM_PATH)
        assert injector.inject_language_block('en_ui', texts, plugin, segments=segments)
        patched = cvas_rom.__class__(ROM_PATH)
        patched.data = bytes(injector.modified_data)
        re = _lang_texts(plugin.get_text_segments(patched), 'en_ui')
        assert re == texts
        assert injector.modified_data[0x0EA72C:0x0F01C4] == b'\x00' * (0x0F01C4 - 0x0EA72C)
        assert injector.modified_data[0x0F01C4:0x110004] == injector.original_data[0x0F01C4:0x110004]

    def test_inject_multiple_blocks_same_instance_no_overlap(self, plugin, segments, cvas_rom):
        """Повторная релокация в одном инстансе: find_free_space должен видеть
        уже записанные данные (modified_data), иначе вторая релокация перезапишет первую."""
        en_ui = _lang_texts(segments, 'en_ui')
        en = _lang_texts(segments, 'en')
        ui_long = [en_ui[0] + '[PAGEBREAK]' + 'X' * 30000, *en_ui[1:]]
        en_long = [en[0] + '[PAGEBREAK]' + 'Y' * 40000, *en[1:]]
        injector = TextInjector(ROM_PATH)
        assert injector.inject_language_block('en_ui', ui_long, plugin, segments=segments)
        assert injector.inject_language_block('en', en_long, plugin, segments=segments)
        patched = cvas_rom.__class__(ROM_PATH)
        patched.data = bytes(injector.modified_data)
        re_ui = _lang_texts(plugin.get_text_segments(patched), 'en_ui')
        re_en = _lang_texts(plugin.get_text_segments(patched), 'en')
        assert re_ui == ui_long
        assert re_en == en_long

    def test_inject_count_mismatch_false(self, plugin, segments):
        injector = TextInjector(ROM_PATH)
        assert injector.inject_language_block('en', ['[PAGE]x'], plugin, segments=segments) is False
        assert injector.modified_data == injector.original_data

    def test_inject_unknown_lang_false(self, plugin, segments):
        injector = TextInjector(ROM_PATH)
        assert injector.inject_language_block('ja', [], plugin, segments=segments) is False

    def test_inject_unencodable_text_false(self, plugin, segments):
        texts = _lang_texts(segments, 'en')
        texts = ['[PAGE]Сомā', *texts[1:]]
        injector = TextInjector(ROM_PATH)
        assert injector.inject_language_block('en', texts, plugin, segments=segments) is False
        assert injector.modified_data == injector.original_data


class TestPointerTable:
    def test_assemble_block(self):
        assert assemble_block([b'A', b'B']) == b'A\x00\x00B\x00\x00'

    def test_find_free_space_empty(self):
        data = bytearray(b'\xff\xff\xff')
        assert find_free_space(data, 3) is None
        assert find_free_space(data, 1) is None

    def test_find_free_space_basic(self):
        data = bytearray(b'\x01\x00\x00\x00\x02\x00')
        assert find_free_space(data, 3) == 1
        assert find_free_space(data, 4) is None

    def test_find_free_space_excluded(self):
        data = bytearray(b'\x00\x00\x01\x00\x00\x00')
        assert find_free_space(data, 3) == 3
        assert find_free_space(data, 3, [(0, 2)]) == 3
        assert find_free_space(data, 3, [(3, 5)]) is None
        assert find_free_space(data, 2) == 0

    def test_patch_pointer_range(self):
        data = bytearray(16)
        patch_pointer_range(data, 0, 0, 2, [0x1234, 0x5678])
        assert data[0:4] == (0x1234 + 0x08000000).to_bytes(4, 'little')
        assert data[4:8] == (0x5678 + 0x08000000).to_bytes(4, 'little')
