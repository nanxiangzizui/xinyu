"""pipeline.py — S23 测试夹具：用 AppTest 驱动 app.py 的真实七步管线。

不是测试文件（pytest 不会收集）。用法：

    chat = Chat()
    reply = chat.say("你好")
    assert rows(chat.sid)[-1]["role"] == "listener"

为什么不直接调 app.handle：handle 依赖 st.session_state，只有 Streamlit 运行时里
才存在。AppTest 跑的是真 app.py（真 chat_input、真侧栏、真管线），所以断言的是
"用户实际经历的那条路"，而不是把单函数拼起来的假流程。
"""
from __future__ import annotations

import json
import pathlib

import logger as logmod
import memory
from streamlit.testing.v1 import AppTest

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")

# 与 app.py:62 同文：F-01 用它对账，文案改了测试要跟着红（由 test_f01 校验）。
FALLBACK_LINE = "我这边刚刚卡了一下，但我在。你可以再说一句吗？"


class Chat:
    """一次会话：一个 AppTest 实例 + 一个 URL 会话 id（?u=）。"""

    def __init__(self, sid: str | None = None):
        self.at = AppTest.from_file(APP, default_timeout=30)
        if sid:
            self.at.query_params["u"] = sid
        self.at.run()
        assert not list(self.at.exception), f"首屏异常：{list(self.at.exception)}"

    @property
    def sid(self) -> str:
        return dict(self.at.query_params)["u"]

    @property
    def messages(self) -> list[dict]:
        return list(self.at.session_state["messages"])

    def state(self, key: str):
        return self.at.session_state[key]

    def say(self, text: str) -> str:
        """发一句、等这一轮跑完，返回助手回复。"""
        before = len(self.messages)
        self.at.chat_input[0].set_value(text).run()
        assert not list(self.at.exception), f"对话异常：{list(self.at.exception)}"
        after = self.messages
        assert len(after) == before + 2, f"消息数不对：{len(after)} != {before + 2}"
        assert after[-2] == {"role": "user", "content": text}
        assert after[-1]["role"] == "assistant"
        return after[-1]["content"]


def rows(sid: str | None = None, action: str | None = None) -> list[dict]:
    """读测试期间写下的结构化日志；按会话哈希 / action 过滤。"""
    out: list[dict] = []
    for path in sorted(pathlib.Path(logmod.LOG_DIR).glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    if sid is not None:
        want = logmod.session_hash(sid)
        out = [row for row in out if row["session_hash"] == want]
    if action is not None:
        out = [row for row in out if row["action"] == action]
    return out


def reply_rows(sid: str) -> list[dict]:
    """用户轮日志：摘要是系统动作，不算一轮对话。"""
    return [row for row in rows(sid) if row["action"] != "summary_compress"]


def memory_of(sid: str) -> dict:
    """直接读磁盘上的记忆（走真实 read_memory，含自愈逻辑）。"""
    return memory.read_memory(sid)


def memory_path(sid: str) -> pathlib.Path:
    return pathlib.Path(memory.DATA_DIR) / f"{sid}.json"


def app_source() -> str:
    return pathlib.Path(APP).read_text(encoding="utf-8")
