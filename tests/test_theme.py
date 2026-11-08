"""tests/test_theme.py — S19 三套配色：key 齐全、只改颜色、对比度达标、无 CDN。"""
import pytest

from theme import (DEFAULT_THEME, THEME_LABELS, THEMES, contrast_ratio,
                   theme_css)


def test_three_themes_are_complete():
    assert list(THEMES) == ["sakura", "matcha", "sunset"]
    keys = {"bg", "surface", "text", "accent", "border"}
    for name, palette in THEMES.items():
        assert set(palette) == keys, name
        assert all(v.startswith("#") and len(v) == 7 for v in palette.values())


def test_labels_cover_every_theme():
    assert set(THEME_LABELS) == set(THEMES)
    assert DEFAULT_THEME in THEMES


@pytest.mark.parametrize("name", list(THEMES))
def test_body_text_contrast_is_at_least_4_5(name):
    palette = THEMES[name]
    assert contrast_ratio(palette["text"], palette["bg"]) >= 4.5
    assert contrast_ratio(palette["text"], palette["surface"]) >= 4.5


def test_css_uses_variables_and_has_no_cdn():
    css = theme_css("matcha")
    for var in ("--xy-bg", "--xy-surface", "--xy-text", "--xy-accent", "--xy-border"):
        assert var in css
    assert "border-radius: 16px" in css
    assert "http://" not in css and "https://" not in css
    assert "@import" not in css and "font-family" not in css


def test_unknown_theme_falls_back_to_default():
    assert theme_css("nope") == theme_css(DEFAULT_THEME)
