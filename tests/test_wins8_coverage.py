import base64
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core import dialogue_manifest, secret_store
from core.dialogue_manifest import _valid_entry, entries_for_rom, manifest_path
from plugins.gba_ff5_advance import FF5AdvancePlugin
from plugins.gba_metroid_fusion import MetroidFusionPlugin
from plugins.gba_wario_land_4 import WarioLand4Plugin


def test_secret_dpapi_roundtrip(tmp_path, monkeypatch):
    """Настоящий DPAPI. Если служба недоступна — пропуск, а не падение.

    Тест лезет в живой `CryptProtectData`: тот глотает OSError и возвращает
    False, поэтому под нагрузкой (параллельный прогон всей матрицы) тест
    мигал. Криптослужба ОС — внешняя зависимость, а не логика проекта.
    """
    monkeypatch.setattr(secret_store.sys, "platform", "win32")
    monkeypatch.setattr(secret_store, "_backend", None)
    backend = secret_store.create_backend(path=tmp_path / "s.dat")
    try:
        stored = backend.store("k", "v")
    except (OSError, AttributeError) as exc:  # pragma: no cover - зависит от ОС
        pytest.skip(f"DPAPI недоступен: {exc}")
    if not stored:  # pragma: no cover - зависит от ОС
        pytest.skip("DPAPI вернул False: служба ключей Windows недоступна")
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


class _FakeBackend:
    """Хранилище в памяти: проверяем обвязку store/load/delete без ОС."""

    def __init__(self) -> None:
        self.data: dict = {}

    def store(self, name, value):
        self.data[name] = value
        return True

    def load(self, name):
        return self.data.get(name)

    def delete(self, name):
        return self.data.pop(name, None) is not None


def test_dpapi_backend_success_path_is_deterministic(monkeypatch, tmp_path):
    """Успешный путь файлового бэкенда без живой криптографии ОС.

    `_DpapiBackend.store/load/delete` глотает OSError и возвращает False,
    поэтому на реальном DPAPI успешный путь проверяется только при работающей
    службе ключей. Здесь она подменена обратимой «шифровкой», так что
    проверяется вся наша логика: атомарная запись, формат файла, чтение,
    удаление — детерминированно на любой машине.
    """
    monkeypatch.setattr(secret_store.sys, "platform", "win32")
    def fake_protect(data: bytes) -> bytes:
        return b"enc:" + bytes(data)

    def fake_unprotect(blob: bytes) -> bytes:
        # Настоящий CryptUnprotectData на мусоре бросает OSError, и
        # _DpapiBackend.load превращает его в None — повторяем это поведение.
        if not bytes(blob).startswith(b"enc:"):
            raise OSError("bad blob")
        return bytes(blob)[4:]

    monkeypatch.setattr(secret_store, "_dpapi_protect", fake_protect)
    monkeypatch.setattr(secret_store, "_dpapi_unprotect", fake_unprotect)
    p = tmp_path / "s.dat"
    backend = secret_store._DpapiBackend(path=p)
    assert backend.store("k", "v") is True
    assert p.exists()
    # в файл уходит base64 от «шифротекста», а не открытый текст
    blob = json.loads(p.read_text(encoding="utf-8"))["secrets"]["k"]
    assert base64.b64decode(blob) == b"enc:v"
    assert "v" not in json.loads(p.read_text(encoding="utf-8"))["secrets"]["k"]
    assert backend.load("k") == "v"
    assert backend.load("нет-такого") is None
    assert backend.delete("k") is True
    assert backend.load("k") is None
    # нерасшифровываемый BLOB — не исключение, а None
    p.write_text(json.dumps({"secrets": {
        "k": base64.b64encode(b"enxx:v").decode()}}), encoding="utf-8")
    # тот же случай на живом DPAPI ловится как OSError -> None
    assert backend.load("k") is None


def test_secret_store_helpers(monkeypatch):
    """Обвязка секретов на подставном хранилище — без DPAPI.

    Прежде здесь стоял настоящий `_DpapiBackend`, и при параллельном прогоне
    тест падал: `CryptProtectData` под нагрузкой возвращает False, а
    `_DpapiBackend.store` превращает это в «не сохранилось». Логика
    `store_secret`/`load_secret` от криптослужбы ОС не зависит.
    """
    monkeypatch.setattr(secret_store, "_backend", _FakeBackend())
    assert secret_store.store_secret("k", "v") is True
    assert secret_store.load_secret("k") == "v"
    # Пустое значение удаляет секрет, а не пишет пустую строку.
    assert secret_store.store_secret("k", "") is True
    assert secret_store.load_secret("k") is None


def test_secret_file_backend_rejects_broken_payloads(monkeypatch, tmp_path):
    """Битый JSON и нерасшифровываемый BLOB дают None, а не исключение.

    Обе ветки не требуют успешной криптографии: первая падает на разборе
    файла, вторая — на заведомо негодном BLOB. Поэтому тест детерминирован.
    """
    monkeypatch.setattr(secret_store.sys, "platform", "win32")
    p = tmp_path / "s.dat"
    monkeypatch.setattr(secret_store, "_backend",
                        secret_store._DpapiBackend(path=p))
    p.write_text("bad json", encoding="utf-8")
    assert secret_store.load_secret("k") is None
    p.write_text(json.dumps(
        {"secrets": {"k": base64.b64encode(b"badblob").decode()}}),
        encoding="utf-8")
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


@pytest.mark.skipif(not sys.platform.startswith("win"),
                reason="DPAPI доступен только на Windows: ctypes.windll отсутствует на Linux/macOS")
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
