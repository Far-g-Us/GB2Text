"""
Тесты диалога Community Plugins.

GUI smoke-тесты: реальный Tk (паттерн test_gui_smoke.py).
"""

import hashlib
import json
import threading
import tkinter as tk
from tkinter import messagebox

import pytest

from core.community_registry import CommunityRegistry
from gui import community_plugins_dialog as cpd

pytestmark = [pytest.mark.gui, pytest.mark.slow]


def _make_root():
    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"Нет Tk display: {e}")
    root.withdraw()
    return root


def _json_content():
    return json.dumps({
        "game_id_pattern": "^GBA_TEST$",
        "segments": [{"name": "text", "start": 0, "end": 100}],
    }).encode("utf-8")


def _make_plugin(plugin_id="gba_test_game", version="1.0.0", plugin_type="json",
                 content=None):
    payload = content if content is not None else _json_content()
    return {
        "id": plugin_id,
        "name": "Test Game",
        "author": "test_author",
        "version": version,
        "game_id_pattern": "^GBA_TEST$",
        "platform": "GBA",
        "description": "Test plugin",
        "type": plugin_type,
        "download_url": "https://example.com/test.json",
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"Нет Tk display: {e}")
    r.withdraw()
    yield r
    try:
        r.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def owner(monkeypatch, tmp_path):
    """Фиктивный owner (GBTextExtractorGUI-совместимый)."""
    for name in ("showwarning", "showinfo", "showerror", "askyesno"):
        monkeypatch.setattr(messagebox, name, lambda *a, **k: False)

    class _I18N:
        def t(self, key, **kwargs):
            table = {
                "plugins.community.title": "Community Plugins",
                "plugins.community.install": "Install",
                "plugins.community.uninstall": "Uninstall",
                "plugins.community.update": "Update",
                "plugins.community.refresh": "Refresh",
                "plugins.community.name": "Name",
                "plugins.community.author": "Author",
                "plugins.community.status": "Status",
                "plugins.community.type": "Type",
                "plugins.community.version": "Version",
                "plugins.community.installed": "Installed",
                "plugins.community.update_available": "Update available",
                "plugins.community.not_installed": "Not installed",
                "plugins.community.fetching": "Loading catalog…",
                "plugins.community.no_connection": "Failed to load catalog: {error}",
                "plugins.community.empty": "Catalog is empty",
                "plugins.community.total": "{count} plugins",
                "plugins.community.installing": "Installing: {name}…",
                "plugins.community.installed_ok": "Plugin installed",
                "plugins.community.uninstalled_ok": "Plugin uninstalled",
                "plugins.community.python_warning": "Python code warning",
                "plugins.community.confirm_uninstall": "Confirm uninstall {name}",
                "plugins.community.name_label": "Name: {name}",
                "plugins.community.version_label": "v{version}",
                "warning.title": "Warning",
                "error.title": "Error",
                "cancel": "Cancel",
            }
            text = table.get(key, key)
            return text.format(**kwargs)

    class _Owner:
        def __init__(self):
            self.i18n = _I18N()
            self.status = None
            self.plugin_manager_reloads = 0

        def set_status(self, message, progress=0):
            self.status = message

        def reload_plugin_manager(self):
            self.plugin_manager_reloads += 1

    return _Owner()


@pytest.fixture
def registry(monkeypatch, tmp_path):
    r = CommunityRegistry(
        plugins_dir=tmp_path / "plugins",
        settings_dir=tmp_path / "settings",
        registry_url="https://example.com/registry.json",
        allowed_hosts=("example.com",),
    )
    return r


def _make_dialog(root, owner, registry):
    return cpd.CommunityPluginsDialog(root, owner, registry=registry, grab=False)


def test_dialog_imports():
    from gui.community_plugins_dialog import CommunityPluginsDialog
    assert CommunityPluginsDialog is not None


def test_dialog_opens_and_populates(root, owner, registry):
    plugins = [_make_plugin()]
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate(plugins, set())
        assert len(dialog.tree.get_children()) == 1
        values = dialog.tree.item("gba_test_game", "values")
        assert values[0] == "Test Game"
        assert values[1] == "test_author"
        assert values[3] == "Not installed"
    finally:
        dialog.win.destroy()


def test_dialog_python_warning(root, owner, registry):
    plug = _make_plugin(plugin_type="python")
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([plug], set())
        dialog.tree.selection_set("gba_test_game")
        dialog._on_install()
        assert not dialog.registry.is_installed("gba_test_game")
    finally:
        dialog.win.destroy()


def test_dialog_install_json(root, owner, registry, monkeypatch):
    plug = _make_plugin()
    payload = _json_content()
    monkeypatch.setattr(registry, "_download_file",
                        lambda url: payload)
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([plug], set())
        dialog.tree.selection_set("gba_test_game")
        plugin = dialog._selected_plugin()
        dialog._start_install(plugin)
        import time
        deadline = time.time() + 5
        while dialog.registry.get_local_version("gba_test_game") is None \
                and time.time() < deadline:
            time.sleep(0.02)
        assert dialog.registry.is_installed("gba_test_game")
    finally:
        dialog.win.destroy()


def test_dialog_update_runs_in_background(root, owner, registry, monkeypatch):
    """_on_update не блокирует главный поток (запускает threading.Thread)."""
    plug = _make_plugin()
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([plug], set())
        dialog.tree.selection_set("gba_test_game")
        started = threading.Event()
        real_thread = threading.Thread

        def spy_thread(*args, **kwargs):
            thread = real_thread(*args, **kwargs)
            thread.start = lambda: started.set()
            return thread

        monkeypatch.setattr(threading, "Thread", spy_thread)
        dialog._on_update()
        assert started.is_set()
        assert dialog._busy is True
    finally:
        dialog.win.destroy()


def test_dialog_install_no_selection(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([_make_plugin()], set())
        plugin = dialog._selected_plugin()
        assert plugin is None
    finally:
        dialog.win.destroy()


def test_dialog_uninstall(root, owner, registry, monkeypatch):
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    plug = _make_plugin()
    dialog = _make_dialog(root, owner, registry)
    try:
        config_dir = dialog.registry.plugins_dir / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "gba_test_game.json").write_text(
            _json_content().decode("utf-8"), encoding="utf-8"
        )
        dialog.registry._record_install(
            "gba_test_game", "1.0.0", "json", "https://example.com/test.json")

        dialog._populate([plug], set())
        dialog.tree.selection_set("gba_test_game")
        dialog._on_uninstall()
        assert not dialog.registry.is_installed("gba_test_game")
        assert owner.plugin_manager_reloads >= 1
    finally:
        dialog.win.destroy()


def test_load_registry_error(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._on_load_error("Network error")
        assert "Failed to load catalog" in dialog.status_var.get()
    finally:
        dialog.win.destroy()


def test_update_available_status(root, owner, registry):
    plug = _make_plugin(plugin_id="gba_test_game")
    plug["version"] = "1.1.0"
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog.registry.settings_dir.mkdir(parents=True)
        installed = {"gba_test_game": {"version": "1.0.0", "type": "json"}}
        (dialog.registry.settings_dir / "community_plugins.json").write_text(
            json.dumps(installed), encoding="utf-8"
        )
        dialog._populate([plug], {"gba_test_game"})
        values = dialog.tree.item("gba_test_game", "values")
        assert values[3] == "Update available"
    finally:
        dialog.win.destroy()


def test_busy_disables_buttons(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._set_busy(True)
        assert dialog._busy is True
        for button in dialog._action_buttons:
            assert str(button.cget("state")) == "disabled"
        dialog._set_busy(False)
        for button in dialog._action_buttons:
            assert str(button.cget("state")) == "normal"
    finally:
        dialog.win.destroy()


def test_safe_after_on_destroyed_window(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    dialog.win.destroy()
    dialog._safe_after(lambda: None)
