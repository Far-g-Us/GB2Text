"""Тесты вставки (encode + релокация) Mario & Luigi: Superstar Saga"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.injector import TextInjector
from core.pointer_table import find_free_space
from core.rom import GameBoyROM
from plugins.gba_mario_luigi_ss import (
    MLSS_ENTRIES,
    MLSS_POINTER_TABLE,
    MarioLuigiSSPlugin,
)

ROM_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'test_roms',
    'Mario & Luigi - Superstar Saga (USA).gba',
)


@pytest.fixture(scope="module")
def mlss_rom() -> GameBoyROM:
    if not os.path.exists(ROM_PATH):
        pytest.skip("Отсутствует test_roms/Mario & Luigi - Superstar Saga (USA).gba")
    return GameBoyROM(ROM_PATH)


@pytest.fixture(scope="module")
def plugin() -> MarioLuigiSSPlugin:
    return MarioLuigiSSPlugin()


@pytest.fixture(scope="module")
def segments(plugin, mlss_rom):
    return plugin.get_text_segments(mlss_rom)


def _lang_segments(segments, lang: str) -> list[dict]:
    return [s for s in segments if s.get('lang') == lang]


def _lang_texts(segments, lang: str) -> list[str]:
    segs = sorted(_lang_segments(segments, lang), key=lambda s: s.get('index', 0))
    return [s['raw_text'] for s in segs]


class TestMLSSTextEncoder:
    def test_encoder_basic(self, plugin):
        enc = plugin.make_text_encoder()
        assert enc.encode('AB') == b'AB'
        assert enc.encode('[FF 0B]') == b'\xFF\x0B'
        assert enc.encode('[FF 0A 00]') == b'\xFF\x0A\x00'

    def test_encoder_glyph_and_ff(self, plugin):
        enc = plugin.make_text_encoder()
        assert enc.encode('[G:18][G:19]Hi') == b'\x18\x19Hi'
        assert enc.encode('a[FF 2B]b') == b'a\xFF\x2Bb'

    def test_encoder_rejects_bad_tokens(self, plugin):
        enc = plugin.make_text_encoder()
        with pytest.raises(ValueError):
            enc.encode('[QX]')
        with pytest.raises(ValueError):
            enc.encode('Сомā')


class TestMLSSRoundTrip:
    def test_text_roundtrip_all_injectable(self, plugin, segments):
        enc = plugin.make_text_encoder()
        dec = plugin._decoder
        checked = 0
        for s in segments:
            if not s.get('injectable'):
                continue
            checked += 1
            assert dec.decode(enc.encode(s['raw_text']), 0, 10 ** 6) == s['raw_text']
        assert checked > 5000

    def test_byte_roundtrip_identity(self, plugin, mlss_rom, segments):
        enc = plugin.make_text_encoder()
        for s in segments:
            if not s.get('injectable'):
                continue
            raw = mlss_rom.data[s['start']:s['end']]
            assert enc.encode(s['raw_text']) == raw

    def test_catalog_records_marked_non_injectable(self, segments):
        en = _lang_segments(segments, 'en')
        non_inj = [s for s in en if not s.get('injectable')]
        assert len(non_inj) == 2
        assert {s['index'] for s in non_inj} == {888, 1023}


class TestMLSSContent:
    def test_known_narrative_phrases(self, segments):
        en = [s['raw_text'] for s in segments if s.get('lang') == 'en']
        assert any("Maybe it's just his age" in t for t in en)
        assert any("Bowser's Castle is" in t for t in en)

    def test_names_unique(self, segments):
        names = [s['name'] for s in segments]
        assert len(names) == len(set(names))

    def test_all_langs_present(self, segments):
        langs = {s.get('lang') for s in segments}
        assert langs == {'de', 'fr', 'es', 'en', 'it'}


class TestMLSSInject:
    def test_inject_en_roundtrip(self, plugin, segments, mlss_rom):
        texts = _lang_texts(segments, 'en')
        injector = TextInjector(ROM_PATH)
        assert injector.inject_interleaved_language('en', texts, plugin, segments=segments)
        patched = mlss_rom.__class__(ROM_PATH)
        patched.data = bytes(injector.modified_data)
        re = _lang_texts(plugin.get_text_segments(patched), 'en')
        assert re == texts

    def test_inject_other_lang_roundtrip(self, plugin, segments, mlss_rom):
        for lang in ('de', 'fr', 'it'):
            texts = _lang_texts(segments, lang)
            injector = TextInjector(ROM_PATH)
            assert injector.inject_interleaved_language(lang, texts, plugin, segments=segments)
            patched = mlss_rom.__class__(ROM_PATH)
            patched.data = bytes(injector.modified_data)
            re = _lang_texts(plugin.get_text_segments(patched), lang)
            assert re == texts

    def test_inject_relocates_on_overflow(self, plugin, segments, mlss_rom):
        texts = _lang_texts(segments, 'en')
        en_segs = sorted(_lang_segments(segments, 'en'), key=lambda s: s.get('index', 0))
        target = next(i for i, s in enumerate(en_segs) if s.get('injectable'))
        # вставляем длинный текст ВНУТРЬ сообщения (до терминатора [FF 0A 00]),
        # сохраняя ровно один FF 0A — иначе запись станет некорректной
        fill = 'X' * 600
        idx_term = texts[target].rfind('[FF 0A')
        if idx_term == -1:
            texts[target] += fill
        else:
            texts[target] = texts[target][:idx_term] + fill + texts[target][idx_term:]
        injector = TextInjector(ROM_PATH)
        assert injector.inject_interleaved_language('en', texts, plugin, segments=segments)
        patched = mlss_rom.__class__(ROM_PATH)
        patched.data = bytes(injector.modified_data)
        re = _lang_texts(plugin.get_text_segments(patched), 'en')
        assert re == texts

    def test_inject_multiple_relocations_no_overlap(self, plugin, segments, mlss_rom):
        """Две релокации в одном инстансе не должны пересекаться:
        find_free_space обязан видеть уже записанные (occupied) зоны."""
        texts = _lang_texts(segments, 'en')
        en_segs = sorted(_lang_segments(segments, 'en'), key=lambda s: s.get('index', 0))
        inj_idx = [i for i, s in enumerate(en_segs) if s.get('injectable')][:2]
        for i in inj_idx:
            t = texts[i]
            k = t.rfind('[FF 0A')
            if k == -1:
                texts[i] = t + 'Y' * 500
            else:
                texts[i] = t[:k] + 'Y' * 500 + t[k:]
        injector = TextInjector(ROM_PATH)
        assert injector.inject_interleaved_language('en', texts, plugin, segments=segments)
        patched = mlss_rom.__class__(ROM_PATH)
        patched.data = bytes(injector.modified_data)
        re = _lang_texts(plugin.get_text_segments(patched), 'en')
        assert re == texts

    def test_inject_via_generic_dispatcher(self, plugin, segments, mlss_rom):
        """inject_language_block должен делегировать interleaved-раскладку
        в inject_interleaved_language автоматически."""
        texts = _lang_texts(segments, 'en')
        injector = TextInjector(ROM_PATH)
        assert injector.inject_language_block('en', texts, plugin, segments=segments)
        patched = mlss_rom.__class__(ROM_PATH)
        patched.data = bytes(injector.modified_data)
        re = _lang_texts(plugin.get_text_segments(patched), 'en')
        assert re == texts

    def test_inject_count_mismatch_false(self, plugin, segments):
        injector = TextInjector(ROM_PATH)
        assert injector.inject_interleaved_language('en', ['A'] * (MLSS_ENTRIES - 1),
                                                    plugin, segments=segments) is False
        assert injector.modified_data == injector.original_data

    def test_inject_unencodable_text_false(self, plugin, segments):
        texts = _lang_texts(segments, 'en')
        texts[0] = 'Сомā'
        injector = TextInjector(ROM_PATH)
        assert injector.inject_interleaved_language('en', texts, plugin, segments=segments) is False

    def test_inject_unknown_lang_false(self, plugin, segments):
        injector = TextInjector(ROM_PATH)
        assert injector.inject_interleaved_language('ja', ['A'] * MLSS_ENTRIES,
                                                    plugin, segments=segments) is False


class TestMLSSPointerTable:
    def test_find_free_space_works(self):
        data = bytearray(b'\x00\x00\x01\x00\x00\x00')
        assert find_free_space(data, 3) == 3
        assert find_free_space(data, 3, [(3, 5)]) is None

    def test_expand_rom_grows_buffer(self, mlss_rom):
        injector = TextInjector(ROM_PATH)
        old_len = len(injector.modified_data)
        dest = injector._expand_rom(700)
        assert len(injector.modified_data) > old_len
        assert dest >= old_len
        assert dest % 0x100 == 0
        # запрошенные байты помещаются от dest
        assert dest + 700 <= len(injector.modified_data)

    def test_meta_index_of(self, plugin):
        meta = plugin.get_pointer_table_meta()
        assert meta['index_of'](3, 3) == 3 * 5 + 3
        assert meta['lang_slots']['en'] == 3
        assert meta['table'] == MLSS_POINTER_TABLE
