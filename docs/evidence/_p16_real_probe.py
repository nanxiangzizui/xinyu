"""P16 真实 key 探针：A 模式 listener 连续三轮是否还以问句收尾。

不打印 key；用临时 DATA_DIR / LOG_DIR；历史里的测试报告是虚构的。
运行：.\.venv\Scripts\python.exe docs/evidence/_p16_real_probe.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="p16real-"))
os.environ["DATA_DIR"] = str(TMP / "memory")
os.environ["LOG_DIR"] = str(TMP / "logs")
os.environ["MOCK_LLM"] = "0"

import orchestrator  # noqa: E402

OUT = ROOT / "docs/evidence/P16-real-listener-2026-11-17.txt"
REPORT = (
    "《阵营小坐标》的结果：随性·自守。秩序1分、随性8分、自守1分。"
    "游戏说明里提到不太吃规矩那套、自在最要紧，分数也主要落在随性这一边。"
    "想与我探讨一下测试结果吗？"
)
TURNS = ["分析一下结果", "你觉得我遇到困难会怎么做", "刚刚我们聊了什么"]
history = [
    {"role": "user", "content": "我做了个测试"},
    {"role": "assistant", "content": REPORT},
    {"role": "user", "content": TURNS[0]},
]
lines = [
    "# P16 真实 key listener 探针",
    f"mock={os.getenv('MOCK_LLM')} key_present={bool(os.getenv('LLM_API_KEY'))}",
    "",
]
state: dict = {}
for i, text in enumerate(TURNS, 1):
    if i > 1:
        history.append({"role": "assistant", "content": reply})
        history.append({"role": "user", "content": text})
    try:
        res = orchestrator.handle(text, "p16-real", history, "sister_heart", state)
    except Exception as exc:  # 探针要留下失败原因，不把异常冒成空结果
        lines.append(f"[{i}] {text}\nERROR {type(exc).__name__}: {exc}")
        break
    reply = res.get("reply", "")
    lines += [
        f"[{i}] user: {text}",
        f"role={res.get('role')} level={res.get('level')} "
        f"len={len(reply)} ends_question={reply.rstrip().endswith(('？', '?'))}",
        f"assistant: {reply}",
        "",
    ]
    if i == 1:
        lines.append("trace: " + ", ".join(
            f"{t.get('node')}:{t.get('status')}" for t in res.get("trace", [])))
        lines.append("")

lines.append(f"temp_data_dir={TMP}")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", OUT)
print("turns", len([x for x in lines if x.startswith("[")]))
