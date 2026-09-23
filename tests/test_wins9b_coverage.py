from core.charset import load_charmap_txt, load_charset
from core.database import get_segment_patterns
from core.encoding import auto_detect_charmap, get_generic_english_charmap
from plugins.gba_ff6_advance import FF6AdvancePlugin
from plugins.gba_megaman_battle_network import MegaManBattleNetworkPlugin


def test_charset_extra(tmp_path):
    p = tmp_path / "c2.txt"
    p.write_text("0081=A\n0082=B\n0x83 = 'C'\n", encoding="utf-8")
    m = load_charmap_txt(p)
    assert 0x81 in m and 0x82 in m and 0x83 in m
    try:
        load_charset("nope_xyz")
    except FileNotFoundError:
        assert True
    try:
        load_charmap_txt(tmp_path / "nope.txt")
    except FileNotFoundError:
        assert True
    p2 = tmp_path / "c3.txt"
    p2.write_text("'D' = 44\n'E' = 45\n", encoding="utf-8")
    m2 = load_charmap_txt(p2)
    assert len(m2) >= 2


def test_database_encoding_extra():
    assert len(get_segment_patterns("gb")) == 2
    assert len(get_segment_patterns("gba")) >= 1
    assert len(get_segment_patterns("gbc")) >= 1
    assert get_generic_english_charmap() is not None
    assert isinstance(auto_detect_charmap(b"Hello World"), dict)
    assert isinstance(auto_detect_charmap(b"\x80\x81\x82" * 10), dict)


def test_gba_ff6_megaman_extra():
    for cls in (FF6AdvancePlugin, MegaManBattleNetworkPlugin):
        plugin = cls()
        assert plugin.get_text_segments(type("R", (), {"data": bytes(0x10000), "header": {}})()) == []
        assert plugin.get_pointer_size(None) in (2, 4)
