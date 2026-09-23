"""F1: 1bpp/4bpp, FontLayout, гейты, PNG, манифест (синтетика, без ROM)."""

from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from PIL import Image

from core.font_tiles import (
    build_font_manifest,
    decode_1bpp_tile,
    decode_2bpp_tile,
    decode_4bpp_tile,
    decode_tile,
    encode_1bpp_tile,
    encode_2bpp_tile,
    encode_4bpp_tile,
    encode_tile,
    font_grids_to_image,
    image_to_grids,
    inject_font_block,
    inject_glyphs,
    is_likely_compressed,
    preview_font_block,
    stride_for_bpp,
    tile_to_ascii,
    tiles_from_rom,
    validate_font_candidate,
    validate_font_meta,
    validate_glyph_widths,
)


def _any(value: object) -> Any:
    return value


def _grid_2bpp() -> list[list[int]]:
    return [[(r + c) % 4 for c in range(8)] for r in range(8)]


def _grid_1bpp() -> list[list[int]]:
    return [[(r + c) % 2 for c in range(8)] for r in range(8)]


def _grid_4bpp() -> list[list[int]]:
    return [[(r * 8 + c) % 16 for c in range(8)] for r in range(8)]


def _layout(**kw: object) -> dict:
    base: dict = {"offset": 0, "bpp": 2, "stride": 16, "count": 2}
    base.update(kw)
    return base


class TestStride:
    def test_known(self):
        assert stride_for_bpp(1) == 8
        assert stride_for_bpp(2) == 16
        assert stride_for_bpp(4) == 32

    def test_unknown(self):
        cases: tuple[Any, ...] = (0, 3, 5, -1, "2", None, True, 2.0)
        for bad in cases:
            with pytest.raises(ValueError):
                stride_for_bpp(bad)


class TestBpp1:
    def test_roundtrip(self):
        grid = _grid_1bpp()
        assert decode_1bpp_tile(encode_1bpp_tile(grid)) == grid

    def test_bit_order(self):
        raw = encode_1bpp_tile([[1] + [0] * 7 for _ in range(8)])
        assert raw == bytes([0x80] * 8)
        assert decode_1bpp_tile(raw)[0] == [1] + [0] * 7

    def test_short_raises(self):
        with pytest.raises(ValueError):
            decode_1bpp_tile(b"\x00" * 7)

    def test_bad_data(self):
        for bad in (None, "xxxxxxxx", 5):
            with pytest.raises(ValueError):
                decode_1bpp_tile(_any(bad))
            with pytest.raises(ValueError):
                decode_4bpp_tile(_any(bad))

    def test_bad_values(self):
        grid = _grid_1bpp()
        grid[0][0] = _any(2)
        with pytest.raises(ValueError):
            encode_1bpp_tile(grid)
        grid[0][0] = _any(True)
        with pytest.raises(ValueError):
            encode_1bpp_tile(grid)

    def test_bad_shape(self):
        with pytest.raises(ValueError):
            encode_1bpp_tile([[0] * 8] * 7)
        with pytest.raises(ValueError):
            encode_1bpp_tile([[0] * 7] * 8)


class TestBpp4:
    def test_roundtrip(self):
        grid = _grid_4bpp()
        assert decode_4bpp_tile(encode_4bpp_tile(grid)) == grid

    def test_nibble_order(self):
        grid = [[0] * 8 for _ in range(8)]
        grid[0][0] = 0x0B
        grid[0][1] = 0x0A
        raw = encode_4bpp_tile(grid)
        assert raw[0] == 0xAB
        assert decode_4bpp_tile(raw)[0][:2] == [0x0B, 0x0A]

    def test_short_raises(self):
        with pytest.raises(ValueError):
            decode_4bpp_tile(b"\x00" * 31)

    def test_bad_values(self):
        grid = _grid_4bpp()
        grid[1][1] = _any(16)
        with pytest.raises(ValueError):
            encode_4bpp_tile(grid)
        grid[1][1] = _any(True)
        with pytest.raises(ValueError):
            encode_4bpp_tile(grid)
        grid[1][1] = _any("f")
        with pytest.raises(ValueError):
            encode_4bpp_tile(grid)

    def test_bad_shape(self):
        with pytest.raises(ValueError):
            encode_4bpp_tile([[0] * 8] * 7)


class TestDispatch:
    def test_decode_ok(self):
        assert decode_tile(encode_1bpp_tile(_grid_1bpp()), 1) == _grid_1bpp()
        assert decode_tile(encode_2bpp_tile(_grid_2bpp()), 2) == _grid_2bpp()
        assert decode_tile(encode_4bpp_tile(_grid_4bpp()), 4) == _grid_4bpp()

    def test_tuple_grids(self):
        grid = tuple(tuple(row) for row in _grid_2bpp())
        assert decode_2bpp_tile(encode_2bpp_tile(grid)) == _grid_2bpp()
        assert tile_to_ascii(grid)[0] == tile_to_ascii(_grid_2bpp())[0]

    def test_decode_bad_bpp(self):
        cases: tuple[Any, ...] = (0, 3, "2", None, True)
        for bad in cases:
            with pytest.raises(ValueError):
                decode_tile(bytes(32), bad)

    def test_encode_ok(self):
        assert encode_tile(_grid_1bpp(), 1) == encode_1bpp_tile(_grid_1bpp())
        assert encode_tile(_grid_2bpp(), 2) == encode_2bpp_tile(_grid_2bpp())
        assert encode_tile(_grid_4bpp(), 4) == encode_4bpp_tile(_grid_4bpp())

    def test_encode_bad_bpp(self):
        cases: tuple[Any, ...] = (0, 5, "4", None, False)
        for bad in cases:
            with pytest.raises(ValueError):
                encode_tile(_grid_2bpp(), bad)


class TestValidateMeta:
    def test_full_explicit(self):
        assert validate_font_meta({"offset": 0x100, "bpp": 2, "stride": 16, "count": 4}, 0x200) == {
            "offset": 0x100,
            "bpp": 2,
            "stride": 16,
            "count": 4,
        }

    def test_defaults(self):
        assert validate_font_meta({"offset": 0}, 64) == {"offset": 0, "bpp": 2, "stride": 16, "count": 4}
        assert validate_font_meta({"offset": 8, "bpp": 1}, 32) == {"offset": 8, "bpp": 1, "stride": 8, "count": 3}

    def test_not_dict(self):
        cases: tuple[Any, ...] = (None, [], "x", 5)
        for bad in cases:
            with pytest.raises(ValueError):
                validate_font_meta(bad, 64)

    def test_bad_rom_len(self):
        cases: tuple[Any, ...] = (True, -1, "64", None)
        for bad in cases:
            with pytest.raises(ValueError):
                validate_font_meta({"offset": 0}, bad)

    def test_missing_offset(self):
        with pytest.raises(ValueError):
            validate_font_meta({"bpp": 2}, 64)

    def test_bad_offset(self):
        cases: tuple[Any, ...] = (True, "x", -1, None, 64, 100)
        for bad in cases:
            with pytest.raises(ValueError):
                validate_font_meta({"offset": bad}, 64)

    def test_bad_bpp(self):
        cases: tuple[Any, ...] = (3, "2", None, True, 1.5)
        for bad in cases:
            with pytest.raises(ValueError):
                validate_font_meta({"offset": 0, "bpp": bad}, 64)

    def test_bad_stride(self):
        with pytest.raises(ValueError):
            validate_font_meta({"offset": 0, "bpp": 1, "stride": 16}, 64)
        cases: tuple[Any, ...] = ("x", True, 0)
        for bad in cases:
            with pytest.raises(ValueError):
                validate_font_meta({"offset": 0, "stride": bad}, 64)

    def test_no_room_default_count(self):
        with pytest.raises(ValueError):
            validate_font_meta({"offset": 24}, 32)

    def test_bad_count(self):
        cases: tuple[Any, ...] = (0, -2, True, "x", type(None))
        for bad in cases:
            with pytest.raises(ValueError):
                validate_font_meta({"offset": 0, "count": bad}, 64)

    def test_overflow(self):
        with pytest.raises(ValueError):
            validate_font_meta({"offset": 32, "count": 3}, 64)


class TestCompressedGate:
    def test_bad_offset(self):
        with pytest.raises(ValueError):
            is_likely_compressed(bytes(16), -1)
        with pytest.raises(ValueError):
            is_likely_compressed(bytes(16), 13)
        cases: tuple[Any, ...] = (True, "x", None, 1.5)
        for bad in cases:
            with pytest.raises(ValueError):
                is_likely_compressed(bytes(16), bad)

    def test_not_compressed(self):
        assert is_likely_compressed(bytes(16), 0) is False
        assert is_likely_compressed(b"\x11\x00\x10\x00" + bytes(12), 0) is False

    def test_zero_size(self):
        assert is_likely_compressed(b"\x10\x00\x00\x00" + bytes(12), 0) is False

    def test_huge_size(self):
        assert is_likely_compressed(b"\x10\xff\xff\xff" + bytes(12), 0) is False

    def test_likely(self):
        assert is_likely_compressed(b"\x10\x00\x10\x00" + bytes(12), 0) is True

    def test_bad_data(self):
        for bad in (None, "xxxxxxxxxxxxxxxx", 5):
            with pytest.raises(ValueError):
                is_likely_compressed(_any(bad), 0)


class TestCandidateGate:
    def _data(self) -> bytearray:
        data = bytearray(64)
        data[0:16] = b"\xaa" * 16
        data[16:32] = b"\x55" * 16
        return data

    def test_ok(self):
        report = validate_font_candidate(self._data(), _layout(count=4))
        assert report == {"blank": 2, "distinct": 2, "empty_ratio": 0.5}

    def test_too_empty(self):
        with pytest.raises(ValueError):
            validate_font_candidate(bytearray(64), _layout(count=4))

    def test_ratio_threshold(self):
        with pytest.raises(ValueError):
            validate_font_candidate(self._data(), _layout(count=4), empty_ratio_max=0.4)

    def test_distinct_threshold(self):
        data = bytearray(64)
        data[0:16] = b"\xaa" * 16
        data[16:32] = b"\xaa" * 16
        with pytest.raises(ValueError):
            validate_font_candidate(data, _layout(count=4), min_nonempty=2)

    def test_all_blank_zero_distinct(self):
        with pytest.raises(ValueError):
            validate_font_candidate(bytearray(64), _layout(count=4), empty_ratio_max=1.0)

    def test_bad_params(self):
        cases: tuple[Any, ...] = (True, "x", -0.1, 1.5, None)
        for bad in cases:
            with pytest.raises(ValueError):
                validate_font_candidate(self._data(), _layout(count=4), empty_ratio_max=bad)
        counts: tuple[Any, ...] = (0, -1, True, "x")
        for bad in counts:
            with pytest.raises(ValueError):
                validate_font_candidate(self._data(), _layout(count=4), min_nonempty=bad)

    def test_too_large(self):
        with pytest.raises(ValueError):
            validate_font_candidate(bytearray(64), _layout(count=70000))

    def test_bad_data(self):
        for bad in (None, "x" * 64, 5):
            with pytest.raises(ValueError):
                validate_font_candidate(_any(bad), _layout(count=4))

    def test_overflow(self):
        with pytest.raises(ValueError):
            validate_font_candidate(bytearray(64), _layout(count=5))

    def test_bad_layout(self):
        with pytest.raises(ValueError):
            validate_font_candidate(bytearray(64), {"offset": 0})
        with pytest.raises(ValueError):
            validate_font_candidate(bytearray(64), _any([]))


class TestPreview:
    def test_ok_no_write(self):
        data = bytearray(64)
        grid = _grid_2bpp()
        plan = preview_font_block(data, _layout(), {1: grid})
        assert [p["index"] for p in plan] == [1]
        assert plan[0]["offset"] == 16
        assert plan[0]["old_bytes"] == bytes(16)
        assert plan[0]["new_bytes"] == encode_2bpp_tile(grid)
        assert bytes(data) == bytes(64)

    def test_bytes_glyph(self):
        data = bytearray(64)
        plan = preview_font_block(data, _layout(), {0: b"\xaa" * 16})
        assert plan[0]["new_bytes"] == b"\xaa" * 16

    def test_bad_layout(self):
        with pytest.raises(ValueError):
            preview_font_block(bytearray(64), {"offset": 0}, {0: bytes(16)})
        for bad_layout in (_layout(offset=-1), _layout(stride=8), _layout(count=0), _layout(bpp=3)):
            with pytest.raises(ValueError):
                preview_font_block(bytearray(64), bad_layout, {0: bytes(16)})

    def test_empty_glyphs(self):
        cases: tuple[Any, ...] = ({}, [], None, "x")
        for bad in cases:
            with pytest.raises(ValueError):
                preview_font_block(bytearray(64), _layout(), bad)

    def test_bad_index(self):
        cases: tuple[Any, ...] = (-1, 2, 9, True, "0", None)
        for bad in cases:
            with pytest.raises(ValueError):
                preview_font_block(bytearray(64), _layout(), {bad: bytes(16)})

    def test_bad_bytes_len(self):
        with pytest.raises(ValueError):
            preview_font_block(bytearray(64), _layout(), {0: bytes(8)})

    def test_bad_grid(self):
        with pytest.raises(ValueError):
            preview_font_block(bytearray(64), _layout(), {0: [[9] * 8] * 8})

    def test_out_of_data(self):
        with pytest.raises(ValueError):
            preview_font_block(bytearray(32), _layout(count=4), {2: bytes(16)})

    def test_global_bounds(self):
        with pytest.raises(ValueError):
            preview_font_block(bytearray(32), _layout(count=4), {0: bytes(16)})

    def test_bad_data(self):
        for bad in (None, "x" * 64, 5):
            with pytest.raises(ValueError):
                preview_font_block(_any(bad), _layout(), {0: bytes(16)})

    def test_mixed_keys(self):
        with pytest.raises(ValueError):
            preview_font_block(bytearray(64), _layout(), {0: bytes(16), _any("a"): bytes(16)})


class TestInjectBlock:
    def test_confirm_required(self):
        cases: tuple[Any, ...] = (False, 0, 1, "yes", None)
        for bad in cases:
            with pytest.raises(ValueError):
                inject_font_block(bytearray(64), _layout(), {0: bytes(16)}, confirm=bad)

    def test_immutable_refused(self):
        with pytest.raises(ValueError):
            inject_font_block(_any(bytes(64)), _layout(), {0: bytes(16)}, confirm=True)
        with pytest.raises(ValueError):
            inject_font_block(_any(None), _layout(), {0: bytes(16)}, confirm=True)

    def test_ok(self):
        data = bytearray(64)
        grid = _grid_2bpp()
        report = inject_font_block(data, _layout(), {0: grid}, confirm=True)
        assert report == [{"index": 0, "offset": 0, "bpp": 2}]
        assert bytes(data[0:16]) == encode_2bpp_tile(grid)
        assert bytes(data[16:]) == bytes(48)

    def test_compressed_refused(self):
        data = bytearray(b"\x10\x00\x10\x00" + bytes(60))
        with pytest.raises(ValueError):
            inject_font_block(data, _layout(), {1: bytes(16)}, confirm=True)
        assert bytes(data) == b"\x10\x00\x10\x00" + bytes(60)

    def test_compressed_allowed(self):
        data = bytearray(b"\x10\x00\x10\x00" + bytes(60))
        report = inject_font_block(data, _layout(), {1: b"\xaa" * 16}, confirm=True, allow_compressed=True)
        assert report == [{"index": 1, "offset": 16, "bpp": 2}]
        assert bytes(data[16:32]) == b"\xaa" * 16

    def test_atomic(self):
        data = bytearray(64)
        with pytest.raises(ValueError):
            inject_font_block(data, _layout(), {0: bytes(16), 1: bytes(8)}, confirm=True)
        assert bytes(data) == bytes(64)

    def test_bounds_before_compressed(self):
        data = bytearray(b"\x10\x00\x10\x00" + bytes(28))
        with pytest.raises(ValueError):
            inject_font_block(data, _layout(count=4), {0: bytes(16)}, confirm=True)
        assert bytes(data) == b"\x10\x00\x10\x00" + bytes(28)

    def test_no_touch_outside(self):
        data = bytearray(bytes(range(256))[:96])
        inject_font_block(data, {"offset": 32, "bpp": 2, "stride": 16, "count": 4}, {0: bytes(16)}, confirm=True)
        assert bytes(data[:32]) == bytes(range(32))
        assert bytes(data[48:]) == bytes(range(48, 96))


class TestInjectGlyphsBpp:
    def test_bad_bpp(self):
        cases: tuple[Any, ...] = (0, 3, "2", None, True)
        for bad in cases:
            with pytest.raises(ValueError):
                inject_glyphs(bytearray(64), 0, {0: bytes(16)}, bpp=bad)

    def test_1bpp_ok(self):
        data = bytearray(32)
        report = inject_glyphs(data, 0, {0: _grid_1bpp()}, stride=8, bpp=1)
        assert report == [{"index": 0, "offset": 0}]
        assert bytes(data[0:8]) == encode_1bpp_tile(_grid_1bpp())

    def test_4bpp_ok(self):
        data = bytearray(64)
        report = inject_glyphs(data, 0, {0: _grid_4bpp()}, stride=32, bpp=4)
        assert report == [{"index": 0, "offset": 0}]
        assert bytes(data[0:32]) == encode_4bpp_tile(_grid_4bpp())

    def test_stride_mismatch(self):
        with pytest.raises(ValueError):
            inject_glyphs(bytearray(64), 0, {0: _grid_4bpp()}, stride=16, bpp=4)


class TestInjectGlyphsGates:
    def test_immutable_refused(self):
        with pytest.raises(ValueError):
            inject_glyphs(_any(bytes(64)), 0, {0: bytes(16)})
        with pytest.raises(ValueError):
            inject_glyphs(_any("x" * 64), 0, {0: bytes(16)})

    def test_bad_stride(self):
        cases: tuple[Any, ...] = (True, "x", None, 1.5)
        for bad in cases:
            with pytest.raises(ValueError):
                inject_glyphs(bytearray(64), 0, {0: bytes(16)}, stride=bad)

    def test_bad_base(self):
        cases: tuple[Any, ...] = (True, "x", None)
        for bad in cases:
            with pytest.raises(ValueError):
                inject_glyphs(bytearray(64), bad, {0: bytes(16)})

    def test_not_dict(self):
        cases: tuple[Any, ...] = (None, [], "x")
        for bad in cases:
            with pytest.raises(ValueError):
                inject_glyphs(bytearray(64), 0, bad)

    def test_bad_index(self):
        cases: tuple[Any, ...] = (True, "0", None, 1.5)
        for bad in cases:
            with pytest.raises(ValueError):
                inject_glyphs(bytearray(64), 0, {bad: bytes(16)})

    def test_mixed_keys(self):
        with pytest.raises(ValueError):
            inject_glyphs(bytearray(64), 0, {0: bytes(16), _any("a"): bytes(16)})


class TestTilesStride:
    def test_ok(self):
        data = bytes(range(64))
        assert tiles_from_rom(data, 0, 2, stride=8) == [data[0:8], data[8:16]]
        assert tiles_from_rom(data, 0, 1, stride=32) == [data[0:32]]

    def test_bad_stride(self):
        for bad in (0, -8):
            with pytest.raises(ValueError):
                tiles_from_rom(bytes(64), 0, 1, stride=bad)

    def test_bad_types(self):
        cases: tuple[Any, ...] = (True, "x", None, 1.5)
        for bad in cases:
            with pytest.raises(ValueError):
                tiles_from_rom(bytes(64), bad, 1)
            with pytest.raises(ValueError):
                tiles_from_rom(bytes(64), 0, bad)
            with pytest.raises(ValueError):
                tiles_from_rom(bytes(64), 0, 1, stride=bad)

    def test_bad_data(self):
        for bad in (None, "x" * 64, 5):
            with pytest.raises(ValueError):
                tiles_from_rom(_any(bad), 0, 1)


class TestPng:
    def test_roundtrip(self):
        grids = [_grid_2bpp(), _grid_1bpp(), [[3] * 8 for _ in range(8)], [[0] * 8 for _ in range(8)]]
        img = font_grids_to_image(grids, columns=2, scale=1)
        assert img.mode == "P"
        assert img.size == (16, 16)
        assert image_to_grids(img, bpp=2) == grids

    def test_scale(self):
        img = font_grids_to_image([_grid_1bpp()], columns=1, scale=2)
        assert img.size == (16, 16)

    def test_partial_row_trim(self):
        grids = [_grid_1bpp() for _ in range(10)]
        img = font_grids_to_image(grids, columns=16, scale=1)
        assert img.size == (128, 8)
        assert image_to_grids(img, bpp=1)[:10] == grids

    def test_empty(self):
        cases: tuple[Any, ...] = ([], (), None, "x")
        for bad in cases:
            with pytest.raises(ValueError):
                font_grids_to_image(bad)

    def test_bad_columns_scale(self):
        cases: tuple[Any, ...] = (0, -1, True, "x")
        for bad in cases:
            with pytest.raises(ValueError):
                font_grids_to_image([_grid_1bpp()], columns=bad)
            with pytest.raises(ValueError):
                font_grids_to_image([_grid_1bpp()], scale=bad)

    def test_bad_grid_values(self):
        with pytest.raises(ValueError):
            font_grids_to_image([[[16] * 8] * 8])

    def test_import_bad_bpp(self):
        img = font_grids_to_image([_grid_1bpp()])
        cases: tuple[Any, ...] = (0, 3, "2", True)
        for bad in cases:
            with pytest.raises(ValueError):
                image_to_grids(img, bpp=bad)

    def test_import_bad_mode(self):
        assert image_to_grids(font_grids_to_image([_grid_1bpp()]), bpp=2)[0] == _grid_1bpp()
        for mode in ("RGB", "L", "RGBA"):
            with pytest.raises(ValueError):
                image_to_grids(Image.new(mode, (8, 8)), bpp=2)
        for bad in (None, "x", 5):
            with pytest.raises(ValueError):
                image_to_grids(_any(bad), bpp=2)

    def test_import_bad_size(self):
        with pytest.raises(ValueError):
            image_to_grids(Image.new("P", (10, 8)), bpp=2)
        with pytest.raises(ValueError):
            image_to_grids(Image.new("P", (4, 8)), bpp=2)

    def test_import_pixel_range(self):
        img = font_grids_to_image([[[5] * 8 for _ in range(8)]])
        with pytest.raises(ValueError):
            image_to_grids(img, bpp=1)
        assert image_to_grids(img, bpp=4)[0] == [[5] * 8 for _ in range(8)]


class TestAsciiGates:
    def test_bad_palette(self):
        from core.font_tiles import tile_to_ascii

        for bad in (None, 5, "ab"):
            with pytest.raises(ValueError):
                tile_to_ascii(_grid_2bpp(), palette=_any(bad))

    def test_bad_grid(self):
        from core.font_tiles import tile_to_ascii

        for bad in (None, 5, "xxxxxxxx"):
            with pytest.raises(ValueError):
                tile_to_ascii(_any(bad))


class TestManifest:
    def test_str_input(self):
        assert build_font_manifest("AB", start_index=5) == {"A": 5, "B": 6}

    def test_list_input(self):
        assert build_font_manifest(["А", "Б"]) == {"А": 0, "Б": 1}

    def test_empty(self):
        assert build_font_manifest([]) == {}

    def test_not_sequence(self):
        with pytest.raises(ValueError):
            build_font_manifest(_any(5))

    def test_bad_start(self):
        cases: tuple[Any, ...] = (-1, True, "x", None)
        for bad in cases:
            with pytest.raises(ValueError):
                build_font_manifest(["A"], start_index=bad)

    def test_bad_char(self):
        cases: tuple[Any, ...] = ("", None, 5)
        for bad in cases:
            with pytest.raises(ValueError):
                build_font_manifest([bad])
        with pytest.raises(ValueError):
            build_font_manifest(["A", ""])

    def test_duplicate(self):
        with pytest.raises(ValueError):
            build_font_manifest(["A", "A"])


class TestWidths:
    def test_ok(self):
        assert validate_glyph_widths([8, 5, 1], 3) == [8, 5, 1]
        assert validate_glyph_widths([], 0) == []

    def test_bad_count(self):
        cases: tuple[Any, ...] = (-1, True, "x")
        for bad in cases:
            with pytest.raises(ValueError):
                validate_glyph_widths([8], bad)

    def test_not_sequence(self):
        with pytest.raises(ValueError):
            validate_glyph_widths(_any(5), 1)

    def test_len_mismatch(self):
        with pytest.raises(ValueError):
            validate_glyph_widths([8, 8], 3)

    def test_bad_value(self):
        cases: tuple[Any, ...] = (0, 9, -1, True, "x", None)
        for bad in cases:
            with pytest.raises(ValueError):
                validate_glyph_widths([bad], 1)


class TestInjectorSaveLayer1:
    def test_checksums_and_bytes(self, tmp_path):
        from core.injector import TextInjector
        from core.rom import GameBoyROM

        size = 0x8000
        data = bytearray(size)
        data[0x134 : 0x13C] = b"FONTTEST"
        checksum = 0
        for addr in range(0x0134, 0x014D):
            checksum = (checksum - data[addr] - 1) & 0xFF
        data[0x14D] = checksum
        total = 0
        for i in range(size):
            if i not in (0x14E, 0x14F):
                total = (total + data[i]) & 0xFFFF
        data[0x14E] = (total >> 8) & 0xFF
        data[0x14F] = total & 0xFF
        src = tmp_path / "font.gb"
        src.write_bytes(bytes(data))
        injector = TextInjector(str(src))
        layout = validate_font_meta({"offset": 0x4000, "bpp": 2, "count": 4}, len(injector.modified_data))
        grid = _grid_2bpp()
        report = inject_font_block(injector.modified_data, layout, {0: grid}, confirm=True)
        assert report == [{"index": 0, "offset": 0x4000, "bpp": 2}]
        out = tmp_path / "font_out.gb"
        injector.save(str(out))
        raw = bytes(out.read_bytes())
        rom = GameBoyROM(str(out))
        assert rom.validate_header()
        assert rom.calculate_global_checksum(raw) == (raw[0x14E] << 8) | raw[0x14F]
        assert tiles_from_rom(raw, 0x4000, 1)[0] == encode_2bpp_tile(grid)
        assert raw[:0x14E] == bytes(data[:0x14E])
        assert raw[0x150:0x4000] == bytes(data[0x150:0x4000])
        assert raw[0x4010:] == bytes(data[0x4010:])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
