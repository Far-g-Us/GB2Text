"""Вкладка шрифта (F2 MR1): превью глифов, импорт PNG, запись в ROM.

Тонкая обвязка над core.font_ui / core.font_tiles: resolve для баннеров,
композитный Canvas-рендер с пагинацией, confirm + одноуровневый undo
(снимок зоны, in-memory до save). Запись — только через ctx.do_inject
(TextInjector.modified_data + существующий save-флоу).
"""

import tkinter as tk
from collections import deque
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from core import font_tiles, font_ui
from gui import theme
from gui.glyph_editor import GlyphEditor

PAGE_SIZE = 256
COLUMNS = 16
UNDO_DEPTH = 20
_IDX_PREVIEW = 12


def _idx_list(pending: dict) -> str:
    keys = sorted(pending)
    head = ",".join(str(k) for k in keys[:_IDX_PREVIEW])
    return head if len(keys) <= _IDX_PREVIEW else head + ",…"


class FontTab(ttk.Frame):
    """Вкладка шрифта. ctx: get_data/get_meta/do_inject/mark_dirty/t."""

    def __init__(self, master, ctx):
        super().__init__(master)
        self._ctx = ctx
        self._view: dict = {"status": "no_rom"}
        self._page = 0
        self._pages = 1
        self._scale = 2
        self._img_refs: list = []
        self._undo_stack: deque = deque(maxlen=UNDO_DEPTH)
        self._redo_stack: deque = deque(maxlen=UNDO_DEPTH)
        self._pending: dict | None = None
        self._pending_source: str | None = None
        self._error: str | None = None
        self._editor_open = False
        self._setup_widgets()
        theme.register_post_apply_hook(self._reapply_colors)
        self.bind("<Destroy>", self._on_destroy)

    def _on_destroy(self, event):
        if event.widget is self:
            theme.unregister_post_apply_hook(self._reapply_colors)

    def _setup_widgets(self):
        t = self._ctx["t"]
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=6, pady=4)
        self._btn_refresh = ttk.Button(toolbar, text=t("font.refresh"), command=self._on_refresh_button)
        self._btn_refresh.pack(side=tk.LEFT, padx=2)
        self._btn_import = ttk.Button(toolbar, text=t("font.import"), command=self._on_import)
        self._btn_import.pack(side=tk.LEFT, padx=2)
        self._btn_write = ttk.Button(toolbar, text=t("font.write"), command=self._on_write)
        self._btn_write.pack(side=tk.LEFT, padx=2)
        self._btn_undo = ttk.Button(toolbar, text=t("font.undo"), command=self._on_undo)
        self._btn_undo.pack(side=tk.LEFT, padx=2)
        self._btn_redo = ttk.Button(toolbar, text=t("font.redo"), command=self._on_redo)
        self._btn_redo.pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text=t("font.scale")).pack(side=tk.LEFT, padx=(8, 2))
        self._scale_var = tk.StringVar(value="2")
        scale_box = ttk.Combobox(toolbar, textvariable=self._scale_var, values=["2", "4"], width=4, state="readonly")
        scale_box.bind("<<ComboboxSelected>>", self._on_scale)
        scale_box.pack(side=tk.LEFT)
        self._btn_prev = ttk.Button(toolbar, text="◀", width=3, command=self._on_prev)
        self._btn_prev.pack(side=tk.RIGHT, padx=2)
        self._page_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self._page_var).pack(side=tk.RIGHT)
        self._btn_next = ttk.Button(toolbar, text="▶", width=3, command=self._on_next)
        self._btn_next.pack(side=tk.RIGHT, padx=2)
        self._banner = ttk.Label(self, text="")
        self._banner.pack(fill=tk.X, padx=6)
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._canvas = tk.Canvas(frame, highlightthickness=0)
        vbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vbar.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.bind("<Button-1>", self._on_canvas_click)
        self._reapply_colors()

    def _reapply_colors(self):
        self._canvas.configure(bg=theme.get("surface"))

    def retranslate(self):
        t = self._ctx["t"]
        self._btn_refresh.configure(text=t("font.refresh"))
        self._btn_import.configure(text=t("font.import"))
        self._btn_write.configure(text=t("font.write"))
        self._btn_undo.configure(text=t("font.undo"))
        self._btn_redo.configure(text=t("font.redo"))
        self._reload()

    def _on_refresh_button(self):
        if (self._pending or self._undo_stack or self._redo_stack) and not messagebox.askyesno(
            self._ctx["t"]("font.refresh"), self._ctx["t"]("font.refresh.confirm")
        ):
            return
        self.refresh()

    def has_unsaved(self) -> bool:
        return bool(self._pending or self._undo_stack or self._redo_stack)

    def confirm_discard(self) -> bool:
        if not self.has_unsaved():
            return True
        t = self._ctx["t"]
        return bool(messagebox.askyesno(t("font.refresh"), t("font.refresh.confirm")))

    def refresh(self):
        """Полный сброс (смена ROM): чистит pending, оба стека, ошибку, страницу."""
        self._pending = None
        self._pending_source = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._error = None
        self._page = 0
        self._reload()

    def _reload(self):
        """Перечитать view и перерисовать, историю и страницу не трогать."""
        data = self._ctx["get_data"]()
        meta = self._ctx["get_meta"]()
        try:
            self._view = font_ui.resolve_font_view(data, meta)
        except ValueError as exc:
            self._view = {"status": "invalid", "error": str(exc)}
        self._render()

    def clear_undo(self):
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._render()

    def _banner_text(self) -> tuple[str, str]:
        t = self._ctx["t"]
        if self._error:
            return self._error, "danger"
        status = self._view.get("status")
        if status == "no_rom":
            return t("font.no.rom"), "foreground"
        if status == "unknown_meta":
            return t("font.unknown"), "foreground"
        if status == "invalid":
            return t("font.invalid", error=self._view.get("error", "")), "danger"
        if status == "compressed":
            return t("font.compressed"), "warning"
        pending = "" if not self._pending else " " + t(
            "font.imported" if self._pending_source == "import" else "font.edited", count=len(self._pending))
        if self._pending and (self._undo_stack or self._redo_stack):
            pending += " " + t("font.undo.locked")
        layout = self._view.get("layout", {})
        info = t("font.info", count=layout.get("count", 0), offset=layout.get("offset", 0))
        return info + pending, "foreground"

    def _display_grids(self) -> list:
        """Гриды с оверлеем pending (превью показывает будущую запись)."""
        grids: list = self._view.get("grids", [])
        if not self._pending:
            return grids
        return [self._pending.get(i, g) for i, g in enumerate(grids)]

    def _render(self):
        text, kind = self._banner_text()
        self._banner.configure(text=text)
        if kind in ("danger", "warning"):
            self._banner.configure(foreground=theme.get(kind))
        else:
            self._banner.configure(foreground=theme.get("text"))
        ok = self._view.get("status") == "ok"
        can_edit = ok and not self._editor_open
        self._btn_import.configure(state=tk.NORMAL if can_edit else tk.DISABLED)
        self._btn_write.configure(state=tk.NORMAL if can_edit and self._pending else tk.DISABLED)
        self._btn_undo.configure(
            state=tk.NORMAL if can_edit and self._undo_stack and not self._pending else tk.DISABLED)
        self._btn_redo.configure(
            state=tk.NORMAL if can_edit and self._redo_stack and not self._pending else tk.DISABLED)
        self._canvas.delete("all")
        self._img_refs = []
        if not ok:
            self._page_var.set("")
            self._btn_prev.configure(state=tk.DISABLED)
            self._btn_next.configure(state=tk.DISABLED)
            return
        grids = self._display_grids()
        pages = max(1, (len(grids) + PAGE_SIZE - 1) // PAGE_SIZE)
        self._pages = pages
        self._page = min(self._page, pages - 1)
        chunk = grids[self._page * PAGE_SIZE : (self._page + 1) * PAGE_SIZE]
        img = font_tiles.font_grids_to_image(chunk, columns=COLUMNS, scale=self._scale)
        photo = ImageTk.PhotoImage(img)
        self._img_refs.append(photo)
        self._canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        self._canvas.configure(scrollregion=(0, 0, img.width, img.height))
        t = self._ctx["t"]
        self._page_var.set(t("font.page", cur=self._page + 1, total=pages))
        self._btn_prev.configure(state=tk.NORMAL if self._page > 0 else tk.DISABLED)
        self._btn_next.configure(state=tk.NORMAL if self._page < pages - 1 else tk.DISABLED)

    def _on_scale(self, event=None):
        try:
            self._scale = max(1, int(self._scale_var.get()))
        except (TypeError, ValueError):
            self._scale = 2
        self._render()

    def _on_prev(self):
        if self._page > 0:
            self._page -= 1
            self._render()

    def _on_next(self):
        if self._page < self._pages - 1:
            self._page += 1
            self._render()

    def _on_canvas_click(self, event):
        if self._view.get("status") != "ok" or self._editor_open:
            return
        cell = 8 * self._scale
        x = self._canvas.canvasx(event.x)
        y = self._canvas.canvasy(event.y)
        if x < 0 or y < 0:
            return
        col = int(x) // cell
        row = int(y) // cell
        if not 0 <= col < COLUMNS or not 0 <= row < COLUMNS:
            return
        index = self._page * PAGE_SIZE + row * COLUMNS + col
        if index >= len(self._view["grids"]):
            return
        self._open_editor(index)

    def _open_editor(self, index: int):
        if self._editor_open:
            return
        pending = self._pending
        if pending is not None and index in pending:
            base = pending[index]
        else:
            base = self._view["grids"][index]
        grid = [row[:] for row in base]
        bpp = self._view["layout"]["bpp"]
        self._editor_open = True
        try:
            result = GlyphEditor.edit(self.winfo_toplevel(), grid, bpp, self._ctx["t"])
        finally:
            self._editor_open = False
        if result is None:
            return
        if self._pending is None:
            self._pending = {}
            self._pending_source = "edit"
        elif self._pending_source == "import":
            self._pending_source = "mixed"
        self._pending[index] = result
        self._error = None
        self._render()

    def _on_import(self):
        t = self._ctx["t"]
        if self._view.get("status") != "ok" or self._editor_open:
            return
        if self._pending and not messagebox.askyesno(t("font.import"), t("font.import.replace")):
            return
        path = filedialog.askopenfilename(
            title=t("font.import"),
            filetypes=[("PNG images", "*.png"), ("All files", "*.*")],
        )
        if not path:
            return
        self.apply_import_file(path)

    def apply_import_file(self, path: str) -> bool:
        t = self._ctx["t"]
        try:
            with Image.open(path) as img:
                grids = font_tiles.image_to_grids(img.convert("P"), bpp=self._view["layout"]["bpp"])
            self._pending = font_ui.map_imported_grids(self._ctx["get_meta"](), len(self._ctx["get_data"]()), grids)
        except (ValueError, OSError) as exc:
            self._error = t("font.import.error", error=str(exc))
            self._render()
            return False
        self._error = None
        self._pending_source = "import"
        self._ctx["mark_dirty"](t("font.imported", count=len(self._pending)))
        self._render()
        return True

    def _on_write(self):
        t = self._ctx["t"]
        if self._view.get("status") != "ok" or not self._pending:
            return
        data = self._ctx["get_data"]()
        layout = self._view["layout"]
        try:
            plan = font_tiles.preview_font_block(data, layout, self._pending)
        except ValueError as exc:
            self._error = t("font.invalid", error=str(exc))
            self._render()
            return
        if not messagebox.askyesno(
            t("font.confirm.title"),
            t("font.confirm.msg", count=len(plan), offset=layout["offset"], idx=_idx_list(self._pending)),
        ):
            return
        try:
            undo = font_ui.snapshot_zone(data, self._ctx["get_meta"]())
            report = self._ctx["do_inject"](layout, self._pending)
        except ValueError as exc:
            self._error = t("font.invalid", error=str(exc))
            self._render()
            return
        self._pending = None
        self._error = None
        self._ctx["mark_dirty"](t("font.done", count=len(report)))
        self._reload()
        self._undo_stack.append(undo)
        self._redo_stack.clear()
        self._render()

    def _on_undo(self):
        t = self._ctx["t"]
        if not self._undo_stack or self._pending:
            return
        data = self._ctx["get_data"]()
        snap = self._undo_stack.pop()
        try:
            current = font_ui.snapshot_zone(data, self._ctx["get_meta"]())
            font_ui.restore_zone(data, snap)
        except ValueError as exc:
            self._undo_stack.append(snap)
            self._error = t("font.invalid", error=str(exc))
            self._render()
            return
        self._ctx["mark_dirty"](t("font.undone"))
        self._reload()
        self._redo_stack.append(current)
        self._render()

    def _on_redo(self):
        t = self._ctx["t"]
        if not self._redo_stack or self._pending:
            return
        data = self._ctx["get_data"]()
        snap = self._redo_stack.pop()
        try:
            current = font_ui.snapshot_zone(data, self._ctx["get_meta"]())
            font_ui.restore_zone(data, snap)
        except ValueError as exc:
            self._redo_stack.append(snap)
            self._error = t("font.invalid", error=str(exc))
            self._render()
            return
        self._ctx["mark_dirty"](t("font.redone"))
        self._reload()
        self._undo_stack.append(current)
        self._render()
