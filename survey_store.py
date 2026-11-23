"""survey_store.py — P44 问卷回收：一行一条的 JSONL + 逐题计数 + 导出。

[SAFE] 只存「选项 + 日期」：不存 session id、不存 IP、不存小时分钟，
所以这份数据和某个人、某段聊天都没法对上——这不是疏漏，是刻意的最小化。
"""
from __future__ import annotations

import csv
import io
import json
import os
import uuid
from datetime import date
from pathlib import Path

import memory
import survey_data as D

FILE_NAME = "responses.jsonl"


def dir_path() -> Path:
    """跟着 memory.DATA_DIR 走（测试会 monkeypatch 它），不复用模块级常量。"""
    return Path(memory.DATA_DIR) / "survey"


def file_path() -> Path:
    return dir_path() / FILE_NAME


def normalise(answers: dict) -> dict:
    """去空白、丢空值、限两项、第 10 题压成一行并截断。"""
    out: dict[str, object] = {}
    for qid in D.IDS:
        val = answers.get(qid)
        if qid == D.Q10_ID:
            text = " ".join(str(val or "").split())[:D.Q10_MAX]
            if text:
                out[qid] = text
            continue
        if isinstance(val, (list, tuple)):
            picked = [str(v) for v in val if str(v) in D.OPTIONS.get(qid, ())]
            if picked:
                out[qid] = picked[:D.MAX_PICK[qid]] if qid in D.MAX_PICK else picked
        elif val and str(val) in D.OPTIONS.get(qid, ()):
            out[qid] = str(val)
    return out


def append(answers: dict, day: str | None = None) -> str:
    """追加一行；返回 rid（随机 8 位，只用来在 CSV 里区分行，不含身份）。"""
    rid = uuid.uuid4().hex[:8]
    row = {"rid": rid, "day": day or date.today().isoformat(),
           "answers": normalise(answers)}
    path = file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return rid


def read_all() -> list[dict]:
    """坏行跳过（边界：文件可能被手工改过），不抛给界面。"""
    path = file_path()
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get("answers"), dict):
            rows.append(row)
    return rows


def count_all(rows: list[dict]) -> dict:
    """逐题计数；多选题各项之和可以大于份数。"""
    by: dict[str, dict[str, int]] = {qid: {} for qid in D.OPTIONS}
    open_count = 0
    for row in rows:
        for qid, val in row["answers"].items():
            if qid == D.Q10_ID:
                open_count += 1
                continue
            for opt in (val if isinstance(val, list) else [val]):
                if qid in by and opt in D.OPTIONS[qid]:
                    by[qid][opt] = by[qid].get(opt, 0) + 1
    return {"n": len(rows), "by": by, "q10": open_count}


def crosses(rows: list[dict]) -> dict:
    """两条交叉：有过难受且没去求助 / 想要下一步且可能会去。"""
    had_and_quiet = 0
    step_and_would = 0
    for row in rows:
        ans = row["answers"]
        asked = ans.get("q4") or []
        asked = asked if isinstance(asked, list) else [asked]
        if ans.get("q2") in D.Q2_HAD and any(r in asked for r in D.Q4_REASONS):
            had_and_quiet += 1
        picked = ans.get("q5") or []
        picked = picked if isinstance(picked, list) else [picked]
        if D.Q5_NEXT_STEP in picked and ans.get("q9") in D.Q9_WOULD:
            step_and_would += 1
    return {"had_and_quiet": had_and_quiet, "step_and_would": step_and_would}


def csv_text(rows: list[dict]) -> str:
    """Excel 能直接开的宽表：rid + day + q1…q10。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["rid", "day", *D.IDS])
    for row in rows:
        ans = row["answers"]
        cells = []
        for qid in D.IDS:
            val = ans.get(qid, "")
            cells.append("|".join(val) if isinstance(val, list) else val)
        writer.writerow([row.get("rid", ""), row.get("day", ""), *cells])
    return buf.getvalue()


def jsonl_text(rows: list[dict]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
