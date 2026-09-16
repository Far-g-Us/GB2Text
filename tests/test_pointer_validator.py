"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.
"""

import pytest

from core.pointer_validator import (
    STATUS_DUPLICATE,
    STATUS_NON_MONOTONIC,
    STATUS_OK,
    STATUS_OUT_OF_BOUNDS,
    STATUS_ZERO,
    PointerValidationError,
    problem_summary,
    repair_pointer_table,
    validate_pointer_table,
)

GBA_BASE = 0x08000000


def _gba_rom(text_offset: int, count: int, stride: int = 4) -> bytes:
    """ROM 0x1000 байт с таблицей указателей в начале, текстом на text_offset."""
    size = max(0x1000, text_offset + 16)
    rom = bytearray(size)
    for i in range(count):
        value = GBA_BASE + text_offset + i * 4
        rom[i * stride:i * stride + 4] = value.to_bytes(4, "little")
    return bytes(rom)


def _gba_repair_rom() -> bytearray:
    rom = bytearray(0x1000)
    for i in range(4):
        rom[i * 4:(i + 1) * 4] = (GBA_BASE + 0x100 + i * 4).to_bytes(4, "little")
    return rom


class TestValidatePointerTable:
    def test_valid_gba_table(self):
        rom = _gba_rom(text_offset=0x100, count=4)
        records = validate_pointer_table(rom, 0, 4)
        assert [r["target"] for r in records] == [0x100, 0x104, 0x108, 0x10C]
        assert all(r["status"] == STATUS_OK for r in records)

    def test_zero_entries(self):
        rom = bytearray(0x1000)
        rom[0:4] = (GBA_BASE + 0x200).to_bytes(4, "little")
        rom[8:12] = (GBA_BASE + 0x300).to_bytes(4, "little")
        records = validate_pointer_table(rom, 0, 4)
        assert records[0]["status"] == STATUS_OK
        assert records[1]["status"] == STATUS_ZERO
        assert records[2]["status"] == STATUS_OK
        assert records[3]["status"] == STATUS_ZERO

    def test_out_of_bounds(self):
        rom = bytearray(0x1000)
        rom[4:8] = (GBA_BASE + 0x9000).to_bytes(4, "little")
        records = validate_pointer_table(rom, 0, 2)
        assert records[1]["status"] == STATUS_OUT_OF_BOUNDS

    def test_negative_target_out_of_bounds(self):
        rom = bytearray(0x1000)
        rom[4:8] = 0x01000000.to_bytes(4, "little")
        records = validate_pointer_table(rom, 0, 2)
        assert records[1]["target"] < 0
        assert records[1]["status"] == STATUS_OUT_OF_BOUNDS

    def test_duplicate_targets(self):
        rom = bytearray(0x1000)
        rom[0:4] = (GBA_BASE + 0x100).to_bytes(4, "little")
        rom[4:8] = (GBA_BASE + 0x100).to_bytes(4, "little")
        records = validate_pointer_table(rom, 0, 3)
        assert records[0]["status"] == STATUS_OK
        assert records[1]["status"] == STATUS_DUPLICATE
        assert records[1]["duplicate_of"] == 0
        assert records[2]["status"] == STATUS_ZERO

    def test_custom_stride(self):
        rom = bytearray(0x1000)
        entries = [(GBA_BASE + 0x100).to_bytes(4, "little"),
                   b"\x00" * 4,
                   (GBA_BASE + 0x200).to_bytes(4, "little")]
        for i, e in enumerate(entries):
            rom[i * 8:i * 8 + 4] = e
        records = validate_pointer_table(rom, 0, 3, stride=8)
        assert [r["status"] for r in records] == [
            STATUS_OK, STATUS_ZERO, STATUS_OK]

    def test_16bit_flat_pointers(self):
        rom = bytearray(0x1000)
        rom[0:2] = (0x0034).to_bytes(2, "little")
        rom[2:4] = (0x0234).to_bytes(2, "little")
        records = validate_pointer_table(rom, 0, 2, stride=2, entry_size=2,
                                         address_base=0)
        assert records[0]["target"] == 0x0034
        assert records[0]["status"] == STATUS_OK
        assert records[1]["target"] == 0x0234
        assert records[1]["status"] == STATUS_OK

    def test_table_out_of_rom(self):
        rom = bytearray(0x80)
        with pytest.raises(PointerValidationError):
            validate_pointer_table(rom, 0x40, 20)

    def test_bad_entry_size(self):
        rom = _gba_rom(text_offset=0x100, count=2)
        with pytest.raises(PointerValidationError):
            validate_pointer_table(rom, 0, 2, entry_size=3)

    def test_non_monotonic(self):
        rom = bytearray(0x1000)
        for i, tgt in enumerate([0x100, 0x108, 0x104, 0x102]):
            rom[i * 4:(i + 1) * 4] = (GBA_BASE + tgt).to_bytes(4, "little")
        records = validate_pointer_table(rom, 0, 4)
        assert records[0]["status"] == STATUS_OK
        assert records[1]["status"] == STATUS_OK
        assert records[2]["status"] == STATUS_NON_MONOTONIC
        assert records[3]["status"] == STATUS_NON_MONOTONIC

    def test_count_zero(self):
        rom = bytearray(0x40)
        assert validate_pointer_table(rom, 0, 0) == []

    def test_count_one(self):
        rom = bytearray(0x1000)
        rom[0:4] = (GBA_BASE + 0x100).to_bytes(4, "little")
        records = validate_pointer_table(rom, 0, 1)
        assert records[0]["status"] == STATUS_OK
        assert records[0]["next"] is None

    def test_negative_count(self):
        rom = bytearray(0x40)
        with pytest.raises(PointerValidationError):
            validate_pointer_table(rom, 0, -1)

    def test_stride_negative(self):
        rom = bytearray(0x1000)
        with pytest.raises(PointerValidationError):
            validate_pointer_table(rom, 0, 4, stride=-4)

    def test_stride_zero(self):
        rom = bytearray(0x1000)
        with pytest.raises(PointerValidationError):
            validate_pointer_table(rom, 0, 4, stride=0)

    def test_stride_less_than_entry_size(self):
        rom = bytearray(0x1000)
        with pytest.raises(PointerValidationError):
            validate_pointer_table(rom, 0, 4, stride=2, entry_size=4)

    def test_problem_summary(self):
        rom = bytearray(0x1000)
        rom[0:4] = (GBA_BASE + 0x100).to_bytes(4, "little")
        rom[8:12] = (GBA_BASE + 0x5000).to_bytes(4, "little")
        rom[12:16] = (GBA_BASE + 0x100).to_bytes(4, "little")
        records = validate_pointer_table(rom, 0, 4)
        summary = problem_summary(records)
        assert summary == {STATUS_OK: 1, STATUS_ZERO: 1,
                           STATUS_OUT_OF_BOUNDS: 1, STATUS_DUPLICATE: 1,
                           STATUS_NON_MONOTONIC: 0}


class TestRepairPointerTable:
    def test_repair_rewrites_targets(self):
        rom = _gba_repair_rom()
        patched = repair_pointer_table(rom, 0, {0: 0x400, 3: 0x410})
        assert patched == 2
        records = validate_pointer_table(rom, 0, 4)
        assert records[0]["target"] == 0x400
        assert records[3]["target"] == 0x410
        assert records[1]["target"] == 0x104

    def test_repair_target_out_of_bounds(self):
        rom = _gba_repair_rom()
        with pytest.raises(PointerValidationError):
            repair_pointer_table(rom, 0, {0: 0x9999})

    def test_repair_pointer_value_overflow(self):
        rom = bytearray(0x1000)
        with pytest.raises(PointerValidationError):
            repair_pointer_table(rom, 0, {0: 0x100}, entry_size=2)

    def test_repair_entry_out_of_rom(self):
        rom = bytearray(8)
        with pytest.raises(PointerValidationError):
            repair_pointer_table(rom, 0, {3: 0x200})

    def test_repair_16bit_flat(self):
        rom = bytearray(0x2000)
        patched = repair_pointer_table(rom, 0, {0: 0x1234}, entry_size=2,
                                       address_base=0)
        assert patched == 1
        assert int.from_bytes(rom[0:2], "little") == 0x1234

    def test_repair_bad_entry_size(self):
        rom = bytearray(0x1000)
        with pytest.raises(PointerValidationError):
            repair_pointer_table(rom, 0, {0: 0x100}, entry_size=3)

    def test_repair_atomic_no_mutation_on_error(self):
        original = _gba_repair_rom()
        snapshot = bytes(original)
        with pytest.raises(PointerValidationError):
            repair_pointer_table(original, 0,
                                 {0: 0x400, 1: 0x9999})
        assert bytes(original) == snapshot

    def test_repair_stride_less_than_entry_size(self):
        rom = bytearray(0x1000)
        with pytest.raises(PointerValidationError):
            repair_pointer_table(rom, 0, {0: 0x100}, stride=2, entry_size=4)
