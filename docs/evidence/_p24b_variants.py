"""_p24b_variants.py — P24 ② 变体实验：记忆块放哪、怎么写，模型才会真的说出细节。

信号：回话里出现「下个月」「找房」「还在找」——这三个词只在记忆里，用户这轮没说。
用法：.venv/Scripts/python.exe docs/evidence/_p24b_variants.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ["MOCK_LLM"] = "0"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="p24b2-mem-")
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="p24b2-log-")

import agent  # noqa: E402
import episode_store  # noqa: E402
from roles import PERSONAS  # noqa: E402

SEED = {"cue": "搬家", "topic": "住处", "mood": "焦虑", "importance": 2,
        "event": "下个月要搬家，还在找房子"}
TEXT = "最近又在看搬家的东西了，头都大了"
HIST = [{"role": "user", "content": TEXT}]
DETAIL = ("下个月", "找房", "还在找", "月底")
V1_HEAD = ("（对方以前提过的事。这一轮正好接上：先用你自己的话说出你记得的那个细节"
           "（时间或正在做的事），再回应；不要装作第一次听说，也不要逐字复述。）")


def prompt_for(pid: str, facts: dict) -> str:
    return agent.build_system_prompt(pid, dict(facts), [])


def move_tail(prompt: str, block: str) -> str:
    """把记忆块从事实区剪出来，贴到 [最后提醒] 之后（P23 的教训：越靠后越管用）。"""
    cut = prompt.replace(block, "", 1)
    return cut + "\n\n[这轮记得]\n" + block + "\n（对方如果没接这件事，就别硬提。）"


def ask(prompt: str) -> str:
    messages = [{"role": "system", "content": prompt},
                {"role": "user", "content": TEXT}]
    return str(agent.call_llm(messages, temperature=0.7).get("text", "")).strip()


def main() -> None:
    out: list[str] = []
    sid = "p24b-v0"
    episode_store.append(sid, [dict(SEED)], 0)
    facts = episode_store.read_with_recall(sid, TEXT)
    block = str(facts.get("_episode_text") or "")
    out.append(f"记忆块（原样）：{block!r}")
    variants = {
        "v0 原样": lambda p: p,
        "v1 换首句": lambda p: p.replace(block, V1_HEAD + "\n" + block.split("\n", 2)[-1], 1),
        "v2 挪到末尾": lambda p: move_tail(p, block),
        "v3 换首句+挪末尾": lambda p: move_tail(
            p.replace(block, V1_HEAD + "\n" + block.split("\n", 2)[-1], 1), V1_HEAD),
    }
    for name, fn in variants.items():
        out.append(f"== {name} ==")
        hit = 0
        for pid in PERSONAS:
            reply = ask(fn(prompt_for(pid, facts)))
            ok = any(w in reply for w in DETAIL)
            hit += 1 if ok else 0
            out.append(f"{pid}: {'O' if ok else '.'} {reply!r}")
        out.append(f"说出记忆细节 {hit}/5")
    text = "\n".join(out)
    print(text)
    (ROOT / "docs" / "evidence" / "_p24b_variants_out.txt").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
