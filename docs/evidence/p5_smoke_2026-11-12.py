"""P5 冒烟：L1/L2/L3 口吻与兜底逐字、prompt 增量；MOCK_LLM=1，不联网。

跑法：& ./.venv/Scripts/python.exe docs/evidence/p5_smoke_2026-11-12.py
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TMP = pathlib.Path(tempfile.mkdtemp(prefix="xinyu_p5_"))
os.environ["MOCK_LLM"] = "1"
os.environ["AGENT_LOOP"] = "1"
os.environ["ALLOW_WEB"] = "0"
os.environ["DATA_DIR"] = str(TMP / "memory")
os.environ["LOG_DIR"] = str(TMP / "logs")
(TMP / "memory").mkdir()
(TMP / "logs").mkdir()

import agent
import guardian
import orchestrator
import roles
import style

BASE = {"sister_heart": 536, "warm_senpai": 547,
        "rational_mentor": 521, "energy_buddy": 540, "quiet_hollow": 495}
checks: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    checks.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


# 1) 五个 prompt 都只多一行锚点，增量 <80 字
for persona in roles.PERSONAS:
    prompt = agent.build_system_prompt(persona, {}, [])
    delta = len(prompt) - BASE[persona]
    check(f"prompt {persona} delta={delta} <80", 0 < delta < 80)
    check(f"prompt {persona} contains hint", style.tone_hint(persona) in prompt)

# 2) L1：五个人设各一枚白名单贴纸，句尾没有「。」
for persona in roles.PERSONAS:
    res = orchestrator.handle("你好", f"p5_l1_{persona}", [], persona, {})
    reply = res["reply"]
    check(f"L1 {persona} level={res['level']}", res["level"] == "L1")
    check(f"L1 {persona} sticker", style.STICKERS[persona] in reply)
    check(f"L1 {persona} no trailing period", not reply.endswith("。"))

# 3) L2：无贴纸、无句尾句号
res_l2 = orchestrator.handle("我觉得自己很没用", "p5_l2", [], "sister_heart", {})
check(f"L2 level={res_l2['level']}", res_l2["level"] == "L2")
check("L2 no sticker", not any(mark in res_l2["reply"] for mark in style.STICKERS.values()))
check("L2 no trailing period", not res_l2["reply"].endswith("。"))

# 4) L3：危机模板逐字不变，无贴纸
res_l3 = orchestrator.handle("我不想活了", "p5_l3", [], "sister_heart", {})
check("L3 verbatim", res_l3["reply"] == guardian.CRISIS_REPLY)
check("L3 no sticker", not any(mark in res_l3["reply"] for mark in style.STICKERS.values()))

# 5) 模板兜底不经过 polish（强制 post 返回 template_fallback）
original_post = orchestrator.guardian.guardian_post_check


def forced_fallback(*args, **kwargs):
    return {"pass": False, "reason": "forced", "rewrite": 0,
            "fixed_reply": guardian.SAFE_FALLBACK["listener"],
            "template_fallback": True}


orchestrator.guardian.guardian_post_check = forced_fallback
try:
    res_fb = orchestrator.handle("你好", "p5_fb", [], "sister_heart", {})
finally:
    orchestrator.guardian.guardian_post_check = original_post
check("fallback verbatim", res_fb["reply"] == guardian.SAFE_FALLBACK["listener"])
check("fallback no sticker", not any(mark in res_fb["reply"] for mark in style.STICKERS.values()))

failed = [name for name, ok in checks if not ok]
print(f"P5 SMOKE {'PASS' if not failed else 'FAIL'} ({len(checks)} checks)")
sys.exit(1 if failed else 0)
