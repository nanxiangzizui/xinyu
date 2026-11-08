"""app.py — Streamlit 页面：免责声明 / 聊天区 / 侧栏 / 固定七步管线。

管线顺序从 S05 起冻结（后续步骤只换零件，不换顺序）：
    判危 → 定角色 → 找事实 → 拼 prompt → 生成 → 审 → 记
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

from agent import build_system_prompt, call_llm              # noqa: E402  顺序要紧
from coordinator import coordinator_decide                   # noqa: E402
from guardian import guardian_post_check, guardian_pre_check  # noqa: E402
from memory import clear_memory, match_lore, read_memory, update_memory  # noqa: E402

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "这是一个情绪陪伴工具，不是心理咨询，也不能替代真人帮助。"
    "如果你或身边的人有危险，请拨打 120 / 110 或 12356。"
)
FALLBACK_LINE = "我这边刚刚卡了一下，但我在。你可以再说一句吗？"
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


def handle(text: str, sid: str, history: list[dict], persona_id: str) -> dict:
    """七步固定管线；异常交给 safe_handle，不在这里吞。"""
    memory = read_memory(sid)                                      # 前置：读记忆
    pre = guardian_pre_check(text)                                 # 1 判危
    dec = coordinator_decide(memory, text, pre["level"])           # 2 定角色
    lore = match_lore(text, sid)                                   # 3 找事实（sid 用于同会话限次）
    prompt = build_system_prompt(persona_id, memory, lore)         # 4 拼 prompt
    resp = call_llm([{"role": "system", "content": prompt},        # 5 生成
                     *history[-10:]])
    post = guardian_post_check(text, resp.get("text", ""),         # 6 审
                               pre["level"], dec["role"])
    fixed = post.get("fixed_reply")
    reply = fixed or resp.get("text") or FALLBACK_LINE
    update_memory(sid, text, reply)                                # 7 记
    return {
        "reply": reply,
        "level": pre["level"],
        "role": dec["role"],
        # 只看字符串会把“模型失败、guardian 换成安全兜底”误判成正常回复（S13 起会发生）。
        "degraded": (not resp.get("ok", False)) or reply == FALLBACK_LINE,
    }


def safe_handle(text: str, sid: str, history: list[dict], persona_id: str) -> dict:
    """任何异常都变成一句人话；日志只记类型名，不记原文与堆栈。"""
    try:
        return handle(text, sid, history, persona_id)
    except Exception as exc:                       # 边界：界面永不显示 traceback
        logger.warning("pipeline_failed session=%s error=%s",
                       sid[:6], type(exc).__name__)
        # 判危失败时风险未知，按中风险记录；绝不按 L1 当“没事”。
        return {"reply": FALLBACK_LINE, "level": "L2", "role": "listener",
                "degraded": True}


def _config_gate() -> None:
    """配置错误当场报，不许伪装成"网络不稳定"。
    缺 Key 时每一轮都会走到 safe_handle，用户看到的却是一句"卡了一下"，排查会跑错方向。
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
    st.query_params["u"] = uuid.uuid4().hex[:12]
    st.rerun()


def _sidebar(sid: str) -> None:
    with st.sidebar:
        st.caption(f"会话 {sid[:6]}")
        st.metric("当前角色", "listener")          # S12 换真实值
        st.metric("当前风险等级", "L1")             # S12 换真实值
        if os.getenv("MOCK_LLM", "0").strip() == "1":
            st.caption("离线演示模式（MOCK）")
        if st.session_state.get("degraded"):
            st.caption(NET_HINT)
        with st.expander("它在记什么"):
            st.json(read_memory(sid))
        st.caption("只记标签与摘要，不存聊天原文；刷新后聊天记录不会恢复。")
        if st.button("清空这次对话"):
            _clear(sid)


def main() -> None:
    st.set_page_config(page_title="心屿 · 情绪陪伴", layout="centered")
    st.title("心屿")
    st.caption(DISCLAIMER)                         # 第一屏常驻，不折叠
    _config_gate()

    sid = get_session_id()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "persona_id" not in st.session_state:
        st.session_state.persona_id = DEFAULT_PERSONA

    _render_history(st.session_state.messages)

    text = (st.chat_input("说说你现在想说的…") or "").strip()
    if text:
        st.session_state.messages.append({"role": "user", "content": text})
        with st.chat_message("user"):
            st.markdown(text)
        with st.chat_message("assistant"):
            with st.spinner("我在听…"):
                result = safe_handle(text, sid, st.session_state.messages,
                                     st.session_state.persona_id)
            st.markdown(result["reply"])
        st.session_state.messages.append({"role": "assistant", "content": result["reply"]})
        st.session_state["degraded"] = result["degraded"]

    _sidebar(sid)


if __name__ == "__main__":
    main()
