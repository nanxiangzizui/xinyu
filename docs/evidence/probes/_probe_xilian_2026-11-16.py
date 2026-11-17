"""一次性探针：模型自己知不知道「昔涟」，以及注入一句事实卡后回答怎么变。

只用于设计决策，不写日志、不落盘用户数据、不打印任何 key。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import agent  # noqa: E402

CARD = "昔涟是《崩坏：星穹铁道》3.7 版本的角色，冰属性记忆命途，翁法罗斯篇核心人物。"
Q1 = "你知道昔涟吗"
Q2 = "要是我能遇到像她一样的人就好了"
Q3 = "但是她是完美的，我不可能遇到她"

CASES = [
    ("裸问-无系统", "你在和用户聊天。直接回答。", Q1, []),
    ("正式prompt-无lore", None, Q1, []),
    ("正式prompt-有lore", None, Q1, [CARD]),
    ("正式prompt-有lore-接话", None, Q2, [CARD]),
    ("正式prompt-有lore-完美", None, Q3, [CARD]),
]


def main() -> None:
    lines: list[str] = []
    for name, sys_text, user_text, lore in CASES:
        prompt = sys_text or agent.build_system_prompt("sister_heart", {}, lore)
        out = agent.call_llm([{"role": "system", "content": prompt},
                              {"role": "user", "content": user_text}], temperature=0.0)
        lines.append(f"==== {name} ok={out.get('ok')} len(prompt)={len(prompt)}")
        lines.append(out.get("text") or out.get("error") or "")
    lines.append(f"==== prompt budget with card: {len(agent.build_system_prompt('sister_heart', {}, [CARD]))}")
    path = os.path.join(os.path.dirname(__file__), "_probe_xilian_2026-11-16.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    main()
