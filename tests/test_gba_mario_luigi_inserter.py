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
    'test_game',
    'Mario & Luigi - Superstar Saga (USA).gba',
)


@pytest.fixture(scope="module")
def mlss_rom() -> GameBoyROM:
    if not os.path.exists(ROM_PATH):
        pytest.skip("Отсутствует test_game/Mario & Luigi - Superstar Saga (USA).gba")
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


class TestMLSSCatalogWindow:
    """Регрессия: запись, перенесённая в свободное место, не должна
    классифицироваться как каталоговая.

    Дефект: верхняя граница окна бралась по следующему указателю своей
    колонки (~2 МБ диалогового пула), запись набирала больше одного FF 0A и
    читалась как каталог на 10 млн символов вместо 655 байт. На непофиченном
    коде этот тест падает: длина переизвлечённого текста != залитой.
    """

    @pytest.mark.parametrize('fill_len', [600, 2500])
    def test_relocated_record_is_not_a_catalog(self, plugin, segments, mlss_rom,
                                              fill_len):
        # 2500 символов обязательно: запись длиннее 0x800 байт после релокации
        # раньше становилась read-only, и перевод молча терялся при inject(),
        # возвращавшем True.
        texts = _lang_texts(segments, 'en')
        en_segs = sorted(_lang_segments(segments, 'en'),
                         key=lambda s: s.get('index', 0))
        target = next(i for i, s in enumerate(en_segs) if s.get('injectable'))
        fill = 'X' * fill_len
        k = texts[target].rfind('[FF 0A')
        if k == -1:
            texts[target] = texts[target] + fill
        else:
            texts[target] = texts[target][:k] + fill + texts[target][k:]

        injector = TextInjector(ROM_PATH)
        assert injector.inject_interleaved_language(
            'en', texts, plugin, segments=segments)
        patched = mlss_rom.__class__(ROM_PATH)
        patched.data = bytes(injector.modified_data)

        resegments = plugin.get_text_segments(patched)
        again = _lang_texts(resegments, 'en')
        moved = [s for s in resegments
                 if isinstance(s.get('start'), int)
                 and s.get('index') == en_segs[target].get('index')]
        assert moved, 'перенесённая запись пропала из манифеста'
        assert moved[0].get('injectable') is True, (
            'перенесённая запись стала read-only и перевод будет потерян')
        assert len(again[target]) == len(texts[target]), (
            f'перенесённая запись прочитана на {len(again[target])} символов '
            f'вместо {len(texts[target])}')
        assert again == texts

        for seg in resegments:
            if seg.get('injectable') is False:
                size = seg['end'] - seg['start']
                assert size <= 0x20000, (
                    f'каталог 0x{seg["start"]:X} раздут до {size} байт')

    def test_real_catalogs_fit_the_thresholds(self, mlss_rom):
        import re
        plugin = MarioLuigiSSPlugin()
        segments = plugin.get_text_segments(mlss_rom)
        data = bytes(mlss_rom.data)
        limit = MarioLuigiSSPlugin._CATALOG_MAX_ZERO_RUN

        def max_zeros(blob: bytes) -> int:
            return max((len(m) for m in re.findall(rb'\x00+', blob)),
                       default=0)

        catalogs = [s for s in segments if s.get('injectable') is False]
        assert catalogs, 'на реальном ROM есть каталоговые записи'
        for seg in catalogs:
            blob = data[seg['start']:seg['end']]
            assert max_zeros(blob) <= limit, (
                f'каталог 0x{seg["start"]:X}: нулевой прогон длиннее '
                f'порога {limit}')

    def test_stale_span_out_of_rom_is_dropped(self, plugin, segments, mlss_rom):
        """Чужой/устаревший спан не должен уводить разбор за конец ROM."""
        plugin.get_text_segments(mlss_rom)
        spans = MarioLuigiSSPlugin._CLASS_CATALOG_SPANS
        assert spans, 'нужны каталоговые спаны'
        key = sorted(spans)[0]
        saved = spans[key]
        try:
            spans[key] = (saved[0], len(mlss_rom.data) + 4096)
            seg = plugin._make_segment(
                mlss_rom.data, saved[0], key[1], key[0], spans)
            assert seg is None
            # start за ROM при валидном target: срабатывает именно проверка
            # границ каталога, а не ранний отсев target.
            spans[key] = (len(mlss_rom.data) + 16, len(mlss_rom.data) + 32)
            assert plugin._make_segment(
                mlss_rom.data, saved[0], key[1], key[0], spans) is None
        finally:
            spans[key] = saved

    def test_detection_knob_invalidates_cache(self, plugin, mlss_rom):
        """Порог входит в ключ кэша: подмена не должна брать устаревшие спаны.

        Без этого будущий monkeyset даёт ложно-зелёный тест: спаны остаются от
        предыдущего скана, и дефект отсечки не воспроизводится.
        """
        plugin.get_text_segments(mlss_rom)
        assert MarioLuigiSSPlugin._CLASS_CATALOG_SPANS
        # Отравляем кэш: если бы порог не входил в ключ, следующее извлечение
        # взяло бы эти пустые спаны и дефект отсечки не воспроизвёлся бы.
        MarioLuigiSSPlugin._CLASS_CATALOG_SPANS = {}
        try:
            MarioLuigiSSPlugin._CATALOG_MAX_ZERO_RUN = 10 ** 9
            plugin.get_text_segments(mlss_rom)
            rescanned = dict(MarioLuigiSSPlugin._CLASS_CATALOG_SPANS)
            key = MarioLuigiSSPlugin._CLASS_CATALOG_ROMKEY
        finally:
            MarioLuigiSSPlugin._CATALOG_MAX_ZERO_RUN = 64
            MarioLuigiSSPlugin.reset_class_cache()
        assert rescanned, 'порог не входит в ключ кэша: спаны не пересканированы'
        assert key is not None and key[-1] == 10 ** 9

    def test_reset_class_cache_clears_state(self, mlss_rom):
        plugin = MarioLuigiSSPlugin()
        plugin.get_text_segments(mlss_rom)
        assert MarioLuigiSSPlugin._CLASS_CATALOG_SPANS
        MarioLuigiSSPlugin.reset_class_cache()
        assert MarioLuigiSSPlugin._CLASS_CATALOG_SPANS == {}
        assert MarioLuigiSSPlugin._CLASS_CATALOG_SCANNED is False
        assert MarioLuigiSSPlugin._CLASS_CATALOG_ROMKEY is None

    def test_reader_does_not_use_republished_spans(self, mlss_rom):
        """Читатель не должен брать спаны, переопубликованные другим потоком.

        Гонка была не в публикации, а в чтении: опубликовав свой кэш, поток
        обращался к общему ClassVar, и другой поток успевал пересканировать свой
        ROM - все девять каталоговых сегментов получали чужие start/end без
        исключения. Здесь публикация подменяется детерминированно: пока первый
        поток заблокирован на первом же _make_segment (он уже опубликовал свой
        кэш и снял снимок), общий атрибут перезаписывается чужими спанами.
        """
        import threading

        plugin = MarioLuigiSSPlugin()
        expected = sorted(
            s['start'] for s in plugin.get_text_segments(mlss_rom)
            if s.get('injectable') is False)
        assert expected, 'нужны каталоговые спаны'

        real_make = MarioLuigiSSPlugin._make_segment
        poisoned = threading.Event()
        released = threading.Event()

        def gated_make(self, data, target, idx, lang, spans):
            if threading.current_thread() is holder.get('t') \
                    and not poisoned.is_set():
                poisoned.set()
                # Чужой поток успел пересканировать свой ROM и переопубликовал
                # спаны: подменяем их на заведомо другие, но валидные адреса.
                foreign = {k: (v[0] + 0x40, v[1] + 0x40)
                           for k, v in MarioLuigiSSPlugin._CLASS_CATALOG_SPANS.items()}
                MarioLuigiSSPlugin._CLASS_CATALOG_SPANS = foreign
                released.set()
                released.wait(20)
            return real_make(self, data, target, idx, lang, spans)

        holder = {}
        MarioLuigiSSPlugin._make_segment = gated_make
        try:
            out = {}

            def run():
                out['a'] = MarioLuigiSSPlugin().get_text_segments(mlss_rom)

            th = threading.Thread(target=run)
            holder['t'] = th
            th.start()
            th.join(60)
        finally:
            MarioLuigiSSPlugin._make_segment = real_make
            MarioLuigiSSPlugin.reset_class_cache()

        assert not th.is_alive(), 'поток не завершился'
        assert 'a' in out
        got = sorted(s['start'] for s in out['a']
                     if s.get('injectable') is False)
        assert got == expected, (
            f'читатель взял переопубликованные спаны: {got[:4]} '
            f'вместо {expected[:4]}')
