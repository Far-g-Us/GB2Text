import sys
from pathlib import Path

from core.gba_support import GBALZ77Handler
from core.guide import GuideManager
from core.pointer_table import HEADER_BASE, patch_pointer_range
from plugins.gb_zelda_awakening import ZELDA_TERMINATORS, ZeldaAwakeningPlugin
from plugins.zelda_awakening_common import ZeldaTextDecoder


def test_lz77_not_lz77_passthrough():
    assert GBALZ77Handler().decompress(b"\x00\x01\x02", 0) == (b"\x00\x01\x02", 3)


def test_lz77_truncated_header():
    assert GBALZ77Handler().decompress(b"\x10\x05", 0) == (b"\x10\x05", 2)


def test_lz77_truncated_backref():
    assert GBALZ77Handler().decompress(bytes([0x10, 5, 0, 0, 0x80, 0x00]), 0) == (b"", 6)


def test_guide_frozen_base(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    manager = GuideManager(guides_dir=str(tmp_path))
    assert manager.guides_dir == tmp_path


def test_guide_frozen_base_is_executable_dir(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(Path, "mkdir", lambda self, *args, **kwargs: None)
    manager = GuideManager(guides_dir="frozen_guides_probe")
    assert manager.guides_dir == Path(sys.executable).parent / "frozen_guides_probe"


def test_patch_pointer_range_end():
    data = bytearray(16)
    patch_pointer_range(data, 0, 0, 1, [0x100, 0x200])
    assert data[0:4] == (0x100 + HEADER_BASE).to_bytes(4, "little")
    assert data[4:8] == b"\x00\x00\x00\x00"


def test_patch_pointer_range_bounds():
    data = bytearray(b"\xaa\xbb\xcc\xdd")
    patch_pointer_range(data, 2, 0, 5, [0x100])
    assert data == bytearray(b"\xaa\xbb\xcc\xdd")


def test_zelda_plugin_accessors():
    plugin = ZeldaAwakeningPlugin()
    assert plugin.get_terminators("seg") == ZELDA_TERMINATORS
    assert plugin.get_compression_handler("seg") is None


def test_zelda_encode_caret():
    assert ZeldaTextDecoder().encode("^") == b"\x5e"


def test_zelda_encode_unsupported_skipped():
    assert ZeldaTextDecoder().encode("é") == b""


def test_zelda_encode_bad_bracket():
    assert ZeldaTextDecoder().encode("[IC_12") == b"[IC_12"
