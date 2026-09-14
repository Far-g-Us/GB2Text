"""Тесты для FFTA LZSS обработчика (core/compression.FFTA_LZSSHandler)

Проверка паритета с эталонным декомпрессором (references/ffta_lzss_myguyz.py)
на реальных LZSS-блоках из ROM и round-trip компрессора.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.compression import FFTA_LZSSHandler
from references.ffta_lzss_myguyz import lzss_decompress_ex

ROM_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "test_roms",
    "Final Fantasy Tactics Advance (USA).gba",
)


def _collect_ffta_blocks(rom: bytes) -> list[int]:
    """Находит LZSS-блоки текста: маркер 0x32 0x00 + 4-байтовый BE размер

    Возвращает смещения маркера для блоков, которые корректно распаковываются
    эталонным декомпрессором.
    """
    blocks = []
    pos = 0
    n = len(rom)
    while True:
        idx = rom.find(b"\x32\x00", pos)
        if idx == -1 or idx + 6 > n:
            break
        size = int.from_bytes(rom[idx + 2:idx + 6], "big")
        if 0 < size < 0x8000 and lzss_decompress_ex(rom, idx + 2) is not None:
            blocks.append(idx)
        pos = idx + 1
    return blocks


@pytest.fixture(scope="module")
def ffta_lzss_data():
    """ROM и список смещений реальных LZSS-блоков (или skip, если ROM нет)."""
    if not os.path.exists(ROM_PATH):
        pytest.skip("Отсутствует test_roms/Final Fantasy Tactics Advance (USA).gba")
    with open(ROM_PATH, "rb") as f:
        rom = f.read()
    return rom, _collect_ffta_blocks(rom)


class TestFFTALZSSDecompressParity:
    """Декомпрессор обязан совпадать с эталоном на реальных блоках."""

    def test_parity_with_reference_on_rom_blocks(self, ffta_lzss_data):
        rom, blocks = ffta_lzss_data
        handler = FFTA_LZSSHandler()
        assert len(blocks) > 100
        for off in blocks:
            ref = lzss_decompress_ex(rom, off + 2)
            got, consumed = handler.decompress(rom, off + 2)
            assert got == ref[0], f"Расхождение вывода на блоке 0x{off:X}"
            assert consumed == ref[1], f"Расхождение потребления на блоке 0x{off:X}"

    def test_syntactic_failure_cases(self):
        handler = FFTA_LZSSHandler()
        # Составные байты без старших бит — невалидные команды
        for cmd in (0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F):
            stream = bytes([0, 0, 0, 1]) + bytes([cmd]) + b"\x00"
            assert handler.decompress(stream, 0) == (b"", 0), (
                f"Составной байт 0x{cmd:02X} должен давать fail"
            )
        # Пустые и оборванные входы
        assert handler.decompress(b"", 0) == (b"", 0)
        assert handler.decompress(b"\x00\x00\x00", 0) == (b"", 0)
        assert handler.decompress(b"\x00\x00\x00\x00\x40\x41", 0) == (b"", 0)
        # Заявленный размер 1, но команда bit7 с dist=1 при xout=0 → fail
        assert handler.decompress(b"\x00\x00\x00\x01\x80\x00", 0) == (b"", 0)
        # Литералы длиннее доступного входа → fail
        assert handler.decompress(b"\x00\x00\x00\x0A\x7F\x41\x42", 0) == (b"", 0)
        # backref bit4 с недостаточными данными команды → fail
        assert handler.decompress(b"\x00\x00\x00\x04\x10\xFF", 0) == (b"", 0)
        # backref 0x00 с недостаточными данными команды → fail
        assert handler.decompress(b"\x00\x00\x00\x05\x00\x01\x02", 0) == (b"", 0)

    def test_backref_clamp_and_self_reference(self):
        handler = FFTA_LZSSHandler()
        # bit4 с z=0: кламп в начало, повтор первого байта
        stream = b"\x00\x00\x00\x02\x10\x00\x00"
        got, consumed = handler.decompress(stream, 0)
        assert got == b"\x00\x00"
        assert consumed == 7
        assert lzss_decompress_ex(stream, 0) == (b"\x00\x00", consumed)
        # 0x00 с dist=0: самореференсная копия 5 байт с предыдущего байта
        stream = b"\x00\x00\x00\x09" + bytes([0x43]) + b"AAAA" + bytes([0x00, 0x00, 0x00, 0x00])
        got, consumed = handler.decompress(stream, 0)
        assert got == b"A" * 9
        assert lzss_decompress_ex(stream, 0) == (b"A" * 9, consumed)

    def test_literal_overflow_is_clamped(self):
        handler = FFTA_LZSSHandler()
        # Заявленный размер 2, литералы обещают 3 байта → кламп, успех.
        # Осознанное расхождение с эталоном: литералы у oracle при переполнении
        # возвращают None (см. docstring FFTA_LZSSHandler).
        stream = b"\x00\x00\x00\x02\x43\x41\x42\x43"
        got, consumed = handler.decompress(stream, 0)
        assert got == b"AB"
        assert consumed == 7
        assert lzss_decompress_ex(stream, 0) is None
        # Ровное заполнение без переполнения — поведение как у эталона.
        stream = b"\x00\x00\x00\x02\x41\x41\x42"
        assert handler.decompress(stream, 0) == (b"AB", 7)
        assert lzss_decompress_ex(stream, 0) == (b"AB", 7)
        # Исчерпание входа при литералах → по-прежнему fail.
        assert handler.decompress(b"\x00\x00\x00\x05\x44\x41", 0) == (b"", 0)


class TestFFTALZSSCompress:
    """Компрессор: round-trip собственным декомпрессором и эталоном."""

    def test_roundtrip_on_rom_blocks(self, ffta_lzss_data):
        rom, blocks = ffta_lzss_data
        handler = FFTA_LZSSHandler()
        assert len(blocks) > 100
        for off in blocks:
            raw = lzss_decompress_ex(rom, off + 2)[0]
            packed = handler.compress(raw)
            ref = lzss_decompress_ex(packed, 0)
            assert ref is not None, f"Невалидный поток от компрессора на 0x{off:X}"
            assert ref[0] == raw, f"Round-trip (эталон) не сошёлся на 0x{off:X}"
            mine, _ = handler.decompress(packed, 0)
            assert mine == raw, f"Round-trip (свой декодер) не сошёлся на 0x{off:X}"

    def test_roundtrip_synthetic(self):
        handler = FFTA_LZSSHandler()
        samples = [
            b"A",
            b"Hello",
            b"Hello, world!",
            b"AAAA",
            b"AAAAAAAAAA",
            b"\x00\x00",
            b"\x00" * 40,
            b"\x00" * 258,
            b"\x00" * 259,
            b"\x00" * 260,
            b"\x00" * 500,
            b"\xFF" * 10,
            b"\xFF" * 258,
            b"\xFF" * 259,
            b"\xFF" * 260,
            b"\xFF" * 300,
            b"\x00\u00ff" * 50,
            b"abcabcabcabcabcabcabc",
            bytes(range(256)),
            b" AB\nCD\tEF\0GH ",
        ]
        for raw in samples:
            packed = handler.compress(raw)
            ref = lzss_decompress_ex(packed, 0)
            assert ref is not None and ref[0] == raw, f"Round-trip эталона: {raw[:20]!r}"
            got, _ = handler.decompress(packed, 0)
            assert got == raw, f"Round-trip своего декодера: {raw[:20]!r}"

    def test_self_referential_copies(self):
        handler = FFTA_LZSSHandler()
        raw = b"AB" * 40
        packed = handler.compress(raw)
        got, _ = handler.decompress(packed, 0)
        assert got == raw
        assert lzss_decompress_ex(packed, 0)[0] == raw

    def test_compress_compresses_repetitive_data(self):
        handler = FFTA_LZSSHandler()
        for raw in (b"A" * 100, b"\x00" * 300, b"abcde" * 30):
            packed = handler.compress(raw)
            assert len(packed) < len(raw), f"Нет сжатия: {len(packed)} >= {len(raw)}"

    def test_compress_empty_raises(self):
        handler = FFTA_LZSSHandler()
        with pytest.raises(ValueError):
            handler.compress(b"")

    def test_compress_oversize_raises(self):
        handler = FFTA_LZSSHandler()
        with pytest.raises(ValueError):
            handler.compress(b"\x00" * (0x100000 + 1))
