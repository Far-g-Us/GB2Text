import struct
from types import SimpleNamespace

from core.plugin_api import PluginFactory, PluginState
from plugins.gb_pokemon_gen1 import PokemonGen1Plugin
from plugins.gba_castlevania import CVAS_POINTER_COUNT, CVAS_POINTER_TABLE, CastlevaniaGBAPlugin
from plugins.gba_ff4_advance import FF4AdvancePlugin
from plugins.gba_fft_advance import FFTAdvancePlugin
from plugins.gba_golden_sun_tla import GoldenSunTLAPlugin
from plugins.gba_pokemon import PokemonGBAPlugin


def test_plugin_on_load_false():
    cls = PluginFactory.get_plugin_class("example_game")
    plugin = cls()
    plugin.initialize = lambda: False
    assert plugin.on_load() is False
    assert plugin.state == PluginState.LOADING


def test_plugin_on_load_exception():
    cls = PluginFactory.get_plugin_class("example_game")
    plugin = cls()
    plugin.initialize = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    assert plugin.on_load() is False
    assert plugin.state == PluginState.ERROR


def test_plugin_on_unload_exception():
    cls = PluginFactory.get_plugin_class("example_game")
    plugin = cls()
    assert plugin.on_load() is True
    plugin.shutdown = lambda: (_ for _ in ()).throw(RuntimeError("bye"))
    plugin.on_unload()
    assert plugin.state == PluginState.LOADED


def test_plugin_load_save_exceptions(tmp_path, monkeypatch):
    cls = PluginFactory.get_plugin_class("example_game")
    plugin = cls()
    bad = tmp_path / "bad.json"
    bad.write_text("{bad", encoding="utf-8")
    assert plugin.load_config(str(bad)) is False
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
    plugin.set_config("k", "v")
    plugin.save_config(str(tmp_path / "out.json"))
    assert not (tmp_path / "out.json").exists()


def test_gb_gen1_fixed_space_fallback():
    plugin = PokemonGen1Plugin()
    rom = SimpleNamespace(header={"title": "POKEMON RED"}, data=bytes(0x200000))
    segments = plugin.get_text_segments(rom)
    assert segments != []
    assert any("monster_names" in s["name"] for s in segments)


def test_gba_castlevania_non_mono_block(monkeypatch):
    plugin = CastlevaniaGBAPlugin()
    size = CVAS_POINTER_TABLE + 4 * CVAS_POINTER_COUNT
    rom = bytearray(size + 0x1000)
    base = 0x10000
    for i in range(CVAS_POINTER_COUNT):
        val = base + i * 0x100
        if i == 41:
            val = base + 40 * 0x100 - 0x50
        struct.pack_into("<I", rom, CVAS_POINTER_TABLE + i * 4, val + 0x08000000)
    for i in [*range(40), 42]:
        target = base + i * 0x100
        rom[target - 1] = 0x00
        rom[target] = 0x01
        rom[target + 1 : target + 5] = b"ABCD"
        rom[target + 5] = 0x00
        rom[target + 6] = 0x00
    rom[base + 10 * 0x100 + 5] = 0xFF
    segments = plugin.get_text_segments(SimpleNamespace(data=bytes(rom)))
    assert len(segments) == 40


def test_gba_ff4_pointer_table_edge():
    plugin = FF4AdvancePlugin()
    size = 0x323B64
    rom = bytearray(size)
    for i in range(0x2E3670, 0x323B64):
        rom[i] = 0x33
    rom[0x2E3680 : 0x2E3680 + 2] = (0).to_bytes(2, "little")
    rom[0x2E3670:0x2E3673] = bytes([0x01, 0x02, 0x02])
    rom[0x2E3673] = 0x0C
    for i in range(1, 6287):
        rom[0x2E3680 + i * 4 : 0x2E3680 + i * 4 + 2] = (0xFF00).to_bytes(2, "little")
    segments = plugin.get_text_segments(SimpleNamespace(data=bytes(rom)))
    assert any(s["name"] == "ff4_text_0" for s in segments)


def test_gba_fft_lzss_noise_and_short():
    plugin = FFTAdvancePlugin()
    assert plugin._lzss_is_noise(b"") is True
    assert plugin._lzss_is_noise(b"\x00" * 10) is True
    assert plugin._lzss_region(0x100) == "D_mega"


def test_gba_golden_tla_small_and_bad():
    plugin = GoldenSunTLAPlugin()
    assert plugin.get_text_segments(SimpleNamespace(data=bytes(100))) == []
    rom = bytearray(0x0AA100)
    rom[0x0A9F54 : 0x0A9F54 + 8] = struct.pack("<II", 0x07001000, 0x07002000)
    assert plugin.get_text_segments(SimpleNamespace(data=bytes(rom))) == []


def test_gba_pokemon_manifest_and_stub(monkeypatch):
    import plugins.gba_pokemon as gba_pokemon

    plugin = PokemonGBAPlugin()
    rom = SimpleNamespace(header={"game_code": "BPEE"}, data=bytes(0x100))
    monkeypatch.setattr(gba_pokemon, "entries_for_rom", lambda rom: [{"target": 8, "free_after": 4}])
    segments = plugin.get_text_segments(rom)
    assert any(s["kind"] == "pointer_dialogues" for s in segments)
    rom2 = SimpleNamespace(header={"game_code": "BPEJ"}, data=bytes(0x100))
    assert plugin.get_text_segments(rom2) == []


def test_compression_all_handlers():
    from core.compression import AutoDetectCompressionHandler, HuffmanHandler, get_compression_handler

    handler = AutoDetectCompressionHandler()
    assert handler.decompress(b"\x10\x01\x00\x00\x00A", 0) == (b"A", 6)
    assert get_compression_handler("huffman") is not None
    h = HuffmanHandler()
    h.set_tree_pointers(1, 2)
    assert h.decompress_text_block(bytes(10), 50, 60, 0) == b""
    rom = bytearray(16)
    rom[0] = 0xC1
    rom[1] = 0x80
    rom[4] = 0b10
    assert HuffmanHandler().decompress_text_block(bytes(rom), 4, 0, 0) == b"A"


def test_scanner_ml_and_auto(monkeypatch):
    import core.scanner as scanner_mod
    from core.scanner import auto_detect_segments_ml

    monkeypatch.setattr(scanner_mod, "SKLEARN_AVAILABLE", False)
    assert auto_detect_segments_ml(b"A" * 64) == []
    monkeypatch.setattr(scanner_mod, "SKLEARN_AVAILABLE", True)
    assert isinstance(auto_detect_segments_ml(b"A" * 64), list)


def test_auto_detect_groups():
    from plugins.auto_detect import AutoDetectPlugin

    plugin = AutoDetectPlugin()
    assert plugin._group_close_pointers([]) == []
    assert plugin._estimate_segment_length(b"AB", 100) == 0
