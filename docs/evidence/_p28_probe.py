"""P28 探针：把对抗集逐条跑规则层，输出证据表（不调模型、不写记忆）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from guardian import guardian_pre_check  # noqa: E402
from test_adversarial import CASES, KNOWN_GAPS  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "P28-probe-2026-11-20.txt"


def _verdict(cid: str, want: str, got: str) -> str:
    if want == got:
        return "ok"
    return "gap（漏报）" if want > got else "gap（误报）"


def main() -> int:
    rows = []
    for cid, text, want, kind, why in CASES:
        result = guardian_pre_check(text)
        got = result["level"]
        marks = ",".join(result["rule_ids"]) or "-"
        rows.append((cid, kind, want, got, _verdict(cid, want, got), marks, text, why))

    ok = sum(1 for row in rows if row[4] == "ok")
    miss = sum(1 for row in rows if row[4].endswith("漏报）"))
    false = sum(1 for row in rows if row[4].endswith("误报）"))

    lines = [
        "P28 对抗集探针（规则层，无模型）",
        f"total={len(rows)} ok={ok} gap={len(rows) - ok}（漏报 {miss} / 误报 {false}）",
        "",
        "| 编号 | 类别 | 期望 | 实测 | 判定 | 命中规则 | 输入 |",
        "|---|---|---|---|---|---|---|",
    ]
    for cid, kind, want, got, verdict, marks, text, _why in rows:
        lines.append(f"| {cid} | {kind} | {want} | {got} | {verdict} | {marks} | {text} |")
    lines += ["", "已知缺口（xfail）:", "、".join(sorted(KNOWN_GAPS))]
    body = "\n".join(lines)
    OUT.write_text(body + "\n", encoding="utf-8")
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
