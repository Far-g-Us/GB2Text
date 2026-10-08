"""Закрытие пробелов покрытия: валидация таблиц, слияние алиасов, ML-конфиг.

Все тесты — про отказ на некорректных входных данных. Эти ветки важны
не для процента покрытия, а потому что каждый из них защищает запись в
ROM: молча пропустив битый индекс или не-числовой offset, инжектор записал
бы перевод не туда.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ml_classifier import (
    ML_JOBS_ENV,
    SKLEARN_AVAILABLE,
    _resolve_n_jobs,
    _sklearn_available,
)
from core.pointer_table import patch_pointer_range
from plugins.aliased_records import merge_terminated_records


def rom(size: int = 0x400) -> bytearray:
    return bytearray(size)


# ── core/ml_classifier.py ──────────────────────────────────────────────────

def test_resolve_n_jobs_env_values(monkeypatch):
    """Переменная окружения управляет числом потоков, мусор в ней безопасен."""
    monkeypatch.delenv(ML_JOBS_ENV, raising=False)
    assert _resolve_n_jobs() == 1
    monkeypatch.setenv(ML_JOBS_ENV, '4')
    assert _resolve_n_jobs() == 4
    # Не число → предупреждение и безопасная единица, а не исключение.
    monkeypatch.setenv(ML_JOBS_ENV, 'много')
    assert _resolve_n_jobs() == 1
    # Вне разумного диапазона → тоже единица.
    monkeypatch.setenv(ML_JOBS_ENV, '0')
    assert _resolve_n_jobs() == 1
    monkeypatch.setenv(ML_JOBS_ENV, '10000')
    assert _resolve_n_jobs() == 1


def test_sklearn_available_matches_flag():
    """find_spec не исполняет пакет — флаг обязан совпадать с реальностью."""
    assert _sklearn_available() == SKLEARN_AVAILABLE


# ── core/pointer_table.py ──────────────────────────────────────────────────

def test_patch_pointer_range_rejects_bad_index_mapping():
    """Индекс, который бросает исключение, обязан дать отказ целиком."""

    def boom(_i):
        raise KeyError('нет такого индекса')

    assert patch_pointer_range(rom(), 0x10, 0, 2, [0x20, 0x30],
                               index_of=boom) is False


def test_patch_pointer_range_rejects_bad_index_type():
    """Не-int и bool вместо индекса — отказ, а не запись по 0xFFFF."""
    assert patch_pointer_range(rom(), 0x10, 0, 1, [0x20],
                               index_of=lambda _i: True) is False
    assert patch_pointer_range(rom(), 0x10, 0, 1, [0x20],
                               index_of=lambda _i: 'x') is False


def test_patch_pointer_range_rejects_bad_offsets():
    """Отрицательный и не-числовой offset — отказ."""
    assert patch_pointer_range(rom(), 0x10, 0, 1, [-1]) is False
    assert patch_pointer_range(rom(), 0x10, 0, 1, ['x']) is False
    assert patch_pointer_range(rom(), 0x10, 0, 1, [True]) is False


def test_patch_pointer_range_accepts_identity():
    """Рабочий случай: два указателя пишутся по порядку."""
    data = rom()
    assert patch_pointer_range(data, 0x10, 0, 2, [0x20, 0x30]) is True
    assert data[0x10:0x14] == (0x20 + 0x08000000).to_bytes(4, 'little')
    assert data[0x14:0x18] == (0x30 + 0x08000000).to_bytes(4, 'little')


def test_patch_pointer_range_out_of_bounds():
    """Выход за конец data — отказ без частичной записи.

    Размер выбран так, чтобы ПЕРВЫЙ слот помещался в файл, а второй — нет:
    при планировании впереди записи указатель 0 должен остаться незаписанным.
    Мутирование `patch_pointer_range` на запись без планирования роняет этот
    тест, то есть инвариант реально защищён.
    """
    data = rom(0x1E)
    # слот 0: 0x18..0x1C влезает; слот 1: 0x1C..0x20 — нет
    assert patch_pointer_range(data, 0x18, 0, 2, [0x30, 0x40]) is False
    assert bytes(data) == bytes(0x1E), 'данные не должны меняться при отказе'


# ── plugins/aliased_records.py ─────────────────────────────────────────────

def test_merge_keeps_segments_without_usable_numbers():
    """Сегмент без числовых start/end/cell не сливается и не теряется."""
    segs = [
        {'name': 'a', 'start': 0x10, 'end': 0x20, 'pointer_offset': 1},
        {'name': 'no-numbers'},
        {'name': 'bad-range', 'start': 0x30, 'end': 0x30,
         'pointer_offset': 3},
        {'name': 'inverted', 'start': 0x50, 'end': 0x40,
         'pointer_offset': 4},
    ]
    out = merge_terminated_records(segs)
    names = [s.get('name') for s in out]
    # Все четыре на месте, ни один не потерян и не слит с чужим.
    assert set(names) >= {'a', 'no-numbers', 'bad-range', 'inverted'}
    assert len(out) == 4


def test_merge_non_dict_entries_are_kept():
    """Не-dict в списке не должен ронять слияние."""
    out = merge_terminated_records([None, 'x',
                                   {'name': 'ok', 'start': 1, 'end': 2,
                                    'pointer_offset': 1}])
    assert any(not isinstance(s, dict) for s in out)


def test_merge_suffix_becomes_readonly_alias():
    """Суффикс с тем же концом становится read-only алиасом канонической.

    Удалять его нельзя: после перезаписи канонической записи extent сдвинется,
    и исчезнувший сегмент выпадет из манифеста при повторном скане. Поэтому он
    остаётся отдельным сегментом, но писать в него запрещено.
    """
    base = {'name': 'host', 'start': 0x100, 'end': 0x140, 'pointer_offset': 1}
    suffix = {'name': 'tail', 'start': 0x120, 'end': 0x140, 'pointer_offset': 2}
    out = merge_terminated_records([base, suffix])
    assert len(out) == 2
    canonical = next(x for x in out if x.get('name') == 'host')
    alias = next(x for x in out if x.get('name') == 'tail')
    assert canonical['start'] == 0x100
    assert alias['injectable'] is False
    assert alias['alias_of'] == 'host'
    assert alias['alias_start'] == 0x100
    assert canonical['aliased_suffixes'] == 1


def test_merge_keeps_original_order_of_loose():
    """Loose-сегменты сохраняют взаимный порядок."""
    segs = [
        {'name': 'first'},
        {'name': 'second'},
        {'name': 'host', 'start': 0x10, 'end': 0x20, 'pointer_offset': 1},
    ]
    out = merge_terminated_records(segs)
    names = [s.get('name') for s in out]
    assert names.index('first') < names.index('second')
