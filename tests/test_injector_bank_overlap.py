"""Overlap/safe-inject гарды банкового пути (`_inject_bank_segment`).

Недостижимых веток нет: все проверки ловятся геометрией — наложением двух
записей, чужим окном поверх записи и выходом за границы ROM.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.injector import TextInjector
from tests.test_injector_foreign_ranges import (
    ROM_SIZE,
    _AsciiDecoder,
    _injector,
    _plain,
)

TABLE = 0x40
BASE = TABLE + 0x20


def _bank_inj(offsets, *, window=None, extra_meta=None, foreign=()):
    """Инжектор с банковым сегментом; таблица смещений пишется в ROM."""
    seg = {
        'name': 'bank',
        'start': TABLE,
        'end': ROM_SIZE,
        'decoder': _AsciiDecoder(),
        'bank_meta': dict({
            'offsets': list(offsets),
            'offsets_idx': list(range(len(offsets))),
            'count': len(offsets),
            'relocate': False,
        }, **(extra_meta or {})),
    }
    segments = [seg, *list(foreign)]
    if window is not None:
        seg.update(window)
    inj = _injector({'game': segments})
    for idx, rel in enumerate(offsets):
        struct.pack_into('<I', inj.modified_data, TABLE + 4 * idx, rel)
        # Записи намеренно наезжают друг на друга (смещения 0x20 и 0x21):
        # тест проверяет гард перекрытия, а на неперекрывающихся окнах он
        # не сработал бы. Непустая запись нужна ещё и потому, что запись
        # без терминатора вообще не попадает в список сообщений.
        at = TABLE + rel
        inj.modified_data[at:at + 3] = b'HA\x00'
    return inj, seg


def test_overlap_between_own_records_refuses():
    """Вторая запись налезает на первую — это конфликт, а не «не применилось»."""
    inj, seg = _bank_inj([0x20, 0x21])
    assert inj._inject_bank_segment(seg, ['X', 'Y'], False) is False
    assert inj.last_overlap_report, 'перекрытие не зафиксировано'
    entry = inj.last_overlap_report[-1]
    assert entry['segment'] == 'bank'
    assert 'foreign' not in entry, 'свой-на-свой конфликт не чужой'
    # запись не выполнена: ROM не тронут в зоне второй записи
    assert bytes(inj.modified_data[BASE + 1:BASE + 3]) == b'\x00\x00'


def test_overlap_report_is_created_when_attribute_missing():
    """last_overlap_report может отсутствовать — отчёт обязан создаться."""
    inj, seg = _bank_inj([0x20, 0x21])
    del inj.last_overlap_report
    assert inj._inject_bank_segment(seg, ['X', 'Y'], False) is False
    assert inj.last_overlap_report, 'отчёт не создан заново'


def test_foreign_window_over_record_refuses():
    """Чужое окно поверх нашей записи — конфликт с признаком foreign."""
    other = _plain('other', BASE, BASE + 16)
    inj, seg = _bank_inj([0x20], foreign=[other])
    assert inj._inject_bank_segment(seg, ['X'], False) is False
    assert inj.last_overlap_report[-1].get('foreign') is True


def test_overlap_with_skip_long_keeps_going():
    """skip_long пропускает конфликтную запись, а не откатывает сегмент."""
    other = _plain('other', BASE, BASE + 16)
    inj, seg = _bank_inj([0x20, 0x30], foreign=[other])
    assert inj._inject_bank_segment(seg, ['X', 'Y'], True) is True
    assert inj.last_overlap_report, 'пропуск не зафиксирован'


def _out_of_bounds_inj():
    """Запись с room, выходящим за границу ROM: падать должен safe-inject."""
    inj, seg = _bank_inj([0x20])

    def fake(_segment):
        return [{'offset': 0x20, 'length': 0x1000, 'text': 'AAAA'}]

    inj._extract_bank_messages = fake
    return inj, seg


def test_write_outside_rom_refuses():
    """Запись за границей ROM — отказ, а не запись в никуда."""
    inj, seg = _out_of_bounds_inj()
    assert inj._inject_bank_segment(seg, ['B' * 8], False) is False


def test_write_outside_rom_with_skip_long_does_not_report_success():
    """skip_long не превращает отказ в «успех», если ничего не вставлено.

    Пропуск смягчает отказ, но отчёт о результате остаётся честным: все записи
    вышли за границу ROM, вставлено ноль, значит и результат должен быть False,
    иначе GUI скажет «перевод применён», а в ROM ничего не изменилось.
    """
    inj, seg = _out_of_bounds_inj()
    before = bytes(inj.modified_data)
    assert inj._inject_bank_segment(seg, ['B' * 8], True) is False
    assert bytes(inj.modified_data) == before, 'ROM изменён при отказе'


def test_own_span_of_bank_segment_is_disabled():
    """У банка окно сегмента не «свои байты»: запись может попасть внутрь."""
    seg = {'name': 'b', 'start': 0, 'end': 100,
           'bank_meta': {'offsets': [1]}}
    assert TextInjector._own_span(seg) == (None, None)
