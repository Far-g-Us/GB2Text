import base64
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from core import dialogue_manifest, secret_store
from core.dialogue_manifest import _valid_entry, entries_for_rom, manifest_path
from plugins.gba_ff5_advance import FF5AdvancePlugin
from plugins.gba_metroid_fusion import MetroidFusionPlugin
from plugins.gba_wario_land_4 import WarioLand4Plugin


def test_secret_dpapi_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(secret_store.sys, "platform", "win32")
    monkeypatch.setattr(secret_store, "_backend", None)
    backend = secret_store.create_backend(path=tmp_path / "s.dat")
    assert backend.store("k", "v") is True
    assert backend.load("k") == "v"
    assert backend.delete("k") is True
    assert backend.load("k") is None


def test_secret_null_backend(monkeypatch):
    monkeypatch.setattr(secret_store.sys, "platform", "linux")
    monkeypatch.setitem(
        __import__("sys").modules, "keyring", MagicMock(get_keyring=MagicMock(side_effect=Exception("no")))
    )
    backend = secret_store.create_backend()
    assert backend.store("k", "v") is False
    assert backend.load("k") is None
    assert backend.delete("k") is False


def test_secret_store_helpers(monkeypatch, tmp_path):
    monkeypatch.setattr(secret_store, "_backend", None)
    monkeypatch.setattr(secret_store.sys, "platform", "win32")
    p = tmp_path / "s.dat"
    monkeypatch.setattr(secret_store, "DEFAULT_PATH", p)
    assert secret_store.store_secret("k", "v") is True
    assert secret_store.load_secret("k") == "v"
    assert secret_store.store_secret("k", "") is True
    assert secret_store.load_secret("k") is None
    monkeypatch.setattr(secret_store, "_backend", secret_store._DpapiBackend(path=p))
    p.write_text("bad json", encoding="utf-8")
    assert secret_store.load_secret("k") is None
    p.write_text(json.dumps({"secrets": {"k": base64.b64encode(b"badblob").decode()}}), encoding="utf-8")
    assert secret_store.load_secret("k") is None


def test_manifest_valid_entry():
    assert _valid_entry({"target": 10, "free_after": 5, "slots": []}, 20) is True
    assert _valid_entry({"target": "x", "free_after": 5, "slots": []}, 20) is False
    assert _valid_entry({"target": 10, "free_after": 1, "slots": []}, 20) is False
    assert _valid_entry({"target": 10, "free_after": 5, "slots": "x"}, 20) is False
    assert _valid_entry({"target": 10, "free_after": 5, "slots": [1, "x"]}, 20) is False
    assert manifest_path("NOPE") is None
    assert dialogue_manifest._entries_from_file("NOPE") is None
    assert dialogue_manifest.manifest_path("BPEE") is not None


def test_manifest_entries_for_rom(tmp_path, monkeypatch):
    import zlib

    monkeypatch.setattr(dialogue_manifest, "_MANIFESTS_DIR", str(tmp_path))
    rom = SimpleNamespace(header={"game_code": "BPEE"}, data=bytes(20))
    guard = zlib.crc32(rom.data[:0x100])
    (tmp_path / "BPEE.json").write_text(
        json.dumps({"entries": [{"target": 10, "free_after": 5, "slots": []}], "guard": guard}), encoding="utf-8"
    )
    dialogue_manifest._cache.clear()
    assert entries_for_rom(rom) is not None
    dialogue_manifest._cache.clear()
    assert entries_for_rom(rom) is not None
    (tmp_path / "BPEE.json").write_text(
        json.dumps({"entries": [{"target": 10, "free_after": 5, "slots": []}], "guard": 0xDEADBEEF}), encoding="utf-8"
    )
    dialogue_manifest._cache.clear()
    assert entries_for_rom(rom) is None
    (tmp_path / "BPEE.json").write_text("bad json", encoding="utf-8")
    dialogue_manifest._cache.clear()
    assert entries_for_rom(rom) is None
    (tmp_path / "BPEE.json").write_text(json.dumps({"no_entries": []}), encoding="utf-8")
    dialogue_manifest._cache.clear()
    assert entries_for_rom(rom) is None


def test_gba_plugins_basic():
    for cls in (FF5AdvancePlugin, WarioLand4Plugin, MetroidFusionPlugin):
        plugin = cls()
        assert plugin.get_text_segments(SimpleNamespace(data=bytes(10))) == []
        assert plugin.get_terminators("s") is not None
        assert plugin.get_compression_handler("s") is None


def test_secret_dpapi_fail(monkeypatch, tmp_path):
    import ctypes

    monkeypatch.setattr(secret_store.sys, "platform", "win32")
    backend = secret_store._DpapiBackend(path=tmp_path / "s.dat")
    monkeypatch.setattr(ctypes.windll.crypt32, "CryptProtectData", lambda *a, **k: 0)
    assert backend.store("k", "v") is False
    monkeypatch.setattr(ctypes.windll.crypt32, "CryptUnprotectData", lambda *a, **k: 0)
    backend._write({"version": 1, "secrets": {"k": base64.b64encode(b"bad").decode()}})
    assert backend.load("k") is None


def test_manifest_guard_read_fail(tmp_path, monkeypatch):
    import zlib

    monkeypatch.setattr(dialogue_manifest, "_MANIFESTS_DIR", str(tmp_path))
    rom = SimpleNamespace(header={"game_code": "BPEE"}, data=bytes(20))
    guard = zlib.crc32(rom.data[:0x100])
    (tmp_path / "BPEE.json").write_text(
        json.dumps({"entries": [{"target": 10, "free_after": 5, "slots": []}], "guard": guard}), encoding="utf-8"
    )
    dialogue_manifest._cache.clear()
    assert entries_for_rom(rom) is not None
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
    dialogue_manifest._cache.clear()
    assert entries_for_rom(rom) is None
