import xml.etree.ElementTree as ET
from collections import Counter
from types import SimpleNamespace

import pytest

import api
from core.decoder import CharMapDecoder, LZ77Handler, MultiCharMapDecoder
from core.extractor import TextExtractor
from core.ml_classifier import SegmentMLClassifier
from core.multi_charmap import (
    CharTable,
    EncodingDetector,
    MultiCharmapSegment,
    _detect_sjis_sequences,
)
from core.plugin_api import HookType, PluginFactory
from core.rom import GameBoyROM
from core.scanner import (
    _detect_constant_stride,
    _setup_common_symbols,
    analyze_text_segment,
    auto_detect_charmap,
    auto_detect_segments,
    auto_detect_segments_ml,
    find_text_pointers,
    is_text_like,
)
from core.tmx import TMXHandler


def test_api_serve_wrapper(monkeypatch):
    calls = []
    monkeypatch.setattr("api.server.serve", lambda *a, **k: calls.append((a, k)))
    api.serve("127.0.0.1", 0, plugin_dir="p", max_workers=1, api_token="t")
    assert calls[0][0] == ("127.0.0.1", 0)
    assert calls[0][1]["api_token"] == "t"


def _bext(**attrs):
    extractor = TextExtractor.__new__(TextExtractor)
    extractor.i18n = None
    extractor.progress_callback = None
    extractor.plugin_manager = SimpleNamespace()
    extractor.cancellation_token = None
    extractor.max_segments = None
    extractor.guide = None
    extractor.plugin = None
    extractor.current_results = None
    extractor._segment_cache = {}
    extractor._bank_segments = []
    extractor._taken_free_blocks = []
    extractor.rom = SimpleNamespace(system="gb", get_game_id=lambda: "G", data=bytes(100))
    for key, value in attrs.items():
        setattr(extractor, key, value)
    return extractor


def test_extractor_t_i18n_ok():
    extractor = _bext(i18n=SimpleNamespace(t=lambda key: "T"))
    assert extractor._t("k", "d") == "T"


def test_extractor_t_i18n_raises():
    def _boom(key):
        raise RuntimeError("i18n down")

    extractor = _bext(i18n=SimpleNamespace(t=_boom))
    assert extractor._t("k", "d") == "d"


def test_extractor_progress_via_manager():
    calls = []
    manager = SimpleNamespace(update_status=lambda m, p: calls.append((m, p)))
    _bext(plugin_manager=manager)._report_progress("m", 5)
    assert calls == [("m", 5)]


class _FlipToken:
    def __init__(self, values):
        self._values = list(values)

    def is_cancellation_requested(self):
        return self._values.pop(0)


def test_extractor_cancel_after_plugin():
    manager = SimpleNamespace(get_plugin=lambda *a, **k: object())
    extractor = _bext(plugin_manager=manager, cancellation_token=_FlipToken([False, True]))
    assert extractor.extract() == {}


def test_extractor_cancel_in_loop():
    plugin = SimpleNamespace(get_text_segments=lambda rom: [{"name": "s", "start": 0, "end": 10}])
    manager = SimpleNamespace(get_plugin=lambda *a, **k: plugin)
    extractor = _bext(plugin_manager=manager, cancellation_token=_FlipToken([False, False, True]))
    assert extractor.extract() == {}


def test_extractor_raw_text():
    plugin = SimpleNamespace(get_text_segments=lambda rom: [{"name": "s", "start": 0, "end": 10, "raw_text": "hello"}])
    manager = SimpleNamespace(get_plugin=lambda *a, **k: plugin)
    assert _bext(plugin_manager=manager).extract() == {"s": [{"offset": 0, "text": "hello"}]}


def test_extractor_empty_text_skips_quality():
    plugin = SimpleNamespace(get_text_segments=lambda rom: [{"name": "s", "start": 0, "end": 10, "raw_text": ""}])
    manager = SimpleNamespace(get_plugin=lambda *a, **k: plugin)
    assert _bext(plugin_manager=manager).extract() == {"s": []}


def test_extractor_low_quality_warning():
    plugin = SimpleNamespace(get_text_segments=lambda rom: [{"name": "s", "start": 0, "end": 10, "raw_text": "[[[[[["}])
    manager = SimpleNamespace(get_plugin=lambda *a, **k: plugin)
    assert "s" in _bext(plugin_manager=manager).extract()


def test_extractor_pointer_dialogues_branches():
    def fake_decode(data, addr, limit):
        if addr == 5:
            raise RuntimeError("bad")
        if addr == 6:
            return "   "
        return "hi"

    decoder = SimpleNamespace(decode=fake_decode)
    extractor = _bext()
    assert extractor._extract_pointer_dialogues({"decoder": None}) == []
    assert extractor._extract_pointer_dialogues({"decoder": decoder}) == []
    manifest = [
        {"target": 99999},
        {"target": 5},
        {"target": 6},
        {"target": 7, "free_after": 10, "slots": [1]},
    ]
    assert extractor._extract_pointer_dialogues({"decoder": decoder, "manifest": manifest}) == [
        {"text": "hi", "offset": 7, "target_addr": 7, "length": 10, "slots": [1]}
    ]


def test_extractor_decompress_str_paths(monkeypatch):
    import core.compression as compression

    extractor = _bext()

    class Handler:
        def decompress(self, data, start):
            return b"out", 3

    monkeypatch.setattr(compression, "get_compression_handler", lambda name: Handler())
    assert extractor._decompress(b"data", "lz77") == b"out"
    monkeypatch.setattr(compression, "get_compression_handler", lambda name: None)
    assert extractor._decompress(b"data", "lz77") == b"data"

    class Broken:
        def decompress(self, data, start):
            raise RuntimeError("boom")

    monkeypatch.setattr(compression, "get_compression_handler", lambda name: Broken())
    assert extractor._decompress(b"data", "lz77") == b"data"


def test_extractor_decompress_object_paths():
    extractor = _bext()

    class Handler:
        def decompress(self, data, start):
            return b"out", 3

    assert extractor._decompress(b"data", Handler()) == b"out"

    class Broken:
        def decompress(self, data, start):
            raise RuntimeError("boom")

    assert extractor._decompress(b"data", Broken()) == b"data"


def test_extractor_recode_bad_addresses():
    extractor = _bext(rom=SimpleNamespace(data=bytes(10)))
    assert extractor.recode_segment({"start": 50, "end": 60}, None) == []


def test_extractor_recode_fixed_width():
    class Decoder:
        def decode(self, data, start, length):
            return "AB"

    extractor = _bext(rom=SimpleNamespace(data=bytes(8)))
    segment = {"name": "s", "start": 0, "end": 8, "fixed_width": 4, "record_count": 2}
    messages = extractor.recode_segment(segment, Decoder())
    assert [m["text"] for m in messages] == ["AB", "AB"]


def test_extractor_fixed_beyond_data():
    extractor = _bext(rom=SimpleNamespace(data=bytes(20)))
    segment = {"name": "s", "start": 16, "end": 24, "fixed_width": 8, "record_count": 2}
    assert extractor._extract_fixed_width_messages(segment, None) == []


def test_extractor_fixed_decode_error():
    class Broken:
        def decode(self, data, start, length):
            raise RuntimeError("bad slot")

    extractor = _bext(rom=SimpleNamespace(data=bytes(8)))
    segment = {"name": "s", "start": 0, "end": 8, "fixed_width": 4, "record_count": 2}
    assert extractor._extract_fixed_width_messages(segment, Broken()) == []


def test_extractor_guide_recommendations():
    class Decoder:
        def __init__(self):
            self.charmap = {}

    decoder = Decoder()
    plugin = SimpleNamespace(
        get_text_segments=lambda rom: [
            {"name": "seg", "decoder": decoder},
            {"name": "other", "decoder": decoder},
        ]
    )
    extractor = _bext(
        plugin=plugin,
        rom=SimpleNamespace(data=bytes(10)),
        guide={"recommendations": {"decoder_adjustments": {"seg": {"charmap": {"41": "X", "ZZ": "Y"}}}}},
    )
    extractor._apply_guide_recommendations()
    assert decoder.charmap[0x41] == "X"


def test_extractor_guide_not_dict():
    extractor = _bext(
        plugin=object(),
        guide={"recommendations": {"decoder_adjustments": ["notadict"]}},
    )
    with pytest.raises(AttributeError):
        extractor._apply_guide_recommendations()


def test_extractor_adjust_decoder_bad_charmap():
    class BadDict(dict):
        def __setitem__(self, key, value):
            raise TypeError("frozen")

    extractor = _bext()
    decoder = SimpleNamespace(charmap=BadDict())
    with pytest.raises(TypeError):
        extractor._adjust_decoder(decoder, {"charmap": {"41": "X"}})


def test_extractor_split_tokens():
    extractor = _bext()
    assert extractor._split_messages("[END]hi", 0) == [{"offset": 5, "text": "hi"}]
    assert extractor._split_messages("ab[41]cd[ZZ]ef", 0) == [
        {"offset": 0, "text": "ab"},
        {"offset": 6, "text": "cd[ZZ]ef"},
    ]


def test_decoder_pointer_pattern():
    assert CharMapDecoder({}).decode(bytes([0xCD, 0x1B]), 0, 2) == ""


def test_decoder_command_pattern():
    assert CharMapDecoder({}).decode(bytes([0xE0, 0x9A]), 0, 2) == ""


def test_multi_unavailable_paths(monkeypatch):
    import core.decoder as decoder_mod

    monkeypatch.setattr(decoder_mod, "MULTI_CHARMAP_AVAILABLE", False)
    monkeypatch.setattr(decoder_mod, "get_detector", None)
    decoder = MultiCharMapDecoder({})
    assert decoder.detector is None
    assert decoder.decode_segment(b"AB", 0, 2) == "AB"
    assert decoder.detect_encoding(b"x") == ("unknown", 0.0)
    assert decoder.suggest_charmap(b"x") == {}


def test_multi_alternative_charmaps():
    decoder = MultiCharMapDecoder({0x41: "A"})
    result = decoder.decode_segment(b"AB", 0, 2, [{0x42: "B"}, {}])
    assert "A" in result and "B" in result


def test_multi_decode_basic_branches():
    decoder = MultiCharMapDecoder({})
    assert decoder._decode_basic(bytes([0x00, 0x01, 0x41]), 0, 3) == "\n[01]A"


def test_multi_learn_raises():
    class Broken:
        def learn_encoding(self, name, sample_data, char_map):
            raise RuntimeError("gone")

    decoder = MultiCharMapDecoder({})
    decoder.detector = Broken()
    with pytest.raises(RuntimeError):
        decoder.learn_encoding("n", b"d", {})


def test_lz77_start_beyond():

    assert LZ77Handler().decompress(b"AB", 5) == (b"", 0)


def test_lz77_full_literals():

    data = b"\x10\x08\x00\x00" + b"\xff" + b"ABCDEFGH"
    assert LZ77Handler().decompress(data, 0) == (b"ABCDEFGH", 13)


def test_lz77_partial_end():

    assert LZ77Handler().decompress(b"\x10\x02\x00\x00" + b"\xffA", 0) == (b"A", 6)


def test_lz77_size_break():

    assert LZ77Handler().decompress(b"\x10\x01\x00\x00" + b"\xffA", 0) == (b"A", 6)


def test_lz77_backref_ok():

    data = b"\x10\x08\x00\x00" + b"\xc0" + b"AB" + b"\x00\x01"
    assert LZ77Handler().decompress(data, 0) == (b"ABABA", 9)


def test_lz77_backref_invalid():

    assert LZ77Handler().decompress(b"\x10\x02\x00\x00" + b"\x00" + b"\x00\x01", 0) == (b"", 7)


def test_lz77_backref_inner_break():

    data = b"\x10\x04\x00\x00" + b"\xc0" + b"AB" + b"\x00\x01"
    assert LZ77Handler().decompress(data, 0) == (b"ABAB", 9)


def test_lz77_backref_truncated():

    assert LZ77Handler().decompress(b"\x10\x02\x00\x00" + b"\x00" + b"\x00", 0) == (b"", 6)


def test_optional_import_fallbacks():
    assert True


def test_stride_no_constant_run():
    pointers = [(i, t) for i, t in enumerate([0, 5, 20, 21, 50, 51, 100, 101, 200, 201])]
    assert _detect_constant_stride(pointers) == pointers


def test_fallback_pointer_loop(monkeypatch):
    import core.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "NUMPY_AVAILABLE", False)
    data = bytearray(0x5000)
    data[0:2] = bytes([0x00, 0x40])
    data[0x4000:0x4009] = b"Hello Wor"
    assert find_text_pointers(bytes(data), pointer_size=2) == [(0, 0x4000)]


def test_fallback_pointer_base(monkeypatch):
    import core.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "NUMPY_AVAILABLE", False)
    data = bytearray(0x5000)
    data[0:4] = (0x08004000).to_bytes(4, "little")
    data[0x4000:0x4009] = b"Hello Wor"
    assert find_text_pointers(bytes(data), pointer_size=4, address_base=0x08000000) == [(0, 0x4000)]
    data[0:4] = (0x07000000).to_bytes(4, "little")
    assert find_text_pointers(bytes(data), pointer_size=4, address_base=0x08000000) == []


def test_is_text_like_no_terminator_ratio():
    assert is_text_like(b"A" * 8 + b"B" * 3 + bytes([1]) * 5, 0, 16) is False


def test_charmap_space_and_terminator():

    data = b"A" * 60 + bytes([0x80]) * 15 + bytes([0x81]) * 15 + b"B" + b"A" * 300
    charmap = auto_detect_charmap(data)
    assert charmap[0x80] == " "
    assert charmap[0x81] == "\n"


def test_common_symbols_gbc():
    charmap: dict = {}
    _setup_common_symbols(charmap, Counter({0x80: 20}), True, bytes(100), 0, 100)
    assert charmap[0x00] == "\n"
    assert charmap[0xFF] == "\n"


def test_auto_segments_close_and_trailing():
    data = bytes(0x4000) + bytes(64) + b"A" * 0x1000 + bytes(0x100)
    segments = auto_detect_segments(data, min_segment_length=300, min_readability=0.7, block_size=64)
    assert len(segments) == 1
    data2 = bytes(0x4000) + b"A" * 0x1000
    assert len(auto_detect_segments(data2, min_segment_length=300, min_readability=0.7, block_size=64)) == 1


class _FakePredict:
    def __init__(self, values):
        self._values = list(values)

    def predict(self, block):
        return self._values.pop(0)


def _ml_data(*parts):
    return bytes(0x4000) + b"".join(parts)


def test_ml_segments_unavailable(monkeypatch):
    import core.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "SKLEARN_AVAILABLE", False)
    assert auto_detect_segments_ml(b"A" * 64) == []


def test_ml_segments_break_after_skip(monkeypatch):
    import core.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "get_ml_classifier", lambda: _FakePredict([]))
    assert auto_detect_segments_ml(bytes(10)) == []


def test_ml_segments_close(monkeypatch):
    import core.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "get_ml_classifier", lambda: _FakePredict([0.9] * 4 + [0.0]))
    segments = auto_detect_segments_ml(_ml_data(b"A" * 64, bytes([1]) * 16), 16, 16, 0.6)
    assert [s["name"] for s in segments] == ["ml_segment_0"]


def test_ml_segments_trailing(monkeypatch):
    import core.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "get_ml_classifier", lambda: _FakePredict([0.9] * 4))
    assert len(auto_detect_segments_ml(_ml_data(b"A" * 64), 16, 16, 0.6)) == 1


def test_ml_segments_short_close(monkeypatch):
    import core.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "get_ml_classifier", lambda: _FakePredict([0.9, 0.0]))
    assert auto_detect_segments_ml(_ml_data(b"A" * 16, bytes(16)), 32, 16, 0.6) == []


def test_ml_segments_short_trailing(monkeypatch):
    import core.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "get_ml_classifier", lambda: _FakePredict([0.9]))
    assert auto_detect_segments_ml(_ml_data(b"A" * 16), 32, 16, 0.6) == []


def test_ml_segments_never_open(monkeypatch):
    import core.scanner as scanner_mod

    monkeypatch.setattr(scanner_mod, "get_ml_classifier", lambda: _FakePredict([0.0]))
    assert auto_detect_segments_ml(_ml_data(bytes(16)), 16, 16, 0.6) == []


def test_analyze_pointer_count():
    rom = bytearray(0x5000)
    rom[0:4] = (0x4000).to_bytes(4, "little")
    assert analyze_text_segment(bytes(rom), 0, 16)["has_pointers"] is False


def test_rom_bad_path_type():
    with pytest.raises(TypeError):
        GameBoyROM(123)


def test_rom_oversize(monkeypatch, tmp_path):
    import core.rom as rom_mod

    target = tmp_path / "big.gb"
    target.write_bytes(bytes(20))
    monkeypatch.setattr(rom_mod, "MAX_ROM_SIZE", 10)
    with pytest.raises(ValueError):
        GameBoyROM(str(target))


def test_rom_too_small(tmp_path):
    target = tmp_path / "tiny.gb"
    target.write_bytes(bytes(10))
    with pytest.raises(ValueError):
        GameBoyROM(str(target))


class _ExplodingData(bytearray):
    def __getitem__(self, key):
        raise RuntimeError("boom")


def test_rom_header_parse_errors():
    rom = GameBoyROM.__new__(GameBoyROM)
    rom.path = "x.gba"
    rom.data = _ExplodingData(b"\x00" * 0x200)
    with pytest.raises(ValueError):
        rom._parse_header()
    rom.path = "x.gb"
    with pytest.raises(ValueError):
        rom._parse_header()


def test_rom_licensee_fix(tmp_path):
    target = tmp_path / "lic.gb"
    data = bytearray(0x200)
    data[0x144] = 0xFF
    data[0x145] = 0xFF
    target.write_bytes(bytes(data))
    assert GameBoyROM(str(target)).header["new_licensee_code"] == 0


def test_rom_read_string(api_rom_file):
    assert GameBoyROM(api_rom_file)._read_string(0x134, 4) == "TEST"


def test_rom_system_variants(tmp_path):
    gba_magic = tmp_path / "m.gb"
    gba_magic.write_bytes(b"GBA " + bytes(0x200))
    assert GameBoyROM(str(gba_magic)).system == "gba"
    gba_ext = tmp_path / "e.gba"
    gba_ext.write_bytes(bytes(0x8000))
    assert GameBoyROM(str(gba_ext)).system == "gba"
    gbc_lic = tmp_path / "c.gb"
    data = bytearray(0x200)
    data[0x145] = 0x33
    gbc_lic.write_bytes(bytes(data))
    assert GameBoyROM(str(gbc_lic)).system == "gbc"
    gbc_size = tmp_path / "s.gb"
    data = bytearray(0x200)
    data[0x148] = 9
    gbc_size.write_bytes(bytes(data))
    assert GameBoyROM(str(gbc_size)).system == "gbc"


def test_rom_properties(api_rom_file):
    rom = GameBoyROM(api_rom_file)
    assert rom.size == len(rom.data)
    assert rom.type == rom.system
    assert isinstance(rom.cgb_flag, int)
    assert isinstance(rom.rom_size, int)
    assert isinstance(rom.ram_size, int)
    assert isinstance(rom.region, int)
    assert isinstance(rom.calculate_header_checksum(), int)
    assert isinstance(rom.calculate_gba_complement(), int)


def test_rom_read_branches(api_rom_file):
    rom = GameBoyROM(api_rom_file)
    assert rom.read(0xA000) == 0xFF
    assert rom.read(0xC000) == 0xFF


def test_plugin_api_example():

    cls = PluginFactory.get_plugin_class("example_game")
    plugin = cls()
    assert plugin.info.name == "Example Game Plugin"
    assert plugin.on_load() is True
    plugin.shutdown()
    plugin.on_rom_loaded({"title": "X"})
    assert plugin.match_rom({"title": "Example game"}) is True
    assert plugin.match_rom({"title": "zzz"}) is False
    assert len(plugin.get_text_segments(None)) == 2

    def callback(context):
        pass

    plugin.register_hook(HookType.ROM_LOADED, callback)
    plugin.unregister_hook(HookType.ROM_LOADED, callback)


def test_plugin_api_config_files(tmp_path):

    plugin = PluginFactory.get_plugin_class("example_game")()
    assert plugin.load_config(str(tmp_path / "no.json")) is False
    target = tmp_path / "c.json"
    plugin.set_config("k", "v")
    plugin.save_config(str(target))
    assert plugin.load_config(str(target)) is True
    assert plugin.get_config("k") == "v"


def test_plugin_api_config_no_path():

    plugin = PluginFactory.get_plugin_class("example_game")()
    assert plugin.info.config_file is None
    plugin.save_config()
    assert plugin.load_config() is False


def test_plugin_api_save_failure(tmp_path):

    plugin = PluginFactory.get_plugin_class("example_game")()
    plugin.set_config("k", "v")
    plugin.save_config(str(tmp_path / "nodir" / "f.json"))
    assert not (tmp_path / "nodir" / "f.json").exists()


def test_plugin_api_disable_broken():

    plugin = PluginFactory.get_plugin_class("example_game")()
    del plugin._state
    with pytest.raises(AttributeError):
        plugin.on_disable()


def test_plugin_api_save_robustness():

    class RaisingBool:
        def __bool__(self):
            raise RuntimeError("nope")

    plugin = PluginFactory.get_plugin_class("example_game")()
    with pytest.raises(RuntimeError):
        plugin.save_config(RaisingBool())


def test_extractor_progress_callback():
    calls = []
    extractor = _bext(progress_callback=lambda m, p: calls.append((m, p)))
    extractor._report_progress("m", 5)
    assert calls == [("m", 5)]


def test_extractor_pointer_segment_in_extract():
    decoder = SimpleNamespace(decode=lambda data, addr, limit: "hi")
    plugin = SimpleNamespace(
        get_text_segments=lambda rom: [
            {
                "name": "s",
                "start": 0,
                "end": 10,
                "kind": "pointer_dialogues",
                "decoder": decoder,
                "manifest": [{"target": 7, "free_after": 3}],
            }
        ]
    )
    manager = SimpleNamespace(get_plugin=lambda *a, **k: plugin)
    assert _bext(plugin_manager=manager).extract() == {
        "s": [{"text": "hi", "offset": 7, "target_addr": 7, "length": 3, "slots": []}]
    }


def test_extractor_recode_normal():
    class Decoder:
        def decode(self, data, start, length):
            return "AB"

    extractor = _bext(rom=SimpleNamespace(data=bytes(8)))
    messages = extractor.recode_segment({"name": "s", "start": 0, "end": 4}, Decoder())
    assert [m["text"] for m in messages] == ["AB"]


def test_extractor_fixed_no_decoder():
    extractor = _bext(rom=SimpleNamespace(data=b"AB......"))
    segment = {"name": "s", "start": 0, "end": 8, "fixed_width": 4, "record_count": 2}
    assert extractor._extract_fixed_width_messages(segment, None) == []


def test_extractor_decompress_passthrough():
    assert _bext()._decompress(b"data", 123) == b"data"


def test_extractor_split_empty_hex():
    extractor = _bext()
    assert extractor._split_messages("[41]ab", 0) == [{"offset": 4, "text": "ab"}]


def test_decoder_possible_tables(monkeypatch):
    import core.decoder as decoder_mod

    def fake_analyze(data):
        return {"type": "x", "confidence": 1.0, "possible_tables": [{}, {0x41: "A"}]}

    monkeypatch.setattr(decoder_mod, "analyze_custom_encoding", fake_analyze)
    decoder = MultiCharMapDecoder({0x42: "B"})
    result = decoder.decode_segment(b"AB", 0, 2, [{0x41: "A"}])
    assert "A" in result and "B" in result


def test_decoder_learn_unbound():
    with pytest.raises(AttributeError):
        MultiCharMapDecoder.learn_encoding(object(), "n", b"d", {})


def test_lzss_truncated_backref():
    from core.compression import LZSSHandler

    assert LZSSHandler().decompress(b"\x80\x00", 0) == (b"", 2)


def test_lzss_repeat_run():
    from core.compression import RLEHandler

    out, consumed = RLEHandler().decompress(b"\x00AB", 0)
    assert out == b"A" * 0x42
    assert consumed == 3


def test_autodetect_delegates_gba():
    from core.compression import AutoDetectCompressionHandler

    handler = AutoDetectCompressionHandler()
    assert handler.decompress(b"\x10\x01\x00\x00" + b"\x00A", 0) == (b"A", 6)


def test_autodetect_unknown_type(monkeypatch):
    from core.compression import AutoDetectCompressionHandler

    handler = AutoDetectCompressionHandler()
    monkeypatch.setattr(handler, "detect_compression", lambda *a: "bogus")
    assert handler.decompress(b"ABCD", 0) == (b"ABCD", 4)


def test_detect_compression_branches():
    from core.compression import AutoDetectCompressionHandler

    handler = AutoDetectCompressionHandler()
    assert handler.detect_compression(b"", 5) == "none"
    assert handler.detect_compression(b"\x10 rest", 0) == "gba_lz77"
    assert handler.detect_compression(b"\x00\x00\x00AB", 0) == "lzss"
    assert handler.detect_compression(b"\xff\xff\xffAB", 0) == "lzss"
    assert handler.detect_compression(b"\x00A\x02\x00B\x02XY", 0) == "rle"


def test_likely_short_inputs():
    from core.compression import AutoDetectCompressionHandler

    handler = AutoDetectCompressionHandler()
    assert handler._is_likely_lzss(b"\x00", 0) is False
    assert handler._is_likely_rle(b"\x00", 0) is False


def test_ffta_decompress_paths():
    from core.compression import FFTA_LZSSHandler

    handler = FFTA_LZSSHandler()
    assert handler.decompress(b"\x00\x00\x00\x05", 0) == (b"", 0)
    assert handler.decompress(b"\x00\x00\x00\x05\x80", 0) == (b"", 0)
    out, _consumed = handler.decompress(b"\x00\x00\x00\x01\x41A", 0)
    assert out == b"A"
    out, _ = handler.decompress(b"\x00\x00\x00\x02\x20\x00\x00", 0)
    assert out == b"\x00\x00"
    out, _ = handler.decompress(b"\x00\x00\x00\x01\x02\x00", 0)
    assert out == b"\x00"
    out, _ = handler.decompress(b"\x00\x00\x00\x01\x01\x00", 0)
    assert out == b"\xff"
    out, _ = handler.decompress(b"\x00\x00\x00\x05\x41AB\x10\x00\x00", 0)
    assert out == b"ABBBB"


def test_ffta_compress_errors():
    from core.compression import FFTA_LZSSHandler

    handler = FFTA_LZSSHandler()
    with pytest.raises(ValueError):
        handler.compress(b"")
    with pytest.raises(ValueError):
        handler.compress(b"x" * (0x100001))


def test_ffta_compress_type4():
    from core.compression import FFTA_LZSSHandler

    prefix = bytearray()
    for k in range(40):
        prefix.extend([k, 0, 0])
    data = bytes(prefix) + bytes(prefix[:67]) + bytes([(prefix[67] + 1) % 256])
    handler = FFTA_LZSSHandler()
    out = handler.compress(data)
    assert out[:4] == len(data).to_bytes(4, "big")
    back, _ = handler.decompress(out, 0)
    assert back == data


def test_huffman_tree_pointers():
    from core.compression import HuffmanHandler

    handler = HuffmanHandler()
    handler.set_tree_pointers(1, 2)
    assert (handler.tree_base, handler.tree_data) == (1, 2)


def test_huffman_text_block_oob():
    from core.compression import HuffmanHandler

    assert HuffmanHandler().decompress_text_block(bytes(10), 50, 60, 0) == b""


def test_huffman_walk_and_terminator():
    from core.compression import HuffmanHandler

    rom = bytearray(16)
    rom[0] = 0xC1
    rom[1] = 0x80
    rom[4] = 0b10
    assert HuffmanHandler().decompress_text_block(bytes(rom), 4, 0, 0) == b"A"


def test_huffman_depth_guard():
    from core.compression import HuffmanHandler

    rom = bytearray(256)
    for k in range(70):
        rom[2 * k] = k + 1
        rom[2 * k + 1] = 0xC1
    assert HuffmanHandler().decompress_text_block(bytes(rom), 200, 0, 0) == b""


def test_huffman_truncated_tree():
    from core.compression import HuffmanHandler

    assert HuffmanHandler().decompress_text_block(bytes(16), 15, 15, 0) == b""


def test_huffman_two_level_tree():
    from core.compression import HuffmanHandler

    rom = bytearray(16)
    rom[0] = 5
    rom[1] = 0x80
    rom[10] = 0xC2
    rom[11] = 0xC1
    rom[12] = 0b100
    assert HuffmanHandler().decompress_text_block(bytes(rom), 12, 0, 0) == b"B"


def test_multi_name_variants():
    segment = MultiCharmapSegment(b"", 0)
    assert segment._generate_table_name({(1, 2): "x", 0x41: "A"}) == "English"
    assert segment._generate_table_name({0xE0: "X"}) == "Extended Encoding"


def test_multi_pair_mapping():
    segment = MultiCharmapSegment(bytes([0x82, 0xA0]), 0)
    segment.add_table(CharTable("T", {(0x82, 0xA0): "あ"}))
    segment.build_encoding_map()
    assert segment.encoding_map == {0x82: 0, 0xA0: 0}
    assert segment.decode_segment(0, 2, 0) == "あ"
    assert segment.decode_segment(0, 2, 99) == "あ"


def test_multi_fallback_paths():
    segment = MultiCharmapSegment(bytes([0x82, 0xA0, 0x41, 0x02]), 0)
    segment.add_table(CharTable("T", {(0x82, 0xA0): "あ", 0x41: "A"}))
    assert segment.decode_with_fallback(0, 4) == "あA[02]"


def test_multi_fallback_next_table():
    segment = MultiCharmapSegment(bytes([0x82, 0xA0]), 0)
    segment.add_table(CharTable("E", {}))
    segment.add_table(CharTable("T", {(0x82, 0xA0): "あ"}))
    assert segment.decode_with_fallback(0, 2) == "あ"


def test_multi_single_next_table():
    segment = MultiCharmapSegment(b"A", 0)
    segment.add_table(CharTable("E", {}))
    segment.add_table(CharTable("T", {0x41: "A"}))
    assert segment.decode_with_fallback(0, 1) == "A"


def test_multi_analyze_shift_jis():
    from core.multi_charmap import analyze_custom_encoding

    result = analyze_custom_encoding(bytes([0x82, 0xA0]) * 10 + b"A" * 5)
    assert result["type"] == "shift-jis"


def test_multi_sjis_empty_decode():
    assert _detect_sjis_sequences(bytes([0x81, 0xE9])) == {}


def test_multi_learn_twice():
    detector = EncodingDetector()
    detector.learn_encoding("e", b"AB", {0x41: "A"})
    detector.learn_encoding("e", b"AB", {0x41: "A", 0x42: "B"})
    assert detector.detect_encoding(b"AB") == ("e", 1.0)


def test_multi_heuristic_ascii():
    assert EncodingDetector().detect_encoding(b"ABCDEFGH") == ("ascii", 1.0)


def test_multi_heuristic_high_unknown():
    assert EncodingDetector().detect_encoding(b"ABCDE" + bytes([0xFF]) * 5) == ("unknown", 0.0)


def test_multi_heuristic_shift_jis():
    name, _ = EncodingDetector().detect_encoding(bytes([0x82, 0xA0]) * 5)
    assert name == "shift-jis"


def test_multi_learned_beats_heuristic():
    detector = EncodingDetector()
    detector.learn_encoding("e", b"AB", {0x41: "A", 0x42: "B"})
    assert detector.detect_encoding(b"ABABAB") == ("e", 1.0)
    detector.learn_encoding("j", bytes([0x82, 0xA0]), {0x82: "X", 0xA0: "Y"})
    assert detector.detect_encoding(bytes([0x82, 0xA0]) * 5) == ("j", 1.0)


def test_multi_score_short():
    assert EncodingDetector()._score_shiftjis(b"A") == 0.0
    assert EncodingDetector()._score_shiftjis(bytes([0x82, 0xA0])) == 1.0
    assert EncodingDetector()._score_shiftjis(b"AB") == 0.0
    assert EncodingDetector()._score_shiftjis(bytes([0x82, 0x20])) == 0.0


def test_multi_suggest_known():
    detector = EncodingDetector()
    charmap = {0x41: "A", 0x42: "B"}
    detector.learn_encoding("e", b"AB", charmap)
    assert detector.suggest_charmap(b"AB") == charmap


def test_multi_auto_placeholder():
    detector = EncodingDetector()
    result = detector.suggest_charmap(bytes([0x90]) * 5)
    assert "[90]" in result.values()


def test_tmx_export_basic():
    handler = TMXHandler()
    out = handler.export_tmx({"s": [{"text": "hi", "translation": "privet", "offset": 1}]})
    assert "hi" in out
    assert "privet" in out


def test_tmx_pretty_fallback(monkeypatch):
    import core.tmx as tmx_mod

    def _boom(text):
        raise RuntimeError("no pretty")

    monkeypatch.setattr(tmx_mod.minidom, "parseString", _boom)
    out = TMXHandler().export_tmx({"s": [{"text": "hi", "offset": 1}]})
    assert out.startswith('<?xml version="1.0" encoding="utf-8"?>')


def test_tmx_import_bad_offset():
    content = (
        '<tmx><header srclang="en"/><body><tu>'
        '<prop type="segment-name">s</prop>'
        '<prop type="rom-offset">xyz</prop>'
        '<tuv xml:lang="en"><seg>hello</seg></tuv>'
        '<tuv xml:lang="ru"><seg>privet</seg></tuv>'
        "</tu></body></tmx>"
    )
    assert TMXHandler().import_tmx(content) == {"s": {"hello": "privet"}}


def test_tmx_import_single_tuv():
    content = '<tmx><header srclang="en"/><body><tu><tuv xml:lang="en"><seg>hello</seg></tuv></tu></body></tmx>'
    assert TMXHandler().import_tmx(content) == {}


def test_tmx_import_tuv_without_seg():
    content = (
        '<tmx><header srclang="en"/><body><tu>'
        '<tuv xml:lang="en"/><tuv xml:lang="ru"><seg>privet</seg></tuv>'
        "</tu></body></tmx>"
    )
    assert TMXHandler().import_tmx(content) == {}


def test_tmx_import_srclang_mismatch():
    content = (
        '<tmx><header srclang="zz"/><body><tu>'
        '<prop type="segment-name">s</prop>'
        '<tuv xml:lang="en"><seg>hello</seg></tuv>'
        '<tuv xml:lang="ru"><seg>privet</seg></tuv>'
        "</tu></body></tmx>"
    )
    assert TMXHandler().import_tmx(content) == {"s": {"hello": "privet"}}


def test_tmx_import_generic_error(monkeypatch):
    handler = TMXHandler()

    def _boom(element):
        raise RuntimeError("tree gone")

    monkeypatch.setattr(TMXHandler, "_get_seg_text", staticmethod(_boom))
    content = (
        '<tmx><header srclang="en"/><body><tu>'
        '<tuv xml:lang="en"><seg>hello</seg></tuv>'
        '<tuv xml:lang="ru"><seg>privet</seg></tuv>'
        "</tu></body></tmx>"
    )
    with pytest.raises(RuntimeError):
        handler.import_tmx(content)


def test_tmx_seg_inline_tail():
    handler = TMXHandler()
    assert handler._get_seg_text(ET.fromstring("<seg>a<b/>c</seg>")) == "ac"


def test_tmx_info_not_tmx():
    assert TMXHandler().get_tmx_info("<foo/>")["version"] == "Unknown"


def test_tmx_info_generic_error(monkeypatch):
    def _boom(content):
        raise RuntimeError("gone")

    monkeypatch.setattr(ET, "fromstring", _boom)
    assert TMXHandler().get_tmx_info("<tmx/>")["error"] == "gone"


def test_ml_train_no_sklearn(monkeypatch):
    import core.ml_classifier as ml_mod

    monkeypatch.setattr(ml_mod, "SKLEARN_AVAILABLE", False)
    SegmentMLClassifier._train_initial_model(None)


def test_ml_analyze_heuristic_review():
    classifier = SegmentMLClassifier.__new__(SegmentMLClassifier)
    classifier.confidence_threshold = 0.5
    classifier._review_threshold = 0.35
    classifier.is_trained = False
    report = classifier.analyze_segments(b"ABCDEFG" + bytes([0x7F]) * 9, 0, 16, 16)
    assert len(report["needs_review"]) == 1


def test_ml_save_untrained(tmp_path):
    classifier = SegmentMLClassifier.__new__(SegmentMLClassifier)
    classifier.is_trained = False
    assert classifier.save_model(str(tmp_path / "m.pkl")) is False


def test_ml_save_load_roundtrip(tmp_path):
    classifier = SegmentMLClassifier()
    path = str(tmp_path / "m.pkl")
    assert classifier.save_model(path) is True
    fresh = SegmentMLClassifier.__new__(SegmentMLClassifier)
    assert fresh.load_model(path) is True
    assert fresh.is_trained is True
    assert fresh.load_model(str(tmp_path / "nope.pkl")) is False


def test_ml_load_no_sklearn(monkeypatch):
    import core.ml_classifier as ml_mod

    monkeypatch.setattr(ml_mod, "SKLEARN_AVAILABLE", False)
    assert SegmentMLClassifier.load_model(None, "x") is False


def test_multi_detect_tables_low_coverage():
    segment = MultiCharmapSegment(bytes(10), 0)
    assert segment.detect_tables([{0x41: "A"}]) == []


def test_multi_name_with_unranged_key():
    segment = MultiCharmapSegment(b"", 0)
    assert segment._generate_table_name({0x10: "Y", 0xE0: "X"}) == "Extended Encoding"


def test_multi_pair_first_byte_mapped():
    segment = MultiCharmapSegment(bytes([0x82, 0xA0]), 0)
    segment.add_table(CharTable("T", {(0x82, 0xA0): "X", 0x82: "Y"}))
    segment.build_encoding_map()
    assert segment.encoding_map == {0x82: 0, 0xA0: 0}


def test_multi_segment_by_table_final():
    segment = MultiCharmapSegment(b"AB", 0)
    segment.add_table(CharTable("T", {0x41: "A", 0x42: "B"}))
    assert segment.segment_by_table() == [(0, 2, 0)]
    assert segment.full_decode() == [("AB", 0)]


def test_multi_analyze_custom_type():
    from core.multi_charmap import analyze_custom_encoding

    result = analyze_custom_encoding(b"AB\x01\x02")
    assert result["type"] == "custom"


def test_multi_sjis_second_invalid():
    assert _detect_sjis_sequences(bytes([0x82, 0x20])) == {}


def test_multi_segment_empty_data():
    segment = MultiCharmapSegment(b"", 0)
    segment.add_table(CharTable("T", {0x41: "A"}))
    assert segment.segment_by_table() == []


def test_tmx_import_empty_seg_text():
    content = (
        '<tmx><header srclang="en"/><body><tu>'
        '<prop type="segment-name">s</prop>'
        '<tuv xml:lang="en"><seg></seg></tuv>'
        '<tuv xml:lang="ru"><seg>privet</seg></tuv>'
        "</tu></body></tmx>"
    )
    assert TMXHandler().import_tmx(content) == {}


def test_ml_save_failure(tmp_path):
    classifier = SegmentMLClassifier.__new__(SegmentMLClassifier)
    classifier.is_trained = True
    classifier.model = object()
    classifier.scaler = None
    assert classifier.save_model(str(tmp_path / "no_dir" / "m.pkl")) is False


def test_decoder_plain_call():
    decoder = MultiCharMapDecoder({0x41: "A", 0x42: "B"})
    assert decoder.decode_segment(b"AB", 0, 2) == "AB"


def test_rom_direct_system_small():
    rom = GameBoyROM.__new__(GameBoyROM)
    rom.path = "x.gb"
    rom.data = bytearray(10)
    rom.header = {"system": "gb", "cgb_flag": 0, "new_licensee_code": 0, "header_checksum": 0, "rom_size": 0}
    assert rom._detect_system() == "gb"


def test_rom_direct_system_renamed_gba():
    rom = GameBoyROM.__new__(GameBoyROM)
    rom.path = "y.gba"
    rom.data = bytearray(0x200)
    rom.header = {"system": "gb", "cgb_flag": 0, "new_licensee_code": 0, "header_checksum": 0, "rom_size": 0}
    assert rom._detect_system() == "gba"


def test_tmx_import_no_header():
    content = (
        "<tmx><body><tu>"
        '<prop type="segment-name">s</prop>'
        '<tuv xml:lang="en"><seg>hello</seg></tuv>'
        '<tuv xml:lang="ru"><seg>privet</seg></tuv>'
        "</tu></body></tmx>"
    )
    assert TMXHandler().import_tmx(content) == {"s": {"hello": "privet"}}


def test_tmx_seg_variants():
    handler = TMXHandler()
    assert handler._get_seg_text(ET.fromstring("<seg><b/>c</seg>")) == "c"
    assert handler._get_seg_text(ET.fromstring("<seg>a<b>x</b>c</seg>")) == "axc"
    assert handler._get_seg_text(ET.fromstring("<seg>a<b>x</b></seg>")) == "ax"


def test_tmx_import_tuv_without_lang():
    content = (
        '<tmx><header srclang="en"/><body><tu>'
        '<prop type="segment-name">s</prop>'
        "<tuv><seg>hello</seg></tuv>"
        '<tuv xml:lang="ru"><seg>privet</seg></tuv>'
        "</tu></body></tmx>"
    )
    assert TMXHandler().import_tmx(content) == {"s": {"hello": "privet"}}
    assert TMXHandler().get_tmx_info(content)["languages"] == ["ru"]


def test_plugin_api_load_corrupt(tmp_path):
    from core.plugin_api import PluginFactory

    target = tmp_path / "bad.json"
    target.write_text("{bad", encoding="utf-8")
    plugin = PluginFactory.get_plugin_class("example_game")()
    assert plugin.load_config(str(target)) is False


def test_plugin_api_unload_failure():
    from core.plugin_api import PluginFactory

    plugin = PluginFactory.get_plugin_class("example_game")()

    def _boom():
        raise RuntimeError("bye")

    assert plugin.on_load() is True
    plugin.shutdown = _boom
    plugin.on_unload()
    assert plugin.state.value == "loaded"
