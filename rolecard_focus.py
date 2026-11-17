"""rolecard_focus.py — B 聊天页的“补全设定/人物”入口（手动联网一次）。

自动补全在 rolecard_ui._maybe_fill_gap；这里是用户主动指定对象时的补全。
结果只写本次 rc_gap_lines，不写盘、不写 memory；来源链接由代码渲染。
"""
from __future__ import annotations

import streamlit as st

import rolecard_enrich
import rolecard_gap
from rolecard_form import conflict_text, fact_label

FOCUS_HINT = "她好像不认识这个；可以在下面补全一次。"


def _apply_focus() -> None:
    """回调：把选中的盲点事实放进本次对话的临时资料；不改角色卡。"""
    result = st.session_state.get("rc_focus_result") or {}
    facts = [fact for idx, fact in enumerate(result.get("facts", []))
             if st.session_state.get(
                 f"rc_focus_fact_{idx}",
                 fact.get("authority") in rolecard_enrich.AUTHORITATIVE)]
    lines = rolecard_gap.gap_lines(facts, focus=result.get("focus") or "")
    if not lines:
        st.session_state.rc_focus_note = "没选中可用的经历/关系；角色卡没有改动。"
    else:
        st.session_state.rc_gap_lines = lines
        st.session_state.rc_focus_note = (
            f"已补全 {len(lines)} 条；只用于本次对话。"
            "要长期保留，请回建卡页填「角色认知」。")
    st.session_state.rc_focus_result = None


def _render_result() -> None:
    """候选事实、冲突与来源；应用后只影响本次对话。"""
    note = st.session_state.get("rc_focus_note")
    if note:
        st.success(note)
    result = st.session_state.get("rc_focus_result")
    if not result:
        return
    if not result.get("ok"):
        code = result.get("error") or "empty"
        st.warning("没能补全：" + rolecard_enrich.ERROR_LABELS.get(code, code))
        return
    st.caption("候选认知（官方/Wiki 默认勾选，社区/其他默认不选；只加入本次对话，不写盘）：")
    for idx, fact in enumerate(result.get("facts", [])):
        st.checkbox(fact_label(fact),
                    value=fact.get("authority") in rolecard_enrich.AUTHORITATIVE,
                    key=f"rc_focus_fact_{idx}")
    for conflict in result.get("conflicts", []):
        st.caption(conflict_text(conflict))
    for src in result.get("sources", []):
        st.markdown(f"- [{src.get('title') or src['url']}]({src['url']})")
    st.button("加入本次角色认知", key="rc_focus_apply", on_click=_apply_focus)


def render(card: dict) -> None:
    """已知角色才显示；输入只发作品名/角色名/对象，不发送聊天原文。"""
    if card.get("origin") != "known":
        last = next((msg for msg in reversed(st.session_state.get("rc_messages", []))
                     if msg.get("role") == "assistant"), None)
        if last and rolecard_gap.missing_hint(last.get("content", "")):
            st.caption("原创角色没有公开资料；可以回建卡页补「角色认知」。")
        return
    last = next((msg for msg in reversed(st.session_state.get("rc_messages", []))
                 if msg.get("role") == "assistant"), None)
    if last and rolecard_gap.missing_hint(last.get("content", "")):
        st.caption(FOCUS_HINT)
    with st.expander("补全设定或人物（联网一次）"):
        st.caption("只发送作品名、角色名和你填的词；不会发送聊天原文。")
        focus = st.text_input("要补全谁/什么？", key="rc_focus_input",
                              placeholder="例如：青砚 的经历")
        if st.button("检索并提取", key="rc_focus_run",
                     disabled=not focus.strip()):
            for key in [key for key in st.session_state if key.startswith("rc_focus_fact_")]:
                del st.session_state[key]
            with st.spinner("正在检索公开资料…"):
                st.session_state.rc_focus_result = rolecard_enrich.enrich(
                    card, focus=focus)
            st.session_state.rc_focus_note = ""
        _render_result()
        if st.session_state.get("rc_gap_lines"):
            st.caption(f"本次对话临时资料：{len(st.session_state.rc_gap_lines)} 条")
            if st.button("清除本次盲点资料", key="rc_focus_clear"):
                st.session_state.rc_gap_lines = []
                st.session_state.rc_focus_note = "已清除本次盲点资料。"
                st.rerun()
