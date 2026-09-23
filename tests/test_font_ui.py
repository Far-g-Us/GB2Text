"""F2 MR1: логика вкладки шрифта (синтетика, без tkinter/ROM)."""

from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.font_tiles import encode_2bpp_tile
from core.font_ui import (
    map_imported_grids,
    resolve_font_view,
    restore_zone,
    snapshot_zone,
)


def _meta(**kw: object) -> dict:
    base: dict = {"offset": 0, "bpp": 2, "stride": 16, "count": 2}
    base.update(kw)
    return base


def _grid() -> list[list[int]]:
    return [[(r + c) % 4 for c in range(8)] for r in range(8)]


def _any(value: object) -> Any:
    return value


class TestResolve:
    def test_no_rom(self):
        assert resolve_font_view(None, _meta()) == {"status": "no_rom"}

    def test_bad_data(self):
        for bad in ("x" * 64, 5, None.__class__):
            with pytest.raises(ValueError):
                resolve_font_view(_any(bad), _meta())

    def test_unknown_meta(self):
        assert resolve_font_view(bytearray(64), None) == {"status": "unknown_meta"}

    def test_invalid(self):
        view = resolve_font_view(bytearray(64), {"offset": 0, "bpp": 3})
        assert view["status"] == "invalid"
        assert view["error"]

    def test_compressed(self):
        data = bytearray(b"\x10\x00\x10\x00" + bytes(60))
        view = resolve_font_view(data, _meta())
        assert view["status"] == "compressed"
        assert view["layout"] == {"offset": 0, "bpp": 2, "stride": 16, "count": 2}

    def test_ok(self):
        data = bytearray(64)
        data[0:16] = encode_2bpp_tile(_grid())
        view = resolve_font_view(data, _meta())
        assert view["status"] == "ok"
        assert view["layout"] == {"offset": 0, "bpp": 2, "stride": 16, "count": 2}
        assert view["grids"][0] == _grid()
        assert view["grids"][1] == [[0] * 8 for _ in range(8)]

    def test_ok_bytes(self):
        view = resolve_font_view(bytes(64), _meta())
        assert view["status"] == "ok"

    def test_too_large(self):
        data = bytearray(5000 * 16)
        view = resolve_font_view(data, _meta(count=5000))
        assert view["status"] == "invalid"
        assert "too large" in view["error"]

    def test_max_boundary(self):
        data = bytearray(4096 * 16)
        view = resolve_font_view(data, _meta(count=4096))
        assert view["status"] == "ok"
        assert len(view["grids"]) == 4096


class TestSnapshot:
    def test_roundtrip(self):
        from core.font_tiles import inject_font_block

        data = bytearray(64)
        snap = snapshot_zone(data, _meta())
        assert snap == {"offset": 0, "bytes": bytes(32)}
        inject_font_block(data, _meta(), {0: _grid()}, confirm=True)
        assert bytes(data[0:16]) != bytes(16)
        restore_zone(data, snap)
        assert bytes(data) == bytes(64)

    def test_bad_data(self):
        for bad in (None, "x" * 64):
            with pytest.raises(ValueError):
                snapshot_zone(_any(bad), _meta())

    def test_invalid_meta(self):
        with pytest.raises(ValueError):
            snapshot_zone(bytearray(64), {"offset": 0, "bpp": 9})


class TestRestore:
    def test_bad_buf(self):
        for bad in (bytes(64), None, "x" * 64):
            with pytest.raises(ValueError):
                restore_zone(_any(bad), {"offset": 0, "bytes": bytes(16)})

    def test_bad_snapshot(self):
        cases: tuple[Any, ...] = (None, [], "x")
        for bad in cases:
            with pytest.raises(ValueError):
                restore_zone(bytearray(64), _any(bad))

    def test_missing_keys(self):
        with pytest.raises(ValueError):
            restore_zone(bytearray(64), {"offset": 0})
        with pytest.raises(ValueError):
            restore_zone(bytearray(64), {"bytes": bytes(16)})

    def test_bad_offset(self):
        for bad in (True, -1, "x", None):
            with pytest.raises(ValueError):
                restore_zone(bytearray(64), {"offset": _any(bad), "bytes": bytes(16)})

    def test_bad_bytes(self):
        for bad in ("x" * 16, 5, None):
            with pytest.raises(ValueError):
                restore_zone(bytearray(64), {"offset": 0, "bytes": _any(bad)})

    def test_overflow(self):
        with pytest.raises(ValueError):
            restore_zone(bytearray(64), {"offset": 56, "bytes": bytes(16)})


class TestMap:
    def test_ok(self):
        grids = [_grid(), _grid()]
        assert map_imported_grids(_meta(), 64, grids) == {0: grids[0], 1: grids[1]}

    def test_tuple(self):
        grids = (_grid(), _grid())
        assert map_imported_grids(_meta(), 64, _any(grids)) == {0: grids[0], 1: grids[1]}

    def test_bad_layout(self):
        with pytest.raises(ValueError):
            map_imported_grids({"offset": 0, "bpp": 3}, 64, [_grid(), _grid()])

    def test_not_list(self):
        for bad in (None, "xx", 5, {0: _grid()}):
            with pytest.raises(ValueError):
                map_imported_grids(_meta(), 64, _any(bad))

    def test_len_mismatch(self):
        with pytest.raises(ValueError):
            map_imported_grids(_meta(), 64, [_grid()])
        with pytest.raises(ValueError):
            map_imported_grids(_meta(), 64, [])

    def test_bad_grid(self):
        with pytest.raises(ValueError):
            map_imported_grids(_meta(), 64, [_grid(), [[9] * 8] * 8])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
