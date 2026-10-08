"""Ветки, оставшиеся после прохода по `core/injector.py`.

Здесь каждая проверка — про конкретный отказ: не-печатаемый байт в строке,
одна буква вместо двух, повторный неизвестный символ, один и тот же слот
таблицы дважды. Все они возвращают «не текст», а не «текст, который потом
запишут в ROM».
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_advance_wars_rejects_nonprintable_inside_string():
    """Не-печатаемый байт ВНУТРИ строки отвергает её.

    Терминатор обязателен: без него отказ приходит на проверке «строка не
    кончается», и нужная ветка не исполняется вовсе.
    """
    from plugins.gba_advance_wars import _decode_at
    assert _decode_at(b'\x01\x02AB\x00', 0) is None


def test_advance_wars_accepts_plain_ascii():
    """Обычная строка проходит все проверки и декодируется."""
    from plugins.gba_advance_wars import _decode_at
    assert _decode_at(b'BATTLE\x00rest', 0) == 'BATTLE'
    assert _decode_at(b'OK\x00', 0) == 'OK'


def test_advance_wars_accepts_single_letter():
    """Одна буква — тоже текст.

    Порог «>= 2 буквы» был удалён: он не инвариантен к переводу, и
    сокращение `'Map11'` -> `'M'` теряло запись (31 из 186 на Advance Wars).
    Критерий отбора не должен зависеть от длины текста.
    """
    from plugins.gba_advance_wars import _decode_at
    assert _decode_at(b'A1\x00', 0) == 'A1'
    assert _decode_at(b'A\x00rest', 0) == 'A'


def test_advance_wars_still_rejects_non_text_bytes():
    """Непечатный байт по-прежнему означает «здесь не строка»."""
    from plugins.gba_advance_wars import _decode_at
    assert _decode_at(b'A\x01B\x00', 0) is None
    assert _decode_at(b'\x80\x81\x00', 0) is None


def test_advance_wars_newline_inside_string_allowed():
    """Перевод строки внутри строки разрешён: это формат многих игр."""
    from plugins.gba_advance_wars import _decode_at
    assert _decode_at(b'A\nB\x00', 0) == 'A\nB'


def test_advance_wars_unknown_char_reported_only_first_time():
    """Повторный вызов с тем же неизвестным символом не дублирует отчёт."""
    from plugins.gba_advance_wars import AdvanceWarsTextDecoder
    dec = AdvanceWarsTextDecoder({0x41: 'A'})
    for _ in range(2):
        try:
            dec.encode('\u0410')
        except ValueError:
            pass
    assert dec.last_unmapped_chars == ['\u0410']


def test_advance_wars_same_slot_twice_added_once(tmp_path, monkeypatch):
    """Один и тот же слот, прочитанный дважды, попадает в список один раз."""
    import struct

    from plugins import gba_advance_wars as aw

    blob = bytearray(0x200)
    text_at = 0x100
    blob[text_at:text_at + 6] = b'BATTLE\x00'
    ptr = struct.pack('<I', aw.HEADER_BASE + text_at)
    blob[0x10:0x14] = ptr
    # Один и тот же слот в двух записях TABLES: читаем его дважды.
    monkeypatch.setattr(aw, 'TABLES', [(0x10, 1), (0x10, 1)])
    entries = aw._entries_for_rom(bytes(blob))
    assert entries
    assert entries[0]['slots'] == [0x10], 'слот не должен дублироваться'


def test_gb_banks_last_bank_never_empty():
    """Последний банк всегда непустой: bank_count округляет вверх.

    Поэтому ветка «span пуст, банк пропущен» в `scan_for_text_pointers`
    недостижима — иначе размер банка в ROADMAP пришлось бы уточнять.
    """
    from core.gb_banks import BANK_SIZE, bank_count, bank_span
    for size in (0x1000, 0x4001, 0x5000, 0x7FFF, 0x8000, 0x8001):
        for bank in range(bank_count(size)):
            start, stop = bank_span(size, bank)
            assert start < stop, (size, bank)
    assert bank_span(0x5000, 1) == (BANK_SIZE, 0x5000)
