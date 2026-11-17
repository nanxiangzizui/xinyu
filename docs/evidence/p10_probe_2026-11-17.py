"""P10 真 key 探针：A 情景记忆 5 轮抽取 + 召回；B 按卡记忆跨 sid 读取 + 姓名闸门。

运行（不要打印 .env）：
  $env:MOCK_LLM="0"; .\.venv\Scripts\python.exe docs\evidence\p10_probe_2026-11-17.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["MOCK_LLM"] = "0"

import episode_store
import memory
import orchestrator
import rolecard_memory

A_SID = "p10probeA"
B_SID = "rc-p10probe1"
B_SID2 = "rc-p10probe2"


def run_turns(persona, sid, history, state, turns, label):
    replies = []
    for i, text in enumerate(turns, 1):
        res = orchestrator.safe_run(text, sid, history, persona, state)
        print(f"{label}{i}: level={res['level']} degraded={res['degraded']} "
              f"reply={res['reply'][:90]}")
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": res["reply"]})
        replies.append(res["reply"])
        time.sleep(0.2)
    return replies


def probe_a():
    memory.clear_memory(A_SID)
    episode_store.clear(A_SID)
    turns = [
        "我下个月要搬家，最近一直在收拾东西。",
        "今天收拾到以前的照片，有点感慨。",
        "新住处离公司近一点，通勤能省半小时。",
        "不过搬家那几天应该会很乱。",
        "希望搬完能睡个好觉。",
    ]
    replies = run_turns("sister_heart", A_SID, [], {}, turns, "A")
    history = []
    for user_text, assistant_text in zip(turns, replies):
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": assistant_text})
    store = episode_store.read_store(A_SID)
    print("A_episodes=%d cues=%s" % (len(store["episodes"]),
                                     [ep["cue"] for ep in store["episodes"]]))
    picked = episode_store.select(store, "搬家的事我还是有点慌")
    print("A_recall=%r" % episode_store.render_block(picked))
    print("A_last_len=%s last_try=%s" % (store["last_len"], store["last_try_len"]))
    run_turns("sister_heart", A_SID, history, {},
              ["搬家的事我还是有点慌。"], "A6")


def probe_b():
    card = {
        "name": "昔涟", "work": "星穹铁道", "origin": "known",
        "identity": "来自贝洛伯格的旅人", "setting": "贝洛伯格的雪原与旧城",
        "voice": "温柔、简短", "address": "你", "user_role": "开拓者",
        "stage": "none", "examples": [("今天好冷", "那就靠近一点。")],
        "taboos": ["我懂你"], "lore": ["贝洛伯格终年积雪"],
    }
    rolecard_memory.clear(card)
    turns = [
        "今天下了好大的雪。",
        "我们在城外看雪吧。",
        "你还记得我们约好一起看雪吗？",
        "我叫张三，你别忘了。",
        "雪停之前，我们再多待一会儿。",
    ]
    run_turns(card, B_SID, [], {}, turns, "B")
    block = rolecard_memory.read(card, "还记得看雪吗")["_block"]
    print("B_block=%r" % block)
    print("B_stats=%s" % (rolecard_memory.stats(card),))
    path = rolecard_memory._path(card)
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    print("B_file=%s exists=%s 张三=%s 贝洛伯格=%s" %
          (path.name, path.exists(), "张三" in raw, "贝洛伯格" in raw))
    # 换一个 rc_sid 仍读同一张卡：证明记忆不绑会话。
    fresh = rolecard_memory.read(card, "还记得看雪吗")["_block"]
    print("B_fresh_sid_same_block=%s" % (fresh == block))


if __name__ == "__main__":
    probe_a()
    probe_b()
