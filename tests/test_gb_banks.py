"""Тесты bank-aware адресации и поиска указателей GB/GBC.

Проверяется главное свойство: пара `(bank_byte, addr16)` не подменяется
одним числом, а адрес, которого нет в ROM, даёт None, а не
правдоподобный мусор. Ошибка здесь стоит записи поверх игровых данных.
"""
import os
import sys
from typing import cast

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gb_banks import (
    BANK0_ROM_END,
    BANK_SIZE,
    RAM_START,
    BankPointer,
    PointerKind,
    bank_count,
    bank_span,
    classify_pointer,
    group_pointer_runs,
    scan_bank_pointers,
    scan_banked_rows,
    to_bank_addr,
    to_offset,
)

ROM_2MB = 0x200000
ROM_1_5MB = 0x180000


# ── геометрия банков ───────────────────────────────────────────────────────

def test_bank_count_rounds_up():
    assert bank_count(BANK_SIZE) == 1
    assert bank_count(2 * BANK_SIZE) == 2
    assert bank_count(ROM_1_5MB) == 96  # ровно 96 банков по 16 КиБ
    assert bank_count(0) == 0


def test_bank_size_zero_rejected():
    with pytest.raises(ValueError):
        bank_count(ROM_2MB, bank_size=0)


def test_bank_span_clips_last_bank():
    """ROM не выровнен по банку: последний банк короче, и адресов за его
    концом НЕТ. Модуль не подставляет 0xFFFF на месте отсутствующих байтов."""
    start, stop = bank_span(ROM_1_5MB, 96)  # банка 96 в этом ROM уже нет
    assert start == 96 * BANK_SIZE == ROM_1_5MB
    assert stop == ROM_1_5MB
    # а 95-й банк обрезан хвостом файла
    start95, stop95 = bank_span(ROM_1_5MB, 95)
    assert start95 == 95 * BANK_SIZE
    assert stop95 == ROM_1_5MB
    assert stop95 - start95 == ROM_1_5MB - 95 * BANK_SIZE


def test_bank_span_negative_rejected():
    with pytest.raises(ValueError):
        bank_span(ROM_2MB, -1)


# ── пара (bank, addr) → смещение ───────────────────────────────────────────

def test_offset_roundtrip():
    assert to_offset(1, 0x4000, ROM_2MB) == BANK_SIZE
    assert to_bank_addr(BANK_SIZE, ROM_2MB) == (1, 0x4000)
    assert to_offset(1, 0x7FFF, ROM_2MB) == BANK_SIZE + 0x3FFF
    assert to_bank_addr(BANK_SIZE + 0x3FFF, ROM_2MB) == (1, 0x7FFF)


def test_offset_is_not_naive_bank_times_addr():
    """bank*0x4000 + addr сдвинул бы ссылку на целый банк."""
    assert to_offset(1, 0x4000, ROM_2MB) != BANK_SIZE + 0x4000
    assert to_offset(2, 0x5000, ROM_2MB) == 2 * BANK_SIZE + 0x1000


def test_banked_addresses_below_window_rejected():
    """В банке N нельзя адресовать 0x0000..0x3FFF — это банк 0."""
    assert to_offset(1, 0x0000, ROM_2MB) is None
    assert to_offset(1, 0x3FFF, ROM_2MB) is None


def test_bank0_only_has_low_half():
    """В банке 0 физически только 0x0000..0x3FFF."""
    assert to_offset(0, 0x0000, ROM_2MB) == 0
    assert to_offset(0, 0x3FFF, ROM_2MB) == 0x3FFF
    assert to_offset(0, 0x4000, ROM_2MB) is None
    assert to_offset(0, 0x7000, ROM_2MB) is None


def test_offset_outside_rom():
    assert to_offset(0xFF, 0x4000, ROM_2MB) is None
    assert to_offset(1, 0x4000, BANK_SIZE) is None   # банка 1 в 16 КиБ ROM нет
    assert to_offset(0x100, 0x4000, ROM_2MB) is None


def test_offset_rejects_ram_and_garbage():
    assert to_offset(1, RAM_START, ROM_2MB) is None
    assert to_offset(1, 0x8000, ROM_2MB) is None      # ровно за окном CPU
    assert to_offset(-1, 0x4000, ROM_2MB) is None
    assert to_offset(True, 0x4000, ROM_2MB) is None


def test_offset_rejects_non_int_addr():
    """Не-int адрес обязан дать None, а не исключение в середине записи."""
    assert to_offset(1, cast(int, 'x'), ROM_2MB) is None


def test_to_bank_addr_rejects_bool():
    assert to_bank_addr(True, ROM_2MB) is None


def test_to_bank_addr_rejects_garbage():
    assert to_bank_addr(-1, ROM_2MB) is None
    assert to_bank_addr(ROM_2MB, ROM_2MB) is None


def test_clipped_bank_high_address_absent():
    """ROM не кратен банку: в обрезанном хвосте половины адресов нет."""
    odd_rom = 96 * BANK_SIZE + 0x1000  # 96 банков + 4 КиБ
    start, stop = bank_span(odd_rom, 96)
    spare = stop - start
    assert spare == 0x1000
    assert to_offset(96, 0x4000, odd_rom) == start
    # Адрес за пределами хвоста не разрешается: смещение ушло бы за конец.
    assert to_offset(96, 0x4000 + spare, odd_rom) is None
    assert to_offset(95, BANK0_ROM_END + spare - 1, ROM_1_5MB) is not None


# ── классификация ──────────────────────────────────────────────────────────

@pytest.mark.parametrize('value,kind', [
    (0x0000, PointerKind.NULL),
    (0x4000, PointerKind.ROM),
    (0x0001, PointerKind.BANK0),
    (0x8000, PointerKind.VIDEO),
    (0x9FFF, PointerKind.VIDEO),
    (0xA000, PointerKind.RAM),
    (0xC000, PointerKind.RAM),
])
def test_classify_pointer(value, kind):
    assert classify_pointer(value, ROM_2MB) is kind


def test_classify_missing_bank():
    assert classify_pointer(0x4000, ROM_2MB) is PointerKind.ROM
    assert classify_pointer(0x4000, BANK_SIZE) is PointerKind.BANK_MISSING


# ── поиск 16-битных указателей ────────────────────────────────────────────

def make_rom(blobs: dict[int, bytes], size: int = ROM_2MB) -> bytearray:
    data = bytearray(size)
    for offset, blob in blobs.items():
        data[offset:offset + len(blob)] = blob
    return data


def test_scan_finds_16bit_pointer_anywhere():
    data = make_rom({0x0100: (0x4321).to_bytes(2, 'little')})
    hits = scan_bank_pointers(data, 0x4321)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.offset == 0x0100
    assert hit.pointer_bank == 0     # сам указатель лежит в банке 0
    assert hit.target_bank == 1     # 0x4321 лежит в банке 1 (окно 0x4000+)
    assert hit.target_addr == 0x4321
    assert hit.is_text_candidate


def test_scan_bank_restricts_to_region():
    """С `bank=N` ищем только в байтах банка N (подразумеваемый банк)."""
    data = make_rom({0x0100: (0x4321).to_bytes(2, 'little')})
    assert len(scan_bank_pointers(data, 0x4321, bank=0)) == 1
    assert scan_bank_pointers(data, 0x4321, bank=1) == []


def test_scan_rejects_out_of_range_addr():
    with pytest.raises(ValueError):
        scan_bank_pointers(make_rom({}), 0x1_0000)
    with pytest.raises(ValueError):
        scan_bank_pointers(make_rom({}), -1)


def test_scan_min_run_drops_overlaps():
    data = make_rom({0x0300: (0x4321).to_bytes(2, 'little') * 4})
    assert len(scan_bank_pointers(data, 0x4321, min_run=1)) == 4
    assert len(scan_bank_pointers(data, 0x4321, min_run=4)) == 2
    assert len(scan_bank_pointers(data, 0x4321, min_run=3)) == 2


def test_scan_min_run_zero_rejected():
    with pytest.raises(ValueError):
        scan_bank_pointers(make_rom({}), 0x4000, min_run=0)


def test_scan_skips_trailing_byte():
    """Одно байтовое совпадение на последнем байте файла — не указатель."""
    data = bytearray(BANK_SIZE)
    data[-1] = 0x43
    assert scan_bank_pointers(data, 0x4321) == []


# ── таблицы [bank][addr16] ─────────────────────────────────────────────────

def row(bank: int, addr: int, bank_first: bool = True) -> bytes:
    if bank_first:
        return bytes([bank]) + addr.to_bytes(2, 'little')
    return addr.to_bytes(2, 'little') + bytes([bank])


def test_scan_banked_rows_bank_first():
    data = make_rom({0x0200: b''.join(
        row(1, 0x4321 + i * 0x20) for i in range(6))})
    hits = scan_banked_rows(data, 0x0200, 6)
    assert [h.target_bank for h in hits] == [1] * 6
    assert [h.target_addr for h in hits] == [0x4321 + i * 0x20 for i in range(6)]
    assert [h.offset for h in hits] == [0x0200 + 3 * i for i in range(6)]
    assert all(h.is_text_candidate for h in hits)


def test_scan_banked_rows_addr_first():
    data = make_rom({0x0300: b''.join(
        row(2, 0x5000 + i * 0x10, bank_first=False) for i in range(5))})
    hits = scan_banked_rows(data, 0x0300, 5, bank_first=False)
    assert len(hits) == 5
    assert all(h.target_bank == 2 for h in hits)
    assert hits[0].target_addr == 0x5000


def test_scan_banked_rows_skips_missing_bank():
    """Банк за концом ROM пропускается, а не превращается в «исподтишка»."""
    blob = row(0xFF, 0x4321) + b''.join(
        row(1, 0x4321 + i * 0x20) for i in range(5))
    data = make_rom({0x0400: blob}, size=BANK_SIZE * 2)
    hits = scan_banked_rows(data, 0x0400, 6)
    assert {h.target_bank for h in hits} == {1}
    assert len(hits) == 5


def test_scan_banked_rows_stops_at_rom_end():
    """Чтение за концом таблицы обрывается, а не читает мусор ROM."""
    data = make_rom({0x0500: b''.join(
        row(1, 0x4321 + i * 0x20) for i in range(5))})
    assert len(scan_banked_rows(data, 0x0500, 10)) == 5


def test_scan_banked_rows_validates_args():
    with pytest.raises(ValueError):
        scan_banked_rows(make_rom({}), 0, 1, row_size=2)
    with pytest.raises(ValueError):
        scan_banked_rows(make_rom({}), 0, -1)


# ── фильтр ложных срабатываний ────────────────────────────────────────────

def test_banked_filter_rejects_too_few_rows():
    """Одна-две строки — это совпадение, а не таблица."""
    data = make_rom({0x0600: row(1, 0x4321) + row(1, 0x4341)})
    assert scan_banked_rows(data, 0x0600, 2) == []


def test_banked_filter_rejects_non_monotonic():
    """Настоящая таблица не «телепортирует» по адресам."""
    blob = b''.join(row(1, a) for a in (0x4321, 0x7000, 0x4400, 0x4420,
                                       0x4440, 0x4460))
    data = make_rom({0x0700: blob})
    # Первая пара 0x4321 -> 0x7000 имеет шаг > max_addr_step, поэтому
    # longest-run ищет серию из последних четырёх.
    hits = scan_banked_rows(data, 0x0700, 6)
    assert [h.target_addr for h in hits] == [0x4400, 0x4420, 0x4440, 0x4460]


def test_banked_filter_rejects_too_many_banks():
    """Мусор даёт случайные банки; у таблицы их один или два."""
    # Каждый следующий шаг меняет банк — серия рвётся на длине 1.
    blob = b''.join(row(1 + i, 0x4321 + i * 0x20) for i in range(6))
    data = make_rom({0x0800: blob})
    assert scan_banked_rows(data, 0x0800, 6) == []
    # Явно проверим, что дело в банках, а не в чём-то ещё: тот же адрес
    # при одном банке проходит.
    ok = b''.join(row(1, 0x4321 + i * 0x20) for i in range(6))
    assert len(scan_banked_rows(make_rom({0x0800: ok}), 0x0800, 6)) == 6


def test_banked_filter_keeps_two_banks_when_allowed():
    """Два банка — допустимо (часть таблиц ссылается на соседние)."""
    blob = b''.join(row(1 if i < 3 else 2, 0x4321 + i * 0x20)
                    for i in range(6))
    data = make_rom({0x0900: blob})
    hits = scan_banked_rows(data, 0x0900, 6, max_banks=2)
    assert len(hits) == 6
    assert {h.target_bank for h in hits} == {1, 2}


def test_banked_filter_rejects_random_garbage():
    """Фаззинг: случайные байты не должны выглядеть таблицей."""
    accepted = 0
    for seed in range(64):
        block = bytes((seed * 31 + i * 17 + 7) % 256 for i in range(3 * 8))
        data = make_rom({0x0A00: block})
        accepted += 1 if scan_banked_rows(data, 0x0A00, 8) else 0
    # Порог измерялся на произвольных данных: 24% строк проходили без
    # фильтра. С фильтром остаются единицы.
    assert accepted <= 2, accepted


# ── группировка в таблицы ──────────────────────────────────────────────────

def ptr(offset, bank=0):
    return BankPointer(offset=offset, pointer_bank=bank, target_bank=3,
                       target_addr=0x4000, kind=PointerKind.ROM)


def test_group_runs_by_stride():
    runs = group_pointer_runs([ptr(0x100), ptr(0x102), ptr(0x104)], stride=2)
    assert len(runs) == 1 and len(runs[0]) == 3


def test_group_drops_single_match():
    assert group_pointer_runs([ptr(0x100)], stride=2) == []


def test_group_splits_on_gap():
    runs = group_pointer_runs([ptr(0x100), ptr(0x102), ptr(0x900), ptr(0x902)],
                              stride=2)
    assert [len(r) for r in runs] == [2, 2]


def test_group_rejects_bad_stride():
    with pytest.raises(ValueError):
        group_pointer_runs([ptr(0)], stride=0)
