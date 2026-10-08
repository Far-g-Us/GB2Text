"""FRLG latin-шрифт: halves-тайлы, 64B-слоты, halves-мета (синтетика, без ROM)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.font_tiles import (
    decode_2bpp_halves_tile,
    decode_2bpp_tile,
    decode_frlg_latin_glyph,
    encode_2bpp_halves_tile,
    encode_frlg_latin_glyph,
    inject_font_block,
    preview_font_block,
    validate_font_candidate,
    validate_font_meta,
)
from core.font_ui import resolve_font_view
from plugins.gba_pokemon import PokemonGBAPlugin

FRLG_META = {"offset": 0x1FF2F0, "bpp": 2, "stride": 0x40, "count": 256, "halves": [0x10, 0x30]}


def _grid() -> list[list[int]]:
    return [[(r * 3 + c) % 4 for c in range(8)] for r in range(8)]


def test_halves_roundtrip() -> None:
    grid = _grid()
    assert decode_2bpp_halves_tile(encode_2bpp_halves_tile(grid)) == grid


def test_halves_encode_decode_raw() -> None:
    raw = bytes([0x00, 0xFF] + [0x00] * 14)
    assert decode_2bpp_halves_tile(raw)[0] == [3] * 4 + [0] * 4
    assert encode_2bpp_halves_tile(decode_2bpp_halves_tile(raw)) == raw


def test_halves_order_is_not_planar() -> None:
    raw = bytes([0xAA, 0x55] + [0x00] * 14)
    assert decode_2bpp_halves_tile(raw)[0] != decode_2bpp_tile(raw)[0]


def test_halves_bad_input() -> None:
    with pytest.raises(ValueError):
        decode_2bpp_halves_tile(b"\x00" * 15)
    with pytest.raises(ValueError):
        decode_2bpp_halves_tile("x" * 16)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        encode_2bpp_halves_tile([[0] * 7] * 8)
    with pytest.raises(ValueError):
        encode_2bpp_halves_tile([[4] * 8] + [[0] * 8] * 7)
    with pytest.raises(ValueError):
        encode_2bpp_halves_tile([[True] * 8] + [[0] * 8] * 7)


def test_frlg_glyph_roundtrip() -> None:
    top, bottom = _grid(), _grid()[::-1]
    slot = encode_frlg_latin_glyph(top, bottom)
    assert len(slot) == 0x40
    assert slot[0x00:0x10] == bytes(16)
    assert slot[0x20:0x30] == bytes(16)
    assert decode_frlg_latin_glyph(slot) == (top, bottom)
    assert decode_frlg_latin_glyph(bytearray(slot) + b"\xff") == (top, bottom)


def test_frlg_glyph_bad_input() -> None:
    with pytest.raises(ValueError):
        decode_frlg_latin_glyph(b"\x00" * 63)
    with pytest.raises(ValueError):
        decode_frlg_latin_glyph(0x40 * [0])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        encode_frlg_latin_glyph([[9] * 8] * 8, _grid())
    with pytest.raises(ValueError):
        encode_frlg_latin_glyph(_grid(), [[0] * 8] * 7)


def test_meta_halves_ok() -> None:
    norm = validate_font_meta(dict(FRLG_META), 0x2000000)
    assert norm == FRLG_META
    short = {"offset": 0, "bpp": 2, "stride": 16, "count": 2, "halves": [0]}
    assert validate_font_meta(short, 64) == short
    nocount = {"offset": 0x100, "bpp": 2, "stride": 0x40, "halves": [0x10, 0x30]}
    assert validate_font_meta(nocount, 0x200)["count"] == 4
    tupled = {"offset": 0, "bpp": 2, "stride": 0x40, "count": 1, "halves": (0x30, 0x10)}
    assert validate_font_meta(tupled, 0x40)["halves"] == [0x30, 0x10]


def test_meta_halves_bad() -> None:
    base = {"offset": 0, "bpp": 2, "stride": 0x40, "count": 1}
    bads: tuple[object, ...] = ("x", 5, {}, [], [0x10, 0x10], [0x10, 0x18], [-1, 0x10],
                [True, 0x10], ["x", 0x10], [0x10, 0x31], [0x30, 0x40])
    for bad in bads:
        with pytest.raises(ValueError):
            validate_font_meta({**base, "halves": bad}, 0x40)
    for stride in (0, -16, True, "x"):
        with pytest.raises(ValueError):
            validate_font_meta({**base, "stride": stride, "halves": [0x10, 0x30]}, 0x400)


def test_raw_paths_refuse_split() -> None:
    data = bytearray(0x80)
    with pytest.raises(ValueError, match="glyph-aware"):
        preview_font_block(data, {**FRLG_META, "offset": 0, "count": 2}, {0: _grid()})
    with pytest.raises(ValueError, match="glyph-aware"):
        inject_font_block(data, {**FRLG_META, "offset": 0, "count": 2}, {0: _grid()}, confirm=True)
    with pytest.raises(ValueError, match="glyph-aware"):
        validate_font_candidate(data, {**FRLG_META, "offset": 0, "count": 2})
    with pytest.raises(ValueError, match="split layout"):
        preview_font_block(data, {"offset": 0, "bpp": 2, "stride": 0, "count": 1, "halves": [0]}, {})


def test_map_imported_grids_refuses_split() -> None:
    from core.font_ui import map_imported_grids

    with pytest.raises(ValueError, match="glyph-aware"):
        map_imported_grids({**FRLG_META, "offset": 0}, 0x4000, [_grid()] * 256)


def test_resolve_split_is_invalid() -> None:
    view = resolve_font_view(bytearray(0x200), {**FRLG_META, "offset": 0, "count": 2})
    assert view["status"] == "invalid"
    assert "halves" in view["error"]


def test_plugin_font_meta_gating() -> None:
    fresh = PokemonGBAPlugin()
    assert fresh.get_font_meta() is None
    for code, want in (("BPRE", True), ("BPGE", False), ("BPEE", False), ("BPEJ", False), ("XXXX", False)):
        plugin = PokemonGBAPlugin()
        plugin._game_code = code
        meta = plugin.get_font_meta()
        if want:
            assert meta is not None
            assert validate_font_meta(meta, 0x2000000)["halves"] == [0x10, 0x30]
        else:
            assert meta is None
