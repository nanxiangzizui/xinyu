"""_p32_risk_probe.py — P32 校准探针：让模型直接判 33 条对抗集，统计误抬/漏抬。

用法：.venv/Scripts/python.exe docs/evidence/_p32_risk_probe.py
只读：不写 memory / 日志进临时目录；不含任何真实用户内容。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ["MOCK_LLM"] = "0"
os.environ["RISK_REVIEW"] = "1"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="p32-mem-")
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="p32-log-")

import risk_review  # noqa: E402
from test_adversarial import CASES  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "P32-risk-probe-2026-11-20.txt"
ORDER = risk_review.ORDER


def main() -> int:
    rows, exact, over, under, bad = [], 0, 0, 0, 0
    for cid, text, expected, kind, _why in CASES:
        got = risk_review.judge(text)
        if not got["ok"]:
            bad += 1
            got_level, mark = "ERR", "ERR"
        else:
            got_level = got["level"]
            if got_level == expected:
                exact += 1
                mark = "ok"
            elif ORDER[got_level] > ORDER[expected]:
                over += 1
                mark = "OVER"
            else:
                under += 1
                mark = "UNDER"
        rows.append(f"{cid:>4} | 期望 {expected} | 模型 {got_level:<3} | {mark:<5} | {text} | {got.get('why','')}")

    head = [
        "P32 风险复核校准（模型直接判，不经过规则）",
        f"模型：{os.getenv('LLM_MODEL', 'deepseek-chat')} / temperature=0.0",
        f"样本：{len(CASES)} 条（tests/test_adversarial.CASES）",
        f"完全一致 {exact} / 误抬 {over} / 漏抬 {under} / 失败 {bad}",
        "口径：误抬 = 模型给的等级高于期望；漏抬 = 低于期望。",
        "",
        "编号 | 期望 | 模型 | 判定 | 原句 | 模型理由",
        "-" * 100,
    ]
    text = "\n".join(head + rows) + "\n"
    print(text)
    OUT.write_text(text, encoding="utf-8")
    print(f"written {OUT}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
