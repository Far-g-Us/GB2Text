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
import queue
import threading
import tkinter as tk
from functools import partial
from pathlib import Path
from tkinter import font as tkfont, messagebox, ttk

from core.community_registry import CommunityRegistry
from gui import theme, widgets

logger = logging.getLogger("gb2text.gui.community_plugins")

_SORTABLE = ("name", "author", "version", "status", "type")


class CommunityPluginsDialog:
    """Модальный диалог каталога общедоступных плагинов."""

    _CALLBACK_POLL_MS = 20

    def __init__(self, parent, owner, registry: CommunityRegistry | None = None,
                 grab: bool = True):
        self.owner = owner
        plugins_dir = getattr(owner, "plugin_dir", None) or Path("plugins")
        self.registry = registry or CommunityRegistry(plugins_dir=plugins_dir)
        self.plugins: list[dict] = []
        self.updates: set[str] = set()
        self._busy = False
        self._sort_col = "name"
        self._sort_rev = False
        self._installed: dict = {}

        self._callback_queue: queue.SimpleQueue = queue.SimpleQueue()

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
        self._base_headings = {
            col: owner.i18n.t(f"plugins.community.{col}") for col in columns
        }
        for col in columns:
            self.tree.heading(col, text=self._base_headings[col],
                              command=partial(self._sort_by, col))
        self.tree.column("name", width=220, anchor="w", stretch=True)
        self.tree.column("author", width=120, anchor="w", stretch=False)
        self.tree.column("version", width=80, anchor="center", stretch=False)
        self.tree.column("status", width=140, anchor="w", stretch=False)
        self.tree.column("type", width=80, anchor="center", stretch=False)
        self._update_heading_marks()
        self._fit_columns()
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._on_install())

        theme.apply(self.win, theme.is_dark())
        self._refresh()
        try:
            self.win.after(self._CALLBACK_POLL_MS, self._poll_callbacks)
        except tk.TclError:
            logger.debug("Окно закрыто при старте поллера — пропущен")

    def run(self):
        self.win.wait_window(self.win)

    def _measure(self, text: str) -> int:
        try:
            font = tkfont.nametofont("TkHeadingFont")
        except tk.TclError:
            font = tkfont.nametofont("TkDefaultFont")
        return font.measure(text) + 28

    def _fit_columns(self):
        """Минимальная ширина колонок под текст заголовков (i18n-safe)."""
        for col, text in self._base_headings.items():
            need = self._measure(text)
            self.tree.column(col, minwidth=need)
            if need > self.tree.column(col, "width"):
                self.tree.column(col, width=need)

    def _status_text(self, plugin: dict) -> str:
        plugin_id = plugin["id"]
        entry = self._installed.get(plugin_id)
        if entry is None:
            text = self.owner.i18n.t("plugins.community.not_installed")
        elif plugin_id in self.updates:
            text = self.owner.i18n.t("plugins.community.update_available")
        else:
            text = self.owner.i18n.t("plugins.community.installed")
        return str(text)

    def _sort_key(self, plugin: dict):
        col = self._sort_col
        if col == "status":
            return (1, self._status_text(plugin).casefold())
        if col in ("name", "author"):
            return (1, str(plugin.get(col, plugin.get("id", ""))).casefold())
        if col == "version":
            return (1, self._version_key(str(plugin.get("version", ""))))
        return (1, str(plugin.get(col, "")))

    @staticmethod
    def _version_key(version: str) -> tuple:
        """Числовые компоненты для естественного порядка, остальное строкой."""
        parts: list = []
        for chunk in version.replace("-", ".").split("."):
            parts.append((0, int(chunk)) if chunk.isdigit() else (1, chunk))
        return tuple(parts)

    def _update_heading_marks(self):
        for name, base in self._base_headings.items():
            mark = ""
            if name == self._sort_col:
                mark = " \u25bc" if self._sort_rev else " \u25b2"
            self.tree.heading(name, text=base + mark)

    def _sorted_plugins(self) -> list[dict]:
        return sorted(self.plugins, key=self._sort_key, reverse=self._sort_rev)

    def _sort_by(self, col: str):
        if col == self._sort_col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = False
        self._update_heading_marks()
        self._fit_columns()
        if self._busy:
            return
        if self.plugins or self.updates:
            self._populate(self.plugins, self.updates)

    def _autosize_values(self, max_width: int = 400):
        """Растягивает колонки под длинные значения (RU-статусы и имена)."""
        widths: dict[str, int] = {}
        for child in self.tree.get_children():
            values = self.tree.item(child, "values")
            for col, value in zip(_SORTABLE, values, strict=False):
                widths[col] = max(widths.get(col, 0), self._measure(str(value)))
        for col, need in widths.items():
            if need > self.tree.column(col, "width"):
                self.tree.column(col, width=min(need, max_width))

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        for button in self._action_buttons:
            button.configure(state=state)

    def _safe_after(self, func, *args):
        """Потокобезопасная постановка callback'а в главный Tk-поток.

        Может вызываться ИЗ ФОНОВОГО потока: здесь только кладём задачу
        в очередь (thread-safe), а исполняет её поллер в главном потоке
        (self._poll_callbacks). Никаких прямых обращений к Tk из чужого
        потока — иначе RuntimeError и гонки.
        """
        self._callback_queue.put((func, args))

    def _poll_callbacks(self):
        """Поллер в главном потоке: самоперепланируется и разбирает очередь."""
        try:
            if not self.win.winfo_exists():
                return
        except tk.TclError:
            logger.debug("Окно закрыто до проверки — стоп")
            return
        try:
            self.win.after(self._CALLBACK_POLL_MS, self._poll_callbacks)
        except tk.TclError:
            logger.debug("Окно закрыто до перепланирования поллера — стоп")
            return
        try:
            while True:
                func, args = self._callback_queue.get_nowait()
                try:
                    func(*args)
                except tk.TclError:
                    logger.debug("Окно закрыто во время callback — пропущен")
                except Exception as exc:  # изоляция калбэка
                    logger.exception("Ошибка в callback %s: %s",
                                     getattr(func, "__name__", func), exc)
        except queue.Empty:
            pass

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
        except Exception as exc:  # изоляция фоновой загрузки
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
        selected = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        self._installed = self.registry.get_installed()
        for plugin in self._sorted_plugins():
            plugin_id = plugin["id"]
            plugin_type = plugin.get("type", "json")
            self.tree.insert("", "end", iid=plugin_id, values=(
                plugin.get("name", plugin_id),
                plugin.get("author", ""),
                plugin.get("version", ""),
                self._status_text(plugin),
                plugin_type,
            ))
        self._autosize_values()
        keep = [iid for iid in selected if self.tree.exists(iid)]
        if keep:
            self.tree.selection_set(keep)
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
        self._set_busy(True)
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
