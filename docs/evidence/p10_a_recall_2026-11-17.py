"""A 记忆的定向召回探针：重置冷却后直接问“下个月要做什么”，看回复是否用上情景块。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["MOCK_LLM"] = "0"

import episode_store
import orchestrator

A_SID = "p10probeA"
TURNS = [
    "我下个月要搬家，最近一直在收拾东西。",
    "今天收拾到以前的照片，有点感慨。",
    "新住处离公司近一点，通勤能省半小时。",
    "不过搬家那几天应该会很乱。",
    "希望搬完能睡个好觉。",
    "搬家的事我还是有点慌。",
]
REPLIES = [
    "我在。今天想先说哪件事？",
    "收拾东西最磨人了，一件件翻出来又放回去。今天累到哪儿了？",
    "照片这种东西，收着收着就走神了吧。🌿",
    "嗯，半小时不算小数目，每天都能多睡一会儿",
    "乱是难免的。搬之前先理出一箱必备的，到了好找",
    "那箱里放什么，你心里有数吗",
]

store = episode_store.read_store(A_SID)
for ep in store["episodes"]:
    ep["last_recall_seq"] = 0
episode_store.write_store(A_SID, store)
history = []
for user_text, reply in zip(TURNS, REPLIES):
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})

question = "搬家的事我还是有点慌，你还记得吗？"
print("RECALL_BLOCK=%r" % episode_store.render_block(
    episode_store.select(episode_store.read_store(A_SID), question)))
res = orchestrator.safe_run(question, A_SID, history, "sister_heart", {})
print("QUESTION:", question)
print("REPLY:", res["reply"])
print("USED=%s" % any(word in res["reply"] for word in ("搬", "住处", "换")))
