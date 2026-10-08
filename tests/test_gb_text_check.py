"""Проверка текста и монотонности банковых таблиц.

Функции `looks_like_text` / `verify_table` / `scan_text_table` отвечают на
вопрос, который геометрия сама по себе не решает: указатели выглядят как
таблица, но по их адресам может лежать графика, код или данные. Именно на
реальном Pokemon Gold геометрия дала 63 монотонные серии, и НИ ОДНА не
содержала текста: самая длинная (251 строка, банк 109) оказалась таблицей
тайлов. Тесты ниже фиксируют именно это разделение.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gb_banks import (
    BANK_SIZE,
    BankPointer,
    PointerKind,
    looks_like_text,
    scan_text_table,
    text_bytes_at,
    to_offset,
    verify_table,
)

ROM_2BANK = 2 * BANK_SIZE
TEXT = b'HELLO!GOODBYE!'


def put(rom: bytearray, bank: int, addr: int, payload: bytes) -> None:
    off = to_offset(bank, addr, len(rom))
    assert off is not None
    rom[off:off + len(payload)] = payload


def table_at(rom: bytearray, bank: int, addrs: list[int],
             pointer_bank: int = 1) -> list[BankPointer]:
    """Кладёт настоящую таблицу 16-битных указателей в банк 1."""
    base = BANK_SIZE + 0x200
    out = []
    for i, addr in enumerate(addrs):
        pos = base + i * 2
        rom[pos:pos + 2] = addr.to_bytes(2, 'little')
        out.append(BankPointer(offset=pos, pointer_bank=pointer_bank,
                               target_bank=bank, target_addr=addr,
                               kind=PointerKind.ROM, assumed_bank=pointer_bank))
    return out


def ascii_charmap() -> dict[int, str]:
    return {b: chr(b) for b in range(0x20, 0x7F)}


# ── text_bytes_at ──────────────────────────────────────────────────────────

def test_text_bytes_at_reads_until_terminator():
    rom = bytearray(ROM_2BANK)
    put(rom, 1, 0x5000, b'ABC\x00REST')
    chunk, terminated = text_bytes_at(rom, 1, 0x5000)
    assert chunk == b'ABC'
    assert terminated is True


def test_text_bytes_at_reports_missing_terminator():
    # Заливаем НЕ терминатором: иначе 0x00 сразу после строки дал бы
    # «терминатор найден» и тест прошёл бы враньём.
    rom = bytearray(b'\x7f' * ROM_2BANK)
    put(rom, 1, 0x5000, b'ABCDEFGH')
    chunk, terminated = text_bytes_at(rom, 1, 0x5000)
    assert chunk.startswith(b'ABCDEFGH')
    assert terminated is False, 'строка без терминатора — вероятно, не строка'


def test_text_bytes_at_unmapped_address_is_empty():
    rom = bytearray(ROM_2BANK)
    chunk, terminated = text_bytes_at(rom, 1, 0x0000)
    assert chunk == b''
    assert terminated is False


def test_text_bytes_at_honours_custom_terminators():
    rom = bytearray(ROM_2BANK)
    put(rom, 1, 0x5000, b'ABC\xFFREST')
    chunk, terminated = text_bytes_at(rom, 1, 0x5000, terminators=(0xFF,))
    assert chunk == b'ABC'
    assert terminated is True


# ── looks_like_text ────────────────────────────────────────────────────────

def test_looks_like_text_accepts_real_strings():
    rom = bytearray(ROM_2BANK)
    addrs = [0x5000 + i * 0x10 for i in range(6)]
    for addr in addrs:
        put(rom, 1, addr, b'TEXT HERE\x00')
    ok, score = looks_like_text(rom, table_at(rom, 1, addrs),
                                charmap=ascii_charmap())
    assert ok is True
    assert score == 1.0


def test_looks_like_text_rejects_graphics():
    """Тайлы не текст: байты 0x00..0xFF вне карты — это не строки."""
    rom = bytearray(ROM_2BANK)
    addrs = [0x5000 + i * 0x10 for i in range(6)]
    for addr in addrs:
        put(rom, 1, addr, bytes([0x21, 0x6B, 0xC4, 0x06, 0x01, 0x0E,
                                 0x0B, 0xFA]) + bytes(8))
    ok, score = looks_like_text(rom, table_at(rom, 1, addrs),
                                charmap=ascii_charmap())
    assert ok is False
    assert score < 0.5


def test_looks_like_text_empty_input():
    assert looks_like_text(bytearray(ROM_2BANK), []) == (False, 0.0)


def test_looks_like_text_skips_rows_without_resolved_pair():
    rom = bytearray(ROM_2BANK)
    addrs = [0x5000 + i * 0x10 for i in range(4)]
    for addr in addrs:
        put(rom, 1, addr, b'TEXT HERE\x00')
    rows = table_at(rom, 1, addrs)
    rows.append(BankPointer(offset=0, pointer_bank=1, target_bank=None,
                            target_addr=None, kind=PointerKind.BANK_MISSING))
    ok, score = looks_like_text(rom, rows, charmap=ascii_charmap())
    assert ok is True
    assert score == 1.0, 'неразрешимые строки не должны портить долю'


def test_looks_like_text_all_rows_unusable():
    rows = [BankPointer(offset=0, pointer_bank=1, target_bank=None,
                        target_addr=None, kind=PointerKind.BANK_MISSING)]
    assert looks_like_text(bytearray(ROM_2BANK), rows) == (False, 0.0)


def test_looks_like_text_rejects_bad_ratio():
    rom = bytearray(ROM_2BANK)
    addrs = [0x5000 + i * 0x10 for i in range(6)]
    for addr in addrs:
        put(rom, 1, addr, b'TEXT HERE\x00')
    rows = table_at(rom, 1, addrs)
    with pytest.raises(ValueError):
        looks_like_text(rom, rows, min_ratio='x')
    with pytest.raises(ValueError):
        looks_like_text(rom, rows, min_ratio=1.5)


def test_looks_like_text_without_charmap_uses_ascii():
    """Без карты критерий остаётся ASCII-эвристикой — и это видно по score."""
    rom = bytearray(ROM_2BANK)
    addrs = [0x5000 + i * 0x10 for i in range(6)]
    for addr in addrs:
        put(rom, 1, addr, b'TEXT HERE\x00')
    rows = table_at(rom, 1, addrs)
    assert looks_like_text(rom, rows, charmap=ascii_charmap())[1] == 1.0
    assert looks_like_text(rom, rows)[1] == 1.0
    # Gen1-подобные буквы ASCII-критерием не признаются текстом.
    for addr in addrs:
        put(rom, 1, addr, bytes([0x91, 0x92, 0x93, 0x50]))
    assert looks_like_text(rom, rows)[0] is False


def test_looks_like_text_short_strings_skipped():
    rom = bytearray(ROM_2BANK)
    addrs = [0x5000 + i * 0x10 for i in range(6)]
    for addr in addrs:
        put(rom, 1, addr, b'A\x00')
    ok, score = looks_like_text(rom, table_at(rom, 1, addrs),
                                charmap=ascii_charmap(), min_len=2)
    assert ok is False
    assert score == 0.0


# ── verify_table ───────────────────────────────────────────────────────────

def test_verify_table_monotonic_and_text_ok():
    rom = bytearray(ROM_2BANK)
    addrs = [0x5000 + i * 0x10 for i in range(6)]
    for addr in addrs:
        put(rom, 1, addr, b'TEXT HERE\x00')
    rep = verify_table(rom, table_at(rom, 1, addrs), charmap=ascii_charmap())
    assert rep['ok'] is True
    assert rep['monotonic'] is True
    assert rep['descents'] == 0
    assert rep['text_ok'] is True
    assert rep['reasons'] == []


def test_verify_table_detects_descent():
    rom = bytearray(ROM_2BANK)
    addrs = [0x5000, 0x5100, 0x5040, 0x5200]
    for addr in addrs:
        put(rom, 1, addr, b'TEXT HERE\x00')
    rep = verify_table(rom, table_at(rom, 1, addrs), charmap=ascii_charmap())
    assert rep['ok'] is False
    assert rep['monotonic'] is False
    assert rep['descents'] == 1
    assert any('монотонн' in r for r in rep['reasons'])


def test_verify_table_detects_huge_step():
    rom = bytearray(ROM_2BANK)
    addrs = [0x4000, 0x7000]
    for addr in addrs:
        put(rom, 1, addr, b'TEXT HERE\x00')
    rep = verify_table(rom, table_at(rom, 1, addrs), charmap=ascii_charmap())
    assert rep['ok'] is False
    assert rep['max_addr_step'] == 0x3000


def test_verify_table_reports_why_no_text():
    rom = bytearray(ROM_2BANK)
    addrs = [0x5000 + i * 0x10 for i in range(4)]
    for addr in addrs:
        put(rom, 1, addr, bytes([0x21, 0x6B, 0xC4, 0x06, 0x01, 0x0E]))
    rep = verify_table(rom, table_at(rom, 1, addrs), charmap=ascii_charmap())
    assert rep['ok'] is False
    assert rep['text_ok'] is False
    assert any('не текст' in r for r in rep['reasons'])


def test_verify_table_report_always_has_ok():
    """Ключ ok есть в любом отчёте — иначе вызывающий читает KeyError."""
    assert 'ok' in verify_table(bytearray(ROM_2BANK), [])


def test_verify_table_empty_series():
    rep = verify_table(bytearray(ROM_2BANK), [])
    assert rep['ok'] is False
    assert rep['rows'] == 0
    assert rep['reasons'] == ['пустая серия']


def test_verify_table_counts_unusable_rows():
    rows = [BankPointer(offset=i, pointer_bank=1, target_bank=None,
                        target_addr=None, kind=PointerKind.BANK_MISSING)
            for i in range(3)]
    rep = verify_table(bytearray(ROM_2BANK), rows)
    assert rep['unusable'] == 3
    assert rep['ok'] is False


def test_verify_table_rejects_bad_ratio():
    with pytest.raises(ValueError):
        verify_table(bytearray(ROM_2BANK), [], min_ratio=-0.5)


# ── scan_text_table ────────────────────────────────────────────────────────

def _rom_with_text_table(rows: int = 10) -> bytearray:
    rom = bytearray(ROM_2BANK)
    addrs = [0x5000 + i * 0x10 for i in range(rows)]
    for addr in addrs:
        put(rom, 1, addr, b'TEXT HERE\x00')
    table_at(rom, 1, addrs)
    return rom


def test_scan_text_table_finds_monotonic_table():
    rom = _rom_with_text_table(10)
    found = scan_text_table(rom, bank=1, charmap=ascii_charmap(), min_rows=8)
    assert found, 'монотонная таблица с текстом обязана найтись'
    best = found[0]
    assert len(best) == 10
    addrs = [p.target_addr for p in best]
    assert addrs == sorted(addrs), 'адреса обязаны возрастать'
    assert [p.offset for p in best] == sorted(p.offset for p in best)


def test_scan_text_table_ignores_graphics_table():
    """Тот же геометрический вид, но с тайлами вместо текста — не таблица."""
    rom = bytearray(ROM_2BANK)
    addrs = [0x5000 + i * 0x10 for i in range(10)]
    for addr in addrs:
        put(rom, 1, addr, bytes([0x21, 0x6B, 0xC4, 0x06, 0x01, 0x0E,
                                 0x0B, 0xFA]) + bytes(8))
    table_at(rom, 1, addrs)
    assert scan_text_table(rom, bank=1, charmap=ascii_charmap(),
                           min_rows=8) == []


def test_scan_text_table_splits_non_monotonic_at_descent():
    """Убывание адреса разрывает серию: в выдаче не остаётся не монотонных
    таблиц, даже если исходные данные были такими."""
    rom = bytearray(b'\x7f' * ROM_2BANK)
    addrs = [0x5000, 0x5200, 0x5100, 0x5300, 0x5400, 0x5500, 0x5600, 0x5700]
    for addr in addrs:
        put(rom, 1, addr, b'TEXT HERE\x00')
    table_at(rom, 1, addrs)
    for series in scan_text_table(rom, bank=1, charmap=ascii_charmap(),
                                  min_rows=3):
        got = [p.target_addr for p in series]
        assert got == sorted(got), 'монотонность обязана соблюдаться'
        assert 0x5100 not in got or 0x5200 not in got


def test_scan_text_table_too_small_bank():
    rom = bytearray(0x2000)
    assert scan_text_table(rom, bank=0, min_rows=8) == []


def test_scan_text_table_validates_arguments():
    rom = _rom_with_text_table(4)
    with pytest.raises(ValueError):
        scan_text_table(rom, bank=1, stride=0)
    with pytest.raises(ValueError):
        scan_text_table(rom, bank=1, min_rows=1)
    with pytest.raises(ValueError):
        scan_text_table(rom, bank=1, bank_size=0)
    with pytest.raises(ValueError):
        scan_text_table(rom, bank=1, bank_size=-1)

