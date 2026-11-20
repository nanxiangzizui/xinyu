"""_p24d_blind.py — P24 ④ 盲评样本：走真实管线（agenda / 地点 / 记忆 / 风格），真 key。

用法：.venv/Scripts/python.exe docs/evidence/_p24d_blind.py
只读：memory / 日志都进临时目录；样本全是虚构日常句，不含任何真人倾诉。
输出：docs/evidence/P24-blind-samples-2026-11-20.txt
      前 10 条已打乱，评分时先别看末尾的映射表。
"""
from __future__ import annotations

import os
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ["MOCK_LLM"] = "0"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="p24d-mem-")
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="p24d-log-")

import orchestrator  # noqa: E402
from roles import PERSONAS  # noqa: E402

PIDS = list(PERSONAS)   # PERSONAS 是 dict（pid → 人设卡），按下标取要转成列表

# 10 条单轮句：日常、可复现、不带任何真实身份；覆盖 12 个情境里的 8 类。
INPUTS = [
    "今天有点累，什么都不想干",
    "躺了一个小时了，还是睡不着。",
    "今天开会，被领导当着所有人说了一顿。",
    "我妈又打电话来了，问我什么时候回家。",
    "我好像做什么都没做好。",
    "分手三个月了，还是会突然想起来。",
    "明天考试，书一页都没看。",
    "心跳得厉害，静不下来。",
    "想找一个谁也找不到的地方待着。",
    "今天有件好事，我拿到实习了。",
]

DIALOG_USER = [
    "最近挺累的，什么都不想干",
    "试过了，没用。",
    "大概半个月了吧。",
    "嗯。",
]


def one_turn(text: str, sid: str, persona: str) -> dict:
    """单轮走 handle：history 第一条就是本轮用户消息（chat_ui.accept 的口径）。"""
    hist = [{"role": "user", "content": text}]
    return orchestrator.handle(text, sid, hist, persona, {})


def build_dialog(persona: str) -> list[tuple[str, str]]:
    """四轮：接住 → 接住 → 具体化 → 动作；用来盲评节奏，而不是单句。"""
    sid, hist, turns = f"blind-dialog-{persona}", [], []
    for user_text in DIALOG_USER:
        hist.append({"role": "user", "content": user_text})
        res = orchestrator.handle(user_text, sid, hist, persona, {})
        reply = str(res.get("reply", ""))
        turns.append((user_text, reply))
        hist.append({"role": "assistant", "content": reply})
        if res.get("level") == "L3" or res.get("template_fallback"):
            break
    return turns


def main() -> None:
    rows: list[dict] = []
    for i, text in enumerate(INPUTS):
        persona = PIDS[i % len(PIDS)]
        res = one_turn(text, f"blind-{i}", persona)
        rows.append({"text": text, "persona": persona,
                     "reply": str(res.get("reply", "")),
                     "level": res.get("level", ""), "role": res.get("role", "")})
    order = list(range(len(rows)))
    random.Random(24).shuffle(order)   # 固定种子：同一份样本换个顺序就是另一份，别每次变

    out = ["# P24 盲评样本（真 key，deepseek-chat，temperature=0.7）",
           "# 评分时只看「用户 / 心屿」，不要看末尾映射表；人设名一律隐去。",
           ""]
    for n, idx in enumerate(order, 1):
        r = rows[idx]
        out += [f"## 样本 {n}", f"用户：{r['text']}", f"心屿：{r['reply']}", ""]
    out += ["## 对话 A（同一人设，四轮）"]
    for user_text, reply in build_dialog(PIDS[0]):
        out += [f"用户：{user_text}", f"心屿：{reply}"]
    out.append("")

    out += ["", "===== 以下为映射与元数据，评分时遮住 ====="]
    for n, idx in enumerate(order, 1):
        r = rows[idx]
        out.append(f"样本 {n} ← {r['persona']} / level={r['level']} / role={r['role']}")
    out.append(f"对话 A ← {PIDS[0]}")

    path = Path(__file__).with_name("P24-blind-samples-2026-11-20.txt")
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
