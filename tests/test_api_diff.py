import http.client
import json
import threading

import pytest

from api import _core
from api.server import ApiServer


def _start_server(plugin_dir):
    server = ApiServer(("127.0.0.1", 0), plugin_dir=plugin_dir, max_workers=2)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def _post(port, path, payload):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    body = json.dumps(payload).encode("utf-8")
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    response = conn.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    conn.close()
    return response.status, data


def _raw(port, raw_bytes):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    conn.request("POST", "/diff", body=raw_bytes, headers={"Content-Type": "application/json"})
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


@pytest.fixture(scope="module")
def diff_server(tmp_path_factory):
    plugin_dir = str(tmp_path_factory.mktemp("diff_plugs") / "no_plugins")
    server, port = _start_server(plugin_dir)
    yield port
    server.shutdown()
    server.server_close()


def _segments(mapping):
    return {seg: [{"text": text, "offset": 0} for text in texts] for seg, texts in mapping.items()}


def test_diff_identical_roms_empty(diff_server, tmp_path, api_rom_bytes):
    rom = tmp_path / "same.gb"
    rom.write_bytes(api_rom_bytes)
    status, data = _post(diff_server, "/diff", {"rom1": str(rom), "rom2": str(rom)})
    assert status == 200
    assert data["ok"] is True
    assert data["data"]["segments"] == {"added": [], "removed": [], "changed": []}
    assert data["data"]["stats"] == {"added": 0, "removed": 0, "changed": 0}


def test_diff_added_removed_changed(diff_server, tmp_path, api_rom_bytes, monkeypatch):
    first = tmp_path / "first.gb"
    second = tmp_path / "second.gb"
    first.write_bytes(api_rom_bytes)
    second.write_bytes(api_rom_bytes)

    def fake_extract(path, plugin_dir=None, **kwargs):
        if "first" in str(path):
            segs = _segments({"keep": ["same"], "gone": ["old"], "edit": ["before"]})
        else:
            segs = _segments({"keep": ["same"], "edit": ["after"], "fresh": ["new"]})
        return {"segments": segs, "stats": {}}

    monkeypatch.setattr(_core, "extract", fake_extract)
    status, data = _post(diff_server, "/diff", {"rom1": str(first), "rom2": str(second)})
    assert status == 200
    assert data["ok"] is True
    segments = data["data"]["segments"]
    assert segments["added"] == ["fresh"]
    assert segments["removed"] == ["gone"]
    assert segments["changed"] == [{"seg": "edit", "old_summary": "before", "new_summary": "after"}]
    assert data["data"]["stats"] == {"added": 1, "removed": 1, "changed": 1}


def test_diff_summary_truncated(diff_server, tmp_path, api_rom_bytes, monkeypatch):
    first = tmp_path / "t1.gb"
    second = tmp_path / "t2.gb"
    first.write_bytes(api_rom_bytes)
    second.write_bytes(api_rom_bytes)
    long_old = "word " * 20
    long_new = "other " * 20

    def fake_extract(path, plugin_dir=None, **kwargs):
        text = long_old if "t1" in str(path) else long_new
        return {"segments": _segments({"big": [text]}), "stats": {}}

    monkeypatch.setattr(_core, "extract", fake_extract)
    status, data = _post(diff_server, "/diff", {"rom1": str(first), "rom2": str(second)})
    assert status == 200
    changed = data["data"]["segments"]["changed"]
    assert len(changed) == 1
    for summary in (changed[0]["old_summary"], changed[0]["new_summary"]):
        assert summary.endswith("...")
        assert len(summary) == 43


def test_diff_get_method_not_allowed(diff_server):
    status, data = _get(diff_server, "/diff")
    assert status == 405
    assert data["ok"] is False


def test_diff_missing_rom2(diff_server, api_rom_file):
    status, data = _post(diff_server, "/diff", {"rom1": api_rom_file})
    assert status == 400
    assert data["error"]["code"] == "BAD_REQUEST"


def test_diff_invalid_json(diff_server):
    status, data = _raw(diff_server, b"{not json")
    assert status == 400
    assert data["error"]["code"] == "BAD_REQUEST"


def test_diff_missing_rom_contract(diff_server):
    status, data = _post(diff_server, "/diff", {"rom1": "no_such.gb", "rom2": "no_such2.gb"})
    assert status == 200
    assert data["ok"] is False
    assert data["error"]["code"] in ("IO_ERROR", "ROM_ERROR")


def test_diff_wrong_type_contract(diff_server):
    status, data = _post(diff_server, "/diff", {"rom1": 123, "rom2": "x.gb"})
    assert status == 200
    assert data["ok"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_summarize_text():
    assert _core._summarize_text("hello") == "hello"
    assert _core._summarize_text("  a\n b\t c ") == "a b c"
    assert _core._summarize_text("x" * 41) == "x" * 40 + "..."
    assert _core._summarize_text("y" * 40) == "y" * 40


def test_diff_roms_stats(tmp_path, api_rom_bytes, monkeypatch):
    first = tmp_path / "s1.gb"
    second = tmp_path / "s2.gb"
    first.write_bytes(api_rom_bytes)
    second.write_bytes(api_rom_bytes)

    def fake_extract(path, plugin_dir=None, **kwargs):
        if "s1" in str(path):
            return {"segments": _segments({"a": ["1"]}), "stats": {}}
        return {"segments": _segments({"a": ["2"], "b": ["3"]}), "stats": {}}

    monkeypatch.setattr(_core, "extract", fake_extract)
    report = _core.diff_roms(str(first), str(second))
    assert report["segments"]["added"] == ["b"]
    assert report["stats"] == {"added": 1, "removed": 0, "changed": 1}
