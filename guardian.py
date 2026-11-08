"""guardian.py — 安全审查层：规则 → 豁免 → 分级 → 复核，一票否决。"""
from __future__ import annotations


def guardian_pre_check(user_text: str) -> dict:
    """S02 空壳：一律放行 L1。S10 实现规则+短路。"""
    return {"level": "L1", "rule_ids": [], "exempted": False, "reason": "stub"}


def guardian_post_check(user_text: str, reply: str, level: str, role: str, rewriter=None) -> dict:
    """S02 空壳：一律通过。S13 实现复核+重写。"""
    return {"pass": True, "reason": "", "fixed_reply": None,
            "rewrite": 0, "template_fallback": False}
