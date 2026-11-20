"""rolecard_ui.py — B 模式（角色卡）：免责 gate / 角色内对话 / 盲点补全 / 侧栏。

表单在 rolecard_form.py；自动盲点补全在这里的 _maybe_fill_gap，手动补全在
rolecard_focus.py。边界：B 的对话只在 rc_messages，刷新即空；不读 memory.json、
不调 memory.update_memory。长期记忆按卡存在 rolecard_memory（默认
$DATA_DIR/rolecards/<card_key>.json），刷新后同卡还在；侧栏可单独清空。
L3 后只暂停，确认安全可继续同一会话；这次事件进不可淘汰的重点记忆。
唯一另一处落盘是「上一张卡」（$DATA_DIR/rolecards/last.json），只存卡字段，
供建卡页一键继承，不进 memory.json、不进日志。
"""
from __future__ import annotations

import os
import uuid

import streamlit as st

import chat_ui
import guardian
import help_pages
import rolecard
import rolecard_enrich
import rolecard_focus
import rolecard_gap
import rolecard_memory
from orchestrator import safe_run
from panel import LEVEL_LABELS, ROLE_LABELS, render_trace
from resources import pick_resources
from rolecard_form import render_form, reset_form

NET_HINT = "网络不稳定：刚才那条是兜底回复"
STATE_DEFAULTS = {
    "turn": 0, "cooldown": 0, "ever_crisis": False, "levels": [],
    "last_trace": [], "last_level": "L1", "last_role": "listener",
    "last_reason": "default", "degraded": False,
}


def _new_state() -> dict:
    """B 的会话态与 A 同构，但只活在 rc_state 里，不落 memory。"""
    return {k: (v.copy() if isinstance(v, list) else v) for k, v in STATE_DEFAULTS.items()}


def _new_sid() -> str:
    """rc- 前缀让日志/排障一眼分清 A 与 B；这个 id 不写 URL，刷新即换。"""
    return "rc-" + uuid.uuid4().hex[:12]


def ensure_state() -> None:
    """初始化 B 的 session_state；切模式、重跑都不重置已有对话。"""
    st.session_state.setdefault("rc_sid", _new_sid())
    st.session_state.setdefault("rc_messages", [])
    st.session_state.setdefault("rc_state", _new_state())
    st.session_state.setdefault("rc_card", None)
    st.session_state.setdefault("rc_consent", False)
    st.session_state.setdefault("rc_ended", False)
    st.session_state.setdefault("rc_errors", [])
    st.session_state.setdefault("rc_enrich_result", None)
    st.session_state.setdefault("rc_enrich_note", "")
    st.session_state.setdefault("rc_origin", "original")
    st.session_state.setdefault("rc_address", "你")
    st.session_state.setdefault("rc_user_role", "用户")
    st.session_state.setdefault("rc_stage", "none")
    st.session_state.setdefault("rc_lore_text", "")
    st.session_state.setdefault("rc_auto_gap", True)
    st.session_state.setdefault("rc_gap_tried", set())
    st.session_state.setdefault("rc_gap_lines", [])
    st.session_state.setdefault("rc_focus_result", None)
    st.session_state.setdefault("rc_focus_note", "")
    for key, default in _new_state().items():
        st.session_state.rc_state.setdefault(key, default)


def _agree() -> None:
    """回调写独立键：勾选框本身会在 gate 消失后卸载，不能把同意状态挂在它身上。"""
    st.session_state["rc_consent"] = bool(st.session_state.get("rc_consent_box"))


def render_gate() -> None:
    """先免责再建卡：未勾选时既不渲染表单，也不渲染聊天输入。"""
    st.subheader("角色卡模式")
    st.caption("先读这几条；看懂并同意后再开始。")
    for item in rolecard.DISCLAIMER_ITEMS:
        st.markdown(f"- {item}")
    st.checkbox("我已阅读并理解以上说明", key="rc_consent_box", on_change=_agree)


def _reset_session(card: dict | None) -> None:
    """开新会话：换 rc_sid、清对话与临时资料；卡留下（重开）或清空（换卡）。"""
    st.session_state.rc_card = card
    st.session_state.rc_messages = []
    st.session_state.rc_state = _new_state()
    st.session_state.rc_sid = _new_sid()
    st.session_state.rc_ended = False
    st.session_state.rc_errors = []
    st.session_state.rc_gap_tried = set()
    st.session_state.rc_gap_lines = []
    st.session_state.rc_focus_result = None
    st.session_state.rc_focus_note = ""


def _start(card: dict) -> None:
    """开始时清空上一段对话并换 rc_sid：同一个人设也按新会话记日志。"""
    _reset_session(card)


def _change_card() -> None:
    """回调：回建卡页并清空表单；要沿用上一张就点「继承上一张角色卡」。"""
    _reset_session(None)
    reset_form()


def _maybe_fill_gap(text: str, card: dict) -> tuple[dict, dict | None]:
    """自动盲点补全：L3/MOCK/原创/开关关都不联网；每个专名只试一次。"""
    if not st.session_state.get("rc_auto_gap", True):
        return card, None
    if os.getenv("MOCK_LLM", "0").strip() == "1":
        return card, None
    focus = rolecard_gap.detect_focus(text, card)
    tried = st.session_state.setdefault("rc_gap_tried", set())
    if not focus or focus in tried:
        return card, None
    level = guardian.guardian_pre_check(text).get("level", "L1")
    if not rolecard_gap.should_fill(card, focus, level=level):
        return card, None
    tried.add(focus)
    # 新盲点开始就丢掉上一次的临时资料，失败时也不会拿旧资料答新问题。
    st.session_state.rc_gap_lines = []
    with st.spinner(f"我先去回忆一下{focus}…"):
        result = rolecard_enrich.enrich(card, focus=focus)
    if not result.get("ok"):
        code = result.get("error") or "empty"
        return card, {"focus": focus,
                      "error": rolecard_enrich.ERROR_LABELS.get(code, code)}
    # 自动补全只吃官方/Wiki；社区帖（含米游社、17173）留给人手动选。
    trusted = rolecard_enrich.auto_facts(result["facts"])
    lines = rolecard_gap.gap_lines(trusted, focus=focus)
    if not lines:
        return card, {"focus": focus, "count": 0,
                      "sources": result.get("sources") or [],
                      "note": "只找到社区/其他资料，未自动写入；可在下方手动补全。"}
    st.session_state.rc_gap_lines = lines
    return card, {"focus": focus, "count": len(lines),
                  "sources": result.get("sources") or [],
                  "note": "仅采用官方/Wiki 来源；只用于本次对话"}


def _finish_turn(state: dict, result: dict) -> None:
    """更新侧栏态；L3 收尾放在这里，保证 render_chat 不超过 40 行。"""
    state["last_trace"] = result.get("trace", [])
    state["degraded"] = result["degraded"]
    state["last_role"] = result["role"]
    state["last_level"] = result["level"]
    state["last_reason"] = result.get("reason", "default")
    if result["level"] == "L3":
        # [SAFE] P12：L3 先暂停整个 B 会话；这次事件进重点记忆，风险等级不降。
        card = st.session_state.get("rc_card")
        if isinstance(card, dict):
            rolecard_memory.mark_crisis(card)
        st.session_state.rc_ended = True
        st.rerun()


def render_chat(card: dict, sid: str, state: dict) -> None:
    """B 的一轮：合流 → 盲点补全 → safe_run → 先落库再渲染 → 侧栏态。"""
    chat_ui.render_history(st.session_state.rc_messages)
    rolecard_focus.render(card)
    text = (st.chat_input("以角色的身份说点什么…", key="rc_chat_input") or "").strip()
    if not text:
        return
    if rolecard.is_switch_request(text):
        st.info(rolecard.SWITCH_TO_B_LINE)
        return

    history, merged, turn = chat_ui.accept(st.session_state.rc_messages, text)
    state["turn"] = turn
    with st.chat_message("user"):
        st.markdown(text)
    card, gap = _maybe_fill_gap(merged, card)
    hint_card = dict(card)
    hint = rolecard.question_hint(st.session_state.rc_messages)
    if hint:
        hint_card["_hint"] = hint
    gap_lines = st.session_state.get("rc_gap_lines") or []
    if gap_lines:
        hint_card["_gap"] = gap_lines
    with st.spinner("我在听…"):
        result = safe_run(merged, sid, history, hint_card, state)
    parts = chat_ui.reply_parts(result)
    st.session_state.rc_messages.append({
        "role": "assistant", "content": result["reply"],
        "sources": result.get("sources") or [], "gap": gap, "parts": parts})

    def extra() -> None:
        chat_ui.render_gap(gap)
        for item in pick_resources(result["level"], []):
            st.info(f"{item['title']}：{item['detail']}")

    chat_ui.render_reply(parts, animate=True, extra=extra)
    # 盲点资料只服务这一轮；历史里保留了 gap 备注，下一轮不再喂回 prompt。
    st.session_state.rc_gap_lines = []
    _finish_turn(state, result)


def render_ended() -> None:
    """L3 之后：历史可见、输入关闭；确认安全后可继续同一会话。"""
    chat_ui.render_history(st.session_state.rc_messages)
    st.warning("这次角色对话先停在这里。先把安全放在前面。")
    for item in pick_resources("L3", []):
        st.info(f"{item['title']}：{item['detail']}")
    # P26：和 A 模式同一块——先给一个号，再给一句能直接发出去的话。
    help_pages.next_step_block("rc")
    st.markdown("**如果想继续聊，请先调整好自己的状态，并确认现在是安全的。**")
    st.caption("如果还在危险里，请先联系上面的人。")
    if st.button("我好些了，继续吧", key="rc_resume"):
        # [SAFE] 只恢复对话入口，不重置 rc_state：下一轮仍按 L2 地板起算。
        card = st.session_state.get("rc_card")
        if isinstance(card, dict):
            rolecard_memory.mark_resumed(card)
        st.session_state.rc_ended = False
        st.rerun()
    cols = st.columns(2)
    if cols[0].button("重新开始", key="rc_restart"):
        _reset_session(st.session_state.rc_card)   # 同一张卡、新会话
        st.rerun()
    if cols[1].button("回到陪伴模式", key="rc_back"):
        st.session_state["mode"] = "companion"
        st.rerun()


def render_sidebar(state: dict) -> None:
    """B 的侧栏：只读 rc_state 与这张卡的记忆文件；不读 memory.json。"""
    with st.sidebar:
        if st.button("回首页", key="rc_home"):
            st.session_state["mode"] = "home"
            st.rerun()
        st.caption(f"角色卡模式 · 第 {state.get('turn', 0)} 轮")
        if st.session_state.get("rc_card") is not None:
            st.button("换一张卡", key="rc_change_card", on_click=_change_card)
            episodes, summary_len = rolecard_memory.stats(st.session_state.rc_card)
            keys = rolecard_memory.key_count(st.session_state.rc_card)
            st.caption(f"记得 {episodes} 段 · 重点 {keys} 条 · 摘要 {summary_len} 字")
            if st.button("清空这张卡的记忆", key="rc_clear_memory"):
                rolecard_memory.clear(st.session_state.rc_card)
                st.rerun()
        level = state.get("last_level", "L1")
        role = state.get("last_role", "listener")
        st.metric("当前风险等级", LEVEL_LABELS.get(level, level))
        st.metric("当前角色", ROLE_LABELS.get(role, role))
        if os.getenv("MOCK_LLM", "0").strip() == "1":
            st.caption("离线演示模式（MOCK）")
        if state.get("degraded"):
            st.caption(NET_HINT)
        render_trace(state.get("last_trace"))


def render() -> None:
    """B 页面入口：gate → 建卡 → 对话；L3 后只留结束页。"""
    ensure_state()
    if not st.session_state.rc_consent:
        render_gate()
    elif st.session_state.rc_ended:
        render_ended()
    elif st.session_state.rc_card is None:
        render_form(_start)
    else:
        render_chat(st.session_state.rc_card, st.session_state.rc_sid,
                    st.session_state.rc_state)
    render_sidebar(st.session_state.rc_state)
