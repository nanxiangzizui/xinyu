"""P8b 真实 provider smoke：中文→博查，英文→Tavily；不打印 key、不写 data/。

用法（工作区根目录）：
    .\.venv\Scripts\python.exe docs/evidence/p8b_smoke_2026-11-16.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

import web  # noqa: E402


CASES = (
    ("中文/ACG → 博查", "昔涟 崩坏星穹铁道 角色", "bocha"),
    ("英文/技术 → Tavily", "Who is Cyrene in Honkai Star Rail", "tavily"),
)
OUT = ROOT / "docs/evidence/P8b-provider-smoke-2026-11-16.txt"


def main() -> int:
    os.environ["WEB_PROVIDER"] = "auto"
    lines = ["# P8b 真实 provider smoke（2026-11-16）", ""]
    failed = 0
    for label, query, expected in CASES:
        data, err = web.search(query)
        items = (data or {}).get("items") or []
        provider = (data or {}).get("provider", "-")
        first = items[0] if items else {}
        line = f"{label}: provider={provider} err={err or 'ok'} count={len(items)}"
        lines.append(line)
        print(line)
        if items:
            detail = f"  first={first.get('title', '')[:60]} | {first.get('url', '')}"
            lines.append(detail)
            print(detail)
        if err or provider != expected or not items:
            failed += 1
    verdict = "PASS" if failed == 0 else f"FAIL {failed}/{len(CASES)}"
    lines.append(verdict)
    print(verdict)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
