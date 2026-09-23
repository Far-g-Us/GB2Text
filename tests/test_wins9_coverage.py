from core.charset import load_charmap_txt
from core.database import get_segment_patterns
from core.encoding import get_generic_english_charmap
from plugins.gba_ff6_advance import FF6AdvancePlugin
from plugins.gba_megaman_battle_network import MegaManBattleNetworkPlugin


def test_charmap_all_formats(tmp_path):
    p = tmp_path / "c.txt"
    p.write_text(
        "'A' = 41\n"
        "'BC' = 42 43\n"
        "PLAYER = FD 01\n"
        '#define _X "BYTE 0x80 0xA6;"\n'
        "0x44 = 'D'\n"
        "0085=E\n"
        "@ comment\n"
        "// comment\n"
        "\n",
        encoding="utf-8",
    )
    m = load_charmap_txt(p)
    assert "A" in m.values()
    assert "BC" in m.values() or (0x42, 0x43) in m
    assert any("PLAYER" in str(v) for v in m.values())
    assert len(m) >= 5


def test_database_and_encoding():
    assert len(get_segment_patterns("gb")) == 2
    assert get_generic_english_charmap() is not None
    from core.encoding import auto_detect_charmap

    assert isinstance(auto_detect_charmap(b"Hello World"), dict)


def test_gba_plugins_small():
    for cls in (FF6AdvancePlugin, MegaManBattleNetworkPlugin):
        plugin = cls()
        assert plugin.get_text_segments(type("R", (), {"data": bytes(10), "header": {}})()) == []
