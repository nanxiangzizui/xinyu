# -*- coding: utf-8 -*-
"""一次性：导出 28 条规则用例的期望与实际，供报告生成脚本读取。"""
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import os
os.environ.setdefault("MOCK_LLM", "1")
from test_guardian import D_CASES
from guardian import guardian_pre_check

rows = []
for cid, text, level, ids, exempted in D_CASES:
    got = guardian_pre_check(text)
    rows.append({
        "id": cid, "text": text, "expect_level": level,
        "expect_ids": sorted(ids), "expect_exempt": bool(exempted),
        "got_level": got["level"], "got_ids": sorted(got["rule_ids"]),
        "got_exempt": bool(got["exempted"]),
        "ok": got["level"] == level and set(got["rule_ids"]) == set(ids) and bool(got["exempted"]) == bool(exempted),
    })
out = ROOT / "docs" / "report_cases.json"
out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print("rows", len(rows), "ok", sum(r["ok"] for r in rows))
