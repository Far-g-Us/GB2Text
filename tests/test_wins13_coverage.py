import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from plugins.gba_golden_sun import GoldenSunPlugin


def test_editor_import():
    import gui.editor as editor_mod
    assert hasattr(editor_mod, "TextEditorFrame")


def test_golden_sun_small():
    plugin = GoldenSunPlugin()
    from types import SimpleNamespace
    assert plugin.get_text_segments(SimpleNamespace(data=bytes(0x100), header={})) == []
    big = bytearray(0x40000)
    assert isinstance(plugin.get_text_segments(SimpleNamespace(data=bytes(big), header={"title": ""})), list)


def test_main_window_basic():
    import gui.main_window as mw
    assert hasattr(mw, "GBTextExtractorGUI")
