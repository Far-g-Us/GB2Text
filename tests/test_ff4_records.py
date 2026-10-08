"""FF4: поуказательная нарезка на 0x0C-записи (синтетика, без ROM)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rom import GameBoyROM
from plugins.gba_ff4_advance import (
    FF4_POINTER_COUNT,
    FF4_POINTER_TABLE_OFFSET,
    FF4_TEXT_DATA_START,
    FF4AdvancePlugin,
    _code_table_targets,
    _is_junk_record,
)


def _table(first_ptr: int, second_ptr: int) -> bytes:
    table = bytearray(FF4_POINTER_COUNT * 4)
    table[0:2] = first_ptr.to_bytes(2, 'little')
    table[4:6] = second_ptr.to_bytes(2, 'little')
    for i in range(2, FF4_POINTER_COUNT):
        table[i * 4:i * 4 + 2] = (0xFFFF).to_bytes(2, 'little')
    return bytes(table)


TEXT_AT = FF4_POINTER_TABLE_OFFSET + FF4_POINTER_COUNT * 4 + 0x100


def test_single_record_keeps_plain_name() -> None:
    blob = bytes([0x23, 0x24, 0x0C])
    table = _table(TEXT_AT - FF4_TEXT_DATA_START, TEXT_AT - FF4_TEXT_DATA_START + len(blob))
    data = bytearray(0x330000)
    data[TEXT_AT:TEXT_AT + len(blob)] = blob
    data[FF4_POINTER_TABLE_OFFSET:FF4_POINTER_TABLE_OFFSET + len(table)] = table
    rom = GameBoyROM.__new__(GameBoyROM)
    rom.data = bytearray(data)
    rom.header = {'game_code': 'BZ4E'}
    segs = [s for s in FF4AdvancePlugin().get_text_segments(rom) if s['name'].startswith('ff4_text_0')]
    assert [(s['name'], s['start']) for s in segs] == [
        (f'ff4_text_0_{TEXT_AT:06x}', TEXT_AT)]


def test_two_records_split_with_suffix() -> None:
    blob = bytes([0x23, 0x24, 0x0C, 0x24, 0x23, 0x0C])
    table = _table(TEXT_AT - FF4_TEXT_DATA_START, TEXT_AT - FF4_TEXT_DATA_START + len(blob))
    data = bytearray(0x330000)
    data[TEXT_AT:TEXT_AT + len(blob)] = blob
    data[FF4_POINTER_TABLE_OFFSET:FF4_POINTER_TABLE_OFFSET + len(table)] = table
    rom = GameBoyROM.__new__(GameBoyROM)
    rom.data = bytearray(data)
    rom.header = {'game_code': 'BZ4E'}
    segs = [s for s in FF4AdvancePlugin().get_text_segments(rom)
            if s['name'].startswith('ff4_text_0') and s['start'] >= TEXT_AT]
    assert [(s['name'], s['start'], s['end']) for s in segs] == [
        (f'ff4_text_0_{TEXT_AT:06x}', TEXT_AT, TEXT_AT + 3),
        (f'ff4_text_0_{TEXT_AT + 3:06x}', TEXT_AT + 3, TEXT_AT + 6),
    ]


def test_consecutive_terminators_produce_no_empty_record() -> None:
    """Подряд идущие 0x0C не должны порождать записи без текста.

    Регрессия: условие `pos + 1 > rec_start` истинно всегда (rec_start
    равен pos предыдущего разделителя + 1), поэтому «пустые» записи в один
    байт 0x0C попадали в манифест. На реальном BZ4E их было 110, и все
    они были read-only алиасами с пустым текстом.
    """
    blob = bytes([0x23, 0x0C, 0x0C, 0x0C, 0x24, 0x25, 0x0C])
    table = _table(TEXT_AT - FF4_TEXT_DATA_START, TEXT_AT - FF4_TEXT_DATA_START + len(blob))
    data = bytearray(0x330000)
    data[TEXT_AT:TEXT_AT + len(blob)] = blob
    data[FF4_POINTER_TABLE_OFFSET:FF4_POINTER_TABLE_OFFSET + len(table)] = table
    rom = GameBoyROM.__new__(GameBoyROM)
    rom.data = bytearray(data)
    rom.header = {'game_code': 'BZ4E'}
    segs = [s for s in FF4AdvancePlugin().get_text_segments(rom)
            if s['name'].startswith('ff4_text_0') and s['start'] >= TEXT_AT]
    assert [(s['start'], s['end']) for s in segs] == [
        (TEXT_AT, TEXT_AT + 2),
        (TEXT_AT + 4, TEXT_AT + 7),
    ]
    assert all(s.get('original_text') for s in segs), 'запись без текста'


def test_junk_filter_rejects_two_unknown_tokens() -> None:
    """Мусор-фильтр FF4: 2+ неизвестных токена — не текст.

    Пороги по длине текста удалены как нестабильные (перевод меняет длину,
    и запись уходила из манифеста), поэтому проверяем именно оставшийся
    критерий.
    """
    assert _is_junk_record('[9A][A4]') is True
    assert _is_junk_record('[8E]Pic') is False
    assert _is_junk_record('   ') is True
    assert _is_junk_record('') is True


def test_code_table_records_are_not_injectable() -> None:
    """Таблица кодов (2 байта на символ подряд) не должна попасть в записи.

    Сразу за таблицей указателей лежит перечисление charmap в виде
    «2 байта на символ» (`6f 0c` -> 'あ'). Перезапись такой записи ломает
    раскладку символов, поэтому такие цели отбрасываются по геометрии
    указателей (span <= 3 в плотном ряду), а не по длине текста.
    """
    # Последняя цель ряда исключается: следующая цель (500) далеко, span
    # последней записи таблицы измеряется до НЕЁ, а не до предыдущей.
    # На реальном BZ4E это не мешает: там таблица codes не прерывается.
    # Ряд из 12+ целей с шагом <= 3 — таблица кодов, отсекается целиком.
    table = [*range(100, 100 + 24, 2), 500, 900]
    # Последняя цель ряда отсекается: её span измеряется до следующей (500),
    # то есть до обрыва, и большой span её исключает. На BZ4E таблица
    # codes не прерывается, поэтому это на реальных данных не мешает.
    assert _code_table_targets(table) == set(range(100, 100 + 22, 2))
    # Регрессия: на BZ4E меню-строка '0', '/', 'Empty:/' даёт РОВНО такую
    # же геометрию (шаг 1-3, каждая запись закрыта 0x0C), и при min_run=8
    # фильтр съедал 6 настоящих записей, включая каноническое 'Empty'.
    # Оборот ряда настоящей строкой: targets не равномерные.
    menu = [0, 1, 2, 6, 12, 18, 24, 30, 31, 32, 40, 41, 500, 900]
    assert _code_table_targets(menu) == set()
    # Одиночные короткие записи настоящего текста остаются.
    assert _code_table_targets([0, 10, 400, 401, 900]) == set()
