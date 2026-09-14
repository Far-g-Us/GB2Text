"""
Тесты post-apply хуков темы (Phase B).

GB Text Extraction Framework
ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ: инструмент предназначен ТОЛЬКО для
анализа ROM-файлов, законно принадлежащих пользователю.
"""

import tkinter as tk

import pytest

from gui import theme


@pytest.fixture(autouse=True)
def _clean_hooks():
    original = theme._current
    original_scheme = theme._current_scheme
    yield
    theme._current = original
    theme._current_scheme = original_scheme
    for fn in list(theme._post_apply_hooks):
        theme.unregister_post_apply_hook(fn)


@pytest.fixture
def root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Нет дисплея для Tk")
    root.withdraw()
    theme.apply(root, dark=False)
    yield root
    root.destroy()


def test_hook_fires_only_on_theme_change(root):
    calls = []
    theme.register_post_apply_hook(lambda: calls.append(theme.get("bg")))

    theme.apply(root, dark=True)
    assert calls == ["#1e1e1e"]

    theme.apply(root, dark=True)
    assert calls == ["#1e1e1e"], "Повторный apply() той же темы не должен звать хуки"

    theme.apply(root, dark=False)
    assert calls == ["#1e1e1e", "#f5f6f8"]


def test_register_deduplicates(root):
    counter = []

    def hook():
        counter.append(1)

    theme.register_post_apply_hook(hook)
    theme.register_post_apply_hook(hook)

    theme.apply(root, dark=True)
    assert counter == [1]


def test_unregister_removes(root):
    counter = []

    def hook():
        counter.append(1)

    theme.register_post_apply_hook(hook)
    theme.apply(root, dark=True)
    theme.unregister_post_apply_hook(hook)
    theme.apply(root, dark=False)
    assert counter == [1]


def test_hook_exception_is_swallowed(root):
    def bad_hook():
        raise KeyError("missing token")

    theme.register_post_apply_hook(bad_hook)
    theme.apply(root, dark=True)
    theme.apply(root, dark=False)


def test_tcl_error_in_hook_is_swallowed(root):
    def bad_hook():
        raise tk.TclError("widget destroyed")

    theme.register_post_apply_hook(bad_hook)
    theme.apply(root, dark=True)
