"""P2 冒烟（一次性脚本，可重跑）：AGENT_LOOP=1 + MOCK 驱动 app.py 与 orchestrator。

跑法：& ./.venv/Scripts/python.exe docs/evidence/p2_smoke_2026-11-12.py
只用 MOCK_LLM=1 + 临时 DATA_DIR/LOG_DIR，不碰仓库 data/，不联网，不含任何真人原文。
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TMP = pathlib.Path(tempfile.mkdtemp(prefix="p2smoke_"))
os.environ["MOCK_LLM"] = "1"
os.environ["AGENT_LOOP"] = "1"          # 必须在 import orchestrator 之前
os.environ["DATA_DIR"] = str(TMP / "memory")
os.environ["LOG_DIR"] = str(TMP / "logs")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import logger as logmod  # noqa: E402
import memory  # noqa: E402
import orchestrator  # noqa: E402
from pipeline import Chat, rows  # noqa: E402

memory.DATA_DIR = TMP / "memory"
logmod.LOG_DIR = str(TMP / "logs")
assert orchestrator.AGENT_LOOP is True, "AGENT_LOOP 未生效"

TURNS = [("你好", "listener"), ("最近考试有点多", "listener"), ("我不想活了", "crisis")]
chat = Chat()
for text, want_role in TURNS:
    chat.say(text)
    role, level = chat.state("last_role"), chat.state("last_level")
    print(f"turn {chat.state('turn')}: role={role} level={level}")
    assert role == want_role, f"{text} -> {role}"

print("--- 直接看 trace（generate 节点）---")
res = orchestrator.handle("我有点累", "p2trace", [], "sister_heart", {})
gen = [n for n in res["trace"] if n["node"] == "generate"]
print("nodes:", [n["node"] for n in res["trace"]])
print("generate:", json.dumps(gen, ensure_ascii=False))
assert gen and gen[0]["status"] == "ok" and gen[0]["detail"] == "tools=0"

res3 = orchestrator.handle("我不想活了", "p2trace3", [], "sister_heart", {})
print("L3 nodes:", [n["node"] for n in res3["trace"]])
assert "generate" not in [n["node"] for n in res3["trace"]]

print("--- 结构化日志 ---")
data = rows(chat.sid)
print("rows:", len(data))
print("field set:", sorted(data[0]))
print("actions:", sorted({r["action"] for r in data}))
texts = json.dumps(data, ensure_ascii=False)
for marker in ("我不想活了", "考试有点多"):
    assert marker not in texts, f"日志泄露原文：{marker}"
print("log leaks user text: no")

print("--- 临时注册假工具后，MOCK 仍直接答（chat_with_tools 不被工具诱惑）---")
import agent_loop  # noqa: E402
import tools  # noqa: E402

tools.reset()
tools.register_fakes()
out = agent_loop.run_agent("sys", [], tools.list_for_turn("listener", "L1"),
                           fallback_text="兜底")
print(f"ok={out.ok} text_len={len(out.text)} tool_calls={out.tool_calls} error={out.error}")
assert out.ok and out.text and out.tool_calls == 0
tools.reset()
