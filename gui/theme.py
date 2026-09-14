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
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable, Sequence
from tkinter import ttk

logger = logging.getLogger("gb2text.gui.theme")

LIGHT = {
    "bg": "#f5f6f8",
    "surface": "#ffffff",
    "border": "#d0d3d8",
    "text": "#1f2328",
    "text-muted": "#5b6470",
    "text-disabled": "#68707c",
    "accent": "#1a6cb5",
    "on-accent": "#ffffff",
    "success": "#1e7e34",
    "warning": "#8a5d00",
    "danger": "#b42318",
    "diff-added-bg": "#e8f5ea",
    "diff-removed-bg": "#f8d7d0",
    "diff-changed-bg": "#f7ecd0",
    "focus-ring": "#1a6cb5",
}

DARK = {
    "bg": "#1e1e1e",
    "surface": "#252526",
    "border": "#3e3e42",
    "text": "#e0e0e0",
    "text-muted": "#9d9d9d",
    "text-disabled": "#8e8e90",
    "accent": "#569cd6",
    "on-accent": "#081420",
    "success": "#73b366",
    "warning": "#dcdcaa",
    "danger": "#f48771",
    "diff-added-bg": "#18341c",
    "diff-removed-bg": "#4a1c16",
    "diff-changed-bg": "#332b1a",
    "focus-ring": "#569cd6",
}

BRAND = {
    "bg": "#2c3e50",
    "fg": "#ecf0f1",
}

SPACING = {
    "XS": 4,
    "SM": 8,
    "MD": 12,
    "LG": 16,
    "XL": 24,
}

FONT_UI = ("Segoe UI", "SF Pro Text", "Noto Sans", "DejaVu Sans", "TkDefaultFont")
FONT_MONO = ("Consolas", "DejaVu Sans Mono", "Courier New", "monospace")

_current = LIGHT
_current_scheme = "light"
_family_cache: dict[str, str] = {}
_post_apply_hooks: list[Callable[[], None]] = []


def register_post_apply_hook(fn: Callable[[], None]) -> None:
    """Регистрирует callback, вызываемый при СМЕНЕ темы (после apply()).

    Нужен для пер-итем стилей, которые не живут в ttk.Style/tk-опциях
    (например, itemconfigure-цвета в Listbox). callback вызывается
    без аргументов и должен читать токены через theme.get().
    """
    if fn not in _post_apply_hooks:
        _post_apply_hooks.append(fn)


def unregister_post_apply_hook(fn: Callable[[], None]) -> None:
    """Удаляет ранее зарегистрированный post-apply hook."""
    if fn in _post_apply_hooks:
        _post_apply_hooks.remove(fn)


def get(name: str) -> str:
    """Возвращает значение токена текущей темы."""
    return _current[name]


def get_tokens() -> dict[str, str]:
    """Возвращает копию словаря токенов активной темы."""
    return dict(_current)


def style_menu(menu, tokens: dict[str, str] | None = None) -> None:
    """Темизирует tk.Menu токенами текущей темы (или переданными)."""
    _style_menu(menu, tokens if tokens is not None else _current)


def is_dark() -> bool:
    """True, если активна тёмная тема."""
    return _current_scheme == "dark"


def _resolve_family(chain: Sequence[str], root: tk.Misc | None = None) -> str:
    key = chain[0] if chain else "default"
    if key in _family_cache:
        return _family_cache[key]

    master = root if root is not None else getattr(tk, "_default_root", None)
    family = chain[0]
    if master is not None:
        try:
            available = set(tkfont.families(master))
            for candidate in chain:
                if candidate in available:
                    family = candidate
                    break
        except tk.TclError:
            pass
    _family_cache[key] = family
    return family


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 2.x контраст-рацио между двумя hex-цветами."""
    l1, l2 = _luminance(fg), _luminance(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def _channel(value: str) -> float:
    return int(value, 16) / 255


def _linearize(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _luminance(color: str) -> float:
    hex_value = color.lstrip('#')
    r, g, b = (_channel(hex_value[i:i + 2]) for i in (0, 2, 4))
    r, g, b = _linearize(r), _linearize(g), _linearize(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ui_font(size: int = 10, weight: str = "normal", root: tk.Misc | None = None):
    """Кортеж (family, size, weight) для UI-текста."""
    return (_resolve_family(FONT_UI, root), size, weight)


def mono_font(size: int = 10, weight: str = "normal", root: tk.Misc | None = None):
    """Кортеж (family, size, weight) для моноширинного текста."""
    return (_resolve_family(FONT_MONO, root), size, weight)


def _iter_widgets(root: tk.Misc):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except (tk.TclError, RuntimeError):
            pass


def _iter_menus(root: tk.Misc):
    for widget in _iter_widgets(root):
        if isinstance(widget, tk.Menu):
            yield widget


def _style_plain(widget, t: dict[str, str]):
    """Стилизация tk.* виджета. widget без аннотации: typeshed не покрывает
    опции конкретных классов (highlightbackground, selectbackground и т.п.)."""
    try:
        cls = widget.winfo_class()
    except (tk.TclError, RuntimeError):
        return

    try:
        if cls == "Frame":
            widget.configure(bg=t["bg"])
        elif cls == "Label":
            widget.configure(bg=t["bg"], fg=t["text"])
        elif cls == "Listbox":
            widget.configure(
                bg=t["surface"],
                fg=t["text"],
                selectbackground=t["accent"],
                selectforeground=t["on-accent"],
                highlightthickness=2,
                highlightcolor=t["focus-ring"],
                highlightbackground=t["border"],
            )
        elif cls in ("Entry", "Spinbox"):
            widget.configure(
                bg=t["surface"],
                fg=t["text"],
                insertbackground=t["text"],
                selectbackground=t["accent"],
                selectforeground=t["on-accent"],
                highlightthickness=2,
                highlightcolor=t["focus-ring"],
                highlightbackground=t["border"],
            )
        elif cls == "Text":
            widget.configure(
                bg=t["surface"],
                fg=t["text"],
                insertbackground=t["text"],
                selectbackground=t["accent"],
                selectforeground=t["on-accent"],
                highlightthickness=2,
                highlightcolor=t["focus-ring"],
                highlightbackground=t["border"],
                font=mono_font(10, root=widget),
            )
        elif cls == "Button":
            widget.configure(
                bg=t["surface"],
                fg=t["text"],
                activebackground=t["border"],
                activeforeground=t["text"],
                highlightthickness=2,
                highlightcolor=t["focus-ring"],
                highlightbackground=t["border"],
            )
        elif cls == "Canvas":
            widget.configure(
                bg=t["surface"],
                highlightthickness=0,
                highlightcolor=t["focus-ring"],
                highlightbackground=t["border"],
            )
        elif cls == "Scrollbar":
            widget.configure(
                bg=t["surface"],
                troughcolor=t["bg"],
                activebackground=t["border"],
                highlightthickness=0,
                borderwidth=0,
            )
    except (tk.TclError, AttributeError):
        pass


def _style_menu(menu, t: dict[str, str]):
    try:
        menu.configure(
            bg=t["surface"],
            fg=t["text"],
            activebackground=t["accent"],
            activeforeground=t["on-accent"],
            selectcolor=t["bg"],
            borderwidth=1,
        )
    except tk.TclError:
        pass


def apply(root: tk.Misc, dark: bool = True):
    """Применяет тему (ttk.Style + рекурсивный обход tk-виджетов).

    Семейства шрифтов резолвятся один раз за время жизни приложения и
    кэшируются в _family_cache: UI не меняет шрифты в рантайме, поэтому
    инвалидация не требуется. Post-apply хуки запускаются только при
    РЕАЛЬНОЙ смене темы (apply(modal, is_dark()) не триггерит их).
    """
    global _current, _current_scheme
    previous = _current
    _current = DARK if dark else LIGHT
    _current_scheme = "dark" if dark else "light"
    t = _current

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        ".",
        background=t["bg"],
        foreground=t["text"],
        fieldbackground=t["surface"],
        font=ui_font(10, root=root),
    )
    style.configure("TFrame", background=t["bg"])
    style.configure("TLabel", background=t["bg"], foreground=t["text"])
    style.map("TLabel", foreground=[("disabled", t["text-disabled"])])
    style.configure("Muted.TLabel", background=t["bg"], foreground=t["text-muted"])
    style.configure("TLabelframe", background=t["bg"], bordercolor=t["border"])
    style.configure("TLabelframe.Label", background=t["bg"], foreground=t["text"])
    style.configure(
        "TButton",
        background=t["surface"],
        foreground=t["text"],
        bordercolor=t["border"],
        focuscolor=t["focus-ring"],
        padding=(4, 2),
    )
    style.map(
        "TButton",
        background=[("pressed", t["border"]), ("active", t["border"])],
        foreground=[("disabled", t["text-disabled"])],
    )
    accent_pressed = "#4680af" if dark else "#165c9a"
    accent_disabled = "#335f84" if dark else "#81aed6"
    style.configure(
        "Accent.TButton",
        background=t["accent"],
        foreground=t["on-accent"],
        bordercolor=t["accent"],
        focuscolor=t["focus-ring"],
        padding=(4, 2),
    )
    style.map(
        "Accent.TButton",
        background=[("pressed", accent_pressed), ("active", accent_pressed)],
        foreground=[("disabled", accent_disabled)],
    )
    style.configure(
        "TMenubutton",
        background=t["surface"],
        foreground=t["text"],
        bordercolor=t["border"],
        focuscolor=t["focus-ring"],
        padding=(4, 2),
        arrowcolor=t["text-muted"],
    )
    style.map(
        "TMenubutton",
        background=[("pressed", t["border"]), ("active", t["border"])],
        foreground=[("disabled", t["text-disabled"])],
    )
    style.configure(
        "TEntry",
        fieldbackground=t["surface"],
        foreground=t["text"],
        bordercolor=t["border"],
        insertcolor=t["text"],
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", t["bg"])],
        foreground=[("disabled", t["text-disabled"])],
    )
    style.configure("TNotebook", background=t["bg"], bordercolor=t["border"], tabmargins=(2, 4, 2, 0))
    style.configure(
        "TNotebook.Tab",
        background=t["surface"],
        foreground=t["text"],
        padding=(10, 4),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", t["accent"])],
        foreground=[("selected", t["on-accent"])],
    )
    style.configure(
        "Treeview",
        background=t["surface"],
        fieldbackground=t["surface"],
        foreground=t["text"],
        bordercolor=t["border"],
        rowheight=24,
    )
    style.map(
        "Treeview",
        background=[("selected", t["accent"])],
        foreground=[("selected", t["on-accent"])],
    )
    style.configure("Treeview.Heading", background=t["border"], foreground=t["text"], relief="flat")
    style.configure(
        "TCombobox",
        fieldbackground=t["surface"],
        background=t["surface"],
        foreground=t["text"],
        arrowcolor=t["text"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", t["surface"])],
        arrowcolor=[("disabled", t["text-disabled"])],
        foreground=[("disabled", t["text-disabled"])],
    )
    style.configure("TCheckbutton", background=t["bg"], foreground=t["text"], focuscolor=t["focus-ring"])
    style.configure("TRadiobutton", background=t["bg"], foreground=t["text"], focuscolor=t["focus-ring"])
    style.configure(
        "TProgressbar",
        background=t["accent"],
        troughcolor=t["border"],
        bordercolor=t["border"],
    )
    style.configure(
        "TSpinbox",
        fieldbackground=t["surface"],
        foreground=t["text"],
        bordercolor=t["border"],
        arrowcolor=t["text"],
    )
    scrollbar_base = {
        "background": t["surface"],
        "troughcolor": t["bg"],
        "bordercolor": t["border"],
        "arrowcolor": t["text-muted"],
    }
    style.configure("Vertical.TScrollbar", **scrollbar_base)
    style.configure("Horizontal.TScrollbar", **scrollbar_base)

    root.option_add("*TCombobox*Listbox.background", t["surface"])
    root.option_add("*TCombobox*Listbox.foreground", t["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", t["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", t["on-accent"])
    root.option_add("*TCombobox*Listbox.borderWidth", 1)
    root.option_add("*TCombobox*Listbox.relief", "flat")
    root.option_add("*TCombobox*Listbox.font", ui_font(10, root=root))

    for widget in _iter_widgets(root):
        _style_plain(widget, t)
    for menu in _iter_menus(root):
        _style_menu(menu, t)

    if _current is previous:
        return

    for hook in _post_apply_hooks:
        try:
            hook()
        except (tk.TclError, RuntimeError, AttributeError, KeyError, TypeError):
            logger.warning("Post-apply theme hook raised", exc_info=True)
