"""Слияние алиасов записей указательной таблицы (plugins/aliased_records)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from plugins.aliased_records import (
    merge_aliased_records,
    merge_terminated_records,
)


def _seg(index: int, start: int, end: int) -> dict:
    return {
        'name': f'seg_{index}',
        'start': start,
        'end': end,
        'pointer_offset': 1000 + index,
    }


class TestExactDuplicates:
    def test_same_window_merged(self):
        out = merge_aliased_records([_seg(1, 0x100, 0x110), _seg(2, 0x100, 0x110)])
        assert len(out) == 1
        assert out[0]['name'] == 'seg_1'
        assert out[0]['aliased_slots'] == 2
        assert out[0]['pointer_offsets'] == [1001, 1002]

    def test_distinct_windows_untouched(self):
        src = [_seg(1, 0x100, 0x110), _seg(2, 0x200, 0x210)]
        out = merge_aliased_records(src)
        assert [s['name'] for s in out] == ['seg_1', 'seg_2']
        assert 'aliased_slots' not in out[0]

    def test_three_way_alias_keeps_all_slots(self):
        src = [_seg(5, 0x300, 0x320), _seg(6, 0x300, 0x320), _seg(7, 0x300, 0x320)]
        out = merge_aliased_records(src)
        assert len(out) == 1
        assert out[0]['pointer_offsets'] == [1005, 1006, 1007]
        assert out[0]['aliased_slots'] == 3

    def test_order_preserved(self):
        src = [_seg(1, 0x100, 0x110), _seg(2, 0x900, 0x910),
               _seg(3, 0x100, 0x110)]
        out = merge_aliased_records(src)
        assert [s['name'] for s in out] == ['seg_1', 'seg_2']

    def test_no_pointer_offset_passes_through(self):
        loose = {'name': 'loose', 'start': 1, 'end': 2}
        src = [loose, _seg(1, 0x100, 0x110)]
        out = merge_aliased_records(src)
        assert out[0] is loose

    def test_bad_types_passthrough(self):
        bad = {'name': 'bad', 'start': True, 'end': 0x110, 'pointer_offset': 5}
        out = merge_aliased_records([bad])
        assert out == [bad]

    def test_different_start_not_merged_in_exact_mode(self):
        # Точный режим группирует по (start, end): разные старты — разные
        # записи, даже если конец совпал. Суффиксное слияние — отдельная
        # функция (см. TestTerminatedSuffixes).
        src = [_seg(9, 0x300, 0x320), _seg(2, 0x100, 0x320)]
        out = merge_aliased_records(src)
        assert len(out) == 2


class TestTerminatedSuffixes:
    def test_suffix_kept_as_readonly_alias(self):
        # Суффикс НЕ удаляется: иначе после перезаписи канонической записи
        # (extent сдвигается) он исчезает из манифеста при повторном скане.
        # Он остаётся отдельным read-only сегментом.
        src = [_seg(1, 0x100, 0x120), _seg(2, 0x110, 0x120)]
        out = merge_terminated_records(src)
        assert len(out) == 2
        canonical, alias = out
        assert canonical['name'] == 'seg_1'
        assert canonical['aliased_slots'] == 1
        assert canonical['aliased_suffixes'] == 1
        assert alias['name'] == 'seg_2'
        assert alias['injectable'] is False
        assert alias['alias_of'] == 'seg_1'
        assert alias['start'] == 0x110

    def test_exact_duplicates_still_merged_and_count_drops(self):
        src = [_seg(1, 0x100, 0x120), _seg(2, 0x100, 0x120)]
        out = merge_terminated_records(src)
        assert len(out) == 1
        assert out[0]['aliased_slots'] == 2
        assert out[0]['aliased_suffixes'] == 0

    def test_suffix_readonly_never_writable(self):
        src = [_seg(1, 0x100, 0x120), _seg(2, 0x110, 0x120)]
        out = merge_terminated_records(src)
        writable = [s for s in out if s.get('injectable') is not False]
        assert len(writable) == 1
        assert writable[0]['start'] == 0x100

    def test_three_suffixes_all_kept(self):
        src = [_seg(1, 0x100, 0x120), _seg(2, 0x108, 0x120),
               _seg(3, 0x110, 0x120)]
        out = merge_terminated_records(src)
        assert len(out) == 3
        assert sum(1 for s in out if s.get('injectable') is False) == 2

    def test_different_ends_not_merged(self):
        src = [_seg(1, 0x100, 0x120), _seg(2, 0x100, 0x130)]
        out = merge_terminated_records(src)
        assert len(out) == 2

    def test_contained_record_never_becomes_canonical(self):
        src = [_seg(1, 0x110, 0x120), _seg(2, 0x100, 0x120)]
        out = merge_terminated_records(src)
        assert len(out) == 2
        writable = [s for s in out if s.get('injectable') is not False]
        assert writable[0]['start'] == 0x100


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
