"""companion_ui.py — A 模式（陪伴）页面：聊天区、首屏问答与侧栏。

从 app.py 抽出：app 只负责路由，这里只读写 A 的 session_state，
不碰 rc_*，也不判断风险等级。
"""
from __future__ import annotations

import logging

import streamlit as st

import agent
import byok
import chat_ui
import coordinator
import episode_store
import help_pages
import onboard
import quiz_ui
from logger import session_hash
from memory import clear_memory
from orchestrator import safe_run
from panel import (LEVEL_LABELS, REASON_LABELS, ROLE_LABELS,
                   render_panel, render_trace)
from resources import pick_resources
from ui_common import DEFAULT_PERSONA, NET_HINT, get_session_id

logger = logging.getLogger(__name__)

# 侧栏「当前角色」的三个选项：自动是默认，手动只开放 listener / guide。
# crisis 不放进选项：它只由 L3 触发，放进来会让用户以为危机能手动点开。
ROLE_OPTIONS = ("auto",) + coordinator.ROLE_CHOICES
ROLE_OPTION_LABELS = {"auto": "自动判断", **ROLE_LABELS}


def _clear(sid: str) -> None:
    """真删记忆并换新会话：不换 id 的话，侧栏一读记忆文件就会被重建。"""
    for clear_fn in (clear_memory, episode_store.clear, quiz_ui.clear):
        try:
            clear_fn(sid)
        except OSError as exc:                      # 边界：删不掉也不许崩页面
            logger.warning("clear_failed session=%s error=%s",
                           sid[:6], type(exc).__name__)
    st.session_state.messages = []
    st.session_state["last_trace"] = []
    st.session_state["degraded"] = False
    st.session_state["turn"] = 0
    # 清空对话 = 开新会话：冷却与“有过危机”标记必须一起归零，否则新对话永远回不到 guide。
    st.session_state["cooldown"] = 0
    st.session_state["ever_crisis"] = False
    st.session_state["last_role"] = "listener"
    st.session_state["last_level"] = "L1"
    st.session_state["last_reason"] = "default"
    st.session_state["levels"] = []
    st.session_state["ob_open"] = ""
    st.session_state.pop("pending_turn", None)
    st.query_params["u"] = uuid4_hex()
    st.rerun()


def uuid4_hex() -> str:
    """只给 _clear 用；单独一行，避免在函数里再 import uuid。"""
    import uuid
    return uuid.uuid4().hex[:12]


def _role_picker(role: str, reason: str) -> None:
    """侧栏手动选角色：只改 listener / guide，危机仍由等级强制接管。

    选择写回 role_choice，由 orchestrator 在“定角色”与“冷却”之间读走：
    界面这边不做任何判定，冷却期的降级仍由 coordinator 说了算。
    """
    pref = st.session_state.get("role_choice", "auto")
    choice = st.selectbox(
        "当前角色（可切换）", ROLE_OPTIONS,
        index=ROLE_OPTIONS.index(pref) if pref in ROLE_OPTIONS else 0,
        format_func=lambda code: ROLE_OPTION_LABELS.get(code, code),
        help="自动：按你说的话与风险等级切换；危机时一律由系统接管。",
        key="role_pick",
    )
    st.session_state["role_choice"] = choice
    st.caption(f"这一轮：{ROLE_LABELS.get(role, role)} · "
               f"切换原因：{REASON_LABELS.get(reason, reason)}")
    if choice in coordinator.ROLE_CHOICES and choice != role:
        st.caption("手动选择从下一轮开始；危机与危机后的缓冲期由系统接管。")


def _sidebar(sid: str) -> None:
    with st.sidebar:
        quiz_ui.entry()                              # 入口在侧栏顶部，点开才画卡片
        turn = st.session_state.get("turn", 0)
        level = st.session_state.get("last_level", "L1")
        role = st.session_state.get("last_role", "listener")
        reason = st.session_state.get("last_reason", "default")
        st.caption(f"会话 {session_hash(sid)[:6]} · 第 {turn} 轮")
        st.metric("当前风险等级", LEVEL_LABELS.get(level, level))
        _role_picker(role, reason)
        # P20：把"这一轮是聊天还是帮助"写出来，用户才知道刚才的长度是模式选择，不是敷衍。
        if role == "guide":
            st.caption("本轮模式：帮助（可以说到 8 句，给具体步骤）")
            if not agent.web_ready():
                st.caption("检索未开：这一轮只能给通用建议")
        else:
            st.caption("本轮模式：聊天（短句，不主动给方案）")
        st.caption(f"模型来源：{byok.mode_label()}")
        if st.session_state.get("degraded"):
            st.caption(NET_HINT)
        render_panel(sid, _clear)
        render_trace(st.session_state.get("last_trace"))


def _init_state() -> None:
    """A 的会话状态：刷新即重置的字段与持久字段都在这里一次补齐。"""
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("persona_id", DEFAULT_PERSONA)
    # 冷却与“有过危机”只活在本会话：刷新即重置，这是 S11 的既定口径，不是 bug。
    for key, default in (("cooldown", 0), ("ever_crisis", False),
                         ("role_choice", "auto"),
                         ("last_role", "listener"), ("last_level", "L1"),
                         ("last_reason", "default"), ("turn", 0),
                         ("levels", [])):
        st.session_state.setdefault(key, default)
    st.session_state.setdefault("last_trace", [])


def _run_turn(sid: str, text: str) -> None:
    """收一句输入并跑完一轮：管线 → 先落库再渲染 → 侧栏状态。"""
    history, merged, turn = chat_ui.accept(st.session_state.messages, text)
    st.session_state["turn"] = turn
    with st.chat_message("user"):
        st.markdown(text)
    with st.spinner("我在听…"):
        result = safe_run(merged, sid, history,
                          st.session_state.persona_id, st.session_state)
    # 先落库再渲染：渲染这一帧被打断时，回复还在，重绘不会凭空消失。
    st.session_state.messages.append({
        "role": "assistant", "content": result["reply"],
        "sources": result.get("sources") or []})

    def extra() -> None:
        chat_ui.render_sources(result.get("sources"))
        # [SAFE] S10 §8：L2/L3 当轮各出一次资源卡（L2 两张 / L3 三张），L1 为空不打扰。
        # 卡只渲染在本轮，不写进 messages，刷新重绘时不会重复弹（S21 #4 补的口径）。
        for card in pick_resources(result["level"], []):
            st.info(f"{card['title']}：{card['detail']}")

    # P20：帮助模式的分 2–3 个气泡；闲聊保持单气泡（与 P14 之前的观感一致）。
    parts = (chat_ui.reply_parts(result) if result["role"] == "guide"
             else [result["reply"]])
    chat_ui.render_reply(parts, extra=extra)
    st.session_state["last_trace"] = result.get("trace", [])
    st.session_state["degraded"] = result["degraded"]
    st.session_state["last_role"] = result["role"]
    st.session_state["last_level"] = result["level"]
    st.session_state["last_reason"] = result.get("reason", "default")


def _turn(sid: str) -> None:
    """聊天输入；没有输入就什么都不做。"""
    text = (st.chat_input("说说你现在想说的…") or "").strip()
    if text:
        _run_turn(sid, text)


def render(sid: str | None = None) -> None:
    """A 的聊天页：只读写 messages/persona_id 等 A 状态，不碰 rc_*。"""
    sid = sid or get_session_id()
    _init_state()
    pending = st.session_state.pop("pending_turn", "")

    # 首屏引导只在内联卡片里出现：它不挡聊天输入，用户直接打字也能开始。
    # 开场白只算一条 assistant，不算"用户已开口"：卡片与「改一下」留到第一句输入。
    # 从趣味测试页带回来的 pending 句也不再弹引导，用户已经明确要聊结果了。
    has_user = any(m.get("role") == "user" for m in st.session_state.messages)
    has_quiz = any(m.get("quiz") for m in st.session_state.messages)
    if not has_user and not pending and not has_quiz:
        onboard.render(sid)
        kind = st.session_state.get("ob_open", "")
        if kind and not any(m.get("opening") for m in st.session_state.messages):
            line = onboard.opening_line(kind, st.session_state.persona_id)
            if line:
                st.session_state.messages.append(
                    {"role": "assistant", "content": line, "opening": True})

    chat_ui.render_history(st.session_state.messages)
    quiz_ui.render(sid)          # 趣味测试卡片：没点开就什么都不画，也不挡输入
    if pending:
        _run_turn(sid, pending)
    # 无论有没有 pending，都要把输入框放回来；否则从测试页“聊一聊”过来后
    # 只能看到一条自动回复，没法继续说第二句。
    _turn(sid)
    # P26：L3 的「下一步」画在消息流末尾、输入框之外（chat_input 自己进底部容器）。
    # 不能画在 extra 里：那块只在本轮渲染，下一帧按钮就不存在，点击会被丢掉。
    if st.session_state.get("last_level") == "L3" and st.session_state.messages:
        help_pages.next_step_block("chat")
    _sidebar(sid)
