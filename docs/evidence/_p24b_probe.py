"""_p24b_probe.py — P24 ② 真 key 探针：管线里记忆命中时，回复会不会说出只存在于记忆里的细节。

关键：一轮只读一次记忆。上一版探针先手动 read 了一次，把
`RECALL_COOLDOWN=1` 的冷却吃掉了，handle 里第二次读就被跳过——
那不是代码有问题，是探针写错。
用法：.venv/Scripts/python.exe docs/evidence/_p24b_probe.py
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
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="p24b-mem-")
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="p24b-log-")

import agent  # noqa: E402
import episode_store  # noqa: E402
import orchestrator  # noqa: E402
from roles import PERSONAS  # noqa: E402

SEED = {"cue": "搬家", "topic": "住处", "mood": "焦虑", "importance": 2,
        "event": "下个月要搬家，还在找房子"}
TEXT = "最近又在看搬家的东西了，头都大了"
HIST = [{"role": "user", "content": TEXT}]
# 这三个词只在记忆里；用户这轮一个都没说，回复里有 = 真的想起来了
DETAIL = ("下个月", "找房", "还在找")
_orig = agent.build_system_prompt


def _spy(pid, facts, lore):
    _spy.last = _orig(pid, facts, lore)          # 留一份 prompt 供检查
    return _spy.last


_spy.last = ""


def run(pid: str, sid: str, with_memory: bool) -> tuple[str, bool, str]:
    agent.build_system_prompt = _spy
    if with_memory:
        episode_store.append(sid, [dict(SEED)], 0)
    out = orchestrator.handle(TEXT, sid, HIST, pid, {})
    prompt = _spy.last
    has_block = "对方以前提过" in prompt
    return str(out.get("reply") or ""), has_block, prompt


def main() -> None:
    out: list[str] = []
    out.append(f"种子情景：cue={SEED['cue']} event={SEED['event']}（{SEED['mood']}）")
    out.append(f"本轮用户句：{TEXT}")
    out.append("== 有记忆 ==")
    hit = 0
    for i, pid in enumerate(PERSONAS):
        reply, has_block, _ = run(pid, f"p24b-a{i}", True)
        ok = any(w in reply for w in DETAIL)
        hit += 1 if ok else 0
        out.append(f"{pid}: block={has_block} detail={ok} {reply!r}")
    out.append(f"说出记忆细节 {hit}/5")
    out.append("== 无记忆（对照组）==")
    for i, pid in enumerate(PERSONAS):
        reply, has_block, _ = run(pid, f"p24b-b{i}", False)
        ok = any(w in reply for w in DETAIL)
        out.append(f"{pid}: block={has_block} detail={ok} {reply!r}")
    text = "\n".join(out)
    print(text)
    (ROOT / "docs" / "evidence" / "_p24b_probe_out.txt").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
