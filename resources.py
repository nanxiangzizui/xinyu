"""resources.py — 情绪 → 资源卡（纯函数，不做网络与界面）。"""
from __future__ import annotations

# [SAFE] 资源表写死：不许联网查、不许让 LLM 生成。热线写错一个数字就是安全事故。
# 顺序即展示顺序；L1 不给资源（避免打扰）。
RESOURCES = {
    "L3": [
        {"title": "全国心理援助热线", "detail": "12356（24 小时，免费）", "kind": "hotline"},
        {"title": "紧急求助", "detail": "110 / 120", "kind": "emergency"},
        {"title": "校心理中心", "detail": "0571-87713518（工作日）", "kind": "campus"},
    ],
    "L2": [
        {"title": "校心理中心", "detail": "0571-87713518（工作日）", "kind": "campus"},
        {"title": "呼吸练习", "detail": "吸气 4 秒，停 2 秒，呼气 6 秒，重复 5 次", "kind": "exercise"},
    ],
    "L1": [],
}


def pick_resources(level: str, emotion_tags: list[str]) -> list[dict]:
    """按等级返回资源卡；L1 不给资源（避免打扰）。

    emotion_tags 本步不用，保留签名是为了 S20 之后能按标签细分
    （如“睡眠”给睡眠卫生卡片）。不要为了用而硬塞。
    返回浅拷贝：调用方 append 不会污染 RESOURCES。
    """
    return list(RESOURCES.get(level, []))
