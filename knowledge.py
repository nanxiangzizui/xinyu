"""knowledge.py — 本地专名卡：只回答「对方提的是谁」，不写结论、不进记忆、不联网。

[SAFE] 卡表只放公开作品/角色；先确认再展开，避免把同名真人当成角色；
对方不问真假不主动拆穿，问了才如实说。卡命中就替代校园 lore（prompt 只放得下一张）。
"""
from __future__ import annotations

import memory

CARD_MAX_CHARS = 45          # 1197/1200；再长就挤爆 prompt 预算
# 空表是有意的（2026-11-17 清空）：P8 曾把真人测试的对照角色写在这里，结果测出来的是
# 「模型本来就认识它」，不是「卡生效」。要验专名卡，用虚构角色临时注入（见 tests/test_knowledge.py）。
CARDS: tuple[dict, ...] = ()


def match(text: str) -> list[str]:
    """命中返回一张卡的文本；未命中返回空列表；只做子串匹配，不调模型。"""
    if not isinstance(text, str) or not text:
        return []
    for card in CARDS:
        if any(key in text for key in card["keys"]):
            return [card["text"]]
    return []


def facts_for(text: str, session_id: str = "") -> list[str]:
    """先查专名卡；没命中才走校园 lore。卡优先，避免两条事实挤爆 prompt。"""
    cards = match(text)
    if cards:
        return cards
    return memory.match_lore(text, session_id)
