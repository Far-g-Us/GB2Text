from gui.editor import TextEditorFrame
from plugins.gba_golden_sun import GoldenSunPlugin


def test_editor_basic(tmp_path):
    assert TextEditorFrame is not None


def test_golden_sun_basic():
    plugin = GoldenSunPlugin()
    assert plugin.get_text_segments(type("R", (), {"data": bytes(0x100), "header": {}})()) == []


def test_cli_direct(tmp_path, monkeypatch):
    from api import cli

    monkeypatch.setattr("api._core.list_plugins", lambda *a, **k: [])
    assert cli.main(["plugins"]) == 0
    assert cli.main(["plugins", "--json"]) == 0
