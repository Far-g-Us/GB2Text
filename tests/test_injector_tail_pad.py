"""Флаг tail_pad в pointer-вставке: хвост окна затирается или сохраняется.

tail_pad включён только у Oracle of Seasons, где окно записи равно самой
записи и хвост после терминатора — padding. У остальных игр (Pokemon) хвост
содержит 0xFF-пады и соседние данные, и затирание вешало загрузку, поэтому
по умолчанию поведение прежнее.
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.injector import TextInjector

BASE = 0x08000000


class _ToyDecoder:
    def decode(self, data, start, length):
        chunk = bytes(data[start:start + length])
        return chunk.split(b'\x00')[0].decode('ascii', 'replace')

    def encode(self, text):
        return text.encode('ascii')


def _injector(blobs: dict[int, bytes], size: int = 512) -> TextInjector:
    inj = TextInjector.__new__(TextInjector)

    class _FakeROM:
        def __init__(self, data):
            self.data = bytearray(data)

    inj.rom = _FakeROM(bytearray(size))
    inj.original_data = bytearray(size)
    inj.modified_data = bytearray(size)
    inj._segment_cache = {}
    inj._bank_segments = []
    inj._taken_free_blocks = []
    inj._written_spans = []
    inj.last_overflow_report = []
    inj.last_relocate_report = []
    inj.last_overlap_report = []
    inj.last_spellcheck_report = []
    inj.last_fit_report = []
    inj.last_unmapped_chars = []
    inj.logger = logging.getLogger('test')
    for addr, blob in blobs.items():
        inj.rom.data[addr:addr + len(blob)] = blob
        inj.modified_data[addr:addr + len(blob)] = blob
    return inj


def _segment(tail_pad: bool | None = None, pad_byte: int = 0x00,
             name: str = 'toy') -> dict:
    seg = {
        'name': name,
        'kind': 'pointer_dialogues',
        'start': 0,
        'end': 0,
        'decoder': _ToyDecoder(),
        'terminator': b'\x00',
        'terminators': [0x00],
        'manifest': [{'target': 16, 'free_after': 16, 'slots': []}],
    }
    if tail_pad is not None:
        seg['tail_pad'] = tail_pad
    if tail_pad:
        seg['pad_byte'] = pad_byte
    return seg


def test_tail_preserved_by_default():
    inj = _injector({16: b'OLDTEXT\x00' + b'\xaa' * 8})
    seg = _segment()
    assert inj._inject_pointer_dialogues(seg, ['NEW'], True) is True
    window = bytes(inj.modified_data[16:32])
    assert window.startswith(b'NEW\x00')
    # хвост сохранён дословно: остаток исходной записи 'EXT\x00' + 0xAA*8
    assert window[4:] == b'EXT\x00' + b'\xaa' * 8


def test_tail_padded_when_flag_set():
    inj = _injector({16: b'OLDTEXT\x00' + b'\xaa' * 8})
    seg = _segment(tail_pad=True, pad_byte=0x00)
    assert inj._inject_pointer_dialogues(seg, ['NEW'], True) is True
    assert bytes(inj.modified_data[16:32]) == b'NEW\x00' + b'\x00' * 12


def test_tail_pad_custom_byte():
    inj = _injector({16: b'OLDTEXT\x00' + b'\xaa' * 8})
    seg = _segment(tail_pad=True, pad_byte=0xFF)
    assert inj._inject_pointer_dialogues(seg, ['NEW'], True) is True
    assert bytes(inj.modified_data[16:32]) == b'NEW\x00' + b'\xff' * 12


def test_tail_pad_bad_pad_byte_falls_back_to_zero():
    inj = _injector({16: b'OLDTEXT\x00' + b'\xaa' * 8})
    seg = _segment(tail_pad=True)
    seg['pad_byte'] = 'нет'  # тип-еровер: молча откатываемся на 0x00
    assert inj._inject_pointer_dialogues(seg, ['NEW'], True) is True
    assert bytes(inj.modified_data[16:32]) == b'NEW\x00' + b'\x00' * 12


def test_tail_pad_exact_fit_leaves_nothing_to_pad():
    inj = _injector({16: b'0123456789ABCDEF'})
    seg = _segment(tail_pad=True)
    assert inj._inject_pointer_dialogues(seg, ['X' * 15], True) is True
    assert bytes(inj.modified_data[16:32]) == b'X' * 15 + b'\x00'


def test_tail_pad_too_long_reports_overflow():
    inj = _injector({16: b'OLDTEXT\x00' + b'\xaa' * 8})
    seg = _segment(tail_pad=True)
    assert inj._inject_pointer_dialogues(seg, ['X' * 20], True) is False
    assert len(inj.last_overflow_report) == 1
    assert bytes(inj.modified_data[16:32]) == b'OLDTEXT\x00' + b'\xaa' * 8


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
