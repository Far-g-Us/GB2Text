"""Тесты F3 фаз 1-2: тайлы шрифта GB 2bpp (синтетика, без ROM)."""

from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.font_tiles import (
    TILE_BYTES,
    TILE_SIZE,
    decode_2bpp_tile,
    encode_2bpp_tile,
    tile_to_ascii,
    tiles_from_rom,
)


def _sample_raw() -> bytes:
    # Диагональ 3 + вертикаль 1 + инверсия: все значения 0-3 присутствуют.
    raw = bytearray(TILE_BYTES)
    for row in range(TILE_SIZE):
        low = 0
        high = 0
        for col in range(TILE_SIZE):
            value = (row + col) % 4
            low |= (value & 1) << (7 - col)
            high |= ((value >> 1) & 1) << (7 - col)
        raw[row * 2] = low
        raw[row * 2 + 1] = high
    return bytes(raw)


class TestDecode:
    def test_shape_and_values(self):
        grid = decode_2bpp_tile(_sample_raw())
        assert len(grid) == 8 and all(len(row) == 8 for row in grid)
        assert grid[0][7] == (0 + 7) % 4
        assert grid[7][0] == (7 + 0) % 4
        assert {p for row in grid for p in row} == {0, 1, 2, 3}

    def test_short_raises(self):
        with pytest.raises(ValueError):
            decode_2bpp_tile(b"\x00" * 15)

    def test_extra_bytes_ignored(self):
        assert decode_2bpp_tile(_sample_raw() + b"\xff") == decode_2bpp_tile(_sample_raw())

    def test_bytearray_accepted(self):
        assert decode_2bpp_tile(bytearray(_sample_raw())) == decode_2bpp_tile(_sample_raw())


class TestEncode:
    def test_roundtrip(self):
        raw = _sample_raw()
        assert encode_2bpp_tile(decode_2bpp_tile(raw)) == raw

    def test_roundtrip_all_values(self):
        grid = [[(r * 8 + c) % 4 for c in range(8)] for r in range(8)]
        assert decode_2bpp_tile(encode_2bpp_tile(grid)) == grid

    def test_bad_shape(self):
        with pytest.raises(ValueError):
            encode_2bpp_tile([[0] * 8] * 7)
        with pytest.raises(ValueError):
            encode_2bpp_tile([[0] * 7] * 8)

    def test_bad_values(self):
        grid: list[list[Any]] = [[0] * 8 for _ in range(8)]
        grid[3][3] = 4
        with pytest.raises(ValueError):
            encode_2bpp_tile(grid)
        grid[3][3] = -1
        with pytest.raises(ValueError):
            encode_2bpp_tile(grid)
        grid[3][3] = True
        with pytest.raises(ValueError):
            encode_2bpp_tile(grid)
        grid[3][3] = "1"
        with pytest.raises(ValueError):
            encode_2bpp_tile(grid)


class TestAscii:
    def test_known_glyph(self):
        grid = [[0] * 8 for _ in range(8)]
        grid[0] = [3] * 8
        art = tile_to_ascii(grid)
        assert art[0] == "#" * 8
        assert art[1] == " " * 8

    def test_short_palette_raises(self):
        with pytest.raises(ValueError):
            tile_to_ascii([[0] * 8] * 8, palette="ab")

    def test_bad_pixels_raise(self):
        good = [[0] * 8 for _ in range(8)]
        bad = [row[:] for row in good]
        bad[0][0] = 4
        with pytest.raises(ValueError):
            tile_to_ascii(bad)
        bad[0][0] = True
        with pytest.raises(ValueError):
            tile_to_ascii(bad)

    def test_custom_palette(self):
        grid = [[i % 4 for i in range(8)] for _ in range(8)]
        art = tile_to_ascii(grid, palette="0123")
        assert art[0] == "01230123"


class TestTilesFromRom:
    def test_slice(self):
        data = bytes(range(64))
        tiles = tiles_from_rom(data, 16, 2)
        assert tiles == [data[16:32], data[32:48]]

    def test_zero_count(self):
        assert tiles_from_rom(bytes(32), 0, 0) == []

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            tiles_from_rom(bytes(32), -1, 1)
        with pytest.raises(ValueError):
            tiles_from_rom(bytes(32), 0, -1)

    def test_overflow_rejected(self):
        with pytest.raises(ValueError):
            tiles_from_rom(bytes(32), 24, 2)


class TestFontMetaHook:
    def test_default_none(self):
        from core.plugin import GamePlugin

        class P(GamePlugin):
            @property
            def game_id_pattern(self):
                return r"^X$"

            def get_text_segments(self, rom):
                return []

        assert P().get_font_meta() is None

    def test_override(self):
        from core.plugin import GamePlugin

        class P(GamePlugin):
            @property
            def game_id_pattern(self):
                return r"^X$"

            def get_text_segments(self, rom):
                return []

            def get_font_meta(self):
                return {"offset": 0x100, "bpp": 2, "count": 4}

        assert P().get_font_meta() == {"offset": 0x100, "bpp": 2, "count": 4}


class TestInjectGlyphs:
    def test_inplace_bytes(self):
        from core.font_tiles import inject_glyphs

        data = bytearray(64)
        report = inject_glyphs(data, 0, {0: bytes([0xAA] * 16)})
        assert report == [{"index": 0, "offset": 0}]
        assert bytes(data[0:16]) == bytes([0xAA] * 16)
        assert bytes(data[16:]) == bytes(48)

    def test_grid_input_and_order(self):
        from core.font_tiles import inject_glyphs

        grid = [[3] * 8 for _ in range(8)]
        data = bytearray(64)
        report = inject_glyphs(data, 16, {1: grid, 0: bytes(16)})
        assert [r["index"] for r in report] == [0, 1]
        assert bytes(data[16:32]) == bytes(16)
        assert bytes(data[32:48]) == b"\xff" * 16

    def test_bad_input(self):
        from core.font_tiles import inject_glyphs

        with pytest.raises(ValueError):
            inject_glyphs(bytearray(64), 0, {-1: bytes(16)})
        with pytest.raises(ValueError):
            inject_glyphs(bytearray(64), -8, {0: bytes(16)})
        with pytest.raises(ValueError):
            inject_glyphs(bytearray(64), 0, {0: bytes(8)})
        with pytest.raises(ValueError):
            inject_glyphs(bytearray(32), 16, {1: bytes(16)})
        with pytest.raises(ValueError):
            inject_glyphs(bytearray(64), 0, {0: bytes(16)}, stride=0)
        with pytest.raises(ValueError):
            inject_glyphs(bytearray(64), 0, {0: [[0] * 8] * 8}, stride=8)

    def test_no_partial_writes(self):
        from core.font_tiles import inject_glyphs

        data = bytearray(64)
        with pytest.raises(ValueError):
            inject_glyphs(data, 0, {0: bytes(16), 1: bytes(8)})
        assert bytes(data) == bytes(64)

    def test_free_space_composition(self):
        from core.font_tiles import inject_glyphs
        from core.pointer_table import find_free_space

        data = bytearray(b"\x41" * 64 + b"\x00" * 32)
        dest = find_free_space(data, 16, [(0, 64)])
        assert dest == 64
        report = inject_glyphs(data, dest, {0: bytes([0x55] * 16)})
        assert report == [{"index": 0, "offset": 64}]
        assert bytes(data[64:80]) == bytes([0x55] * 16)

    def test_end_to_end_demo(self):
        """Демо механизма: шрифт-блок в синтетическом ROM + кириллический
        глиф А + проверка байтов и ASCII-превью (без реальных ROM)."""
        from core.font_tiles import (
            decode_2bpp_tile,
            inject_glyphs,
            tile_to_ascii,
            tiles_from_rom,
        )

        rom = bytearray(0x200)
        font_base = 0x100
        glyph_a = [
            [0, 0, 1, 1, 1, 1, 0, 0],
            [0, 1, 0, 0, 0, 0, 1, 0],
            [0, 1, 0, 0, 0, 0, 1, 0],
            [0, 1, 1, 1, 1, 1, 1, 0],
            [0, 1, 0, 0, 0, 0, 1, 0],
            [0, 1, 0, 0, 0, 0, 1, 0],
            [0, 1, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
        ]
        report = inject_glyphs(rom, font_base, {0: glyph_a})
        assert report == [{"index": 0, "offset": font_base}]
        (raw,) = tiles_from_rom(rom, font_base, 1)
        assert decode_2bpp_tile(raw) == glyph_a
        art = tile_to_ascii(decode_2bpp_tile(raw))
        assert art[3] == " ...... "


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
