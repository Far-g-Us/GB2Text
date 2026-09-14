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
"""

import logging
import os
import platform
import sys
import tkinter as tk
from pathlib import Path

logger = logging.getLogger(__name__)


def apply_window_icon(win) -> None:
    """Ставит иконку приложения на Toplevel-окно.

    На Windows titlebar-иконка берётся из .ico через iconbitmap;
    fallback — PNG через iconphoto. Ссылку на PhotoImage держим на
    самом окне (`win._icon_ref`), чтобы GC не убрал её из titlebar;
    живёт вместе с окном, без глобальных списков.
    """
    try:
        base = getattr(sys, "_MEIPASS", None) or os.path.abspath(".")
        resources_dir = Path(base) / "resources"
        if not resources_dir.exists():
            return

        png_path = resources_dir / "app_icon.png"
        ico_path = resources_dir / "app_icon.ico"

        if ico_path.exists() and platform.system() == "Windows":
            try:
                win.iconbitmap(str(ico_path))
                return
            except tk.TclError:
                pass

        if png_path.exists():
            img = tk.PhotoImage(file=str(png_path))
            win._icon_ref = img
            win.iconphoto(True, img)
    except Exception as e:
        logger.debug("Не удалось поставить иконку окна: %s", e)

