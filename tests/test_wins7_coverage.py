import struct
from types import SimpleNamespace

import pytest

from core.compression import FFTA_LZSSHandler
from plugins.gb_pokemon_gen1 import Gen1FixedDecoder
from plugins.gba_castlevania import CVAS_POINTER_COUNT, CVAS_POINTER_TABLE, CastlevaniaGBAPlugin
from plugins.gba_ff4_advance import CHARMAP_FF4, FF4TextDecoder
from plugins.gba_fft_advance import FFTAdvancePlugin
from plugins.gba_golden_sun_tla import GoldenSunTLAPlugin
from plugins.gba_pokemon import CHARMAP_POKEMON_GBA, _decode_pokemon_text_static, _encode_pokemon_text


def test_gb_gen1_no_space_fallback():
    decoder = Gen1FixedDecoder({})
    with pytest.raises(ValueError):
        decoder.encode("A")


def test_gba_castlevania_no_terminator():
    plugin = CastlevaniaGBAPlugin()
    size = CVAS_POINTER_TABLE + 4 * CVAS_POINTER_COUNT
    rom = bytearray(size + 0x1000)
    base = 0x10000
    for i in range(CVAS_POINTER_COUNT):
        struct.pack_into("<I", rom, CVAS_POINTER_TABLE + i * 4, base + i * 0x100 + 0x08000000)
    target = base + 10 * 0x100
    rom[target - 1] = 0x00
    rom[target] = 0x01
    rom[target + 1 : target + 10] = b"ABCDEFGH"
    rom[target + 10] = 0x01
    assert plugin._make_segment(bytes(rom), target, target, 0, "en") is None
    rom2 = bytearray(size + 0x1000)
    for i in range(CVAS_POINTER_COUNT):
        struct.pack_into("<I", rom2, CVAS_POINTER_TABLE + i * 4, base + i * 0x100 + 0x08000000)
    rom2[target - 1] = 0x00
    rom2[target] = 0x01
    rom2[target + 1 : target + 5] = b"ABCD"
    seg = plugin._make_segment(bytes(rom2), target, target + 20, 0, "en")
    assert seg is not None


def test_gba_ff4_decode_edge():
    decoder = FF4TextDecoder(CHARMAP_FF4)
    assert decoder.decode(bytes([0x01, 0x0C]), 0, 2) == "e"
    assert decoder.decode(bytes([0xC2, 0x02]), 0, 2) == "[C202]"
    with pytest.raises(ValueError):
        decoder.encode("€")


def test_gba_fft_no_table():
    plugin = FFTAdvancePlugin()
    data = bytearray(16)
    data[0:4] = (0x08).to_bytes(4, "little")
    assert plugin._read_pointer_table(bytes(data), 0, 0, 1, "t") == []
    assert plugin.get_text_segments(SimpleNamespace(data=bytes(100))) == []


def test_gba_golden_small():
    plugin = GoldenSunTLAPlugin()
    assert plugin.get_text_segments(SimpleNamespace(data=bytes(100))) == []
    rom = bytearray(0x0AA100)
    rom[0x0A9F54 : 0x0A9F54 + 8] = struct.pack("<II", 0x08001000, 0x08002000)
    assert len(plugin.get_text_segments(SimpleNamespace(data=bytes(rom)))) == 0


def test_gba_pokemon_decode_truncated():
    assert _decode_pokemon_text_static(bytes([0xF9]), CHARMAP_POKEMON_GBA) == ""
    assert _decode_pokemon_text_static(bytes([0xFD]), CHARMAP_POKEMON_GBA) == ""
    assert _decode_pokemon_text_static(bytes([0xFC]), CHARMAP_POKEMON_GBA) == ""
    assert isinstance(_decode_pokemon_text_static(bytes([0xFC, 0x06]), CHARMAP_POKEMON_GBA), str)


def test_gba_pokemon_decode_encode():
    assert "[29]" in _decode_pokemon_text_static(bytes([0x29]), CHARMAP_POKEMON_GBA)
    assert _encode_pokemon_text("[FONT:ZZ]", CHARMAP_POKEMON_GBA) == bytes([0xFC, 0x06, 0x01])
    assert _encode_pokemon_text("[COLOR:ZZ]", CHARMAP_POKEMON_GBA) == bytes([0xFC, 0x01, 0x00])
    assert _encode_pokemon_text("[BTN_00]", CHARMAP_POKEMON_GBA) == bytes([0xF8, 0x00])
    assert _encode_pokemon_text("[SYM_00]", CHARMAP_POKEMON_GBA) == bytes([0xF9, 0x00])
    assert _encode_pokemon_text("{PLAYER}", CHARMAP_POKEMON_GBA) == bytes([0xFD, 0x01])
    assert _encode_pokemon_text("a\nb", CHARMAP_POKEMON_GBA) == _encode_pokemon_text(
        "a", CHARMAP_POKEMON_GBA
    ) + b"\xfe" + _encode_pokemon_text("b", CHARMAP_POKEMON_GBA)
    data = bytes([0xF8, 0x00, 0xF9, 0x00, 0xFD, 0x01, 0xFC, 0x06, 0x01, 0xFC, 0x01, 0x00, 0xF7, 0x41, 0xFF])
    text = _decode_pokemon_text_static(data, CHARMAP_POKEMON_GBA)
    assert "[BTN" in text or "A" in text
    from plugins.gba_pokemon import PokemonTextDecoder

    dec = PokemonTextDecoder(CHARMAP_POKEMON_GBA)
    assert dec.decode(data, 0, len(data)) != ""
    custom = PokemonTextDecoder({0x20: " ", 0x41: "A"})
    assert custom.encode("a") == bytes([0x41])
    assert custom.encode("€") in (bytes([0x20]), bytes([0x00]))


def test_compression_ffta_breaks():
    handler = FFTA_LZSSHandler()
    out, _ = handler.decompress(b"\x00\x00\x00\x05\x41AB\x10\x00\x00", 0)
    assert out == b"ABBBB"
    out, _ = handler.decompress(b"\x00\x00\x00\x02\x20\x00\x00", 0)
    assert len(out) == 2
    out, _ = handler.decompress(b"\x00\x00\x00\x01\x40\x01", 0)
    assert len(out) == 1
    out, _ = handler.decompress(b"\x00\x00\x00\x02\x02\xff", 0)
    assert len(out) == 2
    out, _ = handler.decompress(b"\x00\x00\x00\x02\x01\xff", 0)
    assert len(out) == 2
    out, _ = handler.decompress(b"\x00\x00\x00\x05\x00\x01\x02\x03\x04", 0)
    assert len(out) == 5


def test_scanner_stride_edge():
    from core.scanner import _detect_constant_stride

    pointers = [(i, i * 10) for i in range(10)]
    filtered = _detect_constant_stride(pointers, min_run=8)
    assert len(filtered) < len(pointers)


def test_auto_detect_edge():
    from plugins.auto_detect import AutoDetectPlugin

    assert AutoDetectPlugin()._estimate_segment_length(b"AB", 100) == 0
    assert AutoDetectPlugin()._group_close_pointers([]) == []


def test_auto_detect_overlap(monkeypatch):
    import plugins.auto_detect as auto_detect
    from plugins.auto_detect import AutoDetectPlugin

    monkeypatch.setattr(
        auto_detect,
        "get_segment_patterns",
        lambda system: [
            {"start_min": 0x4000, "start_max": 0x4000, "end_min": 0x5000, "end_max": 0x5000},
            {"start_min": 0x4800, "start_max": 0x4800, "end_min": 0x5800, "end_max": 0x5800},
        ],
    )
    monkeypatch.setattr(
        auto_detect, "analyze_text_segment", lambda data, s, e: {"readability": 0.9 if s == 0x4000 else 0.8}
    )
    monkeypatch.setattr(auto_detect, "find_text_pointers", lambda *a, **k: [])
    monkeypatch.setattr(auto_detect, "auto_detect_segments", lambda *a, **k: [])
    rom = SimpleNamespace(system="gb", data=bytes(0x9000))
    rom.data = bytearray(0x9000)
    for i in range(0x4000, 0x5000):
        rom.data[i] = 0x41
    for i in range(0x4800, 0x5800):
        rom.data[i] = 0x41
    rom.data = bytes(rom.data)
    segments = AutoDetectPlugin().get_text_segments(rom)
    assert len(segments) == 1


def test_gba_fft_large_rom(monkeypatch):
    import plugins.gba_fft_advance as fft_mod

    plugin = FFTAdvancePlugin()
    monkeypatch.setattr(fft_mod, "FFTA_STRING_TABLES", [(0x100, 0x200, 10, "Test")])
    rom = bytearray(0x1000)
    rom[0x100 : 0x100 + 40] = b"\x00" * 40
    monkeypatch.setattr(plugin, "_read_pointer_table", lambda *a, **k: [{"name": "t_0", "start": 0, "end": 10}])
    monkeypatch.setattr(plugin, "_read_crn_data", lambda *a, **k: [])
    monkeypatch.setattr(plugin, "_scan_lzss_dialogues", lambda *a, **k: [])
    segments = plugin.get_text_segments(SimpleNamespace(data=bytes(rom)))
    assert len(segments) >= 1


def test_gba_pokemon_token_encode():
    from plugins.gba_pokemon import PokemonTextDecoder

    dec = PokemonTextDecoder(CHARMAP_POKEMON_GBA)
    token = next(
        (v for v in CHARMAP_POKEMON_GBA.values() if len(v) >= 2 and not v.startswith("[") and not v.startswith("{")),
        None,
    )
    if token:
        assert dec.encode(token) != b""
    assert PokemonTextDecoder({0x41: "A"}).encode("a") == bytes([0x41])
