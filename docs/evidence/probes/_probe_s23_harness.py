"""_probe_s23_harness.py — 验证 AppTest 能否作为 S23 的"完整管线"测试夹具。

要确认四件事：
1. AppTest 能跑 app.py（MOCK=1 + patch memory.DATA_DIR / logger.LOG_DIR）
2. 会话 id 能从 query_params 读到
3. chat_input 发一句后，messages / 日志 / 记忆 三处都可断言
4. 记忆面板的"确认清除"复选框 + 按钮能被 AppTest 点击
"""
from __future__ import annotations

import io
import json
import pathlib
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import memory  # noqa: E402
import logger  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

tmp = pathlib.Path(tempfile.mkdtemp(prefix="s23probe-"))
memory.DATA_DIR = tmp / "memory"
logger.LOG_DIR = str(tmp / "logs")
import os
os.environ["MOCK_LLM"] = "1"


def log_rows() -> list[dict]:
    files = sorted((tmp / "logs").glob("*.jsonl"))
    out: list[dict] = []
    for f in files:
        out += [json.loads(x) for x in f.read_text("utf-8").splitlines() if x.strip()]
    return out


at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
at.run()
print("exceptions_after_first_run:", list(at.exception))
print("query_params attrs:", type(at.query_params).__name__, dict(at.query_params) if hasattr(at.query_params, "keys") else None)
sid = at.query_params.get("u")
print("sid:", sid)

at.chat_input[0].set_value("你好").run()
print("exceptions_after_turn:", [e.value for e in at.exception])
print("messages:", at.session_state["messages"])
rows = log_rows()
print("log_rows:", rows)
print("memory_file:", (tmp / "memory" / f"{sid}.json").exists())
print("memory:", json.loads((tmp / "memory" / f"{sid}.json").read_text("utf-8")) if sid else None)
print("sidebar_metrics:", [(m.label, m.value) for m in at.sidebar.metric])
print("captions:", [c.value for c in at.sidebar.caption])

# 面板：确认复选框 -> 清除按钮
cb_keys = [c.key for c in at.checkbox]
print("checkbox_keys:", cb_keys)
btn_keys = [b.key for b in at.button]
print("button_keys_before:", btn_keys)
panel_cb = [c for c in at.checkbox if c.key and c.key.startswith("panel_confirm_")]
if panel_cb:
    panel_cb[0].check().run()
    print("button_keys_after_confirm:", [b.key for b in at.button])
    btns = [b for b in at.button if b.key and b.key.startswith("panel_clear_")]
    if btns:
        btns[0].click().run()
        print("sid_after_clear:", at.query_params.get("u"))
        print("old_file_exists:", (tmp / "memory" / f"{sid}.json").exists())
print("tmp:", tmp)
