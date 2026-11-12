"""app.py — Streamlit 页面：免责声明 / 聊天区 / 侧栏 / 记忆面板。

管线（判危 → 定角色 → 找事实 → 拼 prompt → 生成 → 审 → 记）在 P1 搬进了
orchestrator.py：页面只调 safe_run()，不再持有任何业务顺序或等级判断。
"""
from __future__ import annotations

import logging
import os
import re
import uuid

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# 线上（Streamlit Cloud）没有 .env，密钥只放在平台的 Secrets 里，读法是 `st.secrets`，
# 不是环境变量。必须在 import memory / agent 之前铺好：memory.py 的 DATA_DIR 是模块级常量。
_SECRET_KEYS = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "MOCK_LLM",
                "DATA_DIR", "LOG_DIR")


def _bridge_secrets() -> None:
    """把 st.secrets 铺进环境变量，只补空缺，不覆盖已有值。

    [SAFE] 这里必须兜底：本地没有 secrets.toml 时读取会抛异常，
    线上没配 Secrets 时也不该崩——真正缺 Key 由 _config_gate 报，不在这里报两遍。
    """
    try:
        items = st.secrets.to_dict() if hasattr(st.secrets, "to_dict") else dict(st.secrets)
    except Exception:                       # 边界：没有 Secrets 是正常情况
        return
    for key in _SECRET_KEYS:
        val = items.get(key)
        if val is not None and not os.getenv(key):
            os.environ[key] = str(val)


_bridge_secrets()

from logger import session_hash                                  # noqa: E402  顺序要紧
from memory import clear_memory                                  # noqa: E402
from orchestrator import safe_run                                # noqa: E402
from panel import LEVEL_LABELS, REASON_LABELS, ROLE_LABELS, render_panel  # noqa: E402
from resources import pick_resources                             # noqa: E402
from theme import inject_theme, theme_picker                     # noqa: E402

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "这是一个情绪陪伴工具，不是心理咨询，也不能替代真人帮助。"
    "如果你或身边的人有危险，请拨打 120 / 110 或 12356。"
)
NET_HINT = "网络不稳定：刚才那条是兜底回复"
DEFAULT_PERSONA = "sister_heart"

# 与 memory.py 的 ID_RE 同口径：会话 id 来自 URL，必须先校验再交给磁盘层。
SID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")


def get_session_id() -> str:
    """会话 id 只放 URL：session_state 刷新即空，放那里记忆就断了。"""
    raw = st.query_params.get("u")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if isinstance(raw, str) and SID_RE.fullmatch(raw):
        return raw
    sid = uuid.uuid4().hex[:12]
    st.query_params["u"] = sid
    return sid


def _config_gate() -> None:
    """配置错误当场报，不许伪装成"网络不稳定"。
    缺 Key 时每一轮都会走到 safe_run，用户看到的却是一句"卡了一下"，排查会跑错方向。
    """
    if os.getenv("MOCK_LLM", "0").strip() == "1":
        return
    if not os.getenv("LLM_API_KEY"):
        st.error("未配置 LLM_API_KEY：请在 .env 填入 Key，或设 MOCK_LLM=1 离线运行。")
        st.stop()


def _render_history(messages: list[dict]) -> None:
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


def _clear(sid: str) -> None:
    """真删记忆并换新会话：不换 id 的话，侧栏一读记忆文件就会被重建。"""
    try:
        clear_memory(sid)
    except OSError as exc:                          # 边界：删不掉也不许崩页面
        logger.warning("clear_failed session=%s error=%s", sid[:6], type(exc).__name__)
    st.session_state.messages = []
    st.session_state["degraded"] = False
    st.session_state["turn"] = 0
    # 清空对话 = 开新会话：冷却与“有过危机”标记必须一起归零，否则新对话永远回不到 guide。
    st.session_state["cooldown"] = 0
    st.session_state["ever_crisis"] = False
    st.session_state["last_role"] = "listener"
    st.session_state["last_level"] = "L1"
    st.session_state["last_reason"] = "default"
    st.session_state["levels"] = []
    st.query_params["u"] = uuid.uuid4().hex[:12]
    st.rerun()


def _sidebar(sid: str) -> None:
    with st.sidebar:
        turn = st.session_state.get("turn", 0)
        level = st.session_state.get("last_level", "L1")
        role = st.session_state.get("last_role", "listener")
        reason = st.session_state.get("last_reason", "default")
        st.caption(f"会话 {session_hash(sid)[:6]} · 第 {turn} 轮")
        st.metric("当前风险等级", LEVEL_LABELS.get(level, level))
        st.metric("当前角色", ROLE_LABELS.get(role, role))
        st.caption(f"切换原因：{REASON_LABELS.get(reason, reason)}")
        if os.getenv("MOCK_LLM", "0").strip() == "1":
            st.caption("离线演示模式（MOCK）")
        if st.session_state.get("degraded"):
            st.caption(NET_HINT)
        render_panel(sid, _clear)


def main() -> None:
    st.set_page_config(page_title="心屿 · 情绪陪伴", layout="centered")
    st.title("心屿")
    st.caption(DISCLAIMER)                         # 第一屏常驻，不折叠
    _config_gate()

    # 主题注入必须早于聊天区渲染；选择器是侧栏第一项，_sidebar 的内容排在它后面。
    inject_theme(theme_picker())

    sid = get_session_id()
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("persona_id", DEFAULT_PERSONA)
    # 冷却与“有过危机”只活在本会话：刷新即重置，这是 S11 的既定口径，不是 bug。
    for key, default in (("cooldown", 0), ("ever_crisis", False),
                         ("last_role", "listener"), ("last_level", "L1"),
                         ("last_reason", "default"), ("turn", 0),
                         ("levels", [])):
        st.session_state.setdefault(key, default)

    _render_history(st.session_state.messages)

    text = (st.chat_input("说说你现在想说的…") or "").strip()
    if text:
        st.session_state["turn"] += 1
        st.session_state.messages.append({"role": "user", "content": text})
        with st.chat_message("user"):
            st.markdown(text)
        with st.chat_message("assistant"):
            with st.spinner("我在听…"):
                result = safe_run(text, sid, st.session_state.messages,
                                  st.session_state.persona_id, st.session_state)
            st.markdown(result["reply"])
            # [SAFE] S10 §8：L2/L3 当轮各出一次资源卡（L2 两张 / L3 三张），L1 为空不打扰。
            # 卡只渲染在本轮，不写进 messages，刷新重绘时不会重复弹（S21 #4 补的口径）。
            for card in pick_resources(result["level"], []):
                st.info(f"{card['title']}：{card['detail']}")
        st.session_state.messages.append({"role": "assistant", "content": result["reply"]})
        st.session_state["degraded"] = result["degraded"]
        st.session_state["last_role"] = result["role"]
        st.session_state["last_level"] = result["level"]
        st.session_state["last_reason"] = result.get("reason", "default")

    _sidebar(sid)


if __name__ == "__main__":
    main()