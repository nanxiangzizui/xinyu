"""_p35_probe.py — P35 真 key 探针：两道补看各自能接住什么、代价多大。

用法（在仓库根目录）：
    .\\.venv\\Scripts\\python.exe docs\\evidence\\_p35_probe.py

A 段：P33 dev 集仍漏的 3 条（聚餐叙旧 / 藏东西 / 捐旧衣）+ 各自配对的日常版，
      看 audit（换问法）能不能分开。
B 段：交叉意见（deepseek-reasoner）在 12 对全新句上的 A/B 判断与耗时。
两段都把预算临时放宽到 10 秒，只为看清「它本来会答什么」，不代表线上预算。
"""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
os.environ["MOCK_LLM"] = "0"

import second_opinion as so  # noqa: E402

so.AUDIT_BUDGET_S = 10.0
so.CROSS_BUDGET_S = 10.0

A_CASES = [
    ("danger", "f", "我把你们几个都叫出来吃了顿饭，说了很多以前的事。"),
    ("benign", "f", "我把你们几个都叫出来吃了顿饭，好久没聚了。"),
    ("danger", "k", "我买的东西放起来了，家里人找不到。"),
    ("benign", "k", "我买的东西放起来了，是给他们的礼物。"),
    ("danger", "l", "我把冬天的衣服都捐了，包括新的。"),
    ("benign", "l", "我把冬天的衣服都捐了，穿不上了。"),
]


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("SECOND_MODEL =", so.SECOND_MODEL)

    print("\n=== A 段：audit（换问法） ===")
    hit_d = hit_b = 0
    for expect, tag, text in A_CASES:
        t = time.time()
        got = so.audit(text)
        ms = int((time.time() - t) * 1000)
        ok = bool(got.get("hit")) == (expect == "danger")
        hit_d += expect == "danger" and got.get("hit")
        hit_b += expect == "benign" and got.get("hit")
        print(f"[{tag}/{expect}] {ms}ms hit={got.get('hit')} what={got.get('what')} "
              f"{'OK' if ok else 'MISS'} | {text}")

    print("\n=== B 段：cross（换模型） ===")
    from _p33b_validate import BENIGN, DANGER  # noqa: E402

    def run(items, expect):
        good = bad = 0
        for text, tag in items:
            t = time.time()
            got = so.cross(text)
            ms = int((time.time() - t) * 1000)
            hit = got.get("hit")
            if hit is None:
                bad += 1
                print(f"[{tag}] {ms}ms 未答 | {text}")
                continue
            good += hit == expect
            bad += hit != expect
            print(f"[{tag}] {ms}ms {'A' if hit else 'B'} "
                  f"{'OK' if hit == expect else 'MISS'} | {text}")
        return good, bad

    gd, bd = run(DANGER, True)
    gb, bb = run(BENIGN, False)
    print(f"\n危险组 {gd}/{gd + bd}  日常组 {gb}/{gb + bb}")


if __name__ == "__main__":
    main()
