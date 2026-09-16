"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.

Этот проект НЕ содержит и НЕ распространяет никакие ROM-файлы или
защищенные авторским правом материалы. Все ROM-файлы должны быть
законно приобретены пользователем самостоятельно.

Этот инструмент разработан исключительно для исследовательских целей,
обучения и реверс-инжиниринга в рамках, разрешенных законодательством.
"""

"""
Диалог каталога общедоступных плагинов (Community Plugin Registry).

Показывает плагины из удалённого registry.json, позволяет устанавливать,
обновлять и удалять их локально. Сетевые операции выполняются в фоновых
потоках; UI обновляется через win.after с защитой от закрытия окна.
"""

import logging
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from core.community_registry import CommunityRegistry, CommunityRegistryError
from gui import theme, widgets

logger = logging.getLogger("gb2text.gui.community_plugins")


class CommunityPluginsDialog:
    """Модальный диалог каталога общедоступных плагинов."""

    def __init__(self, parent, owner, registry: CommunityRegistry | None = None,
                 grab: bool = True):
        self.owner = owner
        plugins_dir = getattr(owner, "plugin_dir", None) or Path("plugins")
        self.registry = registry or CommunityRegistry(plugins_dir=plugins_dir)
        self.plugins: list[dict] = []
        self.updates: set[str] = set()
        self._busy = False

        self.win = tk.Toplevel(parent)
        self.win.title(owner.i18n.t("plugins.community.title"))
        self.win.geometry("760x480")
        self.win.minsize(500, 320)
        self.win.transient(parent)
        if grab:
            self.win.grab_set()
        widgets.apply_window_icon(self.win)

        frame = ttk.Frame(self.win, padding=theme.SPACING["MD"])
        frame.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(
            value=owner.i18n.t("plugins.community.fetching"))
        ttk.Label(frame, textvariable=self.status_var).pack(
            anchor="w", pady=(0, theme.SPACING["SM"]))

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, theme.SPACING["SM"]))
        self._action_buttons = []
        for key, command in (
            ("plugins.community.install", self._on_install),
            ("plugins.community.update", self._on_update),
            ("plugins.community.uninstall", self._on_uninstall),
            ("plugins.community.refresh", self._refresh),
        ):
            btn = ttk.Button(toolbar, text=owner.i18n.t(key),
                             command=command)
            btn.pack(side="left", padx=theme.SPACING["XS"])
            self._action_buttons.append(btn)
        ttk.Button(toolbar, text=owner.i18n.t("cancel"),
                   command=self.win.destroy).pack(
            side="right", padx=theme.SPACING["XS"])

        columns = ("name", "author", "version", "status", "type")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")
        self.tree.heading("name", text=owner.i18n.t("plugins.community.name"))
        self.tree.heading("author", text=owner.i18n.t("plugins.community.author"))
        self.tree.heading("version", text=owner.i18n.t("plugins.community.version"))
        self.tree.heading("status", text=owner.i18n.t("plugins.community.status"))
        self.tree.heading("type", text=owner.i18n.t("plugins.community.type"))
        self.tree.column("name", width=220, anchor="w")
        self.tree.column("author", width=120, anchor="w")
        self.tree.column("version", width=80, anchor="center")
        self.tree.column("status", width=140, anchor="w")
        self.tree.column("type", width=80, anchor="center")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._on_install())

        theme.apply(self.win, theme.is_dark())
        self._refresh()

    def run(self):
        self.win.wait_window(self.win)

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        for button in self._action_buttons:
            button.configure(state=state)

    def _safe_after(self, func, *args):
        """win.after с защитой от уничтожения окна во время потока."""

        def _wrapped():
            try:
                func(*args)
            except tk.TclError:
                logger.debug("Окно закрыто во время callback — пропущен")

        try:
            self.win.after(0, _wrapped)
        except tk.TclError:
            logger.debug("Окно закрыто до планирования callback — пропущен")

    def _refresh(self):
        """Загружает registry в фоновом потоке и обновляет таблицу."""
        if self._busy:
            return
        self._set_busy(True)
        self.status_var.set(self.owner.i18n.t("plugins.community.fetching"))
        threading.Thread(target=self._load_registry, daemon=True).start()

    def _load_registry(self):
        try:
            plugins = self.registry.fetch_registry()
        except CommunityRegistryError as exc:
            self._safe_after(self._on_load_error, str(exc))
            return
        updates = {p["id"] for p in self.registry.check_updates(plugins)}
        self._safe_after(self._populate, plugins, updates)

    def _on_load_error(self, error: str):
        self._set_busy(False)
        self.status_var.set(self.owner.i18n.t(
            "plugins.community.no_connection", error=error))
        messagebox.showwarning(
            self.owner.i18n.t("warning.title"),
            self.owner.i18n.t("plugins.community.no_connection", error=error),
            parent=self.win,
        )

    def _populate(self, plugins: list[dict], updates: set[str]):
        self.plugins = plugins
        self.updates = updates
        self.tree.delete(*self.tree.get_children())
        installed = self.registry.get_installed()
        for plugin in plugins:
            plugin_id = plugin["id"]
            entry = installed.get(plugin_id)
            if entry is None:
                status = self.owner.i18n.t("plugins.community.not_installed")
            elif plugin_id in updates:
                status = self.owner.i18n.t("plugins.community.update_available")
            else:
                status = self.owner.i18n.t("plugins.community.installed")
            plugin_type = plugin.get("type", "json")
            self.tree.insert("", "end", iid=plugin_id, values=(
                plugin.get("name", plugin_id),
                plugin.get("author", ""),
                plugin.get("version", ""),
                status,
                plugin_type,
            ))
        self._set_busy(False)
        if not plugins:
            self.status_var.set(self.owner.i18n.t("plugins.community.empty"))
        else:
            self.status_var.set(self.owner.i18n.t(
                "plugins.community.total", count=len(plugins)))

    def _selected_plugin(self) -> dict | None:
        selection = self.tree.selection()
        if not selection:
            return None
        plugin_id = selection[0]
        for plugin in self.plugins:
            if plugin.get("id") == plugin_id:
                return plugin
        return None

    def _on_install(self):
        if self._busy:
            return
        plugin = self._selected_plugin()
        if plugin is None:
            return
        self._start_install(plugin)

    def _on_update(self):
        if self._busy:
            return
        plugin = self._selected_plugin()
        if plugin is None:
            return
        self._start_install(plugin)

    def _start_install(self, plugin: dict):
        """Общий путь установки/обновления в фоновом потоке."""
        if plugin.get("type") == "python":
            ok = messagebox.askyesno(
                self.owner.i18n.t("warning.title"),
                self.owner.i18n.t("plugins.community.python_warning"),
                parent=self.win,
            )
            if not ok:
                return
        self.set_busy(True)
        self.status_var.set(self.owner.i18n.t("plugins.community.installing",
                                               name=plugin.get("name", "")))
        plugin_id = plugin.get("id", "")
        threading.Thread(target=self._do_install, args=(plugin_id,),
                         daemon=True).start()

    def _do_install(self, plugin_id: str):
        plugin = next((p for p in self.plugins if p.get("id") == plugin_id), None)
        if plugin is None:
            self._safe_after(self._set_busy, False)
            return
        try:
            self.registry.install(plugin)
        except Exception as exc:
            self._safe_after(self._on_install_error, str(exc))
            return
        self._safe_after(self._on_install_done)

    def _on_install_done(self):
        self.owner.reload_plugin_manager()
        self.owner.set_status(self.owner.i18n.t("plugins.community.installed_ok"))
        self.updates = {p["id"] for p in self.registry.check_updates(self.plugins)}
        self._populate(self.plugins, self.updates)

    def _on_install_error(self, error: str):
        self._set_busy(False)
        self.status_var.set(error)
        messagebox.showerror(
            self.owner.i18n.t("error.title"),
            error,
            parent=self.win,
        )

    def _on_uninstall(self):
        if self._busy:
            return
        plugin = self._selected_plugin()
        if plugin is None:
            return
        plugin_id = plugin.get("id", "")
        if not self.registry.is_installed(plugin_id):
            return
        ok = messagebox.askyesno(
            self.owner.i18n.t("warning.title"),
            self.owner.i18n.t("plugins.community.confirm_uninstall",
                              name=plugin.get("name", plugin_id)),
            parent=self.win,
        )
        if not ok:
            return
        self._set_busy(True)
        threading.Thread(target=self._do_uninstall, args=(plugin_id,),
                         daemon=True).start()

    def _do_uninstall(self, plugin_id: str):
        try:
            self.registry.uninstall(plugin_id)
        except Exception as exc:
            self._safe_after(self._on_install_error, str(exc))
            return
        self._safe_after(self._on_uninstall_done)

    def _on_uninstall_done(self):
        self._set_busy(False)
        self.owner.reload_plugin_manager()
        self.owner.set_status(self.owner.i18n.t("plugins.community.uninstalled_ok"))
        self.updates = {p["id"] for p in self.registry.check_updates(self.plugins)}
        self._populate(self.plugins, self.updates)
