"""Тесты сжатия GB/GBC (Gen1/2): RLE с управляющим байтом и LZ.

Кодеки обязаны быть обратимы: иначе после вставки перевода исходный поток
не воспроизводится и ROM не запускается. Round-trip проверяется на всём,
плюс краевые случаи, где легко «съесть» байты.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gb_compression import (
    LZ_MAX_LENGTH,
    RLE_MAX_RUN,
    ControlByteRLEHandler,
    NintendoLZHandler,
    guess_format,
)

RAW_SAMPLES = [
    b'',
    b'A',
    b'AB',
    b'AAA',
    b'AAAA',
    b'A' * 300,
    b'\x00' * 5,
    b'hello world hello world hello world',
    bytes(range(256)),
    b'\xff' * 4 + b'\x00' * 4 + b'\xff\x00' * 8,
    b'The quick brown fox jumps over the lazy dog. ' * 3,
    bytes([0x20 + (i % 90) for i in range(500)]),
]


@pytest.mark.parametrize('raw', RAW_SAMPLES)
def test_rle_roundtrip(raw):
    handler = ControlByteRLEHandler()
    packed = handler.compress(raw)
    out, consumed = handler.decompress(packed, 0)
    assert out == raw
    assert consumed == len(packed)


@pytest.mark.parametrize('raw', RAW_SAMPLES)
def test_lz_roundtrip(raw):
    handler = NintendoLZHandler()
    packed = handler.compress(raw)
    out, consumed = handler.decompress(packed, 0)
    assert out == raw
    assert consumed == len(packed)


@pytest.mark.parametrize('raw', RAW_SAMPLES)
def test_roundtrip_with_offset(raw):
    """Поток может начинаться не с нуля — старт-смещение обязано учитываться."""
    prefix = b'\xaa' * 7
    blob = prefix + bytes([0xFF]) + ControlByteRLEHandler().compress(raw)
    out, consumed = ControlByteRLEHandler().decompress(blob, 8)
    assert out == raw
    assert consumed == len(blob) - 8


def test_rle_actually_shrinks_long_runs():
    raw = b'X' * RLE_MAX_RUN
    packed = ControlByteRLEHandler().compress(raw)
    assert len(packed) < len(raw)
    assert len(packed) == 2


def test_rle_keeps_short_runs_literal():
    """RLE из 3 одинаковых байт короче НЕ становится: 2 байта против 3 — да,
    но только при размере серии 4+; при 3 литерал короче не выигрывает по
    байтам на единицу, поэтому формат оставляет литерал (совместимость)."""
    raw = b'Z' * 3
    packed = ControlByteRLEHandler().compress(raw)
    out, _ = ControlByteRLEHandler().decompress(packed, 0)
    assert out == raw


def test_rle_truncated_stream_does_not_invent_bytes():
    """Обрезанная литеральная серия не должна дорисовываться нулями."""
    handler = ControlByteRLEHandler()
    # ctrl = 0x09 => ждём 10 литералов, даём 3
    out, consumed = handler.decompress(b'\x09' + b'ABC', 0)
    assert out == b'ABC'
    assert consumed == 4


def test_rle_truncated_repeat_stops():
    handler = ControlByteRLEHandler()
    out, _ = handler.decompress(b'\x85Q', 0)
    assert out == b'Q' * 8


def test_lz_broken_reference_is_not_reported_as_text():
    """Ссылка в пустоту: обрываем поток, а не выводим нули.

    Иначе в отчёт об извлечении ушёл бы правдоподобный «текст» из нулей,
    и при обратной вставке он был бы записан в ROM.
    """
    handler = NintendoLZHandler()
    # флаг = 0x80 (ссылка), hi=0x00, lo=0x00 => offset 1 при выходе 0
    out, _ = handler.decompress(b'\x80\x00\x00', 0)
    assert out == b''


def test_lz_overlapping_copy():
    """Перекрывающаяся ссылка (offset < length) — штатный случай RLE-эффекта."""
    handler = NintendoLZHandler()
    raw = b'ab' * 40
    packed = handler.compress(raw)
    out, _ = handler.decompress(packed, 0)
    assert out == raw


def test_lz_respects_max_length():
    """Серия длиннее 18 байт обязана разбиваться на несколько ссылок."""
    handler = NintendoLZHandler()
    raw = b'Q' * (LZ_MAX_LENGTH * 3)
    packed = handler.compress(raw)
    assert len(packed) > 4  # не одна ссылка
    out, _ = handler.decompress(packed, 0)
    assert out == raw


def test_max_output_guard():
    """Предохранитель ограничивает вывод «болотом»."""
    handler = ControlByteRLEHandler(max_output=32)
    packed = bytes([0xFF]) + b'Z' * RLE_MAX_RUN
    out, _ = handler.decompress(packed, 0)
    assert len(out) <= 32 + RLE_MAX_RUN


def test_guess_format_picks_the_winner():
    rle = ControlByteRLEHandler().compress(b'A' * 200)
    assert guess_format(rle, 0)[0] == 'rle'
    lz = NintendoLZHandler().compress(b'ab' * 100)
    assert guess_format(lz, 0)[0] == 'lz'


def test_guess_format_rejects_plain_text():
    """Несжатый текст не должен объявляться сжатым."""
    plain = b'This is plain uncompressed text, not a compressed stream.'
    assert guess_format(plain, 0)[0] == 'none'


def test_guess_format_does_not_claim_rle_on_arbitrary_bytes():
    """Репродукция ложного срабатывания, найденного на реальных ROM.

    Прежний критерий смотрел только на коэффициент роста, а RLE-распаковка
    произвольных байт почти всегда «растёт»: управляющий байт 0x80..0xFF
    выдаёт 3..130 копий. На пяти реальных GB/GBC ROM старый код объявлял
    `rle` в 48 блоках из 40 на каждой игре, включая Zelda, которая этим
    форматом не сжата. Теперь требуется ещё и текстовость вывода.
    """
    # Байты, которые почти наверняка не сжатый текст, но которые RLE
    # «распаковывает» с большим коэффициентом.
    noise = bytes(range(0x80, 0x100)) + bytes(range(0x00, 0x40))
    verdict, ratio = guess_format(noise, 0)
    assert verdict == 'none', (verdict, ratio)


def test_guess_format_accepts_real_streams():
    """Настоящий сжатый поток обязан определяться, иначе модуль бесполезен."""
    rle = ControlByteRLEHandler().compress(b'A' * 200 + b'B' * 200)
    assert guess_format(rle, 0)[0] == 'rle'
    lz = NintendoLZHandler().compress(b'Pokemon Gold Silver ' * 12)
    assert guess_format(lz, 0)[0] == 'lz'


def test_guess_format_accepts_space_padded_text():
    """GB-текст часто дополнен пробелами — это настоящие серии для RLE."""
    raw = b'ITEM' + b' ' * 40 + b'POKEBALL' + b' ' * 40
    packed = ControlByteRLEHandler().compress(raw)
    assert len(packed) < len(raw)
    assert guess_format(packed, 0)[0] == 'rle'


def test_start_beyond_data_returns_empty():
    for handler in (ControlByteRLEHandler(), NintendoLZHandler()):
        out, consumed = handler.decompress(b'\x00\x01\x02', 99)
        assert out == b''
        assert consumed == 0


# ── charmap-независимый критерий ──────────────────────────────────────────

def test_guess_format_needs_charmap_for_gen1():
    """ASCII-окно для Gen1/2 непригодно — и это была реальная поломка.

    Буквы Gen1 лежат в 0x80..0x99 (проверено на настоящей
    `plugins.gb_pokemon_gen1.CHARMAP_GEN1`): вне ASCII находятся все
    заглавные, поэтому текстовость настоящего текста была 0.018 и
    `guess_format` отвечал `none` на всём. С переданной charmap — 1.00.
    """
    from plugins.gb_pokemon_gen1 import CHARMAP_GEN1

    rev = {char: byte for byte, char in CHARMAP_GEN1.items()}
    encoded = bytes(rev[c] for c in 'POKEMON')
    # Байты Gen1 вне ASCII-окна — иначе проверка была бы бессмысленной.
    assert all(b > 0x7E or b < 0x20 for b in encoded), [hex(b) for b in encoded]

    pad = rev[' ']
    raw = encoded * 3 + bytes([pad]) * 24 + encoded
    packed = ControlByteRLEHandler().compress(raw)
    assert len(packed) < len(raw), 'тест должен быть на СЖИМАЕМОМ потоке'

    assert guess_format(packed, 0)[0] == 'none', \
        'без charmap ASCII-окно обязано давать ложный отказ'
    assert guess_format(packed, 0, charmap=CHARMAP_GEN1)[0] == 'rle'


def test_guess_format_charmap_still_rejects_garbage():
    """Схема с charmap не превращается в «всё сжатое»."""
    from plugins.gb_pokemon_gen1 import CHARMAP_GEN1

    noise = bytes(range(0x00, 0x20)) * 8
    assert guess_format(noise, 0, charmap=CHARMAP_GEN1)[0] == 'none'


def test_guess_format_charmap_lz_on_gen1():
    from plugins.gb_pokemon_gen1 import CHARMAP_GEN1

    rev = {char: byte for byte, char in CHARMAP_GEN1.items()}
    encoded = bytes(rev[c] for c in 'POKEMON')
    packed = NintendoLZHandler().compress(encoded * 12)
    assert guess_format(packed, 0)[0] == 'none'
    assert guess_format(packed, 0, charmap=CHARMAP_GEN1)[0] == 'lz'
