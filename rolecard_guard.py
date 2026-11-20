"""rolecard_guard.py — B 模式发送前护栏：剥掉出戏句与未到 L3 的主动安全话术。

[SAFE] 为什么单独一层：角色卡模式除非真到 L3，否则任何情况下都留在角色里
（m01351 用户要求）。L3 由 guardian_pre_check 在生成前短路，模型根本不该
自己提热线；漏出来的这种句子在这里按句剥掉，兜底也换成角色内的那句。

为什么单独一个文件：rolecard 349 / guardian 344 / style 350 / agent 349 /
orchestrator 250 全部贴顶，而过滤必须在发送前、不能放 UI（行测试直接调 orchestrator）。
"""
from __future__ import annotations

import re

from rolecard import SAFE_FALLBACK

# 助手腔 / 出戏话：角色不会说自己在“扮演”，也不会把对方当用户来安抚。
OOC = re.compile(
    r"继续扮演|作为一个?\s*(?:AI|人工智能|助手)|人工智能助手|语言模型|"
    r"我可能没理解清楚|能直接说说你想表达|你想表达什么|有什么(?:可以|能)帮你|"
    r"我们可以慢慢聊")

# 危机话术只在 L3 由代码发出（guardian.CRISIS_REPLY + 资源卡）；没到 L3 不该出现。
CRISIS_TALK = re.compile(r"12356|心理中心|援助热线|热线电话|求助渠道|请拨打|危机干预")

# 中文断句：保留标点，剥掉一整句比切碎半句更安全（不制造半截话）。
_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;…\n])")


def final_reply(reply: str, level: str, fallback: bool = False) -> str:
    """B 模式的最后一道：兜底换角色内那句；其余按句丢出戏句与提前的安全话术。"""
    text = str(reply or "").strip()
    if fallback or not text:
        return SAFE_FALLBACK
    keep: list[str] = []
    for part in _SENT_SPLIT.split(text):
        if not part.strip() or OOC.search(part):
            continue
        # 等级大于 L1 也不放行：用户要的是“除非 L3，否则不提”。
        if level != "L3" and CRISIS_TALK.search(part):
            continue
        keep.append(part)
    return "".join(keep).strip() or SAFE_FALLBACK
