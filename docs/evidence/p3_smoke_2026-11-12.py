"""P3a 冒烟：假 transport 走通 web.search / tools.execute / AppTest；不连任何真实域名。

跑法：& ./.venv/Scripts/python.exe docs/evidence/p3_smoke_2026-11-12.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="xinyu-p3-"))
os.environ["MOCK_LLM"] = "1"
os.environ["DATA_DIR"] = str(TMP / "memory")
os.environ["LOG_DIR"] = str(TMP / "logs")
os.environ["AGENT_LOOP"] = "1"
os.environ["ALLOW_WEB"] = "1"
os.environ["WEB_PROVIDER"] = "bocha"
os.environ["WEB_API_KEY"] = "fake-key"

import tools
import web

QUERY = "杭州 西湖 开放时间"


def fake_ok(url, headers, timeout_s, body):
    rows = [{"name": "西湖开放时间", "url": "https://example.invalid/xihu",
             "snippet": "占位摘要，不来自真实网络"}]
    return 200, json.dumps({"webPages": {"value": rows}}, ensure_ascii=False).encode("utf-8")


def fake_timeout(url, headers, timeout_s, body):
    raise TimeoutError("simulated")


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        raise SystemExit(1)


# 1 正常检索（假 transport）
data, err = web.search(QUERY, fetch=fake_ok)
check("search ok / 1 item", err == "" and len(data["items"]) == 1)
check("search provider=bocha", data["provider"] == "bocha")

# 2 没配 key → http_401
os.environ["WEB_API_KEY"] = ""
check("no key -> http_401", web.search(QUERY, fetch=fake_ok) == (None, "http_401"))
os.environ["WEB_API_KEY"] = "fake-key"

# 3 超时 → timeout（不是异常）
check("timeout -> timeout", web.search(QUERY, fetch=fake_timeout) == (None, "timeout"))

# 4 日志：只记四个计数，不含 query 与原文
records = []
class Capture(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())

capture = Capture()
logging.getLogger("web").addHandler(capture)
logging.getLogger("web").setLevel(logging.INFO)
web.search("我电话13800138000 " + QUERY, fetch=fake_ok)
logging.getLogger("web").removeHandler(capture)
joined = " | ".join(records)
check("log has provider/status/ms/count", "provider=bocha" in joined and "count=1" in joined)
check("log has no phone", "13800138000" not in joined)
check("log has no query text", "西湖" not in joined)

# 5 注册成工具后走 tools.execute（monkeypatch 模块级 _fetch）
tools.reset()
web.register_tools()
web._fetch = fake_ok
res = tools.execute("web_search", {"query": QUERY})
check("tools.execute ok", res.ok and len(res.data["items"]) == 1)
web._fetch = fake_timeout
res = tools.execute("web_search", {"query": QUERY})
check("tools.execute error payload", res.data.get("error") == "timeout")
tools.reset()

# 6 AppTest：页面启动即注册；AGENT_LOOP=1 的 trace 显示 tools=0
from streamlit.testing.v1 import AppTest

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
at.run()
at.chat_input[0].set_value("今天有点累，想聊聊").run()
trace = at.session_state.get("last_trace")
print("turn role/level:", at.session_state.get("last_role"), at.session_state.get("last_level"))
check("page replied", len(at.markdown) > 0 and "degraded" in at.session_state)
check("web_search registered", "web_search" in tools.REGISTRY)

# 7 开关三层：allow_web 默认关 / 打开才可见 / L3 一律空
import orchestrator

check("AGENT_LOOP=1 read at import", orchestrator.AGENT_LOOP is True)
check("ALLOW_WEB=1 read at import", orchestrator.ALLOW_WEB is True)
names_off = [t["function"]["name"] for t in tools.list_for_turn("guide", "L1")]
names_on = [t["function"]["name"] for t in tools.list_for_turn("guide", "L1", allow_web=True)]
check("web hidden without allow_web", "web_search" not in names_off)
check("web visible with allow_web", "web_search" in names_on)
check("L3 gets no tools", tools.list_for_turn("crisis", "L3", allow_web=True) == [])

print("EXIT 0")
