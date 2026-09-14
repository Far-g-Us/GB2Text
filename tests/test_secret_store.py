"""Тесты core.secret_store: фейковый backend, delete-семантика, миграция ключей."""

import json
from pathlib import Path

import pytest

from core import secret_store
from core.secret_store import _DpapiBackend, _NullBackend, create_backend


class FakeBackend:
    """In-memory backend: считает вызовы, хранит пары имя->значение."""

    def __init__(self):
        self.data = {}
        self.store_calls = 0
        self.delete_calls = 0

    def store(self, name, value) -> bool:
        self.store_calls += 1
        self.data[name] = value
        return True

    def load(self, name):
        return self.data.get(name)

    def delete(self, name) -> bool:
        self.delete_calls += 1
        self.data.pop(name, None)
        return True


class FailingBackend(FakeBackend):
    def store(self, name, value) -> bool:
        self.store_calls += 1
        return False


@pytest.fixture
def fake_store(monkeypatch):
    backend = FakeBackend()
    monkeypatch.setattr(secret_store, "_backend", backend)
    return backend


def test_store_and_load(fake_store):
    assert secret_store.store_secret("deepl_key", "SECRET") is True
    assert secret_store.load_secret("deepl_key") == "SECRET"


def test_delete_removes_value(fake_store):
    secret_store.store_secret("key", "value")
    assert secret_store.delete_secret("key") is True
    assert secret_store.load_secret("key") is None


def test_store_empty_deletes(fake_store):
    secret_store.store_secret("key", "value")
    assert secret_store.store_secret("key", "") is True
    assert secret_store.load_secret("key") is None
    assert fake_store.delete_calls == 1


def test_load_missing_returns_none(fake_store):
    assert secret_store.load_secret("nope") is None


def test_store_failure_reported(monkeypatch):
    monkeypatch.setattr(secret_store, "_backend", FailingBackend())
    assert secret_store.store_secret("key", "value") is False


def test_null_backend_never_persists():
    backend = _NullBackend()
    assert backend.store("key", "value") is False
    assert backend.load("key") is None
    assert backend.delete("key") is False


def test_dpapi_backend_roundtrip(tmp_path, monkeypatch):
    """DPAPI-бэкенд без реальной DPAPI: подмена protect/unprotect тождеством."""
    store = _DpapiBackend(tmp_path / "secrets.dat")
    monkeypatch.setattr(secret_store, "_dpapi_protect", lambda b: b)
    monkeypatch.setattr(secret_store, "_dpapi_unprotect", lambda b: b)

    assert store.store("deepl_key", "VALUE") is True
    assert store.load("deepl_key") == "VALUE"
    assert store.delete("deepl_key") is True
    assert store.load("deepl_key") is None


def test_dpapi_file_format_uses_b64(monkeypatch, tmp_path):
    store = _DpapiBackend(tmp_path / "secrets.dat")
    monkeypatch.setattr(secret_store, "_dpapi_protect", lambda b: b)
    store.store("deepl_key", "VALUE")
    raw = json.loads((tmp_path / "secrets.dat").read_text(encoding="utf-8"))
    assert "VALUE" not in raw["secrets"]["deepl_key"]
    assert "VALUE" in _b64decode(raw["secrets"]["deepl_key"])


def _b64decode(encoded: str) -> str:
    import base64

    return base64.b64decode(encoded).decode("utf-8")


def test_dpapi_atomic_no_tmp_leftovers(tmp_path, monkeypatch):
    store = _DpapiBackend(tmp_path / "secrets.dat")
    monkeypatch.setattr(secret_store, "_dpapi_protect", lambda b: b)
    store.store("k", "v")
    store.store("k2", "v2")
    assert not (tmp_path / "secrets.dat.tmp").exists()
    assert list(tmp_path.iterdir()) == [tmp_path / "secrets.dat"]


def test_dpapi_corrupt_entry_returns_none(monkeypatch, tmp_path, caplog):
    store = _DpapiBackend(tmp_path / "secrets.dat")
    store._write({"version": 1, "secrets": {"bad": "!!!not-b64!!!"}})
    monkeypatch.setattr(
        secret_store, "_dpapi_unprotect", lambda b: (_ for _ in ()).throw(OSError())
    )
    assert store.load("bad") is None
    assert "не удалось" in caplog.text.lower()


def test_create_backend_windows_is_dpapi(monkeypatch):
    monkeypatch.setattr(secret_store.sys, "platform", "win32")
    backend = create_backend(Path("x") / "s.dat")
    assert isinstance(backend, _DpapiBackend)
    assert backend.path == Path("x") / "s.dat"
