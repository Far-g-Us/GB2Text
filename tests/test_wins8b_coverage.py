import base64
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from core import secret_store
from core.dialogue_manifest import entries_for_rom
from plugins.gba_ff5_advance import FF5AdvancePlugin
from plugins.gba_metroid_fusion import MetroidFusionPlugin
from plugins.gba_wario_land_4 import WarioLand4Plugin


def test_secret_write_fail(tmp_path, monkeypatch):
    backend = secret_store._DpapiBackend(path=tmp_path / "s.dat")
    monkeypatch.setattr("tempfile.mkstemp", lambda **k: (_ for _ in ()).throw(OSError("no tmp")))
    assert backend._write({"a": 1}) is False


def test_secret_load_corrupt(tmp_path):
    p = tmp_path / "s.dat"
    p.write_text(json.dumps({"secrets": {"k": "not-base64!"}}), encoding="utf-8")
    backend = secret_store._DpapiBackend(path=p)
    assert backend.load("k") is None
    p.write_text(json.dumps({"version": 1, "secrets": {"k": base64.b64encode(b"bad").decode()}}), encoding="utf-8")
    assert backend.load("k") is None


def test_manifest_guard_mismatch(tmp_path, monkeypatch):
    import zlib

    from core import dialogue_manifest

    monkeypatch.setattr(dialogue_manifest, "_MANIFESTS_DIR", str(tmp_path))
    rom = SimpleNamespace(header={"game_code": "BPEE"}, data=bytes(20))
    guard = zlib.crc32(rom.data[:0x100])
    (tmp_path / "BPEE.json").write_text(
        json.dumps({"entries": [{"target": 10, "free_after": 5, "slots": []}], "guard": guard ^ 1}), encoding="utf-8"
    )
    dialogue_manifest._cache.clear()
    assert entries_for_rom(rom) is None


def test_gba_plugins_coverage():
    for cls in (FF5AdvancePlugin, WarioLand4Plugin, MetroidFusionPlugin):
        plugin = cls()
        rom = SimpleNamespace(data=bytes(0x100), header={"title": ""})
        assert plugin.get_text_segments(rom) == [] or isinstance(plugin.get_text_segments(rom), list)
    assert isinstance(FF5AdvancePlugin().get_text_segments(SimpleNamespace(data=bytes(0x100))), list)


def test_secret_keyring_paths(monkeypatch):
    import sys

    monkeypatch.setitem(
        sys.modules,
        "keyring",
        MagicMock(
            get_password=MagicMock(side_effect=Exception("no")),
            set_password=MagicMock(side_effect=Exception("no")),
            delete_password=MagicMock(side_effect=Exception("no")),
            errors=MagicMock(PasswordDeleteError=Exception),
            get_keyring=MagicMock(return_value=MagicMock()),
        ),
    )
    backend = secret_store._KeyringBackend()
    assert backend.store("k", "v") is False
    assert backend.load("k") is None
    assert isinstance(backend.delete("k"), bool)


def test_secret_read_non_dict(tmp_path):
    p = tmp_path / "s.dat"
    p.write_text(json.dumps({"secrets": []}), encoding="utf-8")
    backend = secret_store._DpapiBackend(path=p)
    assert backend.load("k") is None
