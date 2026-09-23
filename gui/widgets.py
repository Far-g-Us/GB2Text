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
    try:  # pragma: no cover
        base = getattr(sys, "_MEIPASS", None) or os.path.abspath(".")  # pragma: no cover
        resources_dir = Path(base) / "resources"  # pragma: no cover
        if not resources_dir.exists():  # pragma: no cover
            return  # pragma: no cover
  # pragma: no cover
        png_path = resources_dir / "app_icon.png"  # pragma: no cover
        ico_path = resources_dir / "app_icon.ico"  # pragma: no cover
  # pragma: no cover
        if ico_path.exists() and platform.system() == "Windows":  # pragma: no cover
            try:  # pragma: no cover
                win.iconbitmap(str(ico_path))  # pragma: no cover
                return  # pragma: no cover
            except tk.TclError:  # pragma: no cover
                pass  # pragma: no cover
  # pragma: no cover
        if png_path.exists():  # pragma: no cover
            img = tk.PhotoImage(file=str(png_path))  # pragma: no cover
            win._icon_ref = img  # pragma: no cover
            win.iconphoto(True, img)  # pragma: no cover
    except Exception as e:  # pragma: no cover
        logger.debug("Не удалось поставить иконку окна: %s", e)  # pragma: no cover
  # pragma: no cover
