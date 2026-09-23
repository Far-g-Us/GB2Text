"""F2 MR1: smoke вкладки шрифта на mock-ctx (реальный Tk, без ROM)."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.font_tiles import encode_2bpp_tile, font_grids_to_image, inject_font_block
from gui import theme
from gui.font_tab import FontTab

pytestmark = [pytest.mark.gui, pytest.mark.slow]


def _grid() -> list[list[int]]:
    return [[(r + c) % 4 for c in range(8)] for r in range(8)]


def _meta(**kw: object) -> dict:
    base: dict = {"offset": 0, "bpp": 2, "stride": 16, "count": 2}
    base.update(kw)
    return base


def _make_ctx(data, meta):
    calls: dict = {"dirty": []}
    ctx = {
        "get_data": lambda: data,
        "get_meta": lambda: meta,
        "do_inject": lambda layout, glyphs: inject_font_block(data, layout, glyphs, confirm=True),
        "mark_dirty": lambda msg: calls["dirty"].append(msg),
        "t": lambda key, **kw: key,
    }
    return ctx, calls


@pytest.fixture
def root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Нет Tk display: {exc}")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def tab(root, monkeypatch):
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    data = bytearray(64)
    data[0:16] = encode_2bpp_tile(_grid())
    ctx, calls = _make_ctx(data, _meta())
    widget = FontTab(root, ctx)
    widget.pack()
    root.update_idletasks()
    yield widget, data, calls
    theme.unregister_post_apply_hook(widget._reapply_colors)
    widget.destroy()


class TestStates:
    def test_no_rom(self, root):
        ctx, _ = _make_ctx(None, None)
        widget = FontTab(root, ctx)
        widget.refresh()
        assert widget._view["status"] == "no_rom"
        assert str(widget._btn_write["state"]) == "disabled"
        theme.unregister_post_apply_hook(widget._reapply_colors)
        widget.destroy()

    def test_unknown_meta(self, root):
        ctx, _ = _make_ctx(bytearray(64), None)
        widget = FontTab(root, ctx)
        widget.refresh()
        assert widget._view["status"] == "unknown_meta"
        theme.unregister_post_apply_hook(widget._reapply_colors)
        widget.destroy()

    def test_invalid_meta(self, root):
        ctx, _ = _make_ctx(bytearray(64), {"offset": 0, "bpp": 3})
        widget = FontTab(root, ctx)
        widget.refresh()
        assert widget._view["status"] == "invalid"
        theme.unregister_post_apply_hook(widget._reapply_colors)
        widget.destroy()

    def test_compressed(self, root):
        ctx, _ = _make_ctx(bytearray(b"\x10\x00\x10\x00" + bytes(60)), _meta())
        widget = FontTab(root, ctx)
        widget.refresh()
        assert widget._view["status"] == "compressed"
        assert str(widget._btn_write["state"]) == "disabled"
        theme.unregister_post_apply_hook(widget._reapply_colors)
        widget.destroy()

    def test_ok_renders(self, tab):
        widget, _, _ = tab
        widget.refresh()
        assert widget._view["status"] == "ok"
        assert widget._img_refs


class TestImportWriteUndo:
    def test_flow(self, tab, tmp_path, monkeypatch):
        widget, data, calls = tab
        widget.refresh()
        png = tmp_path / "font.png"
        font_grids_to_image([_grid(), _grid()], columns=2).save(str(png))
        assert widget.apply_import_file(str(png)) is True
        assert widget._pending is not None
        assert str(widget._btn_write["state"]) == "normal"
        before = bytes(data)
        widget._on_write()
        assert bytes(data[16:32]) == encode_2bpp_tile(_grid())
        assert len(widget._undo_stack) == 1
        assert len(widget._redo_stack) == 0
        assert calls["dirty"]
        widget._on_undo()
        assert bytes(data) == before
        assert len(widget._undo_stack) == 0
        assert len(widget._redo_stack) == 1
        widget._on_redo()
        assert bytes(data[16:32]) == encode_2bpp_tile(_grid())
        assert len(widget._undo_stack) == 1
        assert len(widget._redo_stack) == 0

    def test_bad_import(self, tab, tmp_path):
        widget, _, _ = tab
        widget.refresh()
        bad = tmp_path / "bad.png"
        font_grids_to_image([_grid()], columns=1).save(str(bad))
        assert widget.apply_import_file(str(bad)) is False
        assert widget._pending is None
        assert "Import failed" in widget._banner.cget("text") or "font.import.error" in widget._banner.cget("text")
        assert str(widget._btn_write["state"]) == "disabled"

    def test_next_guard(self, tab):
        widget, _, _ = tab
        widget.refresh()
        assert widget._page == 0
        widget._on_next()
        assert widget._page == 0

    def test_page_preserved_on_reload(self, root):
        data = bytearray(300 * 16)
        ctx, _ = _make_ctx(data, _meta(count=300))
        widget = FontTab(root, ctx)
        widget.refresh()
        assert widget._pages == 2
        widget._page = 1
        widget._reload()
        assert widget._page == 1
        widget.refresh()
        assert widget._page == 0
        theme.unregister_post_apply_hook(widget._reapply_colors)
        widget.destroy()

    def test_clear_undo(self, tab, tmp_path, monkeypatch):
        widget, _, _ = tab
        widget.refresh()
        png = tmp_path / "font.png"
        font_grids_to_image([_grid(), _grid()], columns=2).save(str(png))
        widget.apply_import_file(str(png))
        widget._on_write()
        assert len(widget._undo_stack) == 1
        widget.clear_undo()
        assert len(widget._undo_stack) == 0
        assert len(widget._redo_stack) == 0
        assert str(widget._btn_undo["state"]) == "disabled"
        assert str(widget._btn_redo["state"]) == "disabled"

    def test_confirm_lists_indices(self, root, tmp_path, monkeypatch):
        from core.font_tiles import inject_font_block

        data = bytearray(64)
        ctx = {
            "get_data": lambda: data,
            "get_meta": lambda: _meta(),
            "do_inject": lambda layout, glyphs: inject_font_block(data, layout, glyphs, confirm=True),
            "mark_dirty": lambda msg: None,
            "t": lambda key, **kw: key + repr(sorted(kw.items())) if kw else key,
        }
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
        widget = FontTab(root, ctx)
        widget.refresh()
        png = tmp_path / "font.png"
        font_grids_to_image([_grid(), _grid()], columns=2).save(str(png))
        widget.apply_import_file(str(png))
        seen: dict = {}
        monkeypatch.setattr(messagebox, "askyesno", lambda title, msg: seen.setdefault("msg", msg) or True)
        widget._on_write()
        assert "0,1" in seen["msg"]
        theme.unregister_post_apply_hook(widget._reapply_colors)
        widget.destroy()

    def test_theme_switch(self, tab):
        widget, _, _ = tab
        widget.refresh()
        theme.apply(widget.winfo_toplevel(), True)
        theme.apply(widget.winfo_toplevel(), False)
        widget.refresh()


class TestPixelEdit:
    def test_edit_ok(self, tab, monkeypatch):
        from gui.glyph_editor import GlyphEditor

        widget, _, _ = tab
        widget.refresh()
        edited = [_grid(), _grid()]
        edited[1][0][0] = 3
        monkeypatch.setattr(GlyphEditor, "edit", staticmethod(lambda *a, **k: edited[1]))
        widget._open_editor(1)
        assert widget._pending == {1: edited[1]}
        assert str(widget._btn_write["state"]) == "normal"

    def test_edit_cancel(self, tab, monkeypatch):
        from gui.glyph_editor import GlyphEditor

        widget, _, _ = tab
        widget.refresh()
        monkeypatch.setattr(GlyphEditor, "edit", staticmethod(lambda *a, **k: None))
        widget._open_editor(0)
        assert widget._pending is None

    def test_edit_deep_copy(self, tab, monkeypatch):
        from gui.glyph_editor import GlyphEditor

        widget, _, _ = tab
        widget.refresh()
        seen = []

        def _fake_edit(master, grid, bpp, t):
            seen.append(grid)
            return None

        monkeypatch.setattr(GlyphEditor, "edit", staticmethod(_fake_edit))
        widget._open_editor(0)
        assert seen and seen[0] == _grid()
        assert seen[0] is not widget._view["grids"][0]

    def test_pending_blocks_undo_redo(self, tab, tmp_path):
        widget, data, _ = tab
        widget.refresh()
        png = tmp_path / "font.png"
        font_grids_to_image([_grid(), _grid()], columns=2).save(str(png))
        widget.apply_import_file(str(png))
        widget._undo_stack.append({"offset": 0, "bytes": bytes(16)})
        before = bytes(data)
        widget._on_undo()
        widget._on_redo()
        assert bytes(data) == before

    def test_redo_cleared_on_write(self, tab, tmp_path):
        widget, _, _ = tab
        widget.refresh()
        png = tmp_path / "font.png"
        font_grids_to_image([_grid(), _grid()], columns=2).save(str(png))
        widget.apply_import_file(str(png))
        widget._on_write()
        widget._on_undo()
        assert len(widget._redo_stack) == 1
        other = [_grid(), _grid()]
        other[0][0][0] = 1
        widget._pending = {0: other[0]}
        widget._on_write()
        assert len(widget._redo_stack) == 0
        assert len(widget._undo_stack) == 1

    def test_undo_depth(self, tab, tmp_path):
        from core.font_tiles import decode_2bpp_tile

        widget, data, _ = tab
        widget.refresh()
        first = [_grid(), _grid()]
        first[0][0][0] = 1
        widget._pending = {0: first[0]}
        widget._on_write()
        second = [_grid(), _grid()]
        second[1][0][0] = 2
        widget._pending = {1: second[1]}
        widget._on_write()
        assert len(widget._undo_stack) == 2
        assert decode_2bpp_tile(bytes(data[0:16]))[0][0] == 1
        assert decode_2bpp_tile(bytes(data[16:32]))[0][0] == 2
        widget._on_undo()
        assert decode_2bpp_tile(bytes(data[16:32]))[0][0] == 0
        assert decode_2bpp_tile(bytes(data[0:16]))[0][0] == 1
        widget._on_undo()
        assert decode_2bpp_tile(bytes(data[0:16]))[0][0] == 0
        widget._on_redo()
        assert decode_2bpp_tile(bytes(data[0:16]))[0][0] == 1
        assert decode_2bpp_tile(bytes(data[16:32]))[0][0] == 0
        widget._on_redo()
        assert decode_2bpp_tile(bytes(data[16:32]))[0][0] == 2

    def test_import_replace_confirm(self, tab, tmp_path, monkeypatch):
        widget, _, _ = tab
        widget.refresh()
        png = tmp_path / "font.png"
        font_grids_to_image([_grid(), _grid()], columns=2).save(str(png))
        widget.apply_import_file(str(png))
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
        widget._on_import()
        assert widget._pending is not None

    def test_hit_test_outside(self, tab):
        widget, _, _ = tab
        widget.refresh()

        class Ev:
            x = 10000
            y = 10000

        widget._on_canvas_click(Ev())
        assert widget._pending is None
        assert widget._editor_open is False

    def test_negative_click_ignored(self, tab):
        widget, _, _ = tab
        widget.refresh()

        class Ev:
            x = -5
            y = -5

        widget._on_canvas_click(Ev())
        assert widget._pending is None

    def test_hook_unregistered_on_destroy(self, root):
        ctx, _ = _make_ctx(bytearray(64), _meta())
        widget = FontTab(root, ctx)
        assert widget._reapply_colors in theme._post_apply_hooks
        widget.destroy()
        assert widget._reapply_colors not in theme._post_apply_hooks

    def test_retranslate_keeps_pending(self, tab, tmp_path):
        widget, _, _ = tab
        widget.refresh()
        png = tmp_path / "font.png"
        font_grids_to_image([_grid(), _grid()], columns=2).save(str(png))
        widget.apply_import_file(str(png))
        widget.retranslate()
        assert widget._pending is not None
        assert len(widget._undo_stack) == 0

    def test_pager_disabled_when_not_ok(self, root):
        ctx, _ = _make_ctx(None, None)
        widget = FontTab(root, ctx)
        widget.refresh()
        assert str(widget._btn_prev["state"]) == "disabled"
        assert str(widget._btn_next["state"]) == "disabled"
        theme.unregister_post_apply_hook(widget._reapply_colors)
        widget.destroy()

    def test_merged_render(self, tab, tmp_path):
        widget, _, _ = tab
        widget.refresh()
        edited = [_grid(), _grid()]
        edited[0][0][0] = 2
        png = tmp_path / "font.png"
        font_grids_to_image(edited, columns=2).save(str(png))
        widget.apply_import_file(str(png))
        assert widget._display_grids()[0][0][0] == 2
        assert widget._display_grids()[1] == _grid()

    def test_failed_import_keeps_pending(self, tab, tmp_path):
        widget, _, _ = tab
        widget.refresh()
        png = tmp_path / "font.png"
        font_grids_to_image([_grid(), _grid()], columns=2).save(str(png))
        widget.apply_import_file(str(png))
        bad = tmp_path / "bad.png"
        font_grids_to_image([_grid()], columns=1).save(str(bad))
        assert widget.apply_import_file(str(bad)) is False
        assert widget._pending is not None
        assert len(widget._pending) == 2

    def test_confirm_discard(self, tab, monkeypatch):
        widget, _, _ = tab
        assert widget.confirm_discard() is True
        widget._pending = {0: _grid()}
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
        assert widget.confirm_discard() is False
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
        assert widget.confirm_discard() is True

    def test_refresh_button_confirms(self, tab, tmp_path, monkeypatch):
        widget, _, _ = tab
        widget.refresh()
        png = tmp_path / "font.png"
        font_grids_to_image([_grid(), _grid()], columns=2).save(str(png))
        widget.apply_import_file(str(png))
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
        widget._on_refresh_button()
        assert widget._pending is not None
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
        widget._on_refresh_button()
        assert widget._pending is None


class TestGlyphEditor:
    def test_paint_cycle_erase_ok(self, root):
        from gui.glyph_editor import GlyphEditor

        grid = [[0] * 8 for _ in range(8)]
        dlg = GlyphEditor(root, grid, 2, lambda key, **kw: key)
        assert dlg.result is None
        dlg._pick(1)
        dlg._paint_at(0, 0, dlg._sel)
        assert dlg._grid[0][0] == 1
        dlg._paint_at(0, 0, 0)
        assert dlg._grid[0][0] == 0
        assert grid[0][0] == 0
        dlg._on_ok()
        assert dlg.result == dlg._grid
        assert dlg.result is not dlg._grid

    def test_cancel(self, root, monkeypatch):
        from gui.glyph_editor import GlyphEditor

        dlg = GlyphEditor(root, [[0] * 8 for _ in range(8)], 1, lambda key, **kw: key)
        dlg._on_cancel()
        assert dlg.result is None

    def test_cancel_dirty_confirm(self, root, monkeypatch):
        from tkinter import messagebox as mb

        from gui.glyph_editor import GlyphEditor

        dlg = GlyphEditor(root, [[0] * 8 for _ in range(8)], 1, lambda key, **kw: key)
        dlg._paint_at(0, 0, 1)
        monkeypatch.setattr(mb, "askyesno", lambda *a, **k: False)
        dlg._on_cancel()
        assert dlg.result is None
        assert dlg.winfo_exists()
        monkeypatch.setattr(mb, "askyesno", lambda *a, **k: True)
        dlg._on_cancel()
        assert dlg.result is None

    def test_indicator_sync(self, root):
        from gui.glyph_editor import GlyphEditor

        dlg = GlyphEditor(root, [[1] + [0] * 7 for _ in range(8)], 2, lambda key, **kw: key)
        assert dlg._pal_buttons[3].cget("text") == "[3]"
        dlg._pick(1)
        assert dlg._pal_buttons[1].cget("text") == "[1]"
        assert dlg._pal_buttons[3].cget("text") == "3"

        class Ev:
            x = 5
            y = 5

        dlg._on_paint(Ev())
        assert dlg._sel == 2
        assert dlg._pal_buttons[2].cget("text") == "[2]"
        dlg.destroy()

    def test_modal_bindings(self, root):
        from gui.glyph_editor import GlyphEditor

        dlg = GlyphEditor(root, [[0] * 8 for _ in range(8)], 2, lambda key, **kw: key)
        assert dlg.transient()
        assert dlg.bind("<Return>")
        assert dlg.bind("<Escape>")
        dlg._on_cancel()
        assert dlg.result is None

    def test_brightness_scale(self, root):
        from gui.glyph_editor import GlyphEditor

        dlg1 = GlyphEditor(root, [[0] * 8 for _ in range(8)], 1, lambda key, **kw: key)
        assert dlg1._color(1) == "#ffffff"
        dlg4 = GlyphEditor(root, [[0] * 8 for _ in range(8)], 4, lambda key, **kw: key)
        assert dlg4._color(15) == "#ffffff"
        assert dlg4._color(1) == "#111111"
        dlg1.destroy()
        dlg4.destroy()


def test_i18n_font_parity():
    import json
    from pathlib import Path

    root = Path(__file__).parent.parent
    en = json.loads((root / "locales" / "en" / "messages.json").read_text(encoding="utf-8"))
    ru = json.loads((root / "locales" / "ru" / "messages.json").read_text(encoding="utf-8"))
    en_keys = {k for k in en if k == "tab.font" or k.startswith("font.")}
    ru_keys = {k for k in ru if k == "tab.font" or k.startswith("font.")}
    assert en_keys == ru_keys != set()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
