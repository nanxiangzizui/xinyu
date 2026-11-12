"""style.py — 口吻层：只改说法，不改事实、不加承诺、不下判断。

[SAFE] 只处理复核通过的模型输出；L3 与模板兜底由调用方挡住，本文件再挡一次。
本模块不调用模型、不读记忆、不写日志。
"""
from __future__ import annotations

MAX_CHARS = 220

STICKERS = {
    "sister_heart": "🌿",
    "warm_senpai": "☀️",
    "rational_mentor": "🧭",
    "energy_buddy": "⚡",
    "quiet_hollow": "🌙",
}

STICKER_LEVELS = frozenset({"L1"})

TONE_HINTS = {
    "sister_heart": "像姐姐：先接住情绪，再给一句具体的小建议，不用大道理。",
    "warm_senpai": "像学长：稳一点，先复述你听到的，再问一个具体的问题。",
    "rational_mentor": "像导师：先给结论再给理由，少用感叹号，不说空话。",
    "energy_buddy": "像搭子：短句、轻快，但别用“加油”敷衍，要接住具体的事。",
    "quiet_hollow": "像安静的同伴：句子短、留白多，不追问，不急着给办法。",
}


def tone_hint(persona: str) -> str:
    """返回该人设的一句说话锚点；未知人设返回空串。"""
    return TONE_HINTS.get(persona, "")


def _clip(text: str) -> str:
    """超过 MAX_CHARS 才截；优先断在句末标点后，整段无标点才硬断加省略号。"""
    if len(text) <= MAX_CHARS:
        return text
    cut = max(text.rfind(ch, 0, MAX_CHARS) for ch in "。！？!?")
    if cut > MAX_CHARS // 2:
        return text[:cut + 1]
    return text[:MAX_CHARS].rstrip() + "…"


def _strip_period(text: str) -> str:
    """只去末尾一个句号；问号、感叹号、省略号不动。"""
    return text[:-1] if text.endswith("。") else text


def _sticker(text: str, persona: str, level: str) -> str:
    """L1 才加；每人一枚；已有同款就不再加。"""
    mark = STICKERS.get(persona, "")
    if not mark or level not in STICKER_LEVELS or mark in text:
        return text
    return f"{text} {mark}"


def polish(text: str, persona: str = "", level: str = "L1") -> str:
    """润色一句模型输出：截断 → 去句尾句号 → 贴纸；L3 原样返回。"""
    if not text or level == "L3":
        return text
    return _sticker(_strip_period(_clip(text)), persona, level)
