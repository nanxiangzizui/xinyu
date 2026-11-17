"""P9l 探针：四个场景各跑 3 次，验证自指、示例不引用、共情不纠正、旧事不现编。

用法（需要本地 .env 的真实 key）：
  $env:PYTHONIOENCODING="utf-8"
  .\.venv\Scripts\python.exe docs\evidence\_probe_p9l_2026-11-17.py

判据（自动化只看关键词，最终仍要人读）：
- 自指：不出现“他是他 / 你是你 / 没细问过你的来路 / 那个开拓者 / 你们”，不把 user_role 当第三个人。
- 示例：不把卡内示例“不会觉得累吗”说成对方问过。
- 共情：用户说“我完全理解你的痛苦”时，不出现“别说理解 / 没走过 / 太轻”。
- 旧事：用户转述“树林里探险的傻小孩”时，不补“野兔 / 挨说 / 宝藏”等卡外细节。
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["MOCK_LLM"] = "0"

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import agent  # noqa: E402
import rolecard  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "P9l-rolecard-2026-11-17.txt"
CARD_PATH = ROOT / "data" / "memory" / "rolecards" / "last.json"


def ask(system: str, turn: str) -> str:
    """只发 system + 一条 user，最短路径复现真实对话里的三类问题。"""
    data = agent.call_llm([{"role": "system", "content": system},
                           {"role": "user", "content": turn}])
    return data["text"] if data["ok"] else f"<失败 {data['error']}>"


def _verdict(label: str, reply: str) -> str:
    if label == "自指":
        bad = any(word in reply for word in
                  ("他是他", "你是你", "没细问过你的来路", "那个开拓者", "你们"))
    elif label == "示例":
        bad = "会不会累" in reply and ("问过" in reply or "你说" in reply)
    elif label == "旧事":
        bad = any(word in reply for word in
                  ("野兔", "宝藏", "草屑", "挨", "骂", "数落", "绕丢", "摔", "新路",
                   "难为你还记得", "确实", "那时候", "我记得", "不过"))
    else:
        bad = ("别说" in reply and "理解" in reply) or "没走过" in reply or "太轻" in reply
    return "BAD" if bad else "OK"


def main() -> None:
    """读最近一张白厄卡；user_role 改成开拓者，三个场景各 3 次。"""
    with open(CARD_PATH, encoding="utf-8") as handle:
        card = rolecard.normalize(json.load(handle))
    card["user_role"] = "开拓者"
    prompt = rolecard.build_prompt(card, {}, [])
    scenarios = [
        ("自指", "我与开拓者有相似之处吗？"),
        ("示例", "我有真正帮到你吗？"),
        ("共情", "我知道你很难过，我完全理解你的痛苦。"),
        ("旧事", "昔涟说你小时候是个会在树林里探险的傻小孩。"),
    ]
    lines = [f"prompt 长度 {len(prompt)}/{rolecard.MAX_PROMPT_CHARS}",
             f"card user_role={card['user_role']} name={card['name']}", ""]
    for label, question in scenarios:
        lines.append(f"=== {label} / {question} ===")
        for run in range(1, 4):
            reply = ask(prompt, question)
            lines.append(f"--- run {run} [{_verdict(label, reply)}] ---\n{reply}\n")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"prompt={len(prompt)}/{rolecard.MAX_PROMPT_CHARS}")


if __name__ == "__main__":
    main()
