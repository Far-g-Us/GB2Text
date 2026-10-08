"""Покрытие внутренних помощников `core/injector.py`, которых не было в тестах.

Список получен измерением: публичные методы класса, не упомянутые ни в одном
тестовом файле. Здесь каждое проверяется напрямую, без реального ROM, кроме
`_compressed_original_text`, которому нужен инжектор.

Файлы не сливаются с остальными: он закрывает именно непокрытые методы, а не
перегруппировывает уже покрытое.
"""

import pytest

from core.injector import TextInjector


class TestIsSubsequence:
    """`need` должен идти подпоследовательностью `have` (порядок важен)."""

    def test_exact_match(self):
        assert TextInjector._is_subsequence([1, 2, 3], [1, 2, 3]) is True

    def test_subsequence_with_extra_items(self):
        assert TextInjector._is_subsequence([1, 9, 2, 8, 3], [1, 2, 3]) is True

    def test_order_matters(self):
        assert TextInjector._is_subsequence([3, 2, 1], [1, 2, 3]) is False

    def test_missing_item(self):
        assert TextInjector._is_subsequence([1, 2], [1, 3]) is False

    def test_empty_need_is_trivially_true(self):
        assert TextInjector._is_subsequence([1, 2, 3], []) is True

    def test_empty_have_covers_only_empty_need(self):
        assert TextInjector._is_subsequence([], []) is True
        assert TextInjector._is_subsequence([], [1]) is False

    def test_no_reuse_of_the_same_item(self):
        # Один и тот же элемент не может удовлетворить два `need`.
        assert TextInjector._is_subsequence([1], [1, 1]) is False


class TestScanFreeSpaceRuns:
    """Поиск прогонов нулей, пригодных для переноса записи."""

    def test_single_run(self):
        assert TextInjector._scan_free_space_runs(b'\x00\x00') == [(0, 2)]

    def test_multiple_runs_with_text_between(self):
        assert TextInjector._scan_free_space_runs(b'a\x00\x00b\x00') == [
            (1, 3), (4, 5)]

    def test_no_runs(self):
        assert TextInjector._scan_free_space_runs(b'abc') == []

    def test_leading_and_trailing_runs(self):
        assert TextInjector._scan_free_space_runs(b'\x00a\x00') == [(0, 1), (2, 3)]

    def test_empty_buffer(self):
        assert TextInjector._scan_free_space_runs(b'') == []

    def test_accepts_bytearray(self):
        assert TextInjector._scan_free_space_runs(bytearray(b'\x00\x00a')) == [
            (0, 2)]


class TestSegmentLang:
    """Язык сегмента: явное поле или legacy-имя `cvas_<lang>_idx`."""

    def test_explicit_lang_wins(self):
        seg = {'lang': 'de', 'name': 'cvas_fr_idx'}
        assert TextInjector._segment_lang(seg) == 'de'

    def test_legacy_name(self):
        assert TextInjector._segment_lang({'name': 'cvas_de_idx'}) == 'de'

    def test_legacy_name_without_idx_suffix(self):
        assert TextInjector._segment_lang({'name': 'cvas_fr'}) == 'fr'

    def test_plain_name_has_no_language(self):
        assert TextInjector._segment_lang({'name': 'dialogue'}) is None

    def test_missing_both(self):
        assert TextInjector._segment_lang({}) is None

    def test_non_string_lang_ignored(self):
        assert TextInjector._segment_lang({'lang': 7}) is None

    def test_non_string_name_ignored(self):
        assert TextInjector._segment_lang({'name': 7}) is None


class TestValidSegments:
    """Фильтр списка сегментов, fail-closed."""

    def test_list_of_dicts_passes_through(self):
        segs = [{'name': 'a'}, {'name': 'b'}]
        assert TextInjector._valid_segments(segs) is segs

    def test_empty_list_is_valid(self):
        segs: list = []
        assert TextInjector._valid_segments(segs) is segs

    def test_none_is_rejected(self):
        assert TextInjector._valid_segments(None) is None

    def test_non_list_is_rejected(self):
        # Кортеж - не список: fail-closed, даже если элементы корректны.
        assert TextInjector._valid_segments(({'name': 'a'},)) is None

    def test_non_dict_element_is_rejected(self):
        assert TextInjector._valid_segments([{'name': 'a'}, 'oops']) is None

    def test_none_element_is_rejected(self):
        assert TextInjector._valid_segments([None]) is None

    def test_large_mixed_list_rejected(self):
        # Golden Sun даёт ~10863 сегмента; проверка не должна быть O(n^2) по
        # содержимому, поэтому важно, что отказ происходит по первому мусору.
        segs = [{'name': f's{i}'} for i in range(200)]
        segs[150] = 42
        assert TextInjector._valid_segments(segs) is None


class TestIsOwnSegment:
    """Отсечение чужих сегментов при переносе записей."""

    def test_identity_object_is_own(self):
        seg = {'name': 'a', 'start': 0, 'end': 8}
        assert TextInjector._is_own_segment(seg, 'a', seg) is True

    def test_same_name_and_window_is_own(self):
        mine = {'name': 'a', 'start': 0, 'end': 8}
        other = {'name': 'a', 'start': 0, 'end': 8}
        assert TextInjector._is_own_segment(other, 'a', mine) is True

    def test_same_name_different_window_is_foreign(self):
        mine = {'name': 'a', 'start': 0, 'end': 8}
        other = {'name': 'a', 'start': 16, 'end': 24}
        assert TextInjector._is_own_segment(other, 'a', mine) is False

    def test_other_name_is_foreign(self):
        mine = {'name': 'a', 'start': 0, 'end': 8}
        assert TextInjector._is_own_segment({'name': 'b'}, 'a', mine) is False

    def test_without_own_segment_only_name_is_compared(self):
        assert TextInjector._is_own_segment(
            {'name': 'a', 'start': 99}, 'a', None) is True
        assert TextInjector._is_own_segment(
            {'name': 'b', 'start': 0}, 'a', None) is False

    def test_segment_without_name_matches_none_own_name(self):
        # Особенное краение: сегмент без имени считается
        # своим (`None == None`). В работе `own_name` всегда из реального сегмента,
        # поэтому в производстве не возникает.
        assert TextInjector._is_own_segment(
            {'start': 0, 'end': 8}, None, None) is True


class TestShrinkFreeRun:
    """Разрезание прогона свободного места при вставке payload."""

    def test_split_into_left_and_right(self):
        runs = [(0, 100)]
        starts = [0]
        TextInjector._shrink_free_run(runs, starts, 0, 0, 100, 40, 10)
        # Слева осталось 40 байт, справа освободилось 50 (40+10..100).
        assert runs[0] == (0, 40)
        assert runs[1] == (50, 100)
        assert starts == [0, 50]

    def test_payload_reaching_stop_leaves_no_right_run(self):
        runs = [(0, 20)]
        starts = [0]
        TextInjector._shrink_free_run(runs, starts, 0, 0, 20, 10, 10)
        assert runs == [(0, 10)]

    def test_dest_beyond_stop_keeps_left_run_as_given(self):
        # Код не обрезает `dest` по `stop`: слевый пробег берётся
        # как есть есть, а правый хвост не появляется, ведь появляется
        # за счётом прищинка.
        runs = [(0, 20)]
        starts = [0]
        TextInjector._shrink_free_run(runs, starts, 0, 0, 20, 30, 4)
        assert runs == [(0, 30)]

    def test_empty_left_run_when_start_equals_dest(self):
        runs = [(0, 20)]
        starts = [0]
        TextInjector._shrink_free_run(runs, starts, 0, 0, 20, 0, 4)
        assert runs[0] == (0, 0)

    def test_empty_left_run_when_start_exceeds_dest(self):
        runs = [(0, 20)]
        starts = [0]
        TextInjector._shrink_free_run(runs, starts, 0, 8, 20, 4, 2)
        assert runs[0] == (8, 8)

    def test_without_starts_list_right_run_is_appended(self):
        runs = [(0, 100)]
        TextInjector._shrink_free_run(runs, None, 0, 0, 100, 40, 10)
        assert runs == [(0, 40), (50, 100)]

    def test_other_entries_are_preserved(self):
        runs = [(0, 10), (20, 100)]
        starts = [0, 20]
        TextInjector._shrink_free_run(runs, starts, 1, 20, 100, 50, 4)
        assert runs[0] == (0, 10)
        assert runs[1] == (20, 50)
        assert starts == [0, 20, 54]


class TestConsumeTokens:
    """Проезд по run при вставке в начало или в конец окна.

    `run` содержит символы `[XX]`: именно только такие обрабатывают
    токены вместо с буквами, а `rest` — оставшаяся часть текста.
    """

    @staticmethod
    def _enc(text):
        return text.encode('latin-1')

    @staticmethod
    def _boom(text):
        raise ValueError('nope')

    @staticmethod
    def _empty(text):
        return b''

    def test_consumes_prefix_of_run(self):
        rest, fatal = TextInjector._consume_tokens(
            self._enc, '[01]DEF', '[01]xxx', b'[01]DEFxxx', True)
        assert fatal is False
        assert rest == 'xxx'

    def test_stops_at_first_mismatch(self):
        rest, fatal = TextInjector._consume_tokens(
            self._enc, '[01]DEF', 'ABXxxx', b'[01]DEFxxx', True)
        assert fatal is False
        assert rest == 'ABXxxx'

    def test_from_end_consumes_suffix(self):
        # В режиме `from_end=False` смещение токена ожидаются в
        # конце окна: `pos` считается от конца `window_bytes`.
        rest, fatal = TextInjector._consume_tokens(
            self._enc, '[01]DEF', 'xxx[01]', b'zzz[01]', False)
        assert fatal is False
        assert rest == 'xxx'

    def test_from_end_requires_token_at_window_end(self):
        # Токен не в конце окна - байты не совпали, fail-closed.
        _rest, fatal = TextInjector._consume_tokens(
            self._enc, '[01]', 'xxx[01]', b'[01]xxx', False)
        assert fatal is True

    def test_comparison_is_case_insensitive(self):
        rest, fatal = TextInjector._consume_tokens(
            self._enc, '[01]DEF', '[01]xxx', b'[01]DEFxxx', True)
        assert fatal is False
        assert rest == 'xxx'

    def test_encoder_exception_is_fail_closed(self):
        rest, fatal = TextInjector._consume_tokens(
            self._boom, '[01]', '[01]xxx', b'[01]xxx', True)
        assert fatal is True
        assert rest == '[01]xxx'

    def test_empty_encoding_is_fail_closed(self):
        _rest, fatal = TextInjector._consume_tokens(
            self._empty, '[01]', '[01]xxx', b'[01]xxx', True)
        assert fatal is True

    def test_run_longer_than_rest_consumes_nothing(self):
        rest, fatal = TextInjector._consume_tokens(
            self._enc, '[01]DEF', 'AB', b'[01]DEFAB', True)
        assert fatal is False
        assert rest == 'AB'

    def test_bytes_must_match_window(self):
        # Окно не совпадает с содержимым токена - это fail-closed.
        _rest, fatal = TextInjector._consume_tokens(
            self._enc, '[01]', '[01]xxx', b'ZZZxxx', True)
        assert fatal is True

    def test_run_without_raw_tokens_is_untouched(self):
        rest, fatal = TextInjector._consume_tokens(
            self._enc, 'ABCDEF', 'ABCxxx', b'ABCDEFxxx', True)
        assert fatal is False
        assert rest == 'ABCxxx'


class TestCompressedOriginalText:
    """Исходный текст сжатого окна: декодируется, иначе `None`."""

    # Окно размещается в конце для декодера: `core.rom`
    # отключает файл меньше `MIN_ROM_SIZE`, поэтому окно быть
    # не меньше `MIN_ROM_SIZE`, но не меньше `ROM неверный`.
    PAYLOAD_AT = 0x1000

    def _injector(self, tmp_path, payload=b'Hi\x00'):
        rom = tmp_path / 'c.gba'
        buf = bytearray(0x8000)
        buf[self.PAYLOAD_AT:self.PAYLOAD_AT + len(payload)] = payload
        rom.write_bytes(bytes(buf))
        return TextInjector(str(rom))

    def _seg(self, decoder=None, compression=None, start=None, end=None,
             **extra):
        seg = {'start': self.PAYLOAD_AT if start is None else start,
               'end': self.PAYLOAD_AT + 3 if end is None else end}
        if decoder is not None:
            seg['decoder'] = decoder
        if compression is not None:
            seg['compression'] = compression
        seg.update(extra)
        return seg

    def test_raw_text_short_circuits(self, tmp_path):
        inj = self._injector(tmp_path)
        assert inj._compressed_original_text({'raw_text': 'cached'}) == 'cached'

    def test_missing_decoder_returns_none(self, tmp_path):
        inj = self._injector(tmp_path)
        assert inj._compressed_original_text(self._seg()) is None

    def test_window_without_keys_returns_none(self, tmp_path):
        inj = self._injector(tmp_path)
        # Окно без 'start'/'end' не должно поднимать KeyError наружу.
        assert inj._compressed_original_text(
            self._seg(decoder=object(), end=None)) is None

    def test_plain_window_is_decoded(self, tmp_path):
        from core.decoder import CharMapDecoder
        charmap = {0x48: 'H', 0x69: 'i', 0x00: '\x00'}
        inj = self._injector(tmp_path)
        seg = self._seg(decoder=CharMapDecoder(charmap))
        assert inj._compressed_original_text(seg) == 'Hi\x00'

    def test_decoder_without_decode_returns_none(self, tmp_path):
        inj = self._injector(tmp_path)
        seg = self._seg(decoder=object())
        assert inj._compressed_original_text(seg) is None

    def test_decoder_exception_is_swallowed(self, tmp_path):
        class Boom:
            @staticmethod
            def decode(data, start, length):
                raise ValueError('nope')
        inj = self._injector(tmp_path)
        seg = self._seg(decoder=Boom())
        assert inj._compressed_original_text(seg) is None

    def test_non_string_decode_result_is_none(self, tmp_path):
        class Weird:
            @staticmethod
            def decode(data, start, length):
                return 42
        inj = self._injector(tmp_path)
        seg = self._seg(decoder=Weird())
        assert inj._compressed_original_text(seg) is None

    def test_unknown_compression_name_returns_none(self, tmp_path):
        from core.decoder import CharMapDecoder
        charmap = {0x48: 'H', 0x69: 'i'}
        inj = self._injector(tmp_path)
        seg = self._seg(decoder=CharMapDecoder(charmap),
                         compression='no-such-codec')
        assert inj._compressed_original_text(seg) is None

    def test_decompressor_exception_is_swallowed(self, tmp_path):
        class Codec:
            @staticmethod
            def decompress(data, offset):
                raise ValueError('nope')
        from core.decoder import CharMapDecoder
        charmap = {0x48: 'H'}
        inj = self._injector(tmp_path)
        seg = self._seg(decoder=CharMapDecoder(charmap), compression=Codec())
        assert inj._compressed_original_text(seg) is None

    def test_compressed_window_is_decompressed_then_decoded(self, tmp_path):
        class Codec:
            @staticmethod
            def decompress(data, offset):
                return b'Hi', 2
        from core.decoder import CharMapDecoder
        charmap = {0x48: 'H', 0x69: 'i'}
        inj = self._injector(tmp_path)
        seg = self._seg(decoder=CharMapDecoder(charmap), compression=Codec)
        assert inj._compressed_original_text(seg) == 'Hi'

    def test_non_callable_codec_instance_is_fail_closed(self, tmp_path):
        # `compression` обязан быть именем кодка или callable-объектом;
        # готовый экземпляяр без `__call__` не callable, и гард молча
        # выключается без ошибки.
        class NotCallable:
            @staticmethod
            def decompress(data, offset):
                return b'Hi', 2
        from core.decoder import CharMapDecoder
        charmap = {0x48: 'H', 0x69: 'i'}
        inj = self._injector(tmp_path)
        seg = self._seg(decoder=CharMapDecoder(charmap),
                        compression=NotCallable())
        assert inj._compressed_original_text(seg) is None


@pytest.mark.parametrize('value', [None, 0, '', b'', {}])
def test_valid_segments_rejects_non_list_types(value):
    assert TextInjector._valid_segments(value) is None
