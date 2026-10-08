"""Матрица входных гардов `inject_interleaved_language`.

Плагин с мультиязычной таблицей указателей (Pokémon GBA): у каждого языка
свой слот, записи адресуются относительными смещениями. Все проверки формы
meta/segments ловятся без файлов на диске — на лёгком фикстуре в 512 байт.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from tests.test_injector_foreign_ranges import ROM_SIZE, _injector

TABLE = 0x100


class _Enc:
    def encode(self, text):
        return text.encode('ascii')


class _MetaPlugin:
    """Плагин с `get_pointer_table_meta` и кодировщиком."""

    def __init__(self, meta, segments=None):
        self._meta = meta
        self._segments = segments if segments is not None else []

    def get_pointer_table_meta(self):
        return self._meta

    def make_text_encoder(self):
        return _Enc()

    def get_text_segments(self, rom):
        return self._segments


def _meta(**over):
    meta = {
        'table': TABLE,
        'count': 2,
        'lang_slots': {'en': 0, 'ru': 1},
        'index_of': lambda text, lang: 0,
    }
    meta.update(over)
    return meta


def _inj(segments=None):
    return _injector({'game': segments or []})


def _seg(index, lang='en', start=0x200, end=0x210):
    return {'name': f'{lang}_{index}', 'lang': lang, 'index': index,
            'start': start, 'end': end}


def test_no_meta_refuses():
    inj = _inj()
    for plugin in (object(), _MetaPlugin(None), _MetaPlugin('not a dict')):
        assert inj.inject_interleaved_language('en', ['a'], plugin) is False


@pytest.mark.parametrize('texts,lang', [
    ('not a list', 'en'),
    (['a'], 42),
    (None, 'en'),
])
def test_bad_texts_or_lang_refuses(texts, lang):
    inj = _inj()
    assert inj.inject_interleaved_language(
        lang, texts, _MetaPlugin(_meta())) is False


@pytest.mark.parametrize('over', [
    {'table': 'x'}, {'table': True},
    {'count': 'x'}, {'count': True},
    {'lang_slots': 'x'}, {'lang_slots': {'ru': 0}},
    {'index_of': 'not callable'},
    {'lang_slots': {'en': True, 'ru': 1}},
    {'lang_slots': {'en': 'x', 'ru': 1}},
    {'table': -1},
    {'table': ROM_SIZE - 2},
])
def test_bad_meta_refuses(over):
    inj = _inj()
    assert inj.inject_interleaved_language(
        'en', ['a'], _MetaPlugin(_meta(**over))) is False


def test_segments_must_be_list():
    inj = _inj()
    assert inj.inject_interleaved_language(
        'en', ['a'], _MetaPlugin(_meta()), segments='not a list') is False


@pytest.mark.parametrize('bad', [
    'not a dict',
    {'lang': 'en', 'index': True, 'start': 0x200, 'end': 0x210},
    {'lang': 'en', 'index': 0, 'start': 'x', 'end': 0x210},
    {'lang': 'en', 'index': 0, 'start': 0x200, 'end': None},
    {'lang': 'en', 'index': 0, 'start': -1, 'end': 0x210},
    {'lang': 'en', 'index': 0, 'start': 0x200, 'end': ROM_SIZE + 1},
])
def test_bad_segments_are_skipped_not_fatal(bad):
    """Битый сегмент пропускается построчно, а не роняет разбор.

    Все варианты дают один и тот же исход: сегмент не попадает в `by_idx`,
    язык остаётся без записей и вставка отказывается. Важно, что ни один
    вариант не падает и не пишет по границам, полученным из мусора.
    """
    good = _seg(0)
    inj = _inj([good, bad])
    before = bytes(inj.modified_data)
    assert inj.inject_interleaved_language(
        'en', ['ab'], _MetaPlugin(_meta(count=1)),
        segments=[good, bad]) is False
    assert bytes(inj.modified_data) == before, 'ROM изменён при отказе'


def test_legacy_name_without_lang_key_is_not_matched():
    """Сегмент без `lang` и без префикса `cvas_` не относится ни к одному языку."""
    seg = {'name': 'plain_0', 'index': 0, 'start': 0x200, 'end': 0x210}
    inj = _inj([seg])
    before = bytes(inj.modified_data)
    assert inj.inject_interleaved_language(
        'en', ['ab'], _MetaPlugin(_meta(count=1)), segments=[seg]) is False
    assert bytes(inj.modified_data) == before, 'ROM изменён при отказе'


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
