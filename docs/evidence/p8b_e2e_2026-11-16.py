"""P8b 端到端 smoke：ALLOW_WEB=1 时模型能否自己调 web_search 并接上话。

只读 .env 的 LLM 配置；记忆/日志写临时目录；输出不含 key、不打印模型生成的
检索 query（日志也只记工具名 / 状态 / 耗时 / 条数）。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
if not os.getenv("LLM_API_KEY") or os.getenv("MOCK_LLM", "0") == "1":
    raise SystemExit("需要真实 LLM_API_KEY 且 MOCK_LLM=0")

_tmp = Path(tempfile.mkdtemp(prefix="p8be2e_"))
os.environ["DATA_DIR"] = str(_tmp / "memory")
os.environ["LOG_DIR"] = str(_tmp / "logs")
os.environ["ALLOW_WEB"] = "1"
os.environ.setdefault("WEB_PROVIDER", "auto")

import web  # noqa: E402
from orchestrator import safe_run  # noqa: E402

web.register_tools()
QUESTION = "帮我查一下昔涟的配音演员是谁"


def main() -> None:
    history = [{"role": "user", "content": QUESTION}]
    res = safe_run(QUESTION, "p8be2e", history, "sister_heart", {})
    trace = res.get("trace") or []
    tools_used = 0
    for step in trace:
        detail = str(step.get("detail") or "")
        if step.get("node") == "generate" and "tools=" in detail:
            tools_used = int(detail.split("tools=", 1)[1].split()[0])
    lines = [
        "P8b e2e smoke 2026-11-16",
        f"model={os.getenv('LLM_MODEL')} provider={os.getenv('WEB_PROVIDER')} "
        f"allow_web=1",
        "",
        f"user: {QUESTION}",
        f"reply: {res['reply']}",
        f"level={res['level']} role={res['role']} degraded={res['degraded']}",
        f"tools_used={tools_used} sources={len(res.get('sources') or [])}",
        "trace=" + ",".join(s["node"] for s in trace),
    ]
    for src in res.get("sources") or []:
        lines.append(f"source: {src.get('title', '')[:80]} | {src.get('url', '')}")
    out = Path(__file__).with_name("P8b-e2e-smoke-2026-11-16.txt")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"tools_used={tools_used} sources={len(res.get('sources') or [])}")


if __name__ == "__main__":
    main()
