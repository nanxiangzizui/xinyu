"""_p32_latency.py — P32 复核调用的延迟抽样（6 条，真实 key）。"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ["MOCK_LLM"] = "0"

import risk_review  # noqa: E402

TEXTS = ["今天有点烦", "食堂的菜有点咸", "最近总提不起劲", "晚上老是睡不着",
         "明天有考试", "我朋友最近不太对"]

stamps = []
for text in TEXTS:
    t0 = time.time()
    got = risk_review.judge(text)
    stamps.append((time.time() - t0) * 1000)
    print(f"{stamps[-1]:.0f}ms level={got['level']} ok={got['ok']}")
print(f"avg={sum(stamps) / len(stamps):.0f}ms max={max(stamps):.0f}ms")
