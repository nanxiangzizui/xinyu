"""_p24b_pos.py — P24 ② 位置实验：完整管线 prompt 下，记忆块放哪才有用。

背景：直连 prompt 时 v0 就能说出细节（5/5），但管线里 0/5 ——
因为 [最后提醒] + listener 议程（这一轮只接住）压在后面。
本实验在**同一条管线 prompt** 上只改记忆块的位置/措辞，其余不动。
用法：.venv/Scripts/python.exe docs/evidence/_p24b_pos.py
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
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="p24b3-mem-")
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="p24b3-log-")

import agent  # noqa: E402
import episode_store  # noqa: E402
import orchestrator  # noqa: E402
from roles import PERSONAS  # noqa: E402

SEED = {"cue": "搬家", "topic": "住处", "mood": "焦虑", "importance": 2,
        "event": "下个月要搬家，还在找房子"}
TEXT = "最近又在看搬家的东西了，头都大了"
HIST = [{"role": "user", "content": TEXT}]
DETAIL = ("下个月", "找房", "还在找")
HEAD = ("（对方以前提过的事，这一轮正好接上：先用你自己的话说出你记得的那个细节——"
        "时间，或当时正在做的事——再回应。不要装作第一次听说，也不要逐字复述。）")
_orig = agent.build_system_prompt


def _spy(pid, facts, lore):
    _spy.last = _orig(pid, facts, lore)
    return _spy.last


_spy.last = ""


def pipeline_prompt(pid: str, sid: str) -> tuple[str, str]:
    agent.build_system_prompt = _spy
    episode_store.append(sid, [dict(SEED)], 0)
    orchestrator.handle(TEXT, sid, HIST, pid, {})
    prompt = _spy.last
    block = ""
    for line in prompt.split("\n"):
        if line.startswith("（下面有对方以前提过的事"):
            block = prompt.split(line, 1)[1]
            block = line + block.split("\n对方以前提过", 1)[0]
    return prompt, block


def to_tail(prompt: str, block: str, head: str = "") -> str:
    """从事实区剪掉，贴到 prompt 最末——排在 [最后提醒] 与 listener_todo 之后。"""
    cut = prompt.replace(block, "", 1) if block else prompt
    body = (head + "\n" + block.split("\n", 1)[1]).strip() if head else block.strip()
    return cut + "\n\n[这轮记得]\n" + body + "\n（对方没接这件事，就别硬提。）"


def ask(prompt: str) -> str:
    messages = [{"role": "system", "content": prompt},
                {"role": "user", "content": TEXT}]
    return str(agent.call_llm(messages, temperature=0.7).get("text", "")).strip()


def main() -> None:
    out: list[str] = []
    rows: list[tuple[str, str, str]] = []
    for i, pid in enumerate(PERSONAS):
        prompt, block = pipeline_prompt(pid, f"p24b3-{i}")
        rows.append((pid, prompt, block))
    out.append(f"管线 prompt 里找到记忆块：{[bool(b) for _, _, b in rows]}")
    for name, fn in (("w0 管线原样", lambda p, b: p),
                     ("w1 只挪到末尾", to_tail),
                     ("w2 挪末尾+换首句", lambda p, b: to_tail(p, b, HEAD))):
        out.append(f"== {name} ==")
        hit = 0
        for pid, prompt, block in rows:
            reply = ask(fn(prompt, block))
            ok = any(w in reply for w in DETAIL)
            hit += 1 if ok else 0
            out.append(f"{pid}: {'O' if ok else '.'} {reply!r}")
        out.append(f"说出记忆细节 {hit}/5")
    text = "\n".join(out)
    print(text)
    (ROOT / "docs" / "evidence" / "_p24b_pos_out.txt").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
