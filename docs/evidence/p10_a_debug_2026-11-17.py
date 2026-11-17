"""调试 A 抽取为什么 0 条：复放探针对话，打印模型原始 JSON 与逐条闸门结果。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["MOCK_LLM"] = "0"

import agent
import episode_store
import memory_extract

TURNS = [
    "我下个月要搬家，最近一直在收拾东西。",
    "今天收拾到以前的照片，有点感慨。",
    "新住处离公司近一点，通勤能省半小时。",
    "不过搬家那几天应该会很乱。",
    "希望搬完能睡个好觉。",
]
REPLIES = [
    "我在。今天想先说哪件事？",
    "收拾东西挺磨人的，一件件翻出来，心里也跟着乱。今天收拾到哪儿了？",
    "照片这东西，翻着翻着就停下来了。是哪一段的旧时光，让你多看了几眼？",
    "半小时，一年下来能省不少时间。照片里那些，是舍不得，还是只是感慨？",
    "乱就乱那几天，过去了就好。照片里是哪个时候的你？",
]

history = []
for user_text, reply in zip(TURNS[:4], REPLIES[:4]):
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})

lines, user_blob, _ = memory_extract._blobs(history, TURNS[4], REPLIES[4])
print("LINES:\n" + "\n".join(lines))
print("USER_BLOB:", user_blob)
out = agent.call_llm([{"role": "system", "content": memory_extract.A_SYS},
                      {"role": "user", "content": "\n".join(lines)}],
                     temperature=0.0)
print("OK:", out.get("ok"), "ERR:", out.get("error"))
raw = str(out.get("text") or "")
print("RAW:", raw)
parsed = memory_extract.parse_a(raw, user_blob)
print("PARSED:", parsed)
try:
    items = json.loads(raw).get("episodes") or []
except Exception as exc:
    print("JSON_ERR:", type(exc).__name__)
    items = []
for item in items:
    print("ITEM:", item)
    print("CLEAN:", episode_store.clean_episode(item))
    if episode_store.clean_episode(item):
        ep = episode_store.clean_episode(item)
        print("cue_in_blob:", ep["cue"] in user_blob,
              "quote:", episode_store.quotes_source(ep["event"], [user_blob]),
              "names:", episode_store.names_in(user_blob))
