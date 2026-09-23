import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from api import cli
from api._core import SDKError


def test_cli_all_commands(tmp_path, monkeypatch):
    monkeypatch.setattr("api._core.list_plugins", lambda *a, **k: [{"kind": "config", "name": "N", "game_id_pattern": "P", "signature": True}])
    assert cli.main(["plugins"]) == 0
    assert cli.main(["plugins", "--json"]) == 0
    monkeypatch.setattr("api._core.detect", lambda *a, **k: {"game_id": "G", "system": "S", "title": "T", "size": 1, "plugin": None})
    assert cli.main(["detect", "r.gb"]) == 0
    assert cli.main(["detect", "r.gb", "--json"]) == 0
    monkeypatch.setattr("api._core.extract", lambda *a, **k: {"segments": {"s": [{"offset": 1, "text": "hi"}]}})
    assert cli.main(["extract", "r.gb"]) == 0
    assert cli.main(["extract", "r.gb", "--format", "json"]) == 0
    assert cli.main(["extract", "r.gb", "--format", "csv", "-o", str(tmp_path / "o.csv")]) == 0
    assert cli.main(["extract", "r.gb", "--json"]) == 0
    monkeypatch.setattr("api._core.load_json_file", lambda *a, **k: {"s": ["hi"]})
    monkeypatch.setattr("api._core.inject", lambda *a, **k: {"output_path": "o.gb", "checksum": 0, "segments": {"s": True}})
    assert cli.main(["inject", "r.gb", "--translations", "t.json"]) == 0
    assert cli.main(["inject", "r.gb", "--translations", "t.json", "--json"]) == 0
    with pytest.raises(SystemExit):
        cli.main(["extract", "r.gb", "--json", "--format", "json"])
    monkeypatch.setattr("api._core.detect", lambda *a, **k: (_ for _ in ()).throw(SDKError("X", "x")))
    assert cli.main(["detect", "r.gb"]) == 1
    assert cli.main(["detect", "r.gb", "--json"]) == 1
    monkeypatch.setattr("api._core.detect", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cli.main(["detect", "r.gb"]) == 1
    assert cli.main(["detect", "r.gb", "--json"]) == 1
    monkeypatch.setattr("api._core.list_plugins", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cli.main(["plugins"]) == 1


def test_cli_serve(monkeypatch):
    monkeypatch.setattr("api.serve", lambda *a, **k: None)
    assert cli.main(["serve", "--port", "8123"]) == 0


def test_cli_helpers(monkeypatch):
    monkeypatch.setattr(sys.stdout, "reconfigure", lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    cli._reconfigure_stdout()
    assert cli._emit({"x": 1}, True) is None
    assert cli._emit({"x": 1}, False) == {"x": 1}
    assert cli._fail(SDKError("X", "msg"), True) == 1
    assert cli._fail(SDKError("X", "msg"), False) == 1
