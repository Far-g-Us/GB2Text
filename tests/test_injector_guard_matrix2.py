"""Матрица защитных гардов `_inject_pointer_dialogues`.

Недостижимых веток здесь нет: все проверки типов и форм ловятся подачей
некорректного манифеста, невалидного перевода или энкодера. Непокрытым
оставался именно этот блок `return _fail()`.

Фикстур — лёгкий `_injector()` на 512 байт из
`tests/test_injector_foreign_ranges.py`: копировать настоящую ROM ради
проверки форм не нужно, а копирование 4 МБ на каждый вызов оставляло
184 МБ мусора в `%TEMP%` за прогон.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from tests.test_injector_foreign_ranges import _injector

ENTRY = {'target': 0x100, 'free_after': 0x20, 'slots': [0x200]}


def _decoder():
    class D:
        def decode(self, data, start, length):
            return ''

        def encode(self, text):
            return b'\xff'
    return D()


def _seg(manifest, decoder=None, terminator=b'\xff'):
    return {'decoder': decoder or _decoder(), 'manifest': manifest,
            'terminator': terminator}


def _with_encoder(encoder):
    seg = _seg([dict(ENTRY)])
    seg['pointer_encoder'] = encoder
    return seg


@pytest.mark.parametrize('skip_long', [False, True])
def test_entry_not_dict_fails(skip_long):
    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(
        _seg(['not a dict']), ['x'], skip_long) is False


@pytest.mark.parametrize('bad', [
    {'target': 'x', 'free_after': 0x20},
    {'target': True, 'free_after': 0x20},
    {'target': 0x100, 'free_after': None},
    {'target': 0x100, 'free_after': True},
    {'free_after': 0x20},
])
@pytest.mark.parametrize('skip_long', [False, True])
def test_entry_bad_addr_or_room_fails(bad, skip_long):
    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(
        _seg([bad]), ['x'], skip_long) is False


@pytest.mark.parametrize('skip_long', [False, True])
def test_translation_not_str_fails(skip_long):
    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(
        _seg([ENTRY]), [123], skip_long) is False


def test_encoder_gets_live_buffer_on_retry():
    """Oracle жмёт против содержимого словаря: нужен modified_data.

    Энкодер сначала зовётся без буфера и падает TypeError, затем получает
    живой буфер — без этого после перевода словаря он развернулся бы в чужой
    текст.
    """
    calls = []

    def encoder(text, rom=None):
        calls.append(rom is not None)
        if rom is None:
            raise TypeError('нужен буфер')
        return b'\xff'

    inj = _injector({'game': []})
    inj._inject_pointer_dialogues(_with_encoder(encoder), ['x'], False)
    assert calls == [False, True], (
        'энкодер должен быть вызван без буфера, затем с modified_data')


@pytest.mark.parametrize('exc', [ValueError, KeyError, IndexError])
@pytest.mark.parametrize('skip_long', [False, True])
def test_encoder_typeerror_retried_then_raises(exc, skip_long):
    """TypeError без буфера, затем отказ с буфером — оба пути отказа."""
    def encoder(text, rom=None, _exc=exc):
        if rom is None:
            raise TypeError('нужен буфер')
        raise _exc('boom')

    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(
        _with_encoder(encoder), ['x'], skip_long) is False


@pytest.mark.parametrize('exc', [ValueError, KeyError, IndexError])
@pytest.mark.parametrize('skip_long', [False, True])
def test_encoder_value_error_fails(exc, skip_long):
    def encoder(text, *a, _exc=exc):
        raise _exc('boom')

    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(
        _with_encoder(encoder), ['x'], skip_long) is False


@pytest.mark.parametrize('skip_long', [False, True])
def test_encoder_returns_non_bytes_fails(skip_long):
    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(
        _with_encoder(lambda text, *a: 'not bytes'), ['x'], skip_long) is False


@pytest.mark.parametrize('skip_long', [False, True])
def test_bad_terminator_reports_and_refuses(skip_long):
    """Битый терминатор: отказ, но причина попадает в отчёт."""
    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(
        _seg([ENTRY], terminator='not bytes'), ['x'], skip_long) is False
    assert inj.last_overflow_report, 'отчёт о переполнении не заполнен'
    assert inj.last_overflow_report[0]['length'] == -1


@pytest.mark.parametrize('bad', [
    {'target': -1, 'free_after': 4},
    {'target': 0x100, 'free_after': -1},
    {'target': 10 ** 9, 'free_after': 4},
])
@pytest.mark.parametrize('skip_long', [False, True])
def test_target_outside_rom_fails(bad, skip_long):
    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(
        _seg([bad]), ['x'], skip_long) is False


def test_skip_long_keeps_good_record():
    """skip_long пропускает битую запись, а не откатывает весь язык."""
    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(
        _seg([ENTRY, {'target': 10 ** 9, 'free_after': 4}]),
        ['x', 'y'], True) is True


def test_manifest_not_list_and_translations_shape():
    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(
        _seg('not a list'), ['x'], False) is False
    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(_seg([]), 'not a list', False) is False


def test_empty_translations_is_noop():
    inj = _injector({'game': []})
    assert inj._inject_pointer_dialogues(_seg([]), [], False) is True


def test_fail_rolls_back_tracked_spans():
    """Откат на пути отказа не оставляет записанных спанов."""
    inj = _injector({'game': []})
    before = len(inj._tracked_spans())
    assert inj._inject_pointer_dialogues(
        _seg([ENTRY, {'target': 'bad', 'free_after': 1}]), ['x', 'y'],
        False) is False
    assert len(inj._tracked_spans()) == before


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
