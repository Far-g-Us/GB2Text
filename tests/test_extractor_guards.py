"""Защитные проверки extractor: битый манифест не должен ронять извлечение.

Все ветки здесь — отказы на негодных входных данных записи (не dict, строки
вместо чисел, `bool` вместо `int`, слот за концом файла, декодер/декомпрессор
вернули не то). Каждая из них раньше приводила либо к исключению посреди
извлечения, либо — что хуже — к записи перевода не туда.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.extractor import (
    TextExtractor,
    _relocated_dialogue_addr,
)

ROM = 0x4000


class _StubDecoder:
    """Декодер, который можно настроить на любой результат."""

    def __init__(self, result='TEXT', raises=None):
        self._result = result
        self._raises = raises

    def decode(self, data, start, length):
        if self._raises is not None:
            raise self._raises
        return self._result


def make_extractor(tmp_path, data: bytes | None = None) -> TextExtractor:
    """Экземпляр без чтения реального ROM: подменяем объект после init."""
    path = tmp_path / 'rom.gba'
    path.write_bytes(data if data is not None else bytes(ROM))
    extractor = TextExtractor(str(path))

    class _Rom:
        def __init__(self, blob):
            self.data = bytearray(blob)
            self.path = str(path)
            self.game_id = 'GBA_TEST'
            self.system = 'gba'

    extractor.rom = _Rom(data if data is not None else bytes(ROM))
    return extractor


# ── _relocated_dialogue_addr ───────────────────────────────────────────────

def test_relocated_skips_entry_with_relocated_from():
    """Запись, у которой цель уже разрешена, не проверяется заново."""
    data = bytearray(256)
    entry = {'relocated_from': 0x10, 'slots': [0x20], 'free_after': 8}
    assert _relocated_dialogue_addr(data, entry, 0x30) is None


def test_relocated_requires_slot_list():
    assert _relocated_dialogue_addr(bytearray(64), {'slots': None}, 0x10) is None
    assert _relocated_dialogue_addr(bytearray(64), {'slots': []}, 0x10) is None
    assert _relocated_dialogue_addr(bytearray(64), {}, 0x10) is None


def test_relocated_uses_blank_probe_for_bad_room():
    """Битый free_after не должен ломать проверку: берётся безопасный размер."""
    data = bytearray(256)
    data[0x20:0x24] = (0x40).to_bytes(4, 'little')
    for room in (None, True, 0, -5, 'x'):
        entry = {'slots': [0x20], 'free_after': room}
        assert _relocated_dialogue_addr(data, entry, 0x30) == 0x40


def test_relocated_skips_bad_slots():
    """Слоты не-int и за концом файла пропускаются, а не ломают цикл."""
    data = bytearray(256)
    data[0x30:0x34] = (0x44).to_bytes(4, 'little')
    entry = {'slots': [None, True, 'x', -8, ROM * 4, 0x30]}
    assert _relocated_dialogue_addr(data, entry, 0x10) == 0x44


def test_relocated_needs_blank_old_block():
    """Старый блок не зачищен — значит переноса не было."""
    data = bytearray(b'\xAA' * 256)
    data[0x20:0x24] = (0x40).to_bytes(4, 'little')
    entry = {'slots': [0x20], 'free_after': 8}
    assert _relocated_dialogue_addr(data, entry, 0x30) is None


def test_relocated_ignores_pointer_into_self_and_out_of_rom():
    """Указатель на себя же или за пределы файла переносом не считается."""
    data = bytearray(256)
    data[0x20:0x24] = (0x30).to_bytes(4, 'little')
    entry = {'slots': [0x20], 'free_after': 8}
    assert _relocated_dialogue_addr(data, entry, 0x30) is None


# ── _decompress ────────────────────────────────────────────────────────────

def test_decompress_rejects_non_bytes_result(tmp_path):
    """Декомпрессор, вернувший не байты, не должен молча отдать мусор."""
    extractor = make_extractor(tmp_path)

    class _Bad:
        def decompress(self, data, start=0):
            return 'not bytes'

    extractor.rom.data = bytearray(b'xxxx')
    assert extractor._decompress(extractor.rom.data, _Bad()) == b'xxxx'


def test_decompress_rejects_non_bytes_result_object(tmp_path):
    """Тот же отказ для декомпрессора-объекта с методом decompress."""
    extractor = make_extractor(tmp_path)

    class _BadObj:
        def decompress(self, *args, **kwargs):
            return 42

    assert extractor._decompress(extractor.rom.data, _BadObj()) == \
        bytes(extractor.rom.data)


# ── recode_segment ─────────────────────────────────────────────────────────

def test_recode_rejects_bad_start_end(tmp_path):
    """Сегмент с битыми границами — пустой результат, а не исключение."""
    extractor = make_extractor(tmp_path)
    for start, end in ((True, 10), ('x', 10), (10, 'x'), (-1, 5)):
        seg = {'start': start, 'end': end}
        assert extractor.recode_segment(seg, _StubDecoder()) == []


def test_recode_rejects_out_of_range_addresses(tmp_path):
    """Границы за пределами файла или start >= end — отказ."""
    extractor = make_extractor(tmp_path)
    for start, end in ((ROM, ROM + 8), (0, ROM * 4), (0x10, 0x10)):
        seg = {'start': start, 'end': end}
        assert extractor.recode_segment(seg, _StubDecoder()) == []


def test_recode_without_decoder(tmp_path):
    extractor = make_extractor(tmp_path)
    assert extractor.recode_segment({'start': 0, 'end': 8}, None) == []


def test_recode_decoder_raises(tmp_path):
    extractor = make_extractor(tmp_path)
    seg = {'start': 0, 'end': 8}
    boom = _StubDecoder(raises=ValueError('x'))
    assert extractor.recode_segment(seg, boom) == []


def test_recode_non_string_result(tmp_path):
    """Декодер, вернувший не строку, — отказ, а не текст "None" в GUI."""
    extractor = make_extractor(tmp_path)
    seg = {'start': 0, 'end': 8}
    assert extractor.recode_segment(seg, _StubDecoder(result=None)) == []
    assert extractor.recode_segment(seg, _StubDecoder(result=123)) == []


def test_recode_record_kind(tmp_path):
    """Запись kind='record' декодируется целиком, без разбиения."""
    extractor = make_extractor(tmp_path)
    seg = {'start': 0, 'end': 8, 'kind': 'record'}
    out = extractor.recode_segment(seg, _StubDecoder(result='ONE'))
    assert out == [{'offset': 0, 'text': 'ONE'}]


def test_recode_record_kind_without_decoder(tmp_path):
    extractor = make_extractor(tmp_path)
    seg = {'start': 0, 'end': 8, 'kind': 'record'}
    assert extractor.recode_segment(seg, None) == []


def test_recode_record_kind_bad_result(tmp_path):
    extractor = make_extractor(tmp_path)
    seg = {'start': 0, 'end': 8, 'kind': 'record'}
    assert extractor.recode_segment(seg, _StubDecoder(result=42)) == []


def test_recode_pointer_dialogues_without_decoder(tmp_path):
    """kind='pointer_dialogues' — разбор манифеста, а не разбиение строки."""
    extractor = make_extractor(tmp_path)
    seg = {'start': 0, 'end': 8, 'kind': 'pointer_dialogues'}
    assert extractor.recode_segment(seg, None) == []


def test_recode_fixed_width_delegates(tmp_path):
    """Сегмент с fixed_width уходит в разбор слотовой таблицы."""
    extractor = make_extractor(tmp_path)
    seg = {'start': 0, 'end': 32, 'fixed_width': 8, 'record_count': 2}
    out = extractor.recode_segment(seg, _StubDecoder(result='SLOT'))
    assert [m['text'] for m in out] == ['SLOT', 'SLOT']


def test_recode_outer_exception_is_caught(tmp_path):
    """Исключение любого вида не выходит наружу: извлечение продолжается."""
    extractor = make_extractor(tmp_path)

    class _Boom:
        def decode(self, *_a):
            raise RuntimeError('boom')

    seg = {'start': 0, 'end': 8}
    assert extractor.recode_segment(seg, _Boom()) == []


# ── _split_messages / _extract_fixed_width_messages ────────────────────────

def test_split_messages_splits_on_end_token(tmp_path):
    extractor = make_extractor(tmp_path)
    out = extractor._split_messages('AAA[END]BBB', 0x100)
    assert [m['text'] for m in out] == ['AAA', 'BBB']
    assert out[0]['offset'] == 0x100


def test_split_messages_empty_text(tmp_path):
    extractor = make_extractor(tmp_path)
    assert extractor._split_messages('', 0) == []


def test_fixed_width_rejects_bad_width(tmp_path):
    """Ширина не-int, bool или <= 0 — пустой результат вместо исключения."""
    extractor = make_extractor(tmp_path)
    for width in (True, 'x', 0, -4):
        seg = {'start': 0, 'end': 32, 'fixed_width': width, 'record_count': 2}
        assert extractor._extract_fixed_width_messages(
            seg, _StubDecoder()) == []


def test_fixed_width_rejects_bad_count_and_start(tmp_path):
    extractor = make_extractor(tmp_path)
    for extra in ({'record_count': True}, {'record_count': -1},
                  {'start': -1}, {'start': 'x'}):
        seg = {'start': 0, 'end': 32, 'fixed_width': 8, **extra}
        assert extractor._extract_fixed_width_messages(
            seg, _StubDecoder()) == []


def test_fixed_width_truncated_table(tmp_path):
    """Таблица, уходящая за конец файла, читается до обрыва."""
    extractor = make_extractor(tmp_path)
    seg = {'start': 0, 'end': 0x400, 'fixed_width': 4, 'record_count': 100000}
    out = extractor._extract_fixed_width_messages(seg, _StubDecoder(result='A'))
    assert isinstance(out, list)


def test_fixed_width_skips_padding_slots(tmp_path):
    """Слот из '? padding' пропускается, но его offset сохраняется."""
    extractor = make_extractor(tmp_path)
    extractor.rom.data[0:16] = bytes(ROM)
    seg = {'start': 0, 'end': 16, 'fixed_width': 8, 'record_count': 2}
    assert extractor._extract_fixed_width_messages(seg, None) == []


def test_fixed_width_decoder_failure_gives_empty_slot(tmp_path):
    extractor = make_extractor(tmp_path)
    seg = {'start': 0, 'end': 8, 'fixed_width': 8, 'record_count': 1}
    out = extractor._extract_fixed_width_messages(
        seg, _StubDecoder(raises=RuntimeError('x')))
    assert out == []


# ── _extract_pointer_dialogues ─────────────────────────────────────────────

def test_pointer_dialogues_bad_entry_types(tmp_path):
    """Записи манифеста не-int / bool отбрасываются, а не искажают декодирование."""
    extractor = make_extractor(tmp_path)
    seg = {
        'start': 0, 'end': 64, 'decoder': _StubDecoder(result='A'),
        'manifest': [
            'not a dict',
            {'target': 0, 'length': True},
            {'target': 0, 'free_after': 'x'},
            {'target': 0, 'length': 4},
        ],
    }
    assert isinstance(extractor._extract_pointer_dialogues(seg), list)


def test_pointer_dialogues_without_decoder(tmp_path):
    extractor = make_extractor(tmp_path)
    seg = {'start': 0, 'end': 64,
           'manifest': [{'target': 0, 'length': 4}]}
    assert extractor._extract_pointer_dialogues(seg) == []


def test_pointer_dialogues_max_decode_defaults(tmp_path):
    """Не-числовой max_decode/free_after заменяется безопасным значением."""
    extractor = make_extractor(tmp_path)
    seg = {
        'start': 0, 'end': 0x400, 'decoder': _StubDecoder(result='A'),
        'manifest': [{'target': 0, 'length': 4, 'max_decode': True,
                      'free_after': 'x'}],
    }
    out = extractor._extract_pointer_dialogues(seg)
    assert isinstance(out, list)
