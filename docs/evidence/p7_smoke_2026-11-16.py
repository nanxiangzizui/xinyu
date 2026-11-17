"""P7a + P7c 冒烟：无强制贴纸、连发合并成一轮；MOCK_LLM=1，不联网。

跑法：& ./.venv/Scripts/python.exe docs/evidence/p7_smoke_2026-11-16.py
覆盖：五人设 prompt 预算 / polish 不追加 / 正常一轮 / 连发三段的轮次与气泡 /
连发里夹危机仍 L3 / L2 资源卡只出一次 / 侧栏轮次。
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TMP = pathlib.Path(tempfile.mkdtemp(prefix="xinyu_p7_"))
os.environ["MOCK_LLM"] = "1"
os.environ["AGENT_LOOP"] = "1"
os.environ["ALLOW_WEB"] = "0"
os.environ["DATA_DIR"] = str(TMP / "memory")
os.environ["LOG_DIR"] = str(TMP / "logs")
(TMP / "memory").mkdir()
(TMP / "logs").mkdir()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import agent  # noqa: E402
import guardian  # noqa: E402
import resources  # noqa: E402
import roles  # noqa: E402
import style  # noqa: E402
from pipeline import Chat  # noqa: E402

MEM = {"preferred_tone": "温和", "emotion_tags": ["学业", "失眠"],
       "unresolved_issues": ["期末"], "rolling_summary": "在聊考试压力" * 5}
checks: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    checks.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


# 1) prompt 预算：加了"表情默认不用"这条后最坏仍 ≤1200
worst = 0
for persona in roles.PERSONAS:
    n = len(agent.build_system_prompt(persona, MEM, ["校心理中心工作日可预约"]))
    worst = max(worst, n)
    print(f"    prompt {persona:16s} {n}")
check(f"prompt worst {worst} <= 1200", worst <= 1200)

# 2) P7a：polish 一个字符都不加
appended = [style.polish("我在", p, lv) for p in roles.PERSONAS for lv in ("L1", "L2")]
check("polish appends nothing", all(x == "我在" for x in appended))
check("no sticker table", not hasattr(style, "STICKERS") and not hasattr(style, "STICKER_LEVELS"))
check("emoji rule is default-off", "默认不用" in style.SPEECH_RULES[-1])

# 3) P7c：正常一轮，一问一答仍是两条
chat = Chat("p7_normal")
chat.say("你好")
check("normal turn -> 2 messages",
      [m["role"] for m in chat.messages] == ["user", "assistant"])
check("normal turn -> turn=1", chat.state("turn") == 1)

# 4) P7c：连发三段（前两段是"上一轮被打断后留下的"），只回一次、只涨一轮、四个气泡
burst = Chat("p7_burst")
at = burst.at
at.session_state["messages"] = [
    {"role": "user", "content": "要是我能遇到像她一样的人就好了"},
    {"role": "user", "content": "但是她不可能遇到"},
]
at.chat_input[0].set_value("那人生也没什么意义").run()
roles_seen = [m["role"] for m in at.session_state["messages"]]
print("    burst roles:", roles_seen, "turn:", at.session_state["turn"])
check("burst -> three user bubbles + one reply",
      roles_seen == ["user", "user", "user", "assistant"])
check("burst -> turn counted once", at.session_state["turn"] == 1)
check("burst -> merged text judged L2 (P7b 后)",
      at.session_state["last_level"] == "L2")

# 5) P7c：危机在连发的第一段，仍必须 L3（证明判危扫的是整段）
crisis = Chat("p7_crisis")
at2 = crisis.at
at2.session_state["messages"] = [{"role": "user", "content": "我不想活了"}]
at2.chat_input[0].set_value("你在吗").run()
check("burst -> crisis in first segment still L3",
      at2.session_state["messages"][-1]["content"] == guardian.CRISIS_REPLY
      and at2.session_state["last_level"] == "L3")
check("burst -> L3 cards rendered once", len(at2.info) == len(resources.pick_resources("L3", [])))

print()
failed = [name for name, ok in checks if not ok]
print(f"{len(checks) - len(failed)}/{len(checks)} PASS")
sys.exit(1 if failed else 0)
