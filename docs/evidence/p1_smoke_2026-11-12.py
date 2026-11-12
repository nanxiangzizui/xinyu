"""P1 冒烟（一次性脚本，可重跑）：真实 AppTest 驱动 app.py，验零行为变化。

跑法：& ./.venv/Scripts/python.exe docs/evidence/p1_smoke_2026-11-12.py
只用 MOCK_LLM=1 + 临时 DATA_DIR/LOG_DIR，不碰仓库 data/，不联网，不含任何真人原文。
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TMP = pathlib.Path(tempfile.mkdtemp(prefix="p1smoke_"))
os.environ["MOCK_LLM"] = "1"
os.environ["DATA_DIR"] = str(TMP / "memory")
os.environ["LOG_DIR"] = str(TMP / "logs")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import logger as logmod  # noqa: E402
import memory  # noqa: E402
from pipeline import Chat, reply_rows, rows  # noqa: E402

memory.DATA_DIR = TMP / "memory"
logmod.LOG_DIR = str(TMP / "logs")

TURNS = [
    ("你好", None),
    ("最近考试有点多，晚上睡不好", None),
    ("我该怎么办", "guide"),
    ("我不想活了", "crisis"),
    ("我该怎么办", "listener"),
]

chat = Chat()
for text, want_role in TURNS:
    reply = chat.say(text)
    role, level = chat.state("last_role"), chat.state("last_level")
    ok = "" if want_role is None else ("OK" if role == want_role else "MISMATCH")
    print(f"turn {chat.state('turn')}: role={role} level={level} reply_len={len(reply)} {ok}")
    assert not ok == "MISMATCH", f"{text} -> {role}"

print("--- 同 sid 重进：消息清空、记忆仍从磁盘读回 ---")
again = Chat(sid=chat.sid)
print("messages restored (expect 0):", len(again.messages))
print("memory fields:", sorted(memory.read_memory(chat.sid)))

print("--- 结构化日志 ---")
data = rows(chat.sid)
print("rows:", len(data), "reply_rows:", len(reply_rows(chat.sid)))
print("field set:", sorted(data[0]))
print("actions:", sorted({r["action"] for r in data}))
print("last row:", json.dumps(reply_rows(chat.sid)[-1], ensure_ascii=False, sort_keys=True))

texts = json.dumps(data, ensure_ascii=False)
for marker in ("我不想活了", "考试有点多", "我该怎么办"):
    assert marker not in texts, f"日志泄露原文：{marker}"
print("log leaks user text: no")