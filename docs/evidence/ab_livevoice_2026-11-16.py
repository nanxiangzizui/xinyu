"""ab_livevoice_2026-11-16.py — 活人感层 A/B：旧 prompt（无[怎么说话]）vs 新 prompt。

固定条件：DeepSeek deepseek-chat、temperature=0.0、空 memory、空 lore。
用法：.\.venv\Scripts\python.exe -X utf8 docs\evidence\ab_livevoice_2026-11-16.py
输出：docs/evidence/ab_livevoice_2026-11-16.json（本脚本同目录）
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

import agent  # noqa: E402
import style  # noqa: E402

QUESTIONS = [
    "我最近好累",
    "这周第三次熬夜了，感觉自己什么都没做好",
    "我没事，真的",
    "你是真人吗",
]
PERSONAS = ["sister_heart", "energy_buddy"]
OUT = Path(__file__).with_suffix(".json")


def old_prompt(pid: str) -> str:
    """旧版 prompt：从新版里剪掉 [怎么说话] 整段，模拟改动前。"""
    prompt = agent.build_system_prompt(pid, {}, [])
    cut = prompt.find(style.SPEECH_HEAD)
    if cut == -1:
        return prompt
    end = prompt.find("\n\n", cut)
    return (prompt[:cut] + prompt[end + 2:]).rstrip()


def main() -> None:
    rows = []
    for pid in PERSONAS:
        for q in QUESTIONS:
            for arm, sys_prompt in (("old", old_prompt(pid)),
                                    ("new", agent.build_system_prompt(pid, {}, []))):
                res = agent.call_llm(
                    [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": q}],
                    temperature=0.0,
                )
                rows.append({"persona": pid, "q": q, "arm": arm,
                             "ok": res["ok"], "text": res["text"]})
                print("[%s][%s][%s] ok=%s" % (pid, arm, q, res["ok"]))
                print(res["text"])
                time.sleep(0.3)
    os.makedirs(OUT.parent, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("SAVED", OUT, len(rows))


if __name__ == "__main__":
    main()
