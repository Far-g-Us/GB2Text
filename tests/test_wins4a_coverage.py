import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest

from core.analyzer import TextAnalyzer
from core.plugin import PluginProtocol
from core.xliff import XLIFFHandler
from plugins.gba_advance_wars import AdvanceWarsPlugin
from plugins.gba_ct_special_forces import CTSpecialForcesPlugin
from plugins.gba_custom_robo_gx import CustomRoboGXPlugin
from plugins.gba_megaman_battle_network_2 import MegaManBattleNetwork2Plugin
from plugins.gba_megaman_zero import MegaManZeroPlugin
from plugins.gba_metroid_zero_mission import MetroidZeroMissionPlugin
from plugins.gba_shining_force import ShiningForcePlugin
from plugins.gbc_zelda_seasons import OracleOfSeasonsPlugin
from plugins.zelda_oracle_common import OracleTextDecoder

_STUB_PLUGINS = (
    AdvanceWarsPlugin,
    CTSpecialForcesPlugin,
    CustomRoboGXPlugin,
    MegaManBattleNetwork2Plugin,
    MegaManZeroPlugin,
    MetroidZeroMissionPlugin,
    ShiningForcePlugin,
)


def test_detect_terminators_found():
    data = b"QW\x00\x00\x00ERTY" * 25
    assert 0x00 in TextAnalyzer.detect_terminators(data)


def test_detect_regions_no_text():
    rom = SimpleNamespace(data=bytes([0x01]) * 0x200)
    assert TextAnalyzer.detect_text_regions(rom) == []


def test_detect_regions_long_appended():
    rom = SimpleNamespace(data=bytes(0x150) + b"A" * 150 + bytes([0x01]) * 10)
    assert TextAnalyzer.detect_text_regions(rom) == [(0x150, 0x150 + 149)]


def test_detect_regions_short_skipped():
    rom = SimpleNamespace(data=bytes(0x150) + b"A" * 10 + bytes([0x01]) * 5)
    assert TextAnalyzer.detect_text_regions(rom) == []


def test_validate_invalid_sequence_detected():
    report = TextAnalyzer.validate_extraction(None, {"s": [{"text": "xx[CD][yy", "offset": 0}]})
    assert report["possible_errors"]
    assert report["possible_errors"][0]["issue"] == "invalid_sequence"


def test_validate_low_readability():
    report = TextAnalyzer.validate_extraction(None, {"s": [{"text": "", "offset": 5}]})
    assert report["possible_errors"][0]["issue"] == "low_readability"


def test_plugin_protocol_defaults():
    assert PluginProtocol.get_compression_handler(object(), "s") is None
    assert PluginProtocol.get_terminators(object(), "s") is None
    assert PluginProtocol.get_pointer_size(object(), None) is None
    assert PluginProtocol.validate_rom(object(), None) is None
    assert PluginProtocol.get_font_meta(object()) is None


def test_xliff_export_no_title():
    handler = XLIFFHandler()
    out = handler.export_xliff({"s": [{"text": "hi", "offset": 1}]}, game_title="")
    assert "product-name" not in out
    assert "hi" in out


def test_xliff_export_pretty_fallback(monkeypatch):
    import core.xliff as xliff_mod

    def _boom(text):
        raise RuntimeError("no pretty")

    monkeypatch.setattr(xliff_mod.minidom, "parseString", _boom)
    out = XLIFFHandler().export_xliff({"s": [{"text": "hi", "offset": 1}]})
    assert out.startswith('<?xml version="1.0" encoding="utf-8"?>')


def test_xliff_import_file_without_body():
    assert XLIFFHandler().import_xliff('<xliff><file original="s"></file></xliff>') == {}


def test_xliff_import_unit_without_target():
    content = '<xliff><file original="s"><body><trans-unit id="0"><source>x</source></trans-unit></body></file></xliff>'
    assert XLIFFHandler().import_xliff(content) == {}


def test_xliff_import_bad_id():
    content = (
        '<xliff><file original="s"><body><trans-unit id="abc"><target>y</target></trans-unit></body></file></xliff>'
    )
    assert XLIFFHandler().import_xliff(content) == {}


def test_xliff_import_generic_error(monkeypatch):
    handler = XLIFFHandler()

    def _boom(tag):
        raise RuntimeError("tree gone")

    monkeypatch.setattr(XLIFFHandler, "_local_name", staticmethod(_boom))
    with pytest.raises(RuntimeError):
        handler.import_xliff("<xliff/>")


def test_xliff_apply_unknown_segment():
    assert XLIFFHandler.apply_translations({}, {"nope": {0: "x"}}) == 0


def test_xliff_apply_index_out_of_range():
    assert XLIFFHandler.apply_translations({"s": [{"text": "a"}]}, {"s": {5: "x"}}) == 0


def test_xliff_find_child_none():
    handler = XLIFFHandler()
    assert handler._find_child(ET.fromstring("<a><b/></a>"), "body") is None


def test_xliff_inline_tail_only():
    handler = XLIFFHandler()
    assert handler._get_element_text(ET.fromstring("<target><g/>tail</target>")) == "tail"


def test_seasons_small_rom_empty():
    rom = SimpleNamespace(data=bytes(10))
    assert OracleOfSeasonsPlugin().get_text_segments(rom) == []


def test_stub_plugin_accessors():
    for cls in _STUB_PLUGINS:
        plugin = cls()
        assert plugin.get_pointer_size(None) == 4
        assert plugin.get_terminators("s") == [0x00, 0xFF]
        assert plugin.get_compression_handler("s") is None


def _oracle_table_rom():
    rom = bytearray(0x100000)
    rom[0xFCFE2] = 0x20
    rom[0xFCFE2 + 1] = 0x00
    rom[0xFCFE2 + 2] = 0x00
    rom[0xFCFFA] = 0x24
    rom[0xFCFFA + 1] = 0x00
    rom[0xFCFFA + 2] = 0x00
    rom[0xFD012] = 0x00
    rom[0xFD012 + 1] = 0x00
    rom[0xFD012 + 2] = 0x1C
    for i in range(0x64):
        value = 0x0200
        if i == 2:
            value = 0x0300
        elif i >= 44:
            value = 0x0400
        off = 0x70000 + i * 2
        rom[off] = value & 0xFF
        rom[off + 1] = (value >> 8) & 0xFF
    rom[0x70300] = 0x10
    rom[0x70300 + 1] = 0x00
    for j in range(1, 128):
        value = 0x100 + j * 2
        off = 0x70300 + j * 2
        rom[off] = value & 0xFF
        rom[off + 1] = (value >> 8) & 0xFF
    rom[0x80010:0x80013] = b"\x04\x00\x00"
    return bytes(rom)


def test_oracle_two_groups_and_bases():
    decoder = OracleTextDecoder()
    decoder._init(_oracle_table_rom())
    assert decoder._initialized is True
    assert decoder._text_base2 == 0x90000
    assert decoder._idx_to_addr[(44 << 8) | 0] == 0x90000
    assert decoder._idx_to_addr[0x200] == 0x80010


def test_oracle_manifest_cycle_skipped():
    decoder = OracleTextDecoder()
    assert decoder.build_manifest(_oracle_table_rom()) == []


def test_oracle_high_table_empty_manifest():
    rom = bytearray(0x100000)
    rom[0xFD012] = 0x00
    rom[0xFD012 + 1] = 0x3F
    rom[0xFD012 + 2] = 0x3F
    for i in range(0x64):
        off = 0xFFF00 + i * 2
        rom[off] = 0xFF
        rom[off + 1] = 0xFF
    assert OracleTextDecoder().build_manifest(bytes(rom)) == []


def test_oracle_zeros_decode_out_of_range():
    decoder = OracleTextDecoder()
    data = bytes(0x100000)
    with pytest.raises(ValueError):
        decoder.decode(data, len(data), 4)


def test_oracle_big_base_manifest_break():
    rom = bytearray(0x100000)
    rom[0xFCFE2] = 0x40
    assert OracleTextDecoder().build_manifest(bytes(rom)) == []


def test_oracle_decompress_depth():
    decoder = OracleTextDecoder()
    with pytest.raises(ValueError):
        decoder._decompress(b"\x02\x00", 0, 2, bytearray(), 33, set())


def test_oracle_decompress_unknown_dict_literal():
    decoder = OracleTextDecoder()
    out = bytearray()
    decoder._decompress(b"\x02\x00ABC", 0, 5, out, 0, set())
    assert bytes(out) == b"\x02\x00ABC"


def test_oracle_decompress_cycle():
    decoder = OracleTextDecoder()
    decoder._idx_to_addr = {0x200: 0xAA}
    with pytest.raises(ValueError):
        decoder._decompress(b"\x04\x00", 0, 2, bytearray(), 0, {0xAA})


def test_oracle_decompress_output_guard(monkeypatch):
    import plugins.zelda_oracle_common as common

    monkeypatch.setattr(common, "_MAX_DECOMPRESS_OUT", 0)
    decoder = OracleTextDecoder()
    decoder._idx_to_addr = {0x200: 2}
    with pytest.raises(ValueError):
        decoder._decompress(b"\x04\x00XXAB", 0, 6, bytearray(), 0, set())
    with pytest.raises(ValueError):
        decoder._decompress(b"\x06\x41", 0, 2, bytearray(), 0, set())


def test_oracle_record_bound_hit():
    decoder = OracleTextDecoder()
    decoder._addr_to_index = {2: 0}
    assert decoder._record_bound(b"\x02ABC\x00", 0) == 2


def test_oracle_record_bound_no_trailing():
    decoder = OracleTextDecoder()
    assert decoder._record_bound(b"ABCD", 0) == 4


def test_oracle_stringify_control_tokens():
    decoder = OracleTextDecoder()
    assert decoder._stringify(bytearray(b"\x0a\x01"), None) == "[CHILD]"
    assert decoder._stringify(bytearray(b"\x0a\x02"), None) == "[SECRET1]"
    assert decoder._stringify(bytearray(b"\x0a\x03"), None) == "[SECRET2]"
    assert decoder._stringify(bytearray(b"\x00"), None) == ""


def test_oracle_index_name_tx():
    assert OracleTextDecoder._index_name(0x401) == "TX_0001"


def test_oracle_label_token_none():
    assert OracleTextDecoder._label_token("JUMP", None, 5) == "[JUMP(0x05)]"


def test_oracle_encode_literal_bracket():
    assert OracleTextDecoder().encode_literal("[") == b"["


def test_oracle_encode_col_out_of_range():
    assert OracleTextDecoder().encode_literal("[COL(999)]") == b"[COL(999)]"


def test_oracle_encode_unmapped_twice():
    decoder = OracleTextDecoder()
    assert decoder.encode_literal("€") == b""
    assert decoder.encode_literal("€") == b""
    assert decoder.last_unmapped_chars == ["€"]


def test_oracle_dict_compress_no_phrases():
    assert OracleTextDecoder()._dict_compress(b"AB") == b"AB"


def test_oracle_dict_phrases_skip_high():
    decoder = OracleTextDecoder()
    decoder._last_data = b"\x00" * 10
    decoder._idx_to_addr = {0x400: 0}
    assert decoder._dict_phrases() == []


def test_oracle_dict_phrases_bad_entry_skipped():
    decoder = OracleTextDecoder()
    data = bytearray(60)
    data[50] = 0x04
    data[51] = 0x00
    decoder._last_data = bytes(data)
    decoder._idx_to_addr = {0x200: 50}
    assert decoder._dict_phrases() == []


def test_oracle_encode_sym_in_range():
    assert OracleTextDecoder().encode_literal("[SYM(5)]") == bytes([0x06, 5])


def test_oracle_encode_item_out_of_range():
    assert OracleTextDecoder().encode_literal("[ITEM(999)]") == b"[ITEM(999)]"


def test_oracle_label_param_forms():
    decoder = OracleTextDecoder()
    assert decoder._label_param("TX_0001") == 1
    assert decoder._label_param("ZZZ") is None
