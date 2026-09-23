from types import SimpleNamespace

import gui.widgets as widgets_mod
from core.mbc import create_mbc
from plugins.gba_ff12_dawn_of_souls import FF12DawnOfSoulsPlugin
from plugins.gba_mario_luigi_ss import MarioLuigiSSPlugin
from plugins.gba_zelda_tmc import ZeldaTMCPlugin


def test_widgets_tooltip():
    assert widgets_mod is not None


def test_mbc_variants():
    assert create_mbc(bytes(0x100), 0, 0) is not None
    assert create_mbc(bytes(0x100), 1, 1) is not None


def test_gba_plugins_tmc_ff12_mario():
    for cls in (ZeldaTMCPlugin, FF12DawnOfSoulsPlugin, MarioLuigiSSPlugin):
        plugin = cls()
        assert plugin.get_text_segments(SimpleNamespace(data=bytes(0x100), header={})) == []
