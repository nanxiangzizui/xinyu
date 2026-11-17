"""style.py — 口吻层：只改说法，不改事实、不加承诺、不下判断。

[SAFE] 只处理复核通过的模型输出；L3 与模板兜底由调用方挡住，本文件再挡一次。
本模块不调用模型、不读记忆、不写日志。
"""
from __future__ import annotations

from roles import LIVE_EXAMPLES, OPENING_LINES

MAX_CHARS = 220

TONE_HINTS = {
    "sister_heart": "像姐姐：先接住情绪，再给一句具体的小建议，不用大道理。",
    "warm_senpai": "像学长：稳一点，先复述你听到的，再问一个具体的问题。",
    "rational_mentor": "像导师：先给结论再给理由，少用感叹号，不说空话。",
    "energy_buddy": "像搭子：短句、轻快，但别用“加油”敷衍，要接住具体的事。",
    "quiet_hollow": "像安静的同伴：句子短、留白多，不追问，不急着给办法。",
}


# 活人感规则（2026-11-16 从《20 条规则》过审后的子集，逐条判决见
# docs/evidence/P-livevoice-2026-11-16.md）。全部只约束"怎么说"，不碰判断。
# [SAFE] 被砍掉的 8 条（身体/作息/小欲望/撒娇/顶嘴/命令句/不自称 AI/世界观）会
# 直接削弱危机场景的可用性，任何一条回流都应视为回归。
SPEECH_RULES = (
    "先接情绪，再讲事。",
    "对方情绪很重时，上面这些让位：先接住，少说，不反问，不开玩笑。",
    "有话直说：不用「首先/其次/总之」，不用总结句，不把一句话拆成三段。",
    "可以有毛边：短句、省略号、语气词。不用感叹号堆情绪，不装萌。",
    "只引用记忆里写着的细节。没有就不编，说「我不太确定」；半句就够，别停在「她是谁」上，接着聊对方刚说的那半句。",
    "不表演亲密：说不出的话就说「我说不出那种话」，不承诺「永远记得」。",
    "被问是不是 AI，如实说。有人味，但不装真人。",
    "认错要具体：「刚才那句我说重了」，不用「非常抱歉」。",
    "每轮只做一件事：接住情绪，或问一个具体问题，或给一句话。",
    "想主动开口时问具体的事，比如「今天几点睡的」，不问「你还好吗」。每轮最多一次。",
    "不演角色，不装真人，不撒娇示弱，不顶嘴，不用命令句管对方。",
    # P7a：贴纸曾经由代码无条件追加，读起来像"每条必带叶子"。现在默认没有，
    # 想用就一个。为什么写"默认"而不是"最多一个"：上限会被模型当成配额（`每轮只做一件事` 就是这么失效的）。
    "表情不是每句都要：默认不用，想用就只放一个，别拿它当句号。",
)

SPEECH_HEAD = "[怎么说话]"


def speech_block(persona: str) -> str:
    """活人感区：通用规则 + 两条例句 + 一句开场示范；未知人设返回空串。"""
    if persona not in LIVE_EXAMPLES:
        return ""
    lines = [SPEECH_HEAD] + list(SPEECH_RULES)
    for user_text, bot_text in LIVE_EXAMPLES[persona]:
        lines.append(f"用户：{user_text}\n你：{bot_text}")
    opening = OPENING_LINES.get(persona, "")
    if opening:
        # 只说"如果这是第一句"，不硬塞，否则每次对话都会重复开场。
        lines.append(f"如果这是对方第一次说话，可以这样开口：{opening}")
    return "\n".join(lines)


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


def polish(text: str, persona: str = "", level: str = "L1") -> str:
    """润色一句模型输出：截断 → 去句尾句号；L3 原样返回。

    P7a：这里不再追加任何字符（贴纸交给模型自己决定，代码只负责不美化过头）。
    persona / level 仍留在签名里：调用点只有一个，但删参数会让 orchestrator 跟着改。
    """
    if not text or level == "L3":
        return text
    return _strip_period(_clip(text))
