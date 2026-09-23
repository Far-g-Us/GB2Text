import struct
from types import SimpleNamespace

import pytest

from plugins.gb_pokemon_gen1 import (
    CHARMAP_GEN1,
    GEN1_TERMINATORS,
    Gen1FixedDecoder,
    Gen1TextDecoder,
    PokemonGen1Plugin,
)
from plugins.gba_advance_wars import AdvanceWarsPlugin
from plugins.gba_castlevania import (
    CHARMAP_CVAS,
    CVAS_POINTER_COUNT,
    CVAS_POINTER_TABLE,
    CastlevaniaGBAPlugin,
    CVASTextDecoder,
    CVASTextEncoder,
)
from plugins.gba_ct_special_forces import CTSpecialForcesPlugin
from plugins.gba_custom_robo_gx import CustomRoboGXPlugin
from plugins.gba_ff4_advance import (
    CHARMAP_FF4,
    FF4_POINTER_COUNT,
    FF4_POINTER_SIZE,
    FF4_POINTER_TABLE_OFFSET,
    FF4_TEXT_DATA_START,
    FF4AdvancePlugin,
    FF4TextDecoder,
    _strip_unknown_tokens,
)
from plugins.gba_fft_advance import FFTAdvancePlugin, FFTATextDecoder, _decode_ffta_text
from plugins.gba_golden_sun_tla import GoldenSunTLAPlugin, GoldenSunTLATextDecoder
from plugins.gba_megaman_battle_network_2 import MegaManBattleNetwork2Plugin
from plugins.gba_megaman_zero import MegaManZeroPlugin
from plugins.gba_metroid_zero_mission import MetroidZeroMissionPlugin
from plugins.gba_pokemon import (
    CHARMAP_POKEMON_GBA,
    PokemonGBAPlugin,
    _build_f9_glyphs,
    _decode_pokemon_text_static,
    _encode_pokemon_text,
)
from plugins.gba_shining_force import ShiningForcePlugin

_STUB_PLUGINS = (
    AdvanceWarsPlugin,
    CTSpecialForcesPlugin,
    CustomRoboGXPlugin,
    MegaManBattleNetwork2Plugin,
    MegaManZeroPlugin,
    MetroidZeroMissionPlugin,
    ShiningForcePlugin,
)


def test_stub_plugin_accessors():
    for cls in _STUB_PLUGINS:
        plugin = cls()
        assert plugin.get_pointer_size(None) == 4
        assert plugin.get_terminators("s") == [0x00, 0xFF]
        assert plugin.get_compression_handler("s") is None


def test_tla_encode_brace_paths():
    decoder = GoldenSunTLATextDecoder()
    assert decoder.encode("a{") == b"a\x00"
    assert decoder.encode("a{12 zz}") == b"a\x12\x00"


def test_tla_small_rom_empty():
    plugin = GoldenSunTLAPlugin()
    assert plugin.get_text_segments(SimpleNamespace(data=bytes(100))) == []


def _tla_base_rom():
    size = 0x0AA100
    return bytearray(size)


def test_tla_bad_pointers_skipped():
    plugin = GoldenSunTLAPlugin()
    assert plugin.get_text_segments(SimpleNamespace(data=bytes(_tla_base_rom()))) == []


def test_tla_zero_length_break():
    plugin = GoldenSunTLAPlugin()
    rom = _tla_base_rom()
    struct.pack_into("<II", rom, 0x0A9F54, 0x08001000, 0x08002000)
    assert plugin.get_text_segments(SimpleNamespace(data=bytes(rom))) == []


def test_tla_string_body():
    plugin = GoldenSunTLAPlugin()
    rom = _tla_base_rom()
    struct.pack_into("<II", rom, 0x0A9F54, 0x08001000, 0x08002000)
    rom[0x2000] = 5
    rom[0x1000:0x1005] = b"HELLO"
    segments = plugin.get_text_segments(SimpleNamespace(data=bytes(rom)))
    assert len(segments) == 1
    assert segments[0]["start"] == 0x1000


def test_ff4_strip_tokens():
    assert _strip_unknown_tokens("[C280]hi") == "hi"


def test_ff4_decode_terminator():
    decoder = FF4TextDecoder(CHARMAP_FF4)
    assert decoder.decode(bytes([0x01, 0x0C, 0x01]), 0, 3) == "e"


def test_ff4_decode_multi_hit():
    decoder = FF4TextDecoder(CHARMAP_FF4)
    assert decoder.decode(bytes([0xC4, 0xA4]), 0, 2) == "…"


def test_ff4_encode_unknown_control():
    with pytest.raises(ValueError):
        FF4TextDecoder(CHARMAP_FF4).encode("[NOPE]")


def test_ff4_encode_pair_only():
    decoder = FF4TextDecoder({0x41: "A", 0xC4A4: "…"})
    assert decoder.encode("…A") == bytes([0xC4, 0xA4, 0x41])


def test_ff4_encode_unknown_char():
    with pytest.raises(ValueError):
        FF4TextDecoder(CHARMAP_FF4).encode("€")


def test_ff4_pointer_size():
    assert FF4AdvancePlugin().get_pointer_size(None) == FF4_POINTER_SIZE


def test_ff4_table_oob():
    assert FF4AdvancePlugin().get_text_segments(SimpleNamespace(data=bytes(0x100))) == []


def test_ff4_full_table():
    size = FF4_POINTER_TABLE_OFFSET + FF4_POINTER_COUNT * FF4_POINTER_SIZE
    rom = bytearray(size)
    for i in range(FF4_TEXT_DATA_START, size):
        rom[i] = 0x33
    for i in range(FF4_POINTER_COUNT):
        value = 0 if i == 0 else (0xFFFF if i == 5 else 0xFF00)
        rom[FF4_POINTER_TABLE_OFFSET + i * 4 : FF4_POINTER_TABLE_OFFSET + i * 4 + 2] = value.to_bytes(2, "little")
    rom[0x2E3670:0x2E3673] = bytes([0x01, 0x02, 0x02])
    rom[0x2E3673] = 0x0C
    segments = FF4AdvancePlugin().get_text_segments(SimpleNamespace(data=bytes(rom)))
    assert [s["name"] for s in segments] == ["ff4_text_0"]


def test_ff4_accessors():
    plugin = FF4AdvancePlugin()
    assert plugin.get_terminators("s") == [0x0C]
    assert plugin.get_compression_handler("s") is None


def test_cvas_encoder_zero_token():
    with pytest.raises(ValueError):
        CVASTextEncoder({"AB": b"\x00\x41"}).encode("AB")


def test_cvas_raw_bytes_reserved():
    encoder = CVASTextEncoder({})
    with pytest.raises(ValueError):
        encoder.encode("[00]")
    with pytest.raises(ValueError):
        encoder.encode("[00FF]")


def test_cvas_decode_breaks():
    decoder = CVASTextDecoder(CHARMAP_CVAS)
    assert decoder.decode(bytes([0x41, 0x00, 0x42]), 0, 3) == "A"
    assert decoder.decode(b"\x06", 0, 1) == "\n"


def test_cvas_pointer_meta():
    assert CastlevaniaGBAPlugin().get_pointer_table_meta()["count"] == CVAS_POINTER_COUNT


def test_cvas_table_oob():
    assert CastlevaniaGBAPlugin().get_text_segments(SimpleNamespace(data=bytes(0x1000))) == []


def test_cvas_bad_targets():
    size = CVAS_POINTER_TABLE + 4 * CVAS_POINTER_COUNT
    assert CastlevaniaGBAPlugin().get_text_segments(SimpleNamespace(data=bytes(size))) == []


def _cvas_full_rom():
    import struct as _struct

    size = CVAS_POINTER_TABLE + 4 * CVAS_POINTER_COUNT
    rom = bytearray(size + 0x1000)
    base = 0x10000
    for i in range(CVAS_POINTER_COUNT):
        value = base + i * 0x100
        if i == 41:
            value = base + 40 * 0x100 - 0x50
        _struct.pack_into("<I", rom, CVAS_POINTER_TABLE + i * 4, value + 0x08000000)
    for i in [*range(40), 42]:
        target = base + i * 0x100
        rom[target - 1] = 0x00
        rom[target] = 0x01
        rom[target + 1 : target + 5] = b"ABCD"
        rom[target + 5] = 0x00
        rom[target + 6] = 0x00
    return bytes(rom)


def test_cvas_full_table():
    segments = CastlevaniaGBAPlugin().get_text_segments(SimpleNamespace(data=_cvas_full_rom()))
    assert len(segments) == 40
    assert all(s["name"].startswith("cvas_en_ui_") for s in segments)


def test_cvas_make_segment_branches():
    plugin = CastlevaniaGBAPlugin()
    data = bytearray(64)
    assert plugin._make_segment(data, 0, 10, 0, "en") is None
    data[9] = 0x00
    data[10] = 0x02
    assert plugin._make_segment(data, 10, 30, 0, "en") is None
    data[20] = 0x00
    data[21] = 0x01
    data[22:26] = b"ABCD"
    assert plugin._make_segment(data, 21, 21, 0, "en") is None
    data[30] = 0x00
    data[31] = 0x01
    data[32:36] = b"ABCD"
    data[36] = 0x00
    data[37] = 0x00
    segment = plugin._make_segment(bytes(data), 31, 60, 0, "en")
    assert segment["start"] == 31
    assert segment["name"] == "cvas_en_0"


def test_cvas_accessors():
    from plugins.gba_castlevania import CVAS_TERMINATORS

    plugin = CastlevaniaGBAPlugin()
    assert plugin.get_terminators("s") == CVAS_TERMINATORS
    assert plugin.get_compression_handler("s") is None


def test_ffta_pointer_table_skips():
    plugin = FFTAdvancePlugin()
    data = bytearray(16)
    data[0:8] = bytes([0x80, 0xB0, 0x00, 0x00, 0x40, 0x00, 0x00, 0x00])
    assert plugin._read_pointer_table(bytes(data), 0, 0, 2, "t") == []
    data3 = bytearray(10)
    assert plugin._read_pointer_table(bytes(data3), 0, 0, 3, "t") == []


def test_ffta_pointer_table_append():
    plugin = FFTAdvancePlugin()
    data = bytearray(7)
    data[0:4] = bytes([0x04, 0x00, 0x00, 0x00])
    data[4:7] = bytes([0x80, 0xB0, 0x00])
    segments = plugin._read_pointer_table(bytes(data), 0, 0, 1, "t")
    assert [s["name"] for s in segments] == ["t_0"]
    assert segments[0]["start"] == 4


def test_ffta_crn_names():
    plugin = FFTAdvancePlugin()
    data = bytearray(0x55128C + 200)
    pos = 0x55128C
    for _idx in range(62):
        data[pos : pos + 2] = b"AB"
        data[pos + 2] = 0x00
        pos += 3
    segments = plugin._read_crn_data(bytes(data))
    assert len(segments) == 62
    assert any(n.endswith("_2") for n in [s["name"] for s in segments])


def test_ffta_lzss_region():
    assert FFTAdvancePlugin._lzss_region(0x495000) == "D0"
    assert FFTAdvancePlugin._lzss_region(0x4B1000) == "D1"
    assert FFTAdvancePlugin._lzss_region(0x9C0000) == "D_mega"
    assert FFTAdvancePlugin._lzss_region(0x100) == "D_mega"


def test_ffta_tiny_rom_empty():
    assert FFTAdvancePlugin().get_text_segments(SimpleNamespace(data=bytes(0x100))) == []


def _lzss_block(lzss, raw):
    return b"\x32\x00" + lzss.compress(raw)


def test_ffta_lzss_scan_markers():
    from core.compression import FFTA_LZSSHandler

    lzss = FFTA_LZSSHandler()
    rom = bytearray(0x4A0000)
    big_stream = b"".join(b"\x41\x80\xb0" for _ in range(100))
    big = b"\x32\x00" + (200).to_bytes(4, "big") + big_stream
    rom[0x490000 : 0x490000 + len(big)] = big
    inner = 0x490010
    small_raw = bytes([0x80, 0xB0]) * 10
    small = _lzss_block(lzss, small_raw)
    rom[inner : inner + len(small)] = small
    rom[0x491000:0x491006] = b"\x32\x00\x00\x00\x00\x00"
    noisy = _lzss_block(lzss, bytes(100))
    rom[0x492000 : 0x492000 + len(noisy)] = noisy
    single = _lzss_block(lzss, b"A")
    rom[0x493000 : 0x493000 + len(single)] = single
    rom[0x4A0000 - 3 : 0x4A0000] = b"\x32\x00\x01"
    segments = FFTAdvancePlugin()._scan_lzss_dialogues(bytes(rom))
    assert len(segments) == 1
    assert "_D0_" in segments[0]["name"]
    assert segments[0]["text"].startswith("AAA")


def test_ffta_accessors():
    plugin = FFTAdvancePlugin()
    from plugins.gba_fft_advance import FFTA_TERMINATORS

    assert plugin.get_terminators("s") == FFTA_TERMINATORS
    assert plugin.get_compression_handler("s") is None


def test_ffta_decode_leading_zero():
    text, consumed = _decode_ffta_text(b"\x00ABC", 0, 4)
    assert text == ""
    assert consumed == 0


def test_ffta_single_unknown_paths():
    text, _ = _decode_ffta_text(b"\x01\x14\x41", 0, 3)
    assert text == "[14][40_41]"
    text, _ = _decode_ffta_text(b"\x01\x16", 0, 2)
    assert text == "[16]"


def test_ffta_encode_choice_multi():
    decoder = FFTATextDecoder()
    assert decoder.encode("[CHOICE]", force_multi=True).startswith(b"\x40\x53")


def test_ffta_tokenize_unknown_char():
    decoder = FFTATextDecoder()
    with pytest.raises(ValueError):
        decoder.encode("{€}")


def test_pokemon_static_unknown():
    assert _decode_pokemon_text_static(bytes([0x29]), CHARMAP_POKEMON_GBA) == "[29]"


def test_pokemon_encode_paths():
    assert _encode_pokemon_text("[BTN_AB]", CHARMAP_POKEMON_GBA) == bytes([0xF8, 0xAB])
    assert _encode_pokemon_text("[SYM_12]", CHARMAP_POKEMON_GBA) == bytes([0xF9, 0x12])
    assert _encode_pokemon_text("[FONT:ZZ]", CHARMAP_POKEMON_GBA) == bytes([0xFC, 0x06, 0x01])
    assert _encode_pokemon_text("[COLOR:ZZ]", CHARMAP_POKEMON_GBA) == bytes([0xFC, 0x01, 0x00])
    assert _encode_pokemon_text("[NOPE]", CHARMAP_POKEMON_GBA) == b""
    assert _encode_pokemon_text("{NOPE}", CHARMAP_POKEMON_GBA) == b""
    assert _encode_pokemon_text("a\nb", CHARMAP_POKEMON_GBA) == _encode_pokemon_text(
        "a", CHARMAP_POKEMON_GBA
    ) + b"\xfe" + _encode_pokemon_text("b", CHARMAP_POKEMON_GBA)


def test_pokemon_f9_glyphs_sorted():
    glyphs = _build_f9_glyphs({})
    assert glyphs == sorted(glyphs, key=lambda kv: len(kv[0]), reverse=True)
    assert all(isinstance(code, int) for _, code in glyphs)


def test_pokemon_segments_tiny():
    plugin = PokemonGBAPlugin()
    rom = SimpleNamespace(header={"game_code": "BPEE"}, data=bytes(0x100))
    assert plugin.get_text_segments(rom) == []


def test_pokemon_segments_manifest(monkeypatch):
    import plugins.gba_pokemon as gba_pokemon

    plugin = PokemonGBAPlugin()
    rom = SimpleNamespace(header={"game_code": "BPEE"}, data=bytes(0x100))
    monkeypatch.setattr(gba_pokemon, "entries_for_rom", lambda rom: [{"target": 8, "free_after": 4}])
    segments = plugin.get_text_segments(rom)
    assert [s["kind"] for s in segments] == ["pointer_dialogues"]


def test_pokemon_accessors():
    plugin = PokemonGBAPlugin()
    from plugins.gba_pokemon import POKEMON_TERMINATORS

    assert plugin.get_terminators("s") == POKEMON_TERMINATORS
    assert plugin.get_compression_handler("s") is None


def test_pokemon_fixed_unknown():
    from plugins.gba_pokemon import CHARMAP_POKEMON_GBA, PokemonFixedTextDecoder

    assert PokemonFixedTextDecoder(CHARMAP_POKEMON_GBA).decode(bytes([0x29]), 0, 1) == "[29]"


def test_gen1_decode_unknown():
    assert Gen1TextDecoder(CHARMAP_GEN1).decode(bytes([0x01]), 0, 1) == "[01]"


def test_gen1_encode_paths():
    decoder = Gen1TextDecoder(CHARMAP_GEN1)
    assert decoder.encode("[END]") == b""
    assert decoder.encode("[41]") == b""
    assert decoder.encode("€") == b""


def test_gen1_fixed_paths():
    decoder = Gen1FixedDecoder(CHARMAP_GEN1)
    assert decoder.decode(b"\x50ABC", 0, 4) == ""
    assert decoder.decode(bytes([0x01]), 0, 1) == "[01]"
    assert decoder.encode("[41]") == b""
    assert decoder.encode("€") == bytes([0x7F])


def test_gen1_validate_size():
    plugin = PokemonGen1Plugin()
    rom = SimpleNamespace(header={"title": "POKEMON RED"}, data=bytes(0x100))
    assert plugin.validate_rom(rom) is False


def test_gen1_unknown_title():
    plugin = PokemonGen1Plugin()
    rom = SimpleNamespace(header={"title": "NOPE"}, data=bytes(0x100))
    assert plugin.get_text_segments(rom) == []


def test_gen1_table_exceeds():
    plugin = PokemonGen1Plugin()
    rom = SimpleNamespace(header={"title": "POKEMON RED"}, data=bytes(0x100))
    assert plugin.get_text_segments(rom) == []


def test_gen1_accessors():
    plugin = PokemonGen1Plugin()

    assert plugin.get_terminators("s") == GEN1_TERMINATORS
    assert plugin.get_compression_handler("s") is None


def test_seasons_small_rom():
    from plugins.gbc_zelda_seasons import OracleOfSeasonsPlugin

    assert OracleOfSeasonsPlugin().get_text_segments(SimpleNamespace(data=bytes(10))) == []


def test_dx_small_rom_empty():
    from plugins.gbc_zelda_awakening_dx import ZeldaAwakeningDXPlugin

    assert ZeldaAwakeningDXPlugin().get_text_segments(SimpleNamespace(data=bytes(10))) == []


def test_dx_accessors():
    from plugins.gbc_zelda_awakening_dx import ZELDA_TERMINATORS, ZeldaAwakeningDXPlugin

    plugin = ZeldaAwakeningDXPlugin()
    assert plugin.get_terminators("s") == ZELDA_TERMINATORS
    assert plugin.get_compression_handler("s") is None


def _auto_rom():
    rom = bytearray(b"\x01" * 0x9000)
    rom[0x6000:0x6010] = b"A" * 0x10
    rom[0x6074:0x6450] = b"A" * (0x6450 - 0x6074)
    rom[0x64B4:0x9000] = b"A" * (0x9000 - 0x64B4)
    return bytes(rom)


def _auto_pointers():
    return [
        (0, 0x5000),
        (2, 0x5020),
        (4, 0x5100),
        (6, 0x5120),
        (8, 0x6000),
        (10, 0x6020),
        (12, 0x6080),
        (14, 0x60A0),
        (16, 0x6300),
        (18, 0x6320),
    ]


def test_autodetect_patterns_skip():
    from plugins.auto_detect import AutoDetectPlugin

    rom = SimpleNamespace(system="gb", data=bytes([1]) * 16500)
    assert AutoDetectPlugin().get_text_segments(rom) == []


def test_autodetect_patterns_low_density():
    from plugins.auto_detect import AutoDetectPlugin

    rom = SimpleNamespace(system="gb", data=bytes([1]) * 0x9000)
    assert AutoDetectPlugin().get_text_segments(rom) == []


def test_autodetect_pointer_groups(monkeypatch):
    import plugins.auto_detect as auto_detect
    from plugins.auto_detect import AutoDetectPlugin as _Plugin

    monkeypatch.setattr(auto_detect, "get_segment_patterns", lambda system: [])
    monkeypatch.setattr(auto_detect, "find_text_pointers", lambda *a, **k: _auto_pointers())
    monkeypatch.setattr(_Plugin, "_estimate_segment_length", lambda self, data, start, min_length=100: 300)
    segments = _Plugin().get_text_segments(SimpleNamespace(system="gb", data=_auto_rom()))
    assert {s["name"] for s in segments} == {"pointer_segment_3", "pointer_segment_4"}


def test_autodetect_short_group_skipped(monkeypatch):
    import plugins.auto_detect as auto_detect
    from plugins.auto_detect import AutoDetectPlugin as _Plugin

    monkeypatch.setattr(auto_detect, "get_segment_patterns", lambda system: [])
    monkeypatch.setattr(auto_detect, "find_text_pointers", lambda *a, **k: [(0, 0x6000)])
    monkeypatch.setattr(_Plugin, "_estimate_segment_length", lambda self, data, start, min_length=100: 100)
    monkeypatch.setattr(auto_detect, "auto_detect_segments", lambda *a, **k: [])
    segments = _Plugin().get_text_segments(SimpleNamespace(system="gb", data=_auto_rom()))
    assert segments == []


def test_autodetect_fallback(monkeypatch):
    import plugins.auto_detect as auto_detect

    monkeypatch.setattr(auto_detect, "get_segment_patterns", lambda system: [])
    monkeypatch.setattr(auto_detect, "find_text_pointers", lambda *a, **k: [])
    from plugins.auto_detect import AutoDetectPlugin

    data = bytes([1]) * 0x4000 + b"A" * 0x800 + bytes([1]) * 0x100 + b"A" * 0x800
    segments = AutoDetectPlugin().get_text_segments(SimpleNamespace(system="gb", data=data))
    assert len(segments) == 2


def test_autodetect_trim(monkeypatch):
    import plugins.auto_detect as auto_detect
    from plugins.auto_detect import AutoDetectPlugin as _Plugin

    monkeypatch.setattr(auto_detect, "get_segment_patterns", lambda system: [])
    monkeypatch.setattr(
        auto_detect,
        "find_text_pointers",
        lambda *a, **k: [(2 * i, 0x1000 + i * 0x1000) for i in range(25)],
    )
    monkeypatch.setattr(_Plugin, "_estimate_segment_length", lambda self, data, start, min_length=100: 300)

    data = bytearray(0x1A000)
    for i in range(25):
        base = 0x1000 + i * 0x1000
        data[base : base + 0x1000] = b"A" * 0x1000
    segments = _Plugin().get_text_segments(SimpleNamespace(system="gb", data=bytes(data)))
    assert len(segments) == 20


def test_autodetect_estimate_oob():
    from plugins.auto_detect import AutoDetectPlugin

    assert AutoDetectPlugin()._estimate_segment_length(b"AB", 100) == 0
