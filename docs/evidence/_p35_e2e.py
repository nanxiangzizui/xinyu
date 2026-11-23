"""_p35_e2e.py — P35 端到端探针：走完整 check()，量召回、过判与总耗时。

12 对全新句（_p33b_validate）各过一遍 risk_review.check()，第二意见用真 key。
预算按线上值（审计 2s / 交叉 6s），所以这里看到的超时就是线上会遇到的超时。
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

import risk_review  # noqa: E402
import second_opinion as so  # noqa: E402


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from _p33b_validate import BENIGN, DANGER  # noqa: E402

    print(f"audit_budget={so.AUDIT_BUDGET_S}s cross_budget={so.CROSS_BUDGET_S}s "
          f"model={so.SECOND_MODEL}")

    def run(items, want_l3):
        rows = []
        for text, tag in items:
            t = time.time()
            out = risk_review.check(text, None)
            ms = int((time.time() - t) * 1000)
            flags = ",".join(x for x in out["rule_ids"] if x.startswith("SECOND"))
            hit = out["level"] == "L3" if want_l3 else out["level"] == "L1"
            rows.append((tag, ms, out["level"], out.get("signal"), out.get("accum"), flags, hit, text))
        return rows

    danger = run(DANGER, True)
    benign = run(BENIGN, False)

    for label, rows in (("危险组", danger), ("日常组", benign)):
        print(f"\n--- {label} ---")
        for tag, ms, lvl, sig, acc, flags, hit, text in rows:
            print(f"[{tag}] {ms}ms {lvl}/{sig}/accum={acc} {flags or '-'} "
                  f"{'OK' if hit else 'MISS'} | {text}")

    d_ok = sum(r[6] for r in danger)
    b_ok = sum(r[6] for r in benign)
    d_ms = sorted(r[1] for r in danger)
    b_ms = sorted(r[1] for r in benign)
    print(f"\n危险组 {d_ok}/{len(danger)}   日常组 {b_ok}/{len(benign)}")
    print(f"延迟 危险 p50={d_ms[len(d_ms) // 2]}ms max={d_ms[-1]}ms | "
          f"日常 p50={b_ms[len(b_ms) // 2]}ms max={b_ms[-1]}ms")


if __name__ == "__main__":
    main()
