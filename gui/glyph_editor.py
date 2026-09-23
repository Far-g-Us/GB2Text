"""Модальный попиксельный редактор глифа 8x8 (MR2).

ЛКМ красит выбранным значением (повторный клик по той же ячейке циклит
дальше), ПКМ сбрасывает в 0, палитра задаёт выбранное. Яркость превью
нормирована на maxval (не in-game палитра). Strictly modal: transient +
grab + wait_window, закрытие окна = Cancel.
"""

import tkinter as tk
from functools import partial
from tkinter import messagebox, ttk

from gui import theme

CELL = 24


class GlyphEditor(tk.Toplevel):
    """Редактор одного глифа. result: грид 8x8 после OK, None после Cancel."""

    def __init__(self, master, grid, bpp, t):
        super().__init__(master)
        self.title(t("font.editor.title"))
        self._t = t
        self._maxval = (1 << bpp) - 1
        self._step = 255 // self._maxval
        self._grid = [row[:] for row in grid]
        self._initial = [row[:] for row in grid]
        self._sel = self._maxval
        self.result = None
        self._cells: dict[tuple[int, int], int] = {}
        self._build()
        self._mark_sel()
        self.bind("<Return>", lambda event: self._on_ok())
        self.bind("<Escape>", lambda event: self._on_cancel())
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.focus_set()

    @classmethod
    def edit(cls, master, grid, bpp, t):
        dlg = cls(master, grid, bpp, t)
        dlg.grab_set()
        dlg.wait_window()
        return dlg.result

    def _color(self, value: int) -> str:
        level = value * self._step
        return f"#{level:02x}{level:02x}{level:02x}"

    def _build(self):
        body = ttk.Frame(self, padding=8)
        body.pack()
        self._canvas = tk.Canvas(
            body, width=8 * CELL, height=8 * CELL, highlightthickness=1,
            highlightbackground=theme.get("border"), bg=theme.get("surface"),
        )
        self._canvas.pack()
        for r in range(8):
            for c in range(8):
                item = self._canvas.create_rectangle(
                    c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL,
                    fill=self._color(self._grid[r][c]), outline=theme.get("border"),
                )
                self._cells[(r, c)] = item
        self._canvas.bind("<Button-1>", self._on_paint)
        self._canvas.bind("<Button-3>", self._on_erase)
        pal = ttk.Frame(body)
        pal.pack(pady=(8, 0))
        self._pal_buttons: list = []
        for value in range(self._maxval + 1):
            btn = ttk.Button(pal, text=str(value), width=4, command=partial(self._pick, value))
            btn.grid(row=value // 8, column=value % 8, padx=1, pady=1)
            self._pal_buttons.append(btn)
        bar = ttk.Frame(body)
        bar.pack(pady=(8, 0))
        ttk.Button(bar, text=self._t("font.editor.ok"), command=self._on_ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text=self._t("cancel"), command=self._on_cancel).pack(side=tk.LEFT, padx=4)

    def _pick(self, value: int):
        self._sel = value
        self._mark_sel()

    def _mark_sel(self):
        for btn, val in zip(self._pal_buttons, range(self._maxval + 1), strict=True):
            btn.configure(text=f"[{val}]" if val == self._sel else str(val))

    def _paint_at(self, row: int, col: int, value: int):
        self._grid[row][col] = value
        self._canvas.itemconfigure(self._cells[(row, col)], fill=self._color(value))

    def _on_paint(self, event):
        col = int(self._canvas.canvasx(event.x)) // CELL
        row = int(self._canvas.canvasy(event.y)) // CELL
        if not 0 <= col < 8 or not 0 <= row < 8:
            return
        if self._grid[row][col] == self._sel:
            self._sel = (self._sel + 1) % (self._maxval + 1)
            self._mark_sel()
        self._paint_at(row, col, self._sel)

    def _on_erase(self, event):
        col = int(self._canvas.canvasx(event.x)) // CELL
        row = int(self._canvas.canvasy(event.y)) // CELL
        if 0 <= col < 8 and 0 <= row < 8:
            self._paint_at(row, col, 0)

    def _on_ok(self):
        self.result = [row[:] for row in self._grid]
        self.destroy()

    def _on_cancel(self):
        if self._grid != self._initial and not messagebox.askyesno(
            self._t("font.editor.title"), self._t("font.editor.discard")
        ):
            return
        self.result = None
        self.destroy()
