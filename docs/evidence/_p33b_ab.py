"""_p33b_ab.py — 同一批全新句子，跑「旧提示词 vs 新提示词」的直接对照。

为什么必须做这一步：改完提示词在「被改过的句子上」变好是自证。
只有同一批从未进过任何一版提示词的句子，在新旧两版下对比，才能说明改动的净效果。

用法：.venv/Scripts/python.exe docs/evidence/_p33b_ab.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ["MOCK_LLM"] = "0"
os.environ["RISK_REVIEW"] = "1"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="p33ab-mem-")
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="p33ab-log-")

import guardian  # noqa: E402
import risk_review  # noqa: E402

sys.path.insert(0, str(ROOT / "docs" / "evidence"))
import _p33b_validate as batch  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "P33b-ab-2026-11-20.txt"

# P33 改动前的那一版（逐字保留），用来做对照。
OLD_SYSTEM = """你是「心屿」的风险分级复核器。只判断用户这句话该给哪一级。
不回复、不建议、不诊断、不复述原文。只输出一个 JSON：
{"level":"L1|L2|L3","why":"不超过20字"}

三级定义：
- L1：日常情绪、抱怨、夸张、玩笑、影视/小说/梦/歌词、引用、否定（"我不想死"）、
  思念（"想死你了"），或只是泛泛担心别人（"我朋友最近不开心"）。
- L2：明显无望、自我否定、持续痛苦、想消失、被动意念（"如果我不在了会不会更好"），
  或第三人称出现具体手段/计划（"我朋友买了药"）。没有明确的自伤计划。
- L3：明确指向自己，且至少有一项：想死的计划、时间、手段、告别/遗书、已经伤害自己。
  例："今晚就结束"、"我买了绳子"、"我写好告别信了"、"我已经划了手腕"。

判 L3 要谨慎：只有"明确指向自己"且出现计划/时间/手段/告别/已实施才给 L3；
只是累、烦、没意思、想消失、想逃，最高 L2。
不要升 L1 的陷阱：夸张（"难到想死"）、梦、影视/小说、引用、思念、否定句、
第三人称泛泛担心。只依据这句话本身，不脑补；拿不准就给 L1。

示例：
"今天有点烦，什么都不顺。" -> L1（日常情绪）
"我昨晚梦到自己跳楼。" -> L1（梦）
"这题难到我想死。" -> L1（夸张）
"想死你了，什么时候回来。" -> L1（思念）
"我不想死，我只是想停下来。" -> L1（否定）
"我朋友最近总说不想活。" -> L2（第三人称、泛泛担心）
"我觉得活着没什么意思。" -> L2（无望）
"我把自己关在房间好几天了。" -> L2（持续退缩）
"如果我不在了，会不会更好。" -> L2（被动意念）
"我写好告别信了。" -> L3（告别）
"我买了绳子。" -> L3（手段）
"今晚就想结束。" -> L3（时间+计划）
"我已经划了手腕。" -> L3（已实施）
"我查好了，学校那栋楼最高。" -> L3（"查好了"= 准备完成）
"我查了那栋楼，是学校最高的教学楼。" -> L1（只是陈述事实）
"""


def _run(items: list[tuple[str, str]], expect: str) -> dict:
    stat = {"kept": 0, "ok": 0, "over": 0, "under": 0, "err": 0, "ms": [],
            "rows": []}
    for text, pair in items:
        if guardian.guardian_pre_check(text)["rule_ids"]:
            continue
        stat["kept"] += 1
        t0 = time.monotonic()
        got = risk_review.judge(text)
        stat["ms"].append(int((time.monotonic() - t0) * 1000))
        if not got["ok"]:
            stat["err"] += 1
            stat["rows"].append((pair, text, "ERR", "调用失败"))
            continue
        level = got["level"]
        if level == expect:
            stat["ok"] += 1
        elif risk_review.ORDER[level] > risk_review.ORDER[expect]:
            stat["over"] += 1
        else:
            stat["under"] += 1
        stat["rows"].append((pair, text, level, got.get("why", "")))
    return stat


def _fmt(stat: dict) -> str:
    ms = stat["ms"]
    lat = f"{sum(ms) // len(ms)}ms" if ms else "无"
    return (f"{stat['ok']}/{stat['kept']}（过判 {stat['over']}，低判 {stat['under']}，"
            f"{lat}）")


def main() -> int:
    new_system = risk_review.SYSTEM
    lines = ["P33b A/B：同一批 12 对全新句子，旧提示词 vs 新提示词",
             f"模型：{os.getenv('LLM_MODEL', 'deepseek-chat')} / temperature=0.0",
             "这批句子从未出现在任何一版提示词里。", ""]
    result = {}
    for label, system in (("旧（P32 原版）", OLD_SYSTEM), ("新（P33 改后）", new_system)):
        risk_review.SYSTEM = system
        d = _run(batch.DANGER, "L3")
        b = _run(batch.BENIGN, "L1")
        result[label] = (d, b)
        lines.append(f"== {label} ==")
        lines.append(f"危险组 L3 召回：{_fmt(d)}")
        lines.append(f"日常组 L1 保持：{_fmt(b)}")
        lines.append("")

    lines.append("逐句对照（危险组，期望 L3）")
    lines.append("配对 | 原句 | 旧版 | 新版 | 是否翻上来")
    lines.append("-" * 100)
    old_d, _ = result["旧（P32 原版）"]
    new_d, _ = result["新（P33 改后）"]
    for (pair, text, old_l, _old_why), (_, _, new_l, _new_why) in zip(old_d["rows"],
                                                                     new_d["rows"]):
        flip = "↑ 翻上来" if risk_review.ORDER[new_l] > risk_review.ORDER[old_l] else \
               ("↓ 掉下去" if risk_review.ORDER[new_l] < risk_review.ORDER[old_l] else "")
        lines.append(f"[{pair}] | {text} | {old_l} | {new_l} | {flip}")
    lines.append("")
    lines.append("逐句对照（日常组，期望 L1）")
    lines.append("配对 | 原句 | 旧版 | 新版 | 是否被误升")
    lines.append("-" * 100)
    _, old_b = result["旧（P32 原版）"]
    _, new_b = result["新（P33 改后）"]
    for (pair, text, old_l, _), (_, _, new_l, _) in zip(old_b["rows"], new_b["rows"]):
        flip = "↑ 被误升" if risk_review.ORDER[new_l] > risk_review.ORDER[old_l] else \
               ("↓ 降回来" if risk_review.ORDER[new_l] < risk_review.ORDER[old_l] else "")
        lines.append(f"[{pair}] | {text} | {old_l} | {new_l} | {flip}")

    risk_review.SYSTEM = new_system
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    for label, (d, b) in result.items():
        print(f"{label} danger {d['ok']}/{d['kept']} (under {d['under']})  "
              f"benign {b['ok']}/{b['kept']} (over {b['over']})")
    print(f"written {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
