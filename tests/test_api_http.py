"""HTTP-тесты api.server: wire-ошибки, contract-ошибки, лимиты, BUSY, auth."""

import http.client
import json
import threading
from pathlib import Path

import pytest

from api.server import BODY_LIMIT_INJECT, ApiServer, serve


def _start_server(plugin_dir, max_workers=4, addr=("127.0.0.1", 0), api_token=None):
    server = ApiServer(addr, plugin_dir=plugin_dir, max_workers=max_workers,
                       api_token=api_token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def _conn(port):
    return http.client.HTTPConnection("127.0.0.1", port, timeout=30)


def _request(port, method, path, payload=None, headers=None):
    conn = _conn(port)
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    merged = {}
    if body is not None:
        merged["Content-Type"] = "application/json"
    if headers:
        merged.update(headers)
    conn.request(method, path, body=body, headers=merged)
    response = conn.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    conn.close()
    return response.status, data


def _post(port, path, payload, content_type="application/json"):
    conn = _conn(port)
    body = json.dumps(payload).encode("utf-8")
    conn.request("POST", path, body=body, headers={"Content-Type": content_type})
    response = conn.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    conn.close()
    return response.status, data


@pytest.fixture(scope="module")
def http_server(tmp_path_factory):
    plugin_dir = str(tmp_path_factory.mktemp("http_plugs") / "no_plugins")
    server, port = _start_server(plugin_dir, max_workers=2)
    yield port
    server.shutdown()
    server.server_close()


def test_http_health(http_server):
    conn = _conn(http_server)
    conn.request("GET", "/health")
    response = conn.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    conn.close()
    assert response.status == 200
    assert data["ok"] is True
    assert data["data"]["status"] == "ok"


def test_http_plugins_empty(http_server):
    conn = _conn(http_server)
    conn.request("GET", "/plugins")
    response = conn.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    conn.close()
    assert response.status == 200
    assert data["ok"] is True
    assert data["data"] == []


def test_http_detect_ok(http_server, api_rom_file):
    status, data = _post(http_server, "/detect", {"rom": api_rom_file})
    assert status == 200
    assert data["ok"] is True
    assert data["data"]["game_id"] == "GB_TESTTITLEAPI"


def test_http_detect_contract_error(http_server):
    status, data = _post(http_server, "/detect", {"rom": "no_such.gb"})
    assert status == 200
    assert data["ok"] is False
    assert data["error"]["code"] in ("IO_ERROR", "ROM_ERROR")


def test_http_detect_non_json_content_type(http_server):
    status, data = _post(
        http_server, "/detect", {"rom": "x.gb"}, content_type="text/plain"
    )
    assert status == 415
    assert data["ok"] is False
    assert data["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_http_detect_missing_key(http_server):
    status, data = _post(http_server, "/detect", {})
    assert status == 400
    assert data["error"]["code"] == "BAD_REQUEST"


def test_http_detect_non_object_body(http_server):
    status, data = _post(http_server, "/detect", [1, 2, 3])
    assert status == 400
    assert data["error"]["code"] == "BAD_REQUEST"


def test_http_unknown_endpoint(http_server):
    status, data = _post(http_server, "/nope", {})
    assert status == 404
    assert data["error"]["code"] == "NOT_FOUND"


def test_http_wrong_method(http_server):
    conn = _conn(http_server)
    conn.request("GET", "/extract")
    response = conn.getresponse()
    conn.close()
    assert response.status == 405


def test_http_payload_too_large(http_server):
    """Объявленный Content-Length сверх лимита → 413 без чтения тела.

    Сервер отвечает 413, не читая body, поэтому клиент намеренно НЕ отправляет
    всё тело: иначе на Windows возможна гонка — сервер закрывает соединение,
    пока клиент ещё пишет, и клиент ловит ConnectionAbortedError (флаки).
    """
    conn = _conn(http_server)
    conn.putrequest("POST", "/detect")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Content-Length", str((1 << 20) + 1))
    conn.endheaders()
    response = conn.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    conn.close()
    assert response.status == 413
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_http_inject_ok(http_server, api_rom_file, tmp_path):
    extracted = _post(
        http_server,
        "/extract",
        {"rom": api_rom_file, "output": None},
    )
    assert extracted[1]["ok"] is True
    translations = {
        seg: [{"translation": "HI WORLD"} for _ in msgs]
        for seg, msgs in extracted[1]["data"]["segments"].items()
    }
    out_path = str(tmp_path / "patched.gb")
    status, data = _post(
        http_server,
        "/inject",
        {"rom": api_rom_file, "translations": translations, "output": out_path},
    )
    assert status == 200
    assert data["ok"] is True
    assert data["data"]["output_path"] is not None


def test_http_inject_without_output(http_server, api_rom_file, tmp_path):
    extracted = _post(http_server, "/extract", {"rom": api_rom_file})
    assert extracted[1]["ok"] is True
    translations = {
        seg: [{"translation": "HI WORLD"} for _ in msgs]
        for seg, msgs in extracted[1]["data"]["segments"].items()
    }
    status, data = _post(
        http_server, "/inject", {"rom": api_rom_file, "translations": translations}
    )
    assert status == 200
    assert data["ok"] is True
    default_out = data["data"]["output_path"]
    assert default_out.endswith("_translated.gb")
    assert Path(default_out).exists()


def test_http_inject_missing_translations(http_server, api_rom_file):
    status, data = _post(
        http_server, "/inject", {"rom": api_rom_file}
    )
    assert status == 400
    assert data["error"]["code"] == "BAD_REQUEST"


def test_http_inject_wrong_translation_type(http_server, api_rom_file, tmp_path):
    out_path = str(tmp_path / "bad.gb")
    status, data = _post(
        http_server,
        "/inject",
        {"rom": api_rom_file, "translations": "not-a-dict", "output": out_path},
    )
    assert status == 200
    assert data["ok"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_http_busy(tmp_path, api_rom_file):
    plugin_dir = str(tmp_path / "no_plugins")
    server, port = _start_server(plugin_dir, max_workers=1)
    server.semaphore.acquire()
    try:
        status, data = _post(port, "/detect", {"rom": api_rom_file})
        assert status == 503
        assert data["error"]["code"] == "BUSY"
    finally:
        server.semaphore.release()
        server.shutdown()
        server.server_close()


def test_http_limit_constants_sane():
    assert BODY_LIMIT_INJECT > (1 << 20)


# ── аутентификация ────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_server(tmp_path_factory):
    plugin_dir = str(tmp_path_factory.mktemp("auth_plugs") / "no_plugins")
    server, port = _start_server(plugin_dir, max_workers=2, api_token="secret-token")
    yield port
    server.shutdown()
    server.server_close()


def test_http_auth_health_open(auth_server):
    conn = _conn(auth_server)
    conn.request("GET", "/health")
    response = conn.getresponse()
    conn.close()
    assert response.status == 200


def test_http_auth_rejects_missing_token(auth_server):
    status, data = _post(auth_server, "/detect", {"rom": "x.gb"})
    assert status == 401
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_http_auth_rejects_wrong_token(auth_server):
    status, data = _request(
        auth_server, "POST", "/detect", {"rom": "x.gb"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert status == 401
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_http_auth_rejects_plugins_without_token(auth_server):
    conn = _conn(auth_server)
    conn.request("GET", "/plugins")
    response = conn.getresponse()
    conn.close()
    assert response.status == 401


def test_http_auth_accepts_correct_token(auth_server, api_rom_file):
    status, data = _request(
        auth_server, "POST", "/detect", {"rom": api_rom_file},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert status == 200
    assert data["ok"] is True


def test_http_auth_bearer_leading_space_tolerated(auth_server, api_rom_file):
    status, data = _request(
        auth_server, "POST", "/detect", {"rom": api_rom_file},
        headers={"Authorization": "Bearer  secret-token"},
    )
    assert status == 200
    assert data["ok"] is True


def test_http_auth_bearer_scheme_case_insensitive(auth_server, api_rom_file):
    status, data = _request(
        auth_server, "POST", "/detect", {"rom": api_rom_file},
        headers={"Authorization": "bearer secret-token"},
    )
    assert status == 200
    assert data["ok"] is True


def test_http_negative_content_length_rejected(http_server):
    """Content-Length: -1 не должен обходить лимит body (read до EOF)."""
    conn = _conn(http_server)
    conn.putrequest("POST", "/detect")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Content-Length", "-1")
    conn.endheaders()
    conn.send(b'{"rom": "x.gb"}')
    response = conn.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    conn.close()
    assert response.status == 413
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_http_auth_rejects_inject_without_token(auth_server, api_rom_file):
    status, _ = _post(
        auth_server, "/inject", {"rom": api_rom_file, "translations": {}}
    )
    assert status == 401


def test_http_auth_missing_header_same_error(auth_server):
    """401 не раскрывает, настроен ли токен (одинаковый ответ на нет/неверный)."""
    no_header = _post(auth_server, "/detect", {"rom": "x.gb"})
    wrong = _request(
        auth_server, "POST", "/detect", {"rom": "x.gb"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert no_header[1] == wrong[1]


def test_http_auth_authorization_not_logged(auth_server, caplog, api_rom_file):
    """Authorization header не попадает в логи."""
    _request(
        auth_server, "POST", "/detect", {"rom": api_rom_file},
        headers={"Authorization": "Bearer secret-token"},
    )
    for record in caplog.records:
        assert "secret-token" not in record.getMessage()
        assert "Authorization" not in record.getMessage()


def test_serve_requires_token_for_non_loopback(monkeypatch):
    monkeypatch.delenv("GB2TEXT_API_TOKEN", raising=False)
    with pytest.raises(ValueError):
        serve("0.0.0.0", 8765, api_token=None)


def test_env_token_preferred_over_cli(monkeypatch):

    monkeypatch.setenv("GB2TEXT_API_TOKEN", "env-token")
    import api.server as server_mod

    assert server_mod._read_api_token("cli-token") == "env-token"


def test_cli_token_used_when_no_env(monkeypatch):

    monkeypatch.delenv("GB2TEXT_API_TOKEN", raising=False)
    import api.server as server_mod

    assert server_mod._read_api_token("cli-token") == "cli-token"


def test_output_locks_cache_pruned():
    """Свободные и «несвежие» локи вычищаются из кэша, когда он перерос лимит."""
    import time

    server = ApiServer(("127.0.0.1", 0))
    try:
        for i in range(200):
            server.lock_for_output(f"out{i}")
        # Делаем все локи «старыми», чтобы прунинг мог их удалить.
        old = time.monotonic() - 60.0
        for path in list(server._locks_lru):
            server._locks_lru[path] = old
        server.lock_for_output("extra")
        # После прунинга в кэше остаются только актуальные/«свежие» локи.
        assert len(server.output_locks) <= 129
        assert "extra" in server.output_locks
    finally:
        server.server_close()
