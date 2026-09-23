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

        class _SpyThread(real_thread):  # type: ignore[valid-type, misc]
            def start(self) -> None:
                started.set()

        def spy_thread(*args, **kwargs):
            return _SpyThread(*args, **kwargs)

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


def _wait_uninstalled(dialog, timeout=5.0):
    """Дожидается завершения асинхронного uninstall: фон-поток + tk-события.

    Ожидает не только снятия установки, но и срабатывания tk-калбэка
    _on_uninstall_done (он же инкрементит owner.plugin_manager_reloads).
    """
    import time

    reload_target = dialog.owner.plugin_manager_reloads + 1
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        dialog.win.update_idletasks()
        dialog.win.update()
        if (not dialog.registry.is_installed("gba_test_game")
                and dialog.owner.plugin_manager_reloads >= reload_target):
            return
        time.sleep(0.01)
    raise AssertionError(
        "uninstall либо не завершился, либо не перезагрузил менеджер плагинов")


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
        _wait_uninstalled(dialog)
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


def test_dialog_grab_default(root, owner, registry):
    dialog = cpd.CommunityPluginsDialog(root, owner, registry=registry)
    try:
        assert dialog.win is not None
    finally:
        try:
            dialog.win.grab_release()
        except tk.TclError:
            pass
        dialog.win.destroy()


def test_poller_start_tcl_error(root, owner, registry, monkeypatch):
    real_after = tk.Toplevel.after
    calls: list = []

    def flaky_after(self, *args, **kwargs):
        if not calls:
            calls.append(1)
            raise tk.TclError("gone")
        return real_after(self, *args, **kwargs)

    monkeypatch.setattr(tk.Toplevel, "after", flaky_after)
    dialog = _make_dialog(root, owner, registry)
    try:
        assert calls == [1]
    finally:
        dialog.win.destroy()


def test_run_returns_after_destroy(root, owner, registry):
    import time

    dialog = _make_dialog(root, owner, registry)
    worker = threading.Thread(target=dialog.run, daemon=True)
    worker.start()
    deadline = time.monotonic() + 5
    while worker.is_alive() and time.monotonic() < deadline:
        dialog.win.update()
        time.sleep(0.01)
    dialog.win.destroy()
    worker.join(timeout=5)
    assert not worker.is_alive()


def test_poll_winfo_exists_error(root, owner, registry, monkeypatch):
    dialog = _make_dialog(root, owner, registry)
    try:
        def gone():
            raise tk.TclError("gone")

        monkeypatch.setattr(dialog.win, "winfo_exists", gone)
        dialog._poll_callbacks()
        monkeypatch.setattr(dialog.win, "winfo_exists", lambda: False)
        dialog._poll_callbacks()
    finally:
        dialog.win.destroy()


def test_poll_reschedule_error(root, owner, registry, monkeypatch):
    dialog = _make_dialog(root, owner, registry)
    try:
        def gone(*args, **kwargs):
            raise tk.TclError("gone")

        monkeypatch.setattr(tk.Toplevel, "after", gone)
        dialog._poll_callbacks()
    finally:
        dialog.win.destroy()


def test_poll_isolates_failing_callbacks(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        done: list = []

        def boom_tcl():
            raise tk.TclError("x")

        def boom():
            raise RuntimeError("y")

        dialog._safe_after(boom_tcl)
        dialog._safe_after(boom)
        dialog._safe_after(lambda: done.append(1))
        dialog._poll_callbacks()
        dialog.win.update()
        assert done == [1]
    finally:
        dialog.win.destroy()


def test_refresh_when_busy(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._set_busy(True)
        dialog._refresh()
        assert dialog._busy is True
    finally:
        dialog.win.destroy()


def test_load_registry_success(root, owner, registry, monkeypatch):
    plug = _make_plugin()
    monkeypatch.setattr(registry, "fetch_registry", lambda: [plug])
    monkeypatch.setattr(registry, "check_updates", lambda plugins: set())
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._callback_queue.get_nowait()
    except Exception:
        pass
    try:
        dialog._load_registry()
        dialog._poll_callbacks()
        dialog.win.update()
        assert len(dialog.tree.get_children()) == 1
        assert dialog._busy is False
    finally:
        dialog.win.destroy()


def test_populate_empty(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([], set())
        assert len(dialog.tree.get_children()) == 0
        assert "empty" in dialog.status_var.get().lower() or \
            "Catalog" in dialog.status_var.get()
    finally:
        dialog.win.destroy()


def test_selected_plugin_unknown_id(root, owner, registry):
    plug = _make_plugin()
    other = _make_plugin(plugin_id="other_game")
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([plug], set())
        dialog.tree.selection_set("gba_test_game")
        dialog.plugins = [other]
        assert dialog._selected_plugin() is None
    finally:
        dialog.win.destroy()


def test_on_install_when_busy(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([_make_plugin()], set())
        dialog.tree.selection_set("gba_test_game")
        dialog._set_busy(True)
        dialog._on_install()
        assert dialog._busy is True
    finally:
        dialog.win.destroy()


def test_on_install_no_selection_cb(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([_make_plugin()], set())
        dialog._on_install()
        assert dialog._busy is False
    finally:
        dialog.win.destroy()


def test_on_update_guards(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._set_busy(True)
        dialog._on_update()
        assert dialog._busy is True
        dialog._set_busy(False)
        dialog._populate([_make_plugin()], set())
        dialog._on_update()
        assert dialog._busy is False
    finally:
        dialog.win.destroy()


def test_start_install_python_accepted(root, owner, registry, monkeypatch):
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    started: list = []

    class DummyThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            started.append(1)

    plug = _make_plugin(plugin_type="python")
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([plug], set())
        dialog.tree.selection_set("gba_test_game")
        monkeypatch.setattr(threading, "Thread", DummyThread)
        dialog._on_install()
        assert started == [1]
        assert dialog._busy is True
    finally:
        dialog.win.destroy()


def test_do_install_unknown_plugin(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([_make_plugin()], set())
        dialog._do_install("no_such_plugin")
        dialog._poll_callbacks()
        assert dialog._busy is False
    finally:
        dialog.win.destroy()


def test_do_install_error_path(root, owner, registry, monkeypatch):
    def boom(plugin):
        raise RuntimeError("boom")

    monkeypatch.setattr(registry, "install", boom)
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([_make_plugin()], set())
        dialog._do_install("gba_test_game")
        dialog._poll_callbacks()
        dialog.win.update()
        assert dialog._busy is False
        assert "boom" in dialog.status_var.get()
    finally:
        dialog.win.destroy()


def test_on_install_done(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([_make_plugin()], set())
        dialog._on_install_done()
        assert dialog._busy is False
        assert owner.plugin_manager_reloads >= 1
    finally:
        dialog.win.destroy()


def test_on_uninstall_guards(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._set_busy(True)
        dialog._on_uninstall()
        assert dialog._busy is True
        dialog._set_busy(False)
        dialog._populate([_make_plugin()], set())
        dialog._on_uninstall()
        assert dialog._busy is False
    finally:
        dialog.win.destroy()


def test_on_uninstall_not_installed(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([_make_plugin()], set())
        dialog.tree.selection_set("gba_test_game")
        dialog._on_uninstall()
        assert not dialog.registry.is_installed("gba_test_game")
    finally:
        dialog.win.destroy()


def test_on_uninstall_declined(root, owner, registry):
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
        assert dialog.registry.is_installed("gba_test_game")
    finally:
        dialog.win.destroy()


def test_do_uninstall_error_path(root, owner, registry, monkeypatch):
    def boom(plugin_id):
        raise RuntimeError("gone")

    monkeypatch.setattr(registry, "uninstall", boom)
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    dialog = _make_dialog(root, owner, registry)
    try:
        config_dir = dialog.registry.plugins_dir / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "gba_test_game.json").write_text(
            _json_content().decode("utf-8"), encoding="utf-8"
        )
        dialog.registry._record_install(
            "gba_test_game", "1.0.0", "json", "https://example.com/test.json")
        dialog._populate([_make_plugin()], set())
        dialog._do_uninstall("gba_test_game")
        dialog._poll_callbacks()
        dialog.win.update()
        assert dialog._busy is False
    finally:
        dialog.win.destroy()


def _sort_plugins():
    a = _make_plugin(plugin_id="b_game", version="2.0.0")
    a.update({"name": "Beta", "author": "zeta"})
    b = _make_plugin(plugin_id="a_game", version="10.0.0")
    b.update({"name": "alpha", "author": "Alpha"})
    return [a, b]


def test_sort_by_name(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate(_sort_plugins(), set())
        assert [dialog.tree.item(c, "values")[0] for c in dialog.tree.get_children()] == ["alpha", "Beta"]
        dialog._sort_by("name")
        assert [dialog.tree.item(c, "values")[0] for c in dialog.tree.get_children()] == ["Beta", "alpha"]
        assert "▼" in dialog.tree.heading("name", "text")
        dialog._sort_by("author")
        assert [dialog.tree.item(c, "values")[1] for c in dialog.tree.get_children()] == ["Alpha", "zeta"]
        assert "▲" in dialog.tree.heading("author", "text")
        assert "▼" not in dialog.tree.heading("name", "text")
    finally:
        dialog.win.destroy()


def test_sort_by_version_string(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate(_sort_plugins(), set())
        dialog._sort_by("version")
        assert [dialog.tree.item(c, "values")[2] for c in dialog.tree.get_children()] == ["2.0.0", "10.0.0"]
    finally:
        dialog.win.destroy()


def test_sort_version_natural(root, owner, registry):
    a = _make_plugin(plugin_id="x", version="1.9.0")
    b = _make_plugin(plugin_id="y", version="1.10.0")
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate([b, a], set())
        dialog._sort_by("version")
        assert [dialog.tree.item(c, "values")[2] for c in dialog.tree.get_children()] == ["1.9.0", "1.10.0"]
    finally:
        dialog.win.destroy()


def test_sort_initial_mark(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        assert "▲" in dialog.tree.heading("name", "text")
    finally:
        dialog.win.destroy()


def test_sort_busy_guard(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate(_sort_plugins(), set())
        before = [dialog.tree.item(c, "values")[0] for c in dialog.tree.get_children()]
        dialog._set_busy(True)
        dialog._sort_by("author")
        assert dialog._sort_col == "author"
        assert dialog._busy is True
        assert [dialog.tree.item(c, "values")[0] for c in dialog.tree.get_children()] == before
    finally:
        dialog.win.destroy()


def test_sort_keeps_selection(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._populate(_sort_plugins(), set())
        dialog.tree.selection_set("a_game")
        dialog._sort_by("author")
        assert dialog.tree.selection() == ("a_game",)
    finally:
        dialog.win.destroy()


def test_sort_empty_no_crash(root, owner, registry):
    dialog = _make_dialog(root, owner, registry)
    try:
        dialog._sort_by("author")
        assert dialog._sort_col == "author"
    finally:
        dialog.win.destroy()


def test_columns_fit_headers(root, owner, registry):
    from tkinter import font as tkfont

    dialog = _make_dialog(root, owner, registry)
    try:
        try:
            font = tkfont.nametofont("TkHeadingFont")
        except tk.TclError:
            font = tkfont.nametofont("TkDefaultFont")
        for col in ("name", "author", "version", "status", "type"):
            need = font.measure(dialog._base_headings[col]) + 28
            assert dialog.tree.column(col, "width") >= need
            assert dialog.tree.column(col, "minwidth") >= need
    finally:
        dialog.win.destroy()


def test_autosize_long_status(root, owner, registry):
    plug = _make_plugin()
    plug["name"] = "Очень длинное название плагина для проверки ширины колонки"
    dialog = _make_dialog(root, owner, registry)
    try:
        before = dialog.tree.column("name", "width")
        dialog._populate([plug], set())
        assert dialog.tree.column("name", "width") >= before
    finally:
        dialog.win.destroy()
