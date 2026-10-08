"""Матрица отказов `_affix_region_inner`.

Аффикс-регион — запись с фиксированными префиксом/суффиксом (например
`>> `), где переводится только середина. Все проверки ловятся прямыми
вызовами с подставными данными: ни файлов, ни реальной ROM не нужно.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from tests.test_injector_foreign_ranges import _injector

LEAD = '>>'
TRAIL = ': '


def _enc(text):
    return text.encode('ascii')


def _broken_enc(exc):
    def enc(text):
        raise exc('не кодируется')
    return enc


def _seg():
    return {'name': 'win', 'start': 0, 'end': 0x40}


WINDOW_TEXT = '>>HELLO: '
FULL = '>>HELLO: '


def _call(*, enc=None, window_text=WINDOW_TEXT, translation=FULL,
          length=32, lead=LEAD, trail=TRAIL, window_bytes=None):
    inj = _injector({'game': []})
    enc = enc or _enc
    if window_bytes is None:
        # для битого энкодера окно задаётся явно: иначе тест падал бы сам
        window_bytes = window_text.encode('ascii')
    return inj._affix_region_inner(
        _seg(), {'original': window_text}, window_text, enc, translation,
        0, length, window_bytes, lead, trail)


def test_happy_path_returns_room():
    start, room, rest = _call()
    assert start == len('>>'), start
    assert room == 32 - len('>>') - len(': ')
    assert rest


@pytest.mark.parametrize('exc', [ValueError, KeyError, IndexError, TypeError])
def test_encoder_failure_refuses(exc):
    assert _call(enc=_broken_enc(exc)) == (None, None, None)


def test_empty_encoded_affix_refuses():
    """Аффикс нечем кодировать — регион непригоден."""
    def enc(text):
        return b'' if text in (LEAD, TRAIL) else text.encode('ascii')

    assert _call(enc=enc) == (None, None, None)


def test_window_must_start_with_lead():
    assert _call(lead='##', translation='##HELLO: ') == (None, None, None)


def test_window_must_end_with_trail():
    assert _call(trail='???', translation='>>HELLO???') == (None, None, None)


def test_translation_keeps_affixes_and_room():
    """Аффиксы вырезаются, середина переводится, room считается по месту."""
    for tr in ('>>ZZZZ: ', '>>HELLO: ', '>>HELLO: X'):
        start, room, rest = _call(translation=tr)
        assert start == 2 and room == 28 and rest == tr


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
