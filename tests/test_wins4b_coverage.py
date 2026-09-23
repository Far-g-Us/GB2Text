import hashlib
import json
import os
import runpy
from pathlib import Path

import pytest

from api import cli
from core.community_registry import CommunityRegistry, CommunityRegistryError


@pytest.fixture
def registry(tmp_path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    return CommunityRegistry(
        plugins_dir=plugins_dir,
        settings_dir=settings_dir,
        registry_url="https://example.com/registry.json",
        allowed_hosts=("example.com",),
    )


def _valid_entry():
    return {
        "id": "a_b",
        "type": "json",
        "download_url": "https://example.com/a.json",
        "sha256": "00" * 32,
        "version": "1.0",
    }


class _FakeResp:
    def __init__(self, payload=b"", redirect=None, chunks=None):
        self._payload = payload
        self._redirect = redirect
        self._chunks = chunks
        self.headers = {} if redirect is None else {"Location": redirect}

    def raise_for_status(self):
        pass

    @property
    def is_redirect(self):
        return self._redirect is not None

    @property
    def is_permanent_redirect(self):
        return False

    def iter_content(self, chunk_size=65536):
        if self._chunks is not None:
            yield from self._chunks
        else:
            yield self._payload


def _write_cache(registry, plugins):
    registry._cache_file.parent.mkdir(parents=True, exist_ok=True)
    registry._cache_file.write_text(json.dumps({"plugins": plugins}), encoding="utf-8")


def test_fetch_validation_error_cached(registry, monkeypatch):
    _write_cache(registry, [_valid_entry()])

    def _boom(*args, **kwargs):
        raise CommunityRegistryError("net down")

    monkeypatch.setattr("requests.get", _boom)
    assert registry.fetch_registry() == [_valid_entry()]


def test_fetch_generic_error_no_cache(registry, monkeypatch):
    def _boom(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr("requests.get", _boom)
    with pytest.raises(CommunityRegistryError):
        registry.fetch_registry()


def test_installed_not_dict(registry):
    registry._installed_file.parent.mkdir(parents=True, exist_ok=True)
    registry._installed_file.write_text("[1, 2]", encoding="utf-8")
    assert registry.get_installed() == {}


def test_has_update_non_str_local(registry):
    assert registry.has_update({"id": "a", "version": "2.0"}, {"a": {"version": 5}}) is False


def test_install_bad_id(registry):
    with pytest.raises(CommunityRegistryError):
        registry.install({"id": "?? bad ??"})


def test_install_version_gate(registry):
    plugin = _valid_entry()
    plugin["min_gb2text_version"] = "999.0"
    with pytest.raises(CommunityRegistryError):
        registry.install(plugin)


def test_install_non_utf8_json(registry, monkeypatch):
    content = b"\xff\xfe\x00bad"
    plugin = _valid_entry()
    plugin["sha256"] = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(registry, "_download_file", lambda url: content)
    with pytest.raises(CommunityRegistryError):
        registry.install(plugin)


def test_install_unknown_type(registry, monkeypatch):
    content = b'{"game_id_pattern": "x", "segments": []}'
    plugin = _valid_entry()
    plugin["type"] = "zip"
    plugin["sha256"] = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(registry, "_download_file", lambda url: content)
    with pytest.raises(CommunityRegistryError):
        registry.install(plugin)


def test_uninstall_python_type(registry):
    registry._write_installed({"a": {"version": "1", "type": "python"}})
    assert registry.uninstall("a") is True
    assert registry.get_installed() == {}


def test_uninstall_symlink_branch(registry, monkeypatch):
    registry._write_installed({"a": {"version": "1", "type": "json"}})
    target = registry.config_dir / "a.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"{}")
    monkeypatch.setattr(Path, "is_symlink", lambda self: True)
    assert registry.uninstall("a") is True


def test_validate_plugins_variants(registry):
    with pytest.raises(CommunityRegistryError):
        registry._validate_plugins(["x"])
    with pytest.raises(CommunityRegistryError):
        registry._validate_plugins([{"id": ""}])
    entry = _valid_entry()
    entry["type"] = "zip"
    with pytest.raises(CommunityRegistryError):
        registry._validate_plugins([entry])
    entry = _valid_entry()
    del entry["download_url"]
    with pytest.raises(CommunityRegistryError):
        registry._validate_plugins([entry])
    entry = _valid_entry()
    entry["version"] = 5
    with pytest.raises(CommunityRegistryError):
        registry._validate_plugins([entry])


def test_validate_plugin_id_non_str_no_raise(registry):
    assert registry._validate_plugin_id(123, raise_on_empty=False) == ""


def test_resolve_download_url_non_str(registry):
    with pytest.raises(CommunityRegistryError):
        registry._resolve_download_url(123)


def test_download_success(registry, monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResp(payload=b"hello"))
    assert registry._download_file("https://example.com/f") == b"hello"


def test_download_redirect_no_location(registry, monkeypatch):
    resp = _FakeResp(redirect="")
    resp.headers = {}
    monkeypatch.setattr("requests.get", lambda *a, **k: resp)
    with pytest.raises(CommunityRegistryError):
        registry._download_file("https://example.com/f")


def test_download_too_many_redirects(registry, monkeypatch):
    resp = _FakeResp(redirect="https://example.com/r")
    monkeypatch.setattr("requests.get", lambda *a, **k: resp)
    with pytest.raises(CommunityRegistryError):
        registry._download_file("https://example.com/f")


def test_download_generic_error(registry, monkeypatch):
    def _boom(*args, **kwargs):
        raise ConnectionError("cut")

    monkeypatch.setattr("requests.get", _boom)
    with pytest.raises(CommunityRegistryError):
        registry._download_file("https://example.com/f")


def test_download_too_big(registry, monkeypatch):
    resp = _FakeResp(chunks=[b"x" * (6 * 1024 * 1024)])
    monkeypatch.setattr("requests.get", lambda *a, **k: resp)
    with pytest.raises(CommunityRegistryError):
        registry._download_file("https://example.com/f")


def test_validate_json_not_dict(registry):
    with pytest.raises(CommunityRegistryError):
        registry._validate_json_plugin("[1, 2]")


def test_validate_json_bad_segment_field(registry):
    content = json.dumps(
        {
            "game_id_pattern": "x",
            "segments": [{"name": "a", "start": 1.5, "end": 10}],
        }
    )
    with pytest.raises(CommunityRegistryError):
        registry._validate_json_plugin(content)


def test_check_version_no_version_file(registry, monkeypatch):
    monkeypatch.setattr(Path, "exists", lambda self: False)
    assert registry._check_gb2text_version({"min_gb2text_version": "99.0"}) is False


def test_load_cache_not_dict(registry):
    registry._cache_file.parent.mkdir(parents=True, exist_ok=True)
    registry._cache_file.write_text("[1]", encoding="utf-8")
    assert registry._load_cache() is None


def test_load_cache_invalid_plugins(registry):
    _write_cache(registry, [{"id": ""}])
    assert registry._load_cache(validate=True) is None


def test_load_cache_no_validate(registry):
    _write_cache(registry, [_valid_entry()])
    assert registry._load_cache() == [_valid_entry()]


def test_check_version_read_error(registry, monkeypatch):
    def _boom(self, *args, **kwargs):
        raise OSError("disk gone")

    monkeypatch.setattr(Path, "read_text", _boom)
    assert registry._check_gb2text_version({"min_gb2text_version": "99.0"}) is True


def test_atomic_write_replace_fails(tmp_path, monkeypatch):
    target = tmp_path / "f.bin"
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
    with pytest.raises(OSError):
        CommunityRegistry._atomic_write(target, b"data")
    assert list(tmp_path.glob("tmp*")) == []


def test_atomic_write_unlink_fails(tmp_path, monkeypatch):
    target = tmp_path / "f.bin"
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
    monkeypatch.setattr(os, "unlink", lambda *a, **k: (_ for _ in ()).throw(OSError("busy")))
    with pytest.raises(OSError):
        CommunityRegistry._atomic_write(target, b"data")


def test_dialog_run_returns():
    from gui.community_plugins_dialog import CommunityPluginsDialog

    dialog = CommunityPluginsDialog.__new__(CommunityPluginsDialog)
    calls = []

    class FakeWin:
        def wait_window(self, win):
            calls.append(win)

    dialog.win = FakeWin()
    dialog.run()
    assert calls == [dialog.win]


def _mock_core(monkeypatch, **overrides):
    from api import _core

    defaults = {
        "list_plugins": lambda plugin_dir=None: [],
        "detect": lambda rom, plugin_dir=None: {},
        "extract": lambda *a, **k: {"segments": {}},
        "load_json_file": lambda path, limit=None: {},
        "inject": lambda *a, **k: {},
    }
    defaults.update(overrides)
    for name, func in defaults.items():
        monkeypatch.setattr(_core, name, func)


def test_cli_plugins_text(capsys, monkeypatch):
    _mock_core(
        monkeypatch,
        list_plugins=lambda plugin_dir=None: [
            {"kind": "config", "name": "N", "game_id_pattern": "P", "signature": True},
            {"kind": "python", "name": "M", "game_id_pattern": "Q", "signature": False},
        ],
    )
    assert cli.main(["plugins"]) == 0
    out = capsys.readouterr().out
    assert "[hack]" in out


def test_cli_plugins_json(capsys, monkeypatch):
    _mock_core(monkeypatch)
    assert cli.main(["plugins", "--json"]) == 0
    assert '"ok": true' in capsys.readouterr().out


def test_cli_detect_variants(capsys, monkeypatch):
    _mock_core(
        monkeypatch,
        detect=lambda rom, plugin_dir=None: {"game_id": "G", "system": "S", "title": "T", "size": 1, "plugin": None},
    )
    assert cli.main(["detect", "r.gb"]) == 0
    assert "game_id: G" in capsys.readouterr().out
    assert cli.main(["detect", "r.gb", "--json"]) == 0
    assert '"game_id": "G"' in capsys.readouterr().out


def test_cli_extract_formats(capsys, monkeypatch, tmp_path):
    payload = {"segments": {"s": [{"offset": 1, "text": "hi"}]}}
    _mock_core(monkeypatch, extract=lambda *a, **k: payload)
    assert cli.main(["extract", "r.gb"]) == 0
    assert "HI" in capsys.readouterr().out.upper()
    assert cli.main(["extract", "r.gb", "--format", "json"]) == 0
    assert '"hi"' in capsys.readouterr().out
    assert cli.main(["extract", "r.gb", "--format", "csv"]) == 0
    assert "segment,offset,text" in capsys.readouterr().out
    out_csv = tmp_path / "o.csv"
    assert cli.main(["extract", "r.gb", "--format", "csv", "-o", str(out_csv)]) == 0
    assert "hi" in out_csv.read_text(encoding="utf-8")
    assert cli.main(["extract", "r.gb", "--json"]) == 0
    assert '"ok": true' in capsys.readouterr().out


def test_cli_inject_variants(capsys, monkeypatch):
    _mock_core(
        monkeypatch,
        load_json_file=lambda path, limit=None: {"s": ["x"]},
        inject=lambda *a, **k: {"output_path": "o.gb", "checksum": 5, "segments": {"a": True, "b": False}},
    )
    assert cli.main(["inject", "r.gb", "--translations", "t.json"]) == 0
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert cli.main(["inject", "r.gb", "--translations", "t.json", "--json"]) == 0
    assert '"ok": true' in capsys.readouterr().out


def test_cli_serve_mocked(monkeypatch):
    calls = []
    monkeypatch.setattr("api.serve", lambda *a, **k: calls.append((a, k)))
    assert cli.main(["serve", "--port", "8123"]) == 0
    assert calls[0][0][1] == 8123


def test_cli_json_format_conflict():
    with pytest.raises(SystemExit) as exc:
        cli.main(["extract", "r.gb", "--json", "--format", "json"])
    assert exc.value.code == 2


def test_cli_detect_sdk_error(capsys):
    assert cli.main(["detect", "nope_xyz.gb"]) == 1
    assert "INTERNAL" not in capsys.readouterr().err
    assert cli.main(["detect", "nope_xyz.gb", "--json"]) == 1
    assert '"ok": false' in capsys.readouterr().out


def test_cli_detect_generic_error(capsys, monkeypatch):
    from api import _core

    def _boom(*args, **kwargs):
        raise ValueError("unexpected")

    monkeypatch.setattr(_core, "detect", _boom)
    assert cli.main(["detect", "x.gb"]) == 1
    assert "INTERNAL" in capsys.readouterr().err
    assert cli.main(["detect", "x.gb", "--json"]) == 1
    assert '"INTERNAL"' in capsys.readouterr().out


def test_cli_main_non_int_func(monkeypatch):
    parser = cli.build_parser()
    args = parser.parse_args(["plugins"])
    args.func = lambda a: "nope"
    monkeypatch.setattr(cli, "build_parser", lambda: parser)
    monkeypatch.setattr(parser, "parse_args", lambda argv=None: args)
    assert cli.main([]) == 1


def test_cli_reconfigure_variants(monkeypatch):
    _mock_core(monkeypatch)

    class NoReconfigure:
        def write(self, data):
            pass

    monkeypatch.setattr("sys.stdout", NoReconfigure())
    assert cli.main(["plugins", "--json"]) == 0

    class RaisingReconfigure:
        def write(self, data):
            pass

        def reconfigure(self, encoding=None):
            raise OSError("nope")

    monkeypatch.setattr("sys.stdout", RaisingReconfigure())
    assert cli.main(["plugins", "--json"]) == 0


def test_cli_main_module():
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("api.cli", run_name="__main__")
    assert exc.value.code == 2


def test_cli_emit_plain():
    assert cli._emit({"x": 1}, False) == {"x": 1}
