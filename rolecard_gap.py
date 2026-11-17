"""rolecard_gap.py — B 模式盲点检测：从一句话里认出“卡里没有的专名”。

只做保守识别：必须带“你知道/讲讲/是谁/经历了什么”这类句式，不做通用 NER。
识别不到就不补，避免把普通词当人名去联网。
"""
from __future__ import annotations

import re

import rolecard

_NAME = r"[\u4e00-\u9fa5]{2,4}"
_QUOTED = r"[“「\"]?(" + _NAME + r")[”」\"]?"
FOCUS_PATTERNS = (
    re.compile(r"(?:你知道|你认识|你记得|跟我说说|讲讲|聊聊)\s*" + _QUOTED
               + r"\s*(?:是谁|的经历|经历了什么|的事|吗|么)"),
    re.compile(r"^" + _QUOTED + r"\s*(?:是谁|经历了什么|的经历|的事)"),
    re.compile(r"(?:讲讲|说说|聊聊)\s*" + _QUOTED + r"\s*$"),
)
STOPWORDS = frozenset(
    "什么 怎么 为什么 我们 他们 她们 这个 那个 自己 现在 最近 今天 昨天 明天 可以 知道 认识 觉得 感觉".split())
_BAD_PARTS = ("什么", "怎么", "为什么", "吗", "呢", "吧", "我", "你", "他", "她", "它")
MISSING_MARKERS = ("不知道", "不清楚", "不太清楚", "没听说过", "不太了解", "说不准")
GAP_LABELS = {"story": "经历", "world": "世界", "relationship": "原作关系"}


def gap_lines(facts: list[dict], *, focus: str = "", limit: int = 4) -> list[str]:
    """把盲点事实压成 prompt 里的临时条目；只收经历/世界/关系，最多 4 条。"""
    lines = []
    for fact in facts:
        field = str(fact.get("field") or "")
        text = str(fact.get("text") or "").strip()
        if field not in GAP_LABELS or not text:
            continue
        label = GAP_LABELS[field]
        if focus and field == "story":
            label = f"{focus}的{label}"
        lines.append(f"{label}：{text}"[:rolecard.LORE_ITEM_MAX])
        if len(lines) >= limit:
            break
    return lines


def missing_hint(reply: str) -> bool:
    """模型自己说“不认识”时，给手动补全一个提示；只是提示，不自动联网。"""
    return any(marker in str(reply or "") for marker in MISSING_MARKERS)


def _card_text(card: dict) -> str:
    """把卡里已有的名字/设定/认知拼起来，用来判断“已经知道”。"""
    card = rolecard.normalize(card)
    texts = [str(card.get(key) or "") for key in
             ("name", "identity", "setting", "voice", "address", "user_role")]
    for pair in card.get("examples") or []:
        if isinstance(pair, (list, tuple)):
            texts.extend(str(item) for item in pair)
    texts.extend(str(item) for item in card.get("lore") or [])
    return " ".join(texts)


def detect_focus(text: str, card: dict) -> str:
    """返回卡里没有的专名；识别不到/已存在/像普通词就返回空串。"""
    text = str(text or "").strip()
    known = _card_text(card)
    for pattern in FOCUS_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        name = match.group(1).strip()
        if not name or name in STOPWORDS:
            continue
        if any(part in name for part in _BAD_PARTS):
            continue
        if name in known:
            continue
        return name
    return ""


def should_fill(card: dict, focus: str, *, auto: bool = True,
                mock: bool = False, level: str = "L1") -> bool:
    """自动补全的硬条件：已知卡、非 MOCK、非 L3、有专名、开关开。"""
    return bool(auto and not mock and level != "L3" and focus
                and card.get("origin") == "known")
