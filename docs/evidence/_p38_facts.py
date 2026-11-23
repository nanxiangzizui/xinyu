"""P38 诊断：把模型抽出的事实原样打出来，好照着真实分布定判据表。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["MOCK_LLM"] = "0"
os.environ["RISK_REVIEW"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent  # noqa: E402
import guardian  # noqa: E402
import risk_facts  # noqa: E402
import risk_review  # noqa: E402
from _p38_ab import NEW  # noqa: E402


def raw(text: str) -> dict | None:
    out = risk_review._bounded(risk_review._messages(text, risk_facts.DERIVE_SYS))
    if not out or not out.get("ok"):
        return None
    data = agent.safe_json(out.get("text") or "")
    return data if isinstance(data, dict) else None


def main() -> None:
    for tag in (0, 1):
        print("== 危险 ==" if tag == 0 else "== 日常 ==")
        for key, pair in NEW.items():
            text = pair[tag]
            pre = guardian.guardian_pre_check(text)
            d = raw(text)
            if pre["level"] != "L1" or pre["rule_ids"]:
                print(f"[{key}] 规则 {pre['level']} {pre['rule_ids']}")
                continue
            print(json.dumps(d, ensure_ascii=False) if d else f"[{key}] 没答")


if __name__ == "__main__":
    main()
