"""Overlap/safe-inject гарды сжатого и generic-пути (`inject_segment`).

Тот же класс защит, что и в банковом пути: перекрытие с чужой записью, выход за
границу ROM, декодер без `encode`. Фикстур — лёгкий `_injector()` на 512 байт
из `tests/test_injector_foreign_ranges.py`, без файлов на диске.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from tests.test_injector_foreign_ranges import (
    ROM_SIZE,
    _AsciiDecoder,
    _injector,
    _plain,
)

BASE = 0x40
END = BASE + 16


def _plugin(segments):
    class P:
        def get_text_segments(self, rom):
            return segments

    return P()


def _compressed_inj(*, payload=b'ZZZ', foreign=(), start=BASE, end=END,
                    encoder=None):
    seg = {
        'name': 'comp',
        'start': start,
        'end': end,
        'decoder': _AsciiDecoder(),
        'compression': 'huffman',
        'encoder': encoder or (lambda text: payload),
    }
    inj = _injector({'game': [seg, *list(foreign)]})
    return inj, seg


def test_compressed_injects_when_free():
    inj, seg = _compressed_inj()
    assert inj.inject_segment('comp', ['A'], _plugin([seg]),
                              segments=[seg]) is True


def test_compressed_overlap_refuses_and_creates_report():
    """Отчёт о перекрытии создаётся, даже если атрибута не было."""
    inj, seg = _compressed_inj()
    inj._tracked_spans().append((BASE, BASE + 8))
    del inj.last_overlap_report
    assert inj.inject_segment('comp', ['A'], _plugin([seg]),
                              segments=[seg]) is False
    assert inj.last_overlap_report, 'отчёт не создан'
    entry = inj.last_overlap_report[-1]
    assert entry['segment'] == 'comp' and entry['index'] == 0
    assert entry['offset'] == BASE
    assert 'foreign' not in entry, 'свой конфликт не помечен как чужой'


def test_compressed_foreign_window_refuses():
    other = _plain('other', BASE, END)
    inj, seg = _compressed_inj(foreign=[other])
    assert inj.inject_segment('comp', ['A'], _plugin([seg]),
                              segments=[seg]) is False
    assert inj.last_overlap_report[-1].get('foreign') is True


def test_overlap_report_recreated_when_set_to_none():
    """Если атрибут обнулён прямо в момент проверки — отчёт создаётся заново."""
    inj, seg = _compressed_inj()

    def foreign_and_clear(*a, **kw):
        inj.last_overlap_report = None
        return True

    inj._foreign_hit = foreign_and_clear
    assert inj.inject_segment('comp', ['A'], _plugin([seg]),
                              segments=[seg]) is False
    assert inj.last_overlap_report, 'отчёт не создан'
    assert inj.last_overlap_report[-1].get('foreign') is True


@pytest.mark.parametrize('skip_long', [True, False])
def test_compressed_out_of_rom_refuses(skip_long):
    """payload не помещается в остаток ROM — отказ в обоих режимах."""
    inj, seg = _compressed_inj(start=ROM_SIZE - 2, end=ROM_SIZE + 4,
                               payload=b'X' * 8)
    before = bytes(inj.modified_data)
    assert inj.inject_segment('comp', ['A'], _plugin([seg]),
                              segments=[seg],
                              skip_long=skip_long) is False
    assert bytes(inj.modified_data) == before, 'ROM изменён при отказе'


def test_compressed_too_long_skips_or_refuses():
    """Перевод длиннее сжатого окна: отказ, ROM не тронут."""
    inj, seg = _compressed_inj(payload=b'X' * 64)
    before = bytes(inj.modified_data)
    assert inj.inject_segment('comp', ['A'], _plugin([seg]),
                              segments=[seg],
                              skip_long=False) is False
    assert bytes(inj.modified_data) == before, 'ROM изменён при отказе'


def test_compressed_extra_translations_truncated():
    """Сжатый сегмент ждёт одну строку: лишние отбрасываются с предупреждением."""
    inj, seg = _compressed_inj()
    assert inj.inject_segment('comp', ['A', 'B'], _plugin([seg]),
                              segments=[seg]) is True


def test_compressed_empty_translations_is_noop():
    inj, seg = _compressed_inj()
    assert inj.inject_segment('comp', [], _plugin([seg]),
                              segments=[seg]) is True


@pytest.mark.parametrize('skip_long', [True, False])
def test_compressed_encoder_non_bytes_fails(skip_long):
    inj, seg = _compressed_inj(encoder=lambda text: 'not bytes')
    assert inj.inject_segment('comp', ['A'], _plugin([seg]),
                              segments=[seg],
                              skip_long=skip_long) is False


def test_fit_report_failure_does_not_block_write(monkeypatch):
    """Исключение fit_report не должно менять поведение записи (report-only)."""
    import core.textbox as textbox

    def boom(*a, **kw):
        raise RuntimeError('fit не работает')

    monkeypatch.setattr(textbox, 'fit_report', boom)
    inj, seg = _compressed_inj()
    before = bytes(inj.modified_data)
    assert inj.inject_segment('comp', ['A'], _plugin([seg]),
                              segments=[seg]) is True
    assert inj.last_fit_report == [], 'отчёт не сброшен в пустой'
    assert inj.modified_data != before, 'запись не выполнена'


@pytest.mark.parametrize('exc', [ValueError, KeyError, IndexError, TypeError])
def test_recompress_failure_is_reported_not_raised(exc):
    """Энкодер может упасть — это отказ по переводу, а не исключение наружу."""
    def broken(text, _exc=exc):
        raise _exc('recompress failed')

    inj, seg = _compressed_inj(encoder=broken)
    before = bytes(inj.modified_data)
    assert inj.inject_segment('comp', ['A'], _plugin([seg]),
                              segments=[seg]) is False
    assert bytes(inj.modified_data) == before, 'ROM изменён при отказе'


class _DecodeOnly:
    """Декодер без `encode`: сегмент extract-only."""

    def decode(self, data, start, length):
        return bytes(data[start:start + length]).split(b'\x00')[0].decode(
            'ascii', 'replace')


def _generic_inj(decoder):
    """Сегмент generic-пути с НЕПУСТЫМ окном.

    Непустое окно обязательно: иначе отказ случится раньше гарда (на
    несовпадении числа окон), и проверка станет пустой. Данные кладутся в
    `rom.data`, а не в `modified_data`: оригиналы читаются именно оттуда.
    """
    seg = {'name': 'gen', 'start': BASE, 'end': BASE + 6,
           'decoder': decoder, 'compression': None}
    inj = _injector({'game': [seg]})
    inj.rom.data[BASE:BASE + 2] = b'Hi'
    return inj, seg


def test_decoder_without_encode_is_extract_only():
    """Декодер без encode: отказ и предупреждение, а не AttributeError."""
    inj, seg = _generic_inj(_DecodeOnly())
    assert inj._extract_original_messages(seg), (
        'окно должно содержать текст, иначе тест ничего не проверяет')
    before = bytes(inj.modified_data)
    assert inj.inject_segment('gen', ['A'], _plugin([seg]),
                              segments=[seg]) is False
    assert bytes(inj.modified_data) == before


def test_segment_without_decoder_refuses(monkeypatch):
    """У сегмента нет декодера, и построить его не удалось — отказ.

    Реальный путь: плагин отдал сегмент без decoder, а `auto_detect_charmap`
    на его данных упал. Гард обязан отказать, а не упасть на `encode`.
    """
    import core.scanner as scanner

    def boom(*a, **kw):
        raise ValueError('charmap не определился')

    monkeypatch.setattr(scanner, 'auto_detect_charmap', boom)
    inj, seg = _generic_inj(None)
    assert inj._extract_original_messages(seg), (
        'окно должно содержать текст, иначе тест ничего не проверяет')
    before = bytes(inj.modified_data)
    assert inj.inject_segment('gen', ['A'], _plugin([seg]),
                              segments=[seg]) is False
    assert bytes(inj.modified_data) == before
    assert seg.get('decoder') is None, (
        'отказ обязан быть вызван отсутствием decoder, иначе гард не проверен')


@pytest.mark.parametrize('encoder,reason_slug', [
    (lambda text: b'X' * 64, 'compressed_too_long'),
    (lambda text: 'not bytes', 'compressed_encoder_non_bytes'),
    (lambda text: (_ for _ in ()).throw(
        ValueError('char 0x01 not encodable after 0x03')),
     'compressed_recompress_failed'),
])
def test_compressed_refusal_records_reason(encoder, reason_slug):
    """Отказ сжатого пути обязан быть виден: причина попадает в отчёт.

    Отчёт отдельный (`last_compress_report`), а не `last_affix_report`:
    последний участвует в счёте пропусков в
    `tests/test_realrom_pipeline.py::_inject_all`, и причина «поток не
    представим» не должна выглядеть как «переводчик пропустил сообщение».
    """
    inj, seg = _compressed_inj(encoder=encoder)
    before = bytes(inj.modified_data)
    assert inj.inject_segment('comp', ['A'], _plugin([seg]),
                              segments=[seg]) is False
    assert bytes(inj.modified_data) == before
    report = getattr(inj, 'last_compress_report', [])
    assert len(report) == 1, report
    entry = report[0]
    assert entry['segment'] == 'comp'
    assert entry['reason'].startswith(reason_slug)
    assert entry['offset'] == seg['start']


def test_compressed_report_is_reset_per_segment():
    """Отчёт не должен протекать между сегментами (контракт гейта)."""
    inj, seg = _compressed_inj(
        encoder=lambda text: (_ for _ in ()).throw(
            ValueError('char 0x01 not encodable after 0x03')))
    assert inj.inject_segment('comp', ['A'], _plugin([seg]),
                              segments=[seg]) is False
    first = getattr(inj, 'last_compress_report', [])
    assert [e['segment'] for e in first] == ['comp']
    seg2 = dict(seg, name='comp2', start=seg['start'] + 16,
                end=seg['end'] + 16)
    inj.inject_segment('comp2', ['A'], _plugin([seg2]), segments=[seg2])
    # Запись ПЕРВОГО сегмента не должна дожить до второго вызова.
    assert [e['segment'] for e in getattr(inj, 'last_compress_report', [])] \
        == ['comp2']


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))

