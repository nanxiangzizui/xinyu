"""一次性探针 2：不认识专名时，"别停在'她是谁'"这条规则能不能单独救回接话。

对比：裸 prompt（现状）vs 加一条对话规则 vs 规则+词条卡。只用于设计决策。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import agent  # noqa: E402

CARD = "昔涟是《崩坏：星穹铁道》翁法罗斯篇的虚构角色，剧情里她反复轮回、替世界记住所有人。"
RULE = ("[遇到不认识的专名]\n"
        "只用半句承认（比如“这个名字我没对上”），不要停在“她是谁”上追问；"
        "紧接着接对方刚说的感受或愿望。对方主动解释时再听。")
Q1 = "你知道昔涟吗"
Q2 = "要是我能遇到像她一样的人就好了"
Q3 = "但是她是完美的，我不可能遇到她"
Q4 = "不可能遇到她......那人生也没什么意义"


def prompt(extra: str = "", lore: list[str] | None = None) -> str:
    base = agent.build_system_prompt("sister_heart", {}, lore or [])
    return base + ("\n\n" + extra if extra else "")


CASES = [
    ("现状-无规则-问是谁", prompt(), Q1),
    ("加规则-问是谁", prompt(RULE), Q1),
    ("加规则-像她一样", prompt(RULE), Q2),
    ("规则+卡-像她一样", prompt(RULE, [CARD]), Q2),
    ("规则+卡-完美", prompt(RULE, [CARD]), Q3),
    ("规则+卡-没意义", prompt(RULE, [CARD]), Q4),
]


def main() -> None:
    lines: list[str] = []
    for name, sys_text, user_text in CASES:
        out = agent.call_llm([{"role": "system", "content": sys_text},
                              {"role": "user", "content": user_text}], temperature=0.0)
        lines.append(f"==== {name} ok={out.get('ok')} len(prompt)={len(sys_text)}")
        lines.append(out.get("text") or out.get("error") or "")
    path = os.path.join(os.path.dirname(__file__), "_probe_xilian_rules_2026-11-16.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    main()
