import tkinter as tk
import zlib
from types import SimpleNamespace
from typing import Any, cast

import pytest

from core.patcher import (
    BPS_MAGIC,
    PatchError,
    _emit_ips_record,
    _signed_offset,
    _vlq_encode,
    bps_apply,
    bps_create,
    ips_apply,
)
from core.translation_filler import FillOptions, FillResult, FillStrategy, TranslationFiller
from plugins.gbc_pokemon_gsc import GEN1_TERMINATORS, PokemonGSCPlugin
from plugins.generic import GenericGBAPlugin, GenericGBPlugin


def _bps_patch(body: bytes) -> bytes:
    payload = BPS_MAGIC + body
    tail = (0).to_bytes(4, "little") + (0).to_bytes(4, "little")
    return payload + tail + zlib.crc32(payload + tail).to_bytes(4, "little")


def _vlq(value: int) -> bytes:
    return _vlq_encode(value)


def test_signed_offset_odd():
    assert _signed_offset(3) == -1
    assert _signed_offset(4) == 2


def test_bps_short_patch():
    with pytest.raises(PatchError):
        bps_apply(b"", BPS_MAGIC + b"\x01\x02")


def test_bps_meta_beyond_patch():
    body = _vlq(4) + _vlq(4) + _vlq(100)
    with pytest.raises(PatchError):
        bps_apply(b"", _bps_patch(body))


def test_bps_rom_size_mismatch():
    patch = bytearray(bps_create(b"AAAA", b"BBBB"))
    patch[-12:-8] = (0).to_bytes(4, "little")
    patch[-4:] = zlib.crc32(bytes(patch[:-4])).to_bytes(4, "little")
    with pytest.raises(PatchError):
        bps_apply(b"AA", bytes(patch))


def test_bps_instr_truncated():
    body = _vlq(0) + _vlq(5) + _vlq(0)
    with pytest.raises(PatchError):
        bps_apply(b"", _bps_patch(body))


def test_bps_sourceread_beyond_src():
    body = _vlq(2) + _vlq(2) + _vlq(0) + _vlq(16) + _vlq(4) + b"X"
    with pytest.raises(PatchError):
        bps_apply(b"AB", _bps_patch(body))


def test_bps_targetread_beyond_patch():
    body = _vlq(2) + _vlq(2) + _vlq(0) + _vlq(17)
    with pytest.raises(PatchError):
        bps_apply(b"AB", _bps_patch(body))


def test_bps_sourcecopy_offset_beyond():
    body = _vlq(2) + _vlq(2) + _vlq(0) + _vlq(2)
    with pytest.raises(PatchError):
        bps_apply(b"AB", _bps_patch(body))


def test_bps_sourcecopy_out_of_src():
    body = _vlq(2) + _vlq(2) + _vlq(0) + _vlq(2) + _vlq(4)
    with pytest.raises(PatchError):
        bps_apply(b"AB", _bps_patch(body))


def test_bps_targetcopy_offset_beyond():
    body = _vlq(2) + _vlq(2) + _vlq(0) + _vlq(3)
    with pytest.raises(PatchError):
        bps_apply(b"AB", _bps_patch(body))


def test_bps_targetcopy_out_of_target():
    body = _vlq(2) + _vlq(2) + _vlq(0) + _vlq(3) + _vlq(0)
    with pytest.raises(PatchError):
        bps_apply(b"AB", _bps_patch(body))


def test_bps_target_overshoot():
    body = _vlq(4) + _vlq(2) + _vlq(0) + _vlq(12)
    with pytest.raises(PatchError):
        bps_apply(b"AAAA", _bps_patch(body))


def test_ips_emit_beyond_addressing():
    with pytest.raises(PatchError):
        _emit_ips_record(bytearray(), 0x1000000, b"AB")


def test_ips_emit_crosses_boundary():
    with pytest.raises(PatchError):
        _emit_ips_record(bytearray(), 0xFFFFFE, b"ABCD")


def test_ips_apply_short_record():
    with pytest.raises(PatchError):
        ips_apply(b"", b"PATCH" + b"\x00\x00\x00")


def test_ips_apply_truncated_rle():
    patch = b"PATCH" + (0x100).to_bytes(3, "big") + (0).to_bytes(2, "big")
    with pytest.raises(PatchError):
        ips_apply(b"", patch)


def test_ips_apply_rle_beyond_addressing():
    patch = b"PATCH" + (0xFFFF00).to_bytes(3, "big") + (0).to_bytes(2, "big") + (0x200).to_bytes(2, "big") + b"\xaa"
    with pytest.raises(PatchError):
        ips_apply(b"", patch)


def test_ips_apply_record_beyond_addressing():
    patch = b"PATCH" + (0xFFFFFF).to_bytes(3, "big") + (2).to_bytes(2, "big") + b"AB"
    with pytest.raises(PatchError):
        ips_apply(b"", patch)


def test_filler_error_path():
    filler = TranslationFiller(FillOptions(strategy=FillStrategy.PLACEHOLDER, placeholder_template="{missing_key}"))
    result = filler.fill_translation("s", "hi")
    assert result.success is False
    assert result.error_message is not None


def test_filler_copy_stripped():
    filler = TranslationFiller(FillOptions(strategy=FillStrategy.COPY_ORIGINAL, preserve_formatting=False))
    assert filler.fill_translation("s", "  hi  ").filled_translation == "hi"


def test_filler_temporary_stripped_unmarked():
    filler = TranslationFiller(
        FillOptions(strategy=FillStrategy.TEMPORARY_MARK, copy_unchanged=False, mark_temporary=False)
    )
    assert filler.fill_translation("s", "  hi  ").filled_translation == "hi"


def test_filler_batch_skip_warns():
    filler = TranslationFiller(FillOptions(strategy=FillStrategy.SKIP))
    results = filler.fill_batch({"a": "x"})
    assert results["a"].success is False


def test_filler_summary_with_errors():
    filler = TranslationFiller()
    bad = FillResult("a", False, "", FillStrategy.SKIP, "boom")
    good = FillResult("b", True, "x", FillStrategy.COPY_ORIGINAL)
    summary = filler.get_summary({"a": bad, "b": good})
    assert "boom" in summary


def test_theme_unregister_missing():
    import gui.theme as theme

    theme.unregister_post_apply_hook(object())


def test_theme_get_tokens():
    import gui.theme as theme

    assert isinstance(theme.get_tokens(), dict)


def test_theme_resolve_no_master(monkeypatch):
    import gui.theme as theme

    monkeypatch.setattr(tk, "_default_root", None, raising=False)
    assert theme._resolve_family(["NoSuchFamXYZ"], None) == "NoSuchFamXYZ"


def test_theme_resolve_no_match(monkeypatch):
    import gui.theme as theme

    monkeypatch.setattr(theme.tkfont, "families", lambda master: {"Arial"})
    assert theme._resolve_family(["NopeFam"], object()) == "NopeFam"


def test_theme_resolve_tcl_error(monkeypatch):
    import gui.theme as theme

    def _boom(master):
        raise tk.TclError("gone")

    monkeypatch.setattr(theme.tkfont, "families", _boom)
    assert theme._resolve_family(["AnyFam"], object()) == "AnyFam"


class _FakeWidget:
    def __init__(self, cls, fail=None):
        self._cls = cls
        self._fail = fail
        self.configured = {}

    def winfo_class(self):
        if self._fail == "class":
            raise tk.TclError("gone")
        return self._cls

    def configure(self, **kwargs):
        if self._fail == "configure":
            raise tk.TclError("gone")
        self.configured = kwargs

    def winfo_children(self):
        if self._fail == "children":
            raise tk.TclError("gone")
        return []


def _tokens():
    return {
        "bg": "b",
        "text": "t",
        "surface": "s",
        "accent": "a",
        "on-accent": "o",
        "focus-ring": "f",
        "border": "bd",
    }


def test_theme_iter_children_fail():
    import gui.theme as theme

    assert list(theme._iter_widgets(_FakeWidget("Frame", fail="children"))) != []
    assert list(theme._iter_menus(_FakeWidget("Frame"))) == []


def test_theme_style_plain_class_fail():
    import gui.theme as theme

    assert theme._style_plain(_FakeWidget("X", fail="class"), _tokens()) is None


def test_theme_style_plain_label():
    import gui.theme as theme

    widget = _FakeWidget("Label")
    theme._style_plain(widget, _tokens())
    assert widget.configured == {"bg": "b", "fg": "t"}


def test_theme_style_plain_entry():
    import gui.theme as theme

    widget = _FakeWidget("Entry")
    theme._style_plain(widget, _tokens())
    assert widget.configured["bg"] == "s"


def test_theme_style_plain_button():
    import gui.theme as theme

    widget = _FakeWidget("Button")
    theme._style_plain(widget, _tokens())
    assert widget.configured["bg"] == "s"


def test_theme_style_plain_configure_fail():
    import gui.theme as theme

    assert theme._style_plain(_FakeWidget("Label", fail="configure"), _tokens()) is None


def test_theme_style_menu_fail():
    import gui.theme as theme

    class _BoomMenu:
        def configure(self, **kwargs):
            raise tk.TclError("gone")

    assert theme._style_menu(_BoomMenu(), _tokens()) is None


def test_theme_apply_theme_use_fail(monkeypatch):
    import gui.theme as theme

    class _BoomStyle:
        def __init__(self, master):
            pass

        def theme_use(self, name):
            raise tk.TclError("gone")

        def configure(self, *args, **kwargs):
            pass

        def map(self, *args, **kwargs):
            pass

    class _FakeRoot:
        def winfo_children(self):
            return []

        def winfo_class(self):
            return "Frame"

        def configure(self, **kwargs):
            pass

        def option_add(self, *args):
            pass

    previous = (theme._current, theme._current_scheme)
    monkeypatch.setattr("tkinter.ttk.Style", _BoomStyle)
    monkeypatch.setattr(theme, "ui_font", lambda *args, **kwargs: "font")
    try:
        theme.apply(_FakeRoot(), dark=True)
    finally:
        theme._current, theme._current_scheme = previous


def test_generic_estimate_no_terminator():
    assert GenericGBPlugin()._estimate_segment_length(bytes([0x41]) * 0x1100, 0) == 0x100


def test_generic_gba_segments_from_pointers(monkeypatch):
    import core.scanner as scanner

    monkeypatch.setattr(scanner, "find_text_pointers", lambda *args, **kwargs: [(0, 0x100)])
    rom = SimpleNamespace(data=bytes(0x200))
    segments = GenericGBAPlugin().get_text_segments(rom)
    assert [s["name"] for s in segments] == ["gba_segment_0"]


def test_generic_gba_fallback_empty(monkeypatch):
    import core.scanner as scanner

    monkeypatch.setattr(scanner, "find_text_pointers", lambda *args, **kwargs: [])
    rom = SimpleNamespace(data=bytes(0x3D0100))
    segments = GenericGBAPlugin().get_text_segments(rom)
    assert [s["name"] for s in segments] == ["main_text"]


def test_gsc_tables_exceed_rom():
    rom = SimpleNamespace(header={"title": "POKEMON_GLDAAUE"}, data=bytes(0x100))
    assert PokemonGSCPlugin().get_text_segments(cast(Any, rom)) == []


def test_gsc_accessors():
    plugin = PokemonGSCPlugin()
    assert plugin.get_terminators("seg") == list(GEN1_TERMINATORS)
    assert plugin.get_compression_handler("seg") is None
