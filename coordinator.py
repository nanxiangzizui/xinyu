"""coordinator.py — 三角色状态机 + 会话聚合 + 只升不降。"""
from __future__ import annotations

from roles import COOLDOWN, N_WINDOW


def coordinator_decide(memory: dict, user_text: str, level: str) -> dict:
    """S02 空壳：永远 listener。S11 实现状态机。"""
    return {"role": "listener", "reason": "default"}
