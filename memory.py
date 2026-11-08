"""memory.py — 记忆读写：白名单 / 原子写 / 摘要节流 / 清空 / lore 匹配。"""
from __future__ import annotations


def read_memory(session_id: str) -> dict:
    """S02 空壳：返回空字典，不落盘、不报错。S03 实现白名单读取与损坏恢复。"""
    return {}


def write_memory(session_id: str, data: dict) -> None:
    """S02 空壳：什么都不写。S03 实现 .bak + .tmp + os.replace 原子写。"""
    return None


def update_memory(session_id: str, user_text: str, reply: str) -> dict:
    """S02 空壳：返回空字典。S03 实现 scrub + 白名单更新。"""
    return {}


def clear_memory(session_id: str) -> bool:
    """S02 空壳：返回 False（本步没有可删的文件）。S03 实现真删含备份。"""
    return False


def match_lore(user_text: str, session_id: str = "") -> list[str]:
    """S02 空壳：不命中。S20 实现迷你 Lorebook。"""
    return []
