"""rolecard_ui.py — B 模式（角色卡）：免责 gate / 角色内对话 / 盲点补全 / 侧栏。

表单在 rolecard_form.py；自动盲点补全在这里的 _maybe_fill_gap，手动补全在
rolecard_focus.py。B 的对话与状态会按浏览器 sid 保存到
$DATA_DIR/rolecards/chats/<sid>/，刷新后可从「对话记录」继续；不读 memory.json、
不调 memory.update_memory。长期记忆按卡存在 rolecard_memory（默认
$DATA_DIR/rolecards/<card_key>.json），侧栏可单独清空。
L3 后只暂停，确认安全可继续同一会话；这次事件进不可淘汰的重点记忆。
另一处落盘是「上一张卡」（$DATA_DIR/rolecards/last.json），只存卡字段，
供建卡页一键继承，不进 memory.json、不进日志。
"""
from __future__ import annotations

import os

import streamlit as st

import chat_ui
import guardian
import help_pages
import rolecard
import rolecard_chat_store as chat_store
import rolecard_conversations as conversations
import rolecard_edit
import rolecard_enrich
import rolecard_focus
import rolecard_gap
import rolecard_memory
from orchestrator import safe_run
from panel import LEVEL_LABELS, ROLE_LABELS, render_trace
from resources import pick_resources
from rolecard_form import render_form, reset_form, save_last

NET_HINT = "网络不稳定：刚才那条是兜底回复"


def _history_enabled() -> bool:
    return os.getenv("ROLECARD_HISTORY", "1").strip() != "0"


def _edit_enabled() -> bool:
    return os.getenv("ROLECARD_EDIT", "1").strip() != "0"


def ensure_state() -> None:
    """初始化 B 的 session_state；切模式、重跑都不重置已有对话。"""
    s = st.session_state
    s.setdefault("rc_sid", chat_store.new_id())
    s.setdefault("rc_messages", [])
    s.setdefault("rc_state", chat_store.new_state())
    s.setdefault("rc_card", None)
    s.setdefault("rc_consent", False)
    s.setdefault("rc_ended", False)
    s.setdefault("rc_errors", [])
    s.setdefault("rc_enrich_result", None)
    s.setdefault("rc_enrich_note", "")
    s.setdefault("rc_origin", "original")
    s.setdefault("rc_address", "你")
    s.setdefault("rc_user_role", "用户")
    s.setdefault("rc_stage", "none")
    s.setdefault("rc_lore_text", "")
    s.setdefault("rc_auto_gap", True)
    s.setdefault("rc_gap_tried", set())
    s.setdefault("rc_gap_lines", [])
    s.setdefault("rc_focus_result", None)
    s.setdefault("rc_focus_note", "")
    s.setdefault("rc_view", "")
    s.setdefault("rc_edit_open", False)
    s.setdefault("rc_edit_errors", [])
    s.setdefault("rc_delete_id", "")
    s.setdefault("rc_save_failed", False)
    for key, default in chat_store.new_state().items():
        s.rc_state.setdefault(key, default)


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


def _save_or_warn(sid: str) -> bool:
    """保存失败不冒异常；留在当前会话，侧栏给一句提示。"""
    if not _history_enabled():        # 关掉记录就是旧行为：不落盘、不建目录
        return True
    if conversations.save_current(sid):
        st.session_state.rc_save_failed = False
        return True
    st.session_state.rc_save_failed = True
    return False


def _start(card: dict) -> None:
    """开始时清空上一段对话并换 rc_sid：同一个人设也按新会话记日志。"""
    conversations.reset_session(card, "chat")


def _change_card(sid: str) -> None:
    """回调：先保存当前对话，再回建卡页；保存失败就不丢当前会话。"""
    if not _save_or_warn(sid):
        return
    conversations.reset_session(None, "form")
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


def _finish_turn(state: dict, result: dict) -> bool:
    """更新侧栏态；L3 只标结束，由调用方先落盘再 rerun。"""
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
        return True
    return False


def _show_save_error() -> None:
    if st.session_state.get("rc_save_failed"):
        st.warning("这段对话没能保存到本地；先别刷新页面。")


def render_chat(card: dict, sid: str, state: dict) -> None:
    """B 的一轮：合流 → 盲点补全 → safe_run → 先落库再渲染 → 侧栏态。"""
    chat_ui.render_history(st.session_state.rc_messages)
    rolecard_focus.render(card)
    if _edit_enabled():
        new_card = rolecard_edit.render(card)
        if isinstance(new_card, dict):
            card = new_card
            st.session_state.rc_card = card
            st.session_state.rc_last_card = card
            save_last(card)
            _save_or_warn(sid)
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
    # 先落用户这一句：这一轮生成到一半刷新，至少不丢刚说的话。
    _save_or_warn(sid)
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
    ended = _finish_turn(state, result)
    _save_or_warn(sid)
    if ended:
        st.rerun()


def render_ended(sid: str) -> None:
    """L3 之后：历史可见、输入关闭；确认安全后可继续同一会话。"""
    chat_ui.render_history(st.session_state.rc_messages)
    st.warning("这次角色对话先停在这里。先把安全放在前面。")
    _show_save_error()
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
        _save_or_warn(sid)
        st.rerun()
    cols = st.columns(3)
    if cols[0].button("重新开始", key="rc_restart"):
        if _save_or_warn(sid):
            conversations.reset_session(st.session_state.rc_card, "chat")
            st.rerun()
    if cols[1].button("对话记录", key="rc_ended_history"):
        if _save_or_warn(sid):
            conversations.reset_session(None, "list")
            st.rerun()
    if cols[2].button("回到陪伴模式", key="rc_back"):
        st.session_state["mode"] = "companion"
        st.rerun()


def render_sidebar(state: dict, sid: str) -> None:
    """B 的侧栏：只读 rc_state 与这张卡的记忆文件；不读 memory.json。"""
    with st.sidebar:
        _show_save_error()
        st.caption(f"角色卡模式 · 第 {state.get('turn', 0)} 轮")
        if (st.session_state.get("rc_consent") and _history_enabled()
                and chat_store.count(sid) > 0):
            if st.button("对话记录", key="rc_history"):
                if (st.session_state.get("rc_card") is None
                        or _save_or_warn(sid)):
                    conversations.reset_session(None, "list")
                    st.rerun()
        if st.session_state.get("rc_card") is not None:
            st.button("换一张卡", key="rc_change_card",
                      on_click=_change_card, args=(sid,))
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


def render(sid: str) -> None:
    """B 页面入口：gate → 对话/结束页 → 建卡/历史 → 侧栏。"""
    ensure_state()
    card = st.session_state.rc_card
    if not st.session_state.rc_consent:
        render_gate()
    elif card is not None:
        if st.session_state.rc_ended:
            render_ended(sid)
        else:
            render_chat(card, sid, st.session_state.rc_state)
    elif st.session_state.rc_view == "form":
        render_form(_start)
    elif _history_enabled() and chat_store.count(sid) > 0:
        conversations.render_list(sid)
    else:
        render_form(_start)
    render_sidebar(st.session_state.rc_state, sid)
