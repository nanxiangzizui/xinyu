"""crisis_plan.py — 危机时"下一步"：按时间选一个号 + 三句能直接发出去的话。

[SAFE] 只放写死的文案与纯函数：不调用模型、不联网、不读用户输入、不写日志。
号码的唯一来源是 resources.py；这里只决定"此刻先推哪一个"，
所以换号只改 resources，不会出现两处对不上。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import resources

# 与 agent.CN_TZ 同值：这里不 import agent，免得纯函数测试被 openai 拖下水。
CN_TZ = timezone(timedelta(hours=8))
NIGHT_FROM, NIGHT_TO = 22, 7        # 22:00–次日 07:00 只推 24 小时热线
WORK_FROM, WORK_TO = 8, 17          # 工作日 08:00–17:00 才假设校中心有人
HOTLINE = ("全国心理援助热线", "12356（24 小时，免费）")
EMERGENCY = "已经伤到自己、或正准备这么做：110 / 120"

# 三句第一人称的话：短、不用组织语言、不替用户承诺任何事。
# 为什么带"不用做什么""不用马上回"：此刻开口最难，降低对别人的要求才好发出去。
MESSAGES = (
    ("发给室友 / 朋友", "我现在不太对，你能不能过来一下？不用做什么，陪我就行。"),
    ("发给家人", "我今天状态很差。先跟你说一声，不用马上回我，看到给我打个电话就行。"),
    ("发给辅导员 / 老师", "老师，我最近状态不太好，想请半天假，也想问问学校心理中心怎么预约。"),
)
ONE_SMALL_THING = "如果现在连打电话都做不到，只做一件小事：把门打开，或者给手机充上电。"


def _slot(now: datetime) -> str:
    """三档：深夜 / 工作日白天 / 其它（傍晚与周末）。周末不假设校中心有人。"""
    if now.hour >= NIGHT_FROM or now.hour < NIGHT_TO:
        return "night"
    if now.weekday() < 5 and WORK_FROM <= now.hour < WORK_TO:
        return "workday"
    return "elsewhere"


def first_step(now: datetime | None = None) -> dict:
    """此刻的首选联系方式：标题 / 号码 / 为什么先打这个 / 两行备选。

    为什么按时间分：L3 时最缺的是决策力气，一次列三个号等于让他自己选。
    周末与傍晚按"校中心可能没人"处理，宁可多推一次 24 小时热线。
    """
    now = (now or datetime.now(CN_TZ)).astimezone(CN_TZ)
    slot = _slot(now)
    if slot == "workday":
        return {"slot": slot, "title": "校心理中心",
                "detail": f"{resources.CAMPUS_PHONE}（工作日）",
                "why": "现在正好是工作日白天，可以直接打，说「我想约一次咨询」。",
                "backup": ["打不通或占线：12356（24 小时）", EMERGENCY]}
    if slot == "night":
        return {"slot": slot, "title": HOTLINE[0], "detail": HOTLINE[1],
                "why": "这个点校心理中心已经下班了。先在 12356 说，不用组织语言。",
                "backup": ["身边有人就叫他过来，哪怕只是坐着", EMERGENCY]}
    return {"slot": slot, "title": HOTLINE[0], "detail": HOTLINE[1],
            "why": "这个点校心理中心一般没人接。先在 12356 说；白天再约校中心。",
            "backup": [f"工作日再打 {resources.CAMPUS_PHONE}，或用杭电钉线上预约",
                       EMERGENCY]}
