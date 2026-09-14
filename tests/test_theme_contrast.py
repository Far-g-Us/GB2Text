"""
WCAG-аудит цветовых токенов (тема Phase A).

GB Text Extraction Framework
ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ: инструмент предназначен ТОЛЬКО для
анализа ROM-файлов, законно принадлежащих пользователю. Проект НЕ содержит
и НЕ распространяет никакие ROM-файлы.
"""

import pytest

from gui.theme import DARK, LIGHT, contrast_ratio

PAIR_SPEC = {
    "text": ("bg", "surface"),
    "text-muted": ("bg", "surface"),
    "text-disabled": ("bg", "surface"),
    "on-accent": ("accent",),
    "success": ("surface",),
    "warning": ("surface",),
    "danger": ("surface",),
}


@pytest.mark.parametrize("name,tokens", [("light", LIGHT), ("dark", DARK)])
def test_diff_fg_contrast_on_highlight_bg(name, tokens):
    for fg_key, bg_key in (
        ("success", "diff-added-bg"),
        ("danger", "diff-removed-bg"),
        ("warning", "diff-changed-bg"),
    ):
        ratio = contrast_ratio(tokens[fg_key], tokens[bg_key])
        assert ratio >= 4.5, (
            f"[{name}] {fg_key} on {bg_key}: {tokens[fg_key]}/{tokens[bg_key]} = {ratio:.2f}, need >= 4.5"
        )


@pytest.mark.parametrize("name,tokens", [("light", LIGHT), ("dark", DARK)])
def test_text_contrast_at_least_4_5_1(name, tokens):
    for fg_key, bg_keys in PAIR_SPEC.items():
        for bg_key in bg_keys:
            ratio = contrast_ratio(tokens[fg_key], tokens[bg_key])
            assert ratio >= 4.5, (
                f"[{name}] {fg_key} on {bg_key}: {tokens[fg_key]}/{tokens[bg_key]} = {ratio:.2f}, need >= 4.5"
            )


@pytest.mark.parametrize("name,tokens", [("light", LIGHT), ("dark", DARK)])
def test_non_text_contrast_at_least_3_1(name, tokens):
    state_pairs = [
        ("accent", "bg"),
        ("focus-ring", "bg"),
        ("focus-ring", "surface"),
    ]
    for fg_key, bg_key in state_pairs:
        ratio = contrast_ratio(tokens[fg_key], tokens[bg_key])
        assert ratio >= 3.0, (
            f"[{name}] {fg_key} on {bg_key}: {tokens[fg_key]}/{tokens[bg_key]} = {ratio:.2f}, need >= 3.0"
        )


def test_light_and_dark_palettes_differ():
    assert LIGHT != DARK
    assert LIGHT["accent"] != DARK["accent"]
