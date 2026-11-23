"""rolecard_conversations.py — P39 角色卡对话的会话胶水与历史列表。

rolecard_ui 只管“当前这一页”；这里负责换会话、保存当前、从磁盘载入，
以及列表上的继续/删除/新建。记录格式与清洗在 rolecard_chat_store。
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

import rolecard_chat_store as store
from rolecard_form import reset_form


def reset_session(card: dict | None, view: str = "") -> None:
    """开新会话：换 rc_sid、清对话与临时资料；卡留下（重开）或清空（换卡）。"""
    s = st.session_state
    s.rc_card = card
    s.rc_messages = []
    s.rc_state = store.new_state()
    s.rc_sid = store.new_id()
    s.rc_ended = False
    s.rc_errors = []
    s.rc_gap_tried = set()
    s.rc_gap_lines = []
    s.rc_focus_result = None
    s.rc_focus_note = ""
    s.rc_view = view
    s.rc_edit_open = False
    s.rc_edit_errors = []
    s.rc_delete_id = ""
    s.rc_save_failed = False


def save_current(sid: str) -> bool:
    """保存当前会话；还没说过话就返回 True，不建空记录。"""
    s = st.session_state
    card = s.get("rc_card")
    messages = s.get("rc_messages") or []
    if not isinstance(card, dict) or not messages:
        return True
    return store.save(sid, s.get("rc_sid"), card, messages,
                      s.get("rc_state") or {}, bool(s.get("rc_ended")))


def load_into_session(sid: str, conv_id: str) -> bool:
    """把一条记录放回 rc_*；坏记录不动当前会话，返回 False。"""
    record = store.load(sid, conv_id)
    if not record:
        return False
    reset_session(record["card"], "chat")
    s = st.session_state
    s.rc_sid = record["id"]
    s.rc_messages = record["messages"]
    s.rc_state = record["state"]
    s.rc_ended = record["ended"]
    return True


def _stamp(value: float) -> str:
    return datetime.fromtimestamp(value, store.CN_TZ).strftime("%m-%d %H:%M")


def _new_conversation() -> None:
    reset_session(None, "form")
    reset_form()


def _open(sid: str, conv_id: str) -> None:
    if not load_into_session(sid, conv_id):
        st.error("这条记录读不出来，可能在保存时损坏了。")
        return
    st.rerun()


def _delete(sid: str, conv_id: str) -> None:
    if not store.delete(sid, conv_id):
        st.error("删除失败，文件可能正被占用；稍后再试。")
        return
    if st.session_state.get("rc_sid") == conv_id:
        reset_session(None, "list")
    st.session_state["rc_delete_id"] = ""
    st.rerun()


def _row(sid: str, row: dict) -> None:
    """一条记录：标题、轮次、更新时间、继续/删除；删除必须二次确认。"""
    with st.container(border=True):
        left, right = st.columns([4, 2])
        left.markdown(f"**{row['title']}**")
        status = " · 已暂停" if row["ended"] else ""
        left.caption(f"{row['turns']} 轮 · 更新于 {_stamp(row['updated_at'])}{status}")
        if right.button("继续", key=f"rc_open_{row['id']}", type="primary"):
            _open(sid, row["id"])
        if right.button("删除", key=f"rc_del_{row['id']}"):
            st.session_state["rc_delete_id"] = row["id"]
            st.rerun()
        if st.session_state.get("rc_delete_id") == row["id"]:
            st.warning("删除后找不回来。确定删掉这一条？")
            cols = st.columns(2)
            if cols[0].button("确认删除", key=f"rc_del_yes_{row['id']}"):
                _delete(sid, row["id"])
            if cols[1].button("取消", key=f"rc_del_no_{row['id']}"):
                st.session_state["rc_delete_id"] = ""
                st.rerun()


def render_list(sid: str) -> None:
    """对话记录页：按 sid 隔离；没有记录时给新建入口。"""
    st.subheader("对话记录")
    st.caption("只存在当前部署的磁盘上；同一链接的人能看到。"
               "云上重新部署可能丢，重要内容请自己留一份。")
    rows = store.list_chats(sid)
    if not rows:
        st.info("还没有保存的对话。")
    for row in rows:
        _row(sid, row)
    if st.button("＋ 新建对话", key="rc_new_chat", type="primary"):
        _new_conversation()
        st.rerun()
