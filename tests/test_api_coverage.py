import http.client
import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any, cast

import pytest

from api import _core
from api.server import BODY_LIMIT_DETECT_EXTRACT, ApiHandler, ApiServer, serve


def _start_full(plugin_dir):
    server = ApiServer(("127.0.0.1", 0), plugin_dir=plugin_dir, max_workers=2)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


@pytest.fixture(scope="module")
def full_server(tmp_path_factory):
    plugin_dir = str(tmp_path_factory.mktemp("cov_plugs") / "no_plugins")
    server, port = _start_full(plugin_dir)
    yield server, port
    server.shutdown()
    server.server_close()


def _post(port, path, payload):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    body = json.dumps(payload).encode("utf-8")
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    response = conn.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    conn.close()
    return response.status, data


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    conn.request("GET", path)
    response = conn.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    conn.close()
    return response.status, data


def _raw_request(port, head, body, shutdown_write=False):
    sock = socket.create_connection(("127.0.0.1", port), timeout=30)
    sock.sendall(head + body)
    if shutdown_write:
        sock.shutdown(socket.SHUT_WR)
    response = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        response += chunk
    sock.close()
    header, _, raw_body = response.partition(b"\r\n\r\n")
    return int(header.split(b" ")[1]), json.loads(raw_body.decode("utf-8"))


class _StubConn:
    def settimeout(self, timeout):
        pass


class _RaisingRfile:
    def __init__(self, exc):
        self.exc = exc

    def read(self, n=-1):
        raise self.exc


class _FixedRfile:
    def __init__(self, payload):
        self.payload = payload

    def read(self, n=-1):
        return self.payload


def _stub_handler(monkeypatch, headers, rfile, path="/detect"):
    handler = ApiHandler.__new__(ApiHandler)
    handler.headers = cast(Any, dict(headers))
    handler.path = path
    handler.connection = _StubConn()
    handler.rfile = rfile
    calls = []
    monkeypatch.setattr(ApiHandler, "_reply", lambda self, payload, status=200: calls.append((status, payload)))
    return handler, calls


def test_resolve_rom_symlink_first(monkeypatch, tmp_path):
    target = tmp_path / "r.gb"
    target.write_bytes(b"x")
    monkeypatch.setattr(Path, "is_symlink", lambda self: True)
    with pytest.raises(_core.SDKError) as exc:
        _core.resolve_rom(str(target))
    assert exc.value.code == "IO_ERROR"


def test_resolve_rom_symlink_resolved(monkeypatch, tmp_path):
    target = tmp_path / "r.gb"
    target.write_bytes(b"x")
    values = [False, True]
    monkeypatch.setattr(Path, "is_symlink", lambda self: values.pop(0))
    with pytest.raises(_core.SDKError) as exc:
        _core.resolve_rom(str(target))
    assert exc.value.code == "IO_ERROR"


def test_resolve_rom_not_a_file(monkeypatch, tmp_path):
    monkeypatch.setattr(_core, "validate_rom_file", lambda path: None)
    with pytest.raises(_core.SDKError) as exc:
        _core.resolve_rom(str(tmp_path))
    assert exc.value.code == "IO_ERROR"


def test_resolve_output_bad_type(api_rom_file):
    with pytest.raises(_core.SDKError) as exc:
        _core.resolve_output(api_rom_file, 123)
    assert exc.value.code == "VALIDATION_ERROR"


def test_resolve_output_symlink(monkeypatch, api_rom_file):
    monkeypatch.setattr(Path, "is_symlink", lambda self: True)
    with pytest.raises(_core.SDKError) as exc:
        _core.resolve_output(api_rom_file, "out.gb")
    assert exc.value.code == "IO_ERROR"


def test_resolve_output_resolved_symlink(monkeypatch, api_rom_file):
    values = [False, True]
    monkeypatch.setattr(Path, "is_symlink", lambda self: values.pop(0))
    with pytest.raises(_core.SDKError) as exc:
        _core.resolve_output(api_rom_file, "out.gb")
    assert exc.value.code == "IO_ERROR"


def test_build_manager_failure(monkeypatch, tmp_path):
    def _boom(*args, **kwargs):
        raise RuntimeError("no manager")

    monkeypatch.setattr(_core, "get_safe_plugin_manager", _boom)
    with pytest.raises(_core.SDKError) as exc:
        _core.list_plugins(str(tmp_path))
    assert exc.value.code == "INTERNAL"


def test_detect_rom_load_error(monkeypatch, api_rom_file):
    def _boom(*args, **kwargs):
        raise RuntimeError("bad rom")

    monkeypatch.setattr(_core, "GameBoyROM", _boom)
    with pytest.raises(_core.SDKError) as exc:
        _core.detect(api_rom_file)
    assert exc.value.code == "ROM_ERROR"


class _RaisingPluginManager:
    def get_plugin(self, *args, **kwargs):
        raise RuntimeError("lookup failed")


def test_detect_plugin_lookup_error(monkeypatch, api_rom_file):
    monkeypatch.setattr(_core, "get_safe_plugin_manager", lambda *a, **k: _RaisingPluginManager())
    report = _core.detect(api_rom_file)
    assert report["plugin"] is None


class _BrokenPlugin:
    @staticmethod
    def get_text_segments(rom):
        raise RuntimeError("no segments")


class _BrokenExtractor:
    rom = object()
    plugin = _BrokenPlugin()


def test_decoder_names_fallback():
    assert _core._decoder_names(_BrokenExtractor(), {"a": [{"text": "x"}]}) == {"a": None}
    assert _core._decoder_names(_BrokenExtractor(), {}) == {}


def test_extract_sdk_reraise(monkeypatch, api_rom_file):
    class _Boom:
        def __init__(self, *args, **kwargs):
            raise _core.SDKError(_core.C_IO_ERROR, "stop")

    monkeypatch.setattr("core.extractor.TextExtractor", _Boom)
    with pytest.raises(_core.SDKError):
        _core.extract(api_rom_file)


def test_extract_generic_error(monkeypatch, api_rom_file):
    class _Boom:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("extract failed")

    monkeypatch.setattr("core.extractor.TextExtractor", _Boom)
    with pytest.raises(_core.SDKError) as exc:
        _core.extract(api_rom_file)
    assert exc.value.code == "ROM_ERROR"


class _RichPlugin:
    @staticmethod
    def get_text_segments(rom):
        return [{"name": "seg", "decoder": None}]


class _RichExtractor:
    def __init__(self, *args, **kwargs):
        self.rom = object()
        self.plugin = _RichPlugin()

    def extract(self):
        return {"seg": [{"text": "x", "offset": 1, "target_addr": 5, "length": 3, "slots": 2}]}


def test_extract_optional_keys(monkeypatch, api_rom_file):
    monkeypatch.setattr("core.extractor.TextExtractor", _RichExtractor)
    report = _core.extract(api_rom_file)
    entry = report["segments"]["seg"][0]
    assert entry["target_addr"] == 5
    assert entry["length"] == 3
    assert entry["slots"] == 2


def test_translate_items_branches():
    with pytest.raises(_core.SDKError):
        _core._translate_items("nope")
    assert _core._translate_items(["a", {"translation": "b"}]) == ["a", "b"]
    with pytest.raises(_core.SDKError):
        _core._translate_items([{"text": "x"}])


class _NonePluginManager:
    def get_plugin(self, *args, **kwargs):
        return None


def test_inject_plugin_not_found(monkeypatch, api_rom_file):
    monkeypatch.setattr(_core, "get_safe_plugin_manager", lambda *a, **k: _NonePluginManager())
    with pytest.raises(_core.SDKError) as exc:
        _core.inject(api_rom_file, {"seg": ["x"]})
    assert exc.value.code == "PLUGIN_NOT_FOUND"


def test_inject_sdk_reraise(monkeypatch, api_rom_file):
    class _Boom:
        def __init__(self, *args, **kwargs):
            raise _core.SDKError(_core.C_IO_ERROR, "stop")

    monkeypatch.setattr(_core, "TextInjector", _Boom)
    with pytest.raises(_core.SDKError):
        _core.inject(api_rom_file, {"seg": ["x"]})


def test_inject_generic_error(monkeypatch, api_rom_file):
    class _Boom:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("inject failed")

    monkeypatch.setattr(_core, "TextInjector", _Boom)
    with pytest.raises(_core.SDKError) as exc:
        _core.inject(api_rom_file, {"seg": ["x"]})
    assert exc.value.code == "ROM_ERROR"


class _FakeRom:
    def get_game_id(self):
        return "TEST"

    @property
    def system(self):
        return "gb"


class _FakeManager:
    def get_plugin(self, *args, **kwargs):
        return object()


class _FailingSaveInjector:
    def __init__(self, *args, **kwargs):
        self.rom = _FakeRom()

    def inject_segment(self, *args, **kwargs):
        return True

    def save(self, path):
        raise RuntimeError("disk gone")


def test_inject_tmp_cleanup(monkeypatch, tmp_path, api_rom_bytes):
    rom = tmp_path / "cl.gb"
    rom.write_bytes(api_rom_bytes)
    monkeypatch.setattr(_core, "TextInjector", _FailingSaveInjector)
    monkeypatch.setattr(_core, "get_safe_plugin_manager", lambda *a, **k: _FakeManager())
    with pytest.raises(_core.SDKError) as exc:
        _core.inject(str(rom), {"seg": ["x"]})
    assert exc.value.code == "ROM_ERROR"
    assert list(tmp_path.glob("*_translated*.tmp")) == []


def test_inject_tmp_cleanup_oserror(monkeypatch, tmp_path, api_rom_bytes):
    real_remove = os.remove
    rom = tmp_path / "co.gb"
    rom.write_bytes(api_rom_bytes)
    monkeypatch.setattr(_core, "TextInjector", _FailingSaveInjector)
    monkeypatch.setattr(_core, "get_safe_plugin_manager", lambda *a, **k: _FakeManager())

    def _boom(path, *args, **kwargs):
        raise OSError("locked")

    monkeypatch.setattr(os, "remove", _boom)
    with pytest.raises(_core.SDKError):
        _core.inject(str(rom), {"seg": ["x"]})
    leftovers = list(tmp_path.glob("*_translated*.tmp"))
    assert len(leftovers) == 1
    real_remove(leftovers[0])


def test_get_version_fallback(monkeypatch):
    def _boom(*args, **kwargs):
        raise OSError("gone")

    monkeypatch.setattr("builtins.open", _boom)
    assert _core.get_version() == "1.0.0"


class _EmptyFile:
    def read(self):
        return ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_get_version_empty(monkeypatch):
    monkeypatch.setattr("builtins.open", lambda *a, **k: _EmptyFile())
    assert _core.get_version() == "1.0.0"


def test_load_json_too_big(tmp_path):
    target = tmp_path / "t.json"
    target.write_text("{}", encoding="utf-8")
    with pytest.raises(_core.SDKError) as exc:
        _core.load_json_file(str(target), limit=1)
    assert exc.value.code == "VALIDATION_ERROR"


def test_load_json_race_deleted(monkeypatch, tmp_path):
    target = tmp_path / "t.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(os.path, "getsize", lambda path: 2)

    def _gone(*args, **kwargs):
        raise FileNotFoundError("gone")

    monkeypatch.setattr("builtins.open", _gone)
    with pytest.raises(_core.SDKError) as exc:
        _core.load_json_file(str(target))
    assert exc.value.code == "IO_ERROR"


def test_get_unknown_404(full_server):
    _, port = full_server
    status, data = _get(port, "/nope")
    assert status == 404
    assert data["ok"] is False


def test_extract_missing_rom_400(full_server):
    _, port = full_server
    status, data = _post(port, "/extract", {})
    assert status == 400
    assert data["error"]["code"] == "BAD_REQUEST"


def test_extract_bad_max_segments_400(full_server, api_rom_file):
    _, port = full_server
    status, data = _post(port, "/extract", {"rom": api_rom_file, "max_segments": "x"})
    assert status == 400
    assert data["error"]["code"] == "BAD_REQUEST"


def test_inject_resolve_contract(full_server):
    _, port = full_server
    status, data = _post(port, "/inject", {"rom": "nope.gb", "translations": {}})
    assert status == 200
    assert data["ok"] is False
    assert data["error"]["code"] == "IO_ERROR"


class _DeniedLock:
    def acquire(self, timeout=None):
        return False


def test_inject_conflict_409(full_server, api_rom_file, monkeypatch):
    server, port = full_server
    monkeypatch.setattr(server, "lock_for_output", lambda path: _DeniedLock())
    status, data = _post(port, "/inject", {"rom": api_rom_file, "translations": {}})
    assert status == 409
    assert data["error"]["code"] == "CONFLICT"


class _ExplodingLock:
    def acquire(self, timeout=None):
        raise OSError("lock exploded")


def test_inject_lock_blowup(full_server, api_rom_file, monkeypatch):
    server, port = full_server
    monkeypatch.setattr(server, "lock_for_output", lambda path: _ExplodingLock())
    status, data = _post(port, "/inject", {"rom": api_rom_file, "translations": {}})
    assert status == 500
    assert data["ok"] is False
    assert data["error"]["code"] == "INTERNAL"


def test_handle_generic_500(full_server, monkeypatch):
    _, port = full_server

    def _boom(*args, **kwargs):
        raise ValueError("unexpected")

    monkeypatch.setattr(_core, "detect", _boom)
    status, data = _post(port, "/detect", {"rom": "x.gb"})
    assert status == 500
    assert data["ok"] is False
    assert data["error"]["code"] == "INTERNAL"


def test_body_no_content_length(full_server, api_rom_file):
    _, port = full_server
    body = json.dumps({"rom1": api_rom_file, "rom2": api_rom_file}).encode("utf-8")
    head = b"POST /diff HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n"
    status, data = _raw_request(port, head, body, shutdown_write=True)
    assert status == 200
    assert data["ok"] is True


def test_body_bad_content_length(full_server):
    _, port = full_server
    head = b"POST /diff HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: abc\r\nConnection: close\r\n\r\n"
    status, data = _raw_request(port, head, b"{}")
    assert status == 400
    assert data["error"]["code"] == "BAD_REQUEST"


def test_read_body_timeout_stub(monkeypatch):
    headers = {"Content-Type": "application/json", "Content-Length": "5"}
    handler, calls = _stub_handler(monkeypatch, headers, _RaisingRfile(TimeoutError()))
    assert handler._read_json_body() is None
    assert calls[0][0] == 408


def test_read_body_none_stub(monkeypatch):
    headers = {"Content-Type": "application/json", "Content-Length": "5"}
    handler, calls = _stub_handler(monkeypatch, headers, _FixedRfile(None))
    assert handler._read_json_body() is None
    assert calls[0][0] == 400


def test_read_body_oversize_no_length_stub(monkeypatch):
    headers = {"Content-Type": "application/json"}
    handler, calls = _stub_handler(monkeypatch, headers, _FixedRfile(b"x" * (BODY_LIMIT_DETECT_EXTRACT + 1)))
    assert handler._read_json_body() is None
    assert calls[0][0] == 413


def test_contract_internal_masked(full_server, monkeypatch):
    _, port = full_server

    def _boom(*args, **kwargs):
        raise _core.SDKError(_core.C_INTERNAL, "secret detail")

    monkeypatch.setattr(_core, "detect", _boom)
    status, data = _post(port, "/detect", {"rom": "x.gb"})
    assert status == 200
    assert data["ok"] is False
    assert data["error"]["code"] == "INTERNAL"
    assert data["error"]["message"] != "secret detail"


def test_reply_broken_pipe(monkeypatch):
    handler = ApiHandler.__new__(ApiHandler)

    class _Boom:
        def write(self, data):
            raise BrokenPipeError()

    handler.wfile = cast(Any, _Boom())
    monkeypatch.setattr(ApiHandler, "send_response", lambda self, *args: None)
    monkeypatch.setattr(ApiHandler, "send_header", lambda self, *args: None)
    monkeypatch.setattr(ApiHandler, "end_headers", lambda self: None)
    ApiHandler._reply(handler, {"ok": True})
    assert handler.close_connection is True


def test_serve_non_loopback_no_token(monkeypatch):
    monkeypatch.delenv("GB2TEXT_API_TOKEN", raising=False)
    with pytest.raises(ValueError):
        serve("0.0.0.0", 1)


def test_serve_loopback_runs(monkeypatch):
    monkeypatch.delenv("GB2TEXT_API_TOKEN", raising=False)
    monkeypatch.setattr(ApiServer, "serve_forever", lambda self: None)
    serve("127.0.0.1", 0)


def test_serve_keyboard_interrupt(monkeypatch):
    monkeypatch.delenv("GB2TEXT_API_TOKEN", raising=False)

    def _interrupt(self):
        raise KeyboardInterrupt()

    monkeypatch.setattr(ApiServer, "serve_forever", _interrupt)
    serve("127.0.0.1", 0)


def test_auth_non_loopback_delay(tmp_path, monkeypatch):
    plugin_dir = str(tmp_path / "no_plugins")
    server = ApiServer(("127.0.0.1", 0), plugin_dir=plugin_dir, max_workers=2, api_token="s3cret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setattr("api.server._is_loopback", lambda host: False)
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=30)
        body = json.dumps({"rom": "x.gb"}).encode("utf-8")
        started = time.monotonic()
        conn.request("POST", "/detect", body=body, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        conn.close()
        assert response.status == 401
        assert data["ok"] is False
        assert time.monotonic() - started >= 0.4
    finally:
        server.shutdown()
        server.server_close()


def test_output_locks_reuse_and_prune():
    server = ApiServer(("127.0.0.1", 0), plugin_dir="no_plugins_here")
    try:
        first = server.lock_for_output("a")
        assert server.lock_for_output("a") is first
        held = server.lock_for_output("held")
        assert held.acquire(blocking=False) is True
        for index in range(128):
            server.lock_for_output(f"p{index}")
        for path in server._locks_lru:
            server._locks_lru[path] = 0.0
        server.lock_for_output("new")
        assert "new" in server.output_locks
        assert len(server.output_locks) <= 128
        assert server.output_locks["held"] is held
        assert "a" not in server.output_locks
        held.release()
    finally:
        server.server_close()


def test_handle_post_unmatched_path(monkeypatch):
    handler = ApiHandler.__new__(ApiHandler)
    handler.path = "/retired"
    monkeypatch.setattr(ApiHandler, "_read_json_body", lambda self: {})
    calls = []
    monkeypatch.setattr(ApiHandler, "_reply", lambda self, payload, status=200: calls.append((status, payload)))
    ApiHandler._handle_post(handler)
    assert calls == []
