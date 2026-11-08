"""theme.py — 三套配色（樱花 / 抹茶 / 落日）：只改颜色与圆角，不改布局与字号。"""
from __future__ import annotations

import streamlit as st

# 三套都过对比度检查（正文 text 对 bg / surface ≥ 4.5:1）：色值只在这里改。
THEMES: dict[str, dict[str, str]] = {
    "sakura": {"bg": "#FFF7F8", "surface": "#FFE9EC", "text": "#3D3230",
               "accent": "#F7A8B8", "border": "#F3CBD3"},
    "matcha": {"bg": "#F7FAF5", "surface": "#E8F0E3", "text": "#2F3A2C",
               "accent": "#A8C69F", "border": "#CFE0C6"},
    "sunset": {"bg": "#FFF9F4", "surface": "#FBEEE6", "text": "#3D3230",
               "accent": "#FF9E6B", "border": "#F6D3BE"},
}
THEME_LABELS = {"sakura": "樱花", "matcha": "抹茶", "sunset": "落日"}
DEFAULT_THEME = "sakura"
MESSAGE_RADIUS = "16px"


def theme_css(key: str) -> str:
    """返回一套 CSS 变量；未知 key 回落默认主题（样式失败不许影响对话）。"""
    c = THEMES.get(key, THEMES[DEFAULT_THEME])
    return (
        "<style>\n"
        ":root {"
        f"--xy-bg:{c['bg']}; --xy-surface:{c['surface']}; --xy-text:{c['text']};"
        f" --xy-accent:{c['accent']}; --xy-border:{c['border']};"
        "}\n"
        ".stApp { background: var(--xy-bg); color: var(--xy-text); }\n"
        "[data-testid=\"stChatMessage\"] {"
        f" background: var(--xy-surface); border-radius: {MESSAGE_RADIUS};"
        "}\n"
        "</style>"
    )


def inject_theme(key: str) -> None:
    """注入一次主题 CSS。只改颜色与圆角，不引外部字体与 CDN。"""
    st.markdown(theme_css(key), unsafe_allow_html=True)


def theme_picker() -> str:
    """侧栏选择配色；存 session_state，选中即本轮生效。"""
    with st.sidebar:
        return st.radio("配色", list(THEMES), index=0,
                        format_func=lambda k: THEME_LABELS.get(k, k),
                        key="theme")


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 对比度，供测试与证据表使用；只接受 #RRGGBB。"""
    def _lum(hex_color: str) -> float:
        raw = hex_color.lstrip("#")
        channels = [int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4)]

        def _lin(v: float) -> float:
            return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

        r, g, b = (_lin(v) for v in channels)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    hi, lo = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)
