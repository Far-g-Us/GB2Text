"""Закрытие пробелов покрытия в модулях GB/GBC.

Ниже нет ни одной строки «ради покрытия»: каждый тест — либо проверка
пограничного случая, который нашёл ревью (например, `table_offset = -1`
читал последний байт ROM как байт банка), либо ветка отказа, которая обязана
быть fail-closed.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gb_banks import (
    BANK_SIZE,
    BankPointer,
    PointerKind,
    _plausible_run,
    bank_count,
    bank_span,
    scan_banked_rows,
    scan_for_text_pointers,
    to_offset,
)
from core.gb_compression import (
    RLE_MAX_RUN,
    ControlByteRLEHandler,
    NintendoLZHandler,
    _text_likeness,
    guess_format,
)

ROM_2MB = 0x200000
ROM_2BANK = 2 * BANK_SIZE


def row(bank: int, addr: int) -> bytes:
    return bytes([bank]) + addr.to_bytes(2, 'little')


# ── core/gb_banks.py ───────────────────────────────────────────────────────

def test_banked_rows_negative_table_offset_raises():
    """Отрицательный table_offset обязан быть отвергнут, а не прочитан."""
    with pytest.raises(ValueError):
        scan_banked_rows(bytearray(ROM_2BANK), -1, 1)


def test_banked_rows_stops_when_table_runs_past_rom_end():
    """Таблица, оборванная концом файла, читается до обрыва — без исключения.

    Формат строки addr16 + bank (не bank-first): при обрыве последней строки
    без проверки `base + row_size > rom_size` чтение `rom_data[base + 2]`
    выходит за конец и даёт IndexError. В bank-first этот случай не
    отличим от отбрасывания мусорной строки, поэтому он и проверяется здесь.
    """
    data = bytearray(ROM_2BANK)
    rows = [(0x4321 + i * 0x20, 1) for i in range(4)]
    blob = b''.join(addr.to_bytes(2, 'little') + bytes([bank])
                    for addr, bank in rows)
    # Обрыв ровно посередине 5-й строки: остаются 2 байта из 3.
    at = ROM_2BANK - len(blob) - 2
    data[at:at + len(blob)] = blob
    hits = scan_banked_rows(data, at, 10, bank_first=False)
    assert len(hits) == 4, 'читаются ровно 4 целые строки, 5-я обрывается'
    assert [h.target_addr for h in hits] == [0x4321, 0x4341, 0x4361, 0x4381]


def test_plausible_run_all_rejected_returns_empty():
    """Когда ни одна серия не проходит — пустой результат, без исключения."""
    def ptr(bank: int, addr: int) -> BankPointer:
        return BankPointer(offset=0, pointer_bank=0, target_bank=bank,
                           target_addr=addr, kind=PointerKind.ROM)

    rows = [ptr(1 + i, 0x4321 + i * 0x20) for i in range(6)]
    assert _plausible_run(rows, min_rows=4, max_banks=1,
                          max_addr_step=0x2000) == []
    assert _plausible_run([], 4, 2, 0x2000) == []


def test_scan_for_text_pointers_on_empty_rom():
    """Пустой ROM не должен падать и не должен ничего возвращать."""
    assert scan_for_text_pointers(bytearray(0), 0) == []


def test_bank_span_boundary_is_half_open():
    """Проверка границы: конец банка не входит в него."""
    start, stop = bank_span(ROM_2BANK, 1)
    assert (start, stop) == (BANK_SIZE, ROM_2BANK)
    assert to_offset(0, BANK_SIZE, ROM_2BANK) is None
    assert to_offset(1, BANK_SIZE, ROM_2BANK) == BANK_SIZE


def test_bank_count_zero_size_rom():
    assert bank_count(0) == 0


def test_scan_for_text_pointers_walks_banks_and_honours_min_run():
    """Полный скан обходит банки и собирает 16-битную таблицу с шагом 2.

    Внутри обязательно `min_run=1`: при внешнем `min_run=3` дедупликация
    выбрасывает каждую третью находку, и таблица, у которой указатели идут
    через одно слово, не может быть найдена в принципе.
    """
    data = bytearray(BANK_SIZE * 2)
    # Функция ищет серию ПОВТОРОВ одного 16-битного значения через равные
    # промежутки (таблица «один и тот же указатель в нескольких слотах»).
    # Слова идут подряд, поэтому найденные смещения расходятся на stride=2.
    blob = b'\x21\x43' * 8
    at = BANK_SIZE + 0x100
    data[at:at + len(blob)] = blob
    found = scan_for_text_pointers(data, len(data), min_run=3)
    # Остальной ROM заполнен нулями, поэтому в выдаче есть и серии от других
    # значений — берём именно нашу.
    mine = [t for t in found
            if len(t) >= 4 and all(p.target_addr == 0x4321 for p in t)]
    assert mine, 'серия повторов 0x4321 обязана находиться'
    first = mine[0]
    assert [p.offset for p in first] == [at + 2 * i for i in range(8)]
    assert all(p.target_bank == 1 for p in first)
    assert all(p.kind is PointerKind.ROM for p in first)


# ── core/gb_compression.py ─────────────────────────────────────────────────

def test_rle_truncated_repeat_at_buffer_end():
    """Управляющий байт повтора последним в буфере — поток обрывается."""
    handler = ControlByteRLEHandler()
    out, consumed = handler.decompress(b'\x85', 0)
    assert out == b''
    assert consumed == 1


def test_lz_truncated_reference_at_buffer_end():
    """2-байтная ссылка, обрезанная концом буфера."""
    handler = NintendoLZHandler()
    out, consumed = handler.decompress(b'\x80\x10', 0)
    assert out == b''
    assert consumed >= 1


def test_find_match_at_end_of_buffer():
    """Позиция в самом конце: сравнивать нечего."""
    assert NintendoLZHandler._find_match(b'abc', 3, {}) == (0, 0)
    assert NintendoLZHandler._find_match(b'abc', 5, {}) == (0, 0)


def test_find_match_single_trailing_byte():
    """Хвост из одного байта ищется перебором, а не по цепочке."""
    assert NintendoLZHandler._find_match(b'aa', 1, {}) == (1, 1)


def test_find_match_zero_limit():
    assert NintendoLZHandler._find_match(b'', 0, {}) == (0, 0)


def test_text_likeness_of_empty():
    assert _text_likeness(b'', None) == 0.0
    assert _text_likeness(b'', frozenset({0x41})) == 0.0


def test_lz_overlapping_reference_walks_forward():
    """Перекрывающаяся ссылка: offset < length, копирование вперёд."""
    handler = NintendoLZHandler()
    raw = b'\x41' * 40
    packed = handler.compress(raw)
    out, _ = handler.decompress(packed, 0)
    assert out == raw


def test_rle_max_run_boundary():
    """Серия ровно предельной длины кодируется одной командой."""
    handler = ControlByteRLEHandler()
    raw = b'Z' * RLE_MAX_RUN
    packed = handler.compress(raw)
    out, _ = handler.decompress(packed, 0)
    assert out == raw
    assert len(packed) == 2


def test_guess_format_empty_input():
    assert guess_format(b'', 0) == ('none', 0.0)


def test_guess_format_empty_charmap_falls_back_to_ascii():
    """Пустая charmap не должна ломать критерий — откат на ASCII."""
    handler = ControlByteRLEHandler()
    # Нужна серия одинаковых байт: RLE сжимает только повторы.
    packed = handler.compress(b'Hello world! ' * 10 + b' ' * 40)
    assert len(packed) < 260, 'тест должен быть на сжимаемом потоке'
    assert guess_format(packed, 0, charmap={})[0] == 'rle'


# ── core/rom.py, core/encoding.py ─────────────────────────────────────────

def test_rom_title_absent_is_empty_string(tmp_path):
    """ROM без заголовка в хедере отдаёт пустую строку, а не падает."""
    from core.rom import GameBoyROM

    path = tmp_path / 'empty.gb'
    path.write_bytes(bytes(0x8000))
    assert GameBoyROM(str(path)).title == ''


def test_auto_charmap_labels_frequent_terminator():
    """Частый не-ASCII байт, не попавший в charmap, получает метку [TERM_XX].

    Без этого автоподбор charmap молча терял бы управляющий байт, и любой
    декодер выдал бы мусор вместо терминатора.
    """
    from core.encoding import auto_detect_charmap

    # 0xFF — самый частый (становится пробелом), 0x00 — второй по частоте
    # и встречается чаще порога, но не является ASCII-символом.
    data = bytes([0xFF]) * 200 + bytes([0x00]) * 12
    charmap = auto_detect_charmap(data, 0, len(data))
    assert charmap[0xFF] == ' '
    assert charmap[0x00] == '[TERM_00]'
