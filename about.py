"""about.py — "它是什么、不做什么、记了什么"：能力边界与我的数据。

[SAFE] 只读计数，不展示任何原文；删除只调已有的 clear_*，不新增存储、不写日志。
为什么要这一页：不敢用的一半原因是"怕被记录"，另一半是"不知道它能干什么"。
"""
from __future__ import annotations

import logging

import streamlit as st

import episode_store
import memory
import quiz_store
from ui_common import get_session_id

logger = logging.getLogger(__name__)

CAN_DO = (
    "听你说，不打断、不评价，也不急着给建议。",
    "帮你说清楚一团情绪——多问几个具体的，而不是让你「想开点」。",
    "你明确问「怎么办」时，给 1–3 条带时间、动作、量的做法。",
    "记住你自己提起过的事（只存标签与转述，不存原话），侧栏能看到。",
    "你提到危险时先停下来，把求助方式摆在你面前。",
)
CANNOT_DO = (
    "不诊断、不开药，不判断你是不是抑郁。",
    "不替代咨询师、医生，也不替代你身边的朋友。",
    "不保证 24 小时在线：这是课程作品，随时可能下线或换地址。",
    "不承诺保密：涉及安全时，会建议你找真人。",
    "不会主动联系你，也不会记得你没说过的事。",
)
SEE_A_PERSON = (
    "有伤害自己的念头、计划，或者已经这么做了。",
    "睡不着、吃不下、起不来，持续两周以上。",
    "已经影响上课、考试、和人相处。",
    "你想弄清楚「我这是怎么了」——这需要真人来评估。",
)
DATA_NOTE = (
    "都在这台机器的本地 JSON 里，不上传、不进日志；聊天原文不落盘。"
    "云端演示时磁盘是临时的：休眠或重新部署会清空，所以这里不承诺「永久保存」。"
)
OPTIONS = {
    "memory": "对话记忆（概况与标签）",
    "episodes": "情景记忆（你说过的事）",
    "quiz": "测试记录（结果名与分数）",
}
CLEARERS = {
    "memory": memory.clear_memory,
    "episodes": episode_store.clear,
    "quiz": quiz_store.clear,
}


def counts(sid: str) -> dict[str, int]:
    """四类本地记录各有多少：只数条数，不读内容。

    为什么不直接 read_memory：它发现文件不存在时会补写一份默认记忆，
    而"我的数据"页不该因为被打开就产生新文件（看和写要分开）。
    """
    summary_len, at_turn = 0, 0
    if (memory.DATA_DIR / f"{sid}.json").exists():
        mem = memory.read_memory(sid)
        summary_len = len(mem.get("rolling_summary") or "")
        at_turn = int(mem.get("summary_at_turn") or 0)
    return {"summary_len": summary_len, "summary_at_turn": at_turn,
            "episodes": episode_store.count(sid), "quiz": quiz_store.count(sid)}


def delete(sid: str, picks: list[str]) -> list[str]:
    """按勾选真删，返回删到的类别；删不掉只记一条日志，不许崩页面。"""
    done = []
    for key in picks:
        clear = CLEARERS.get(key)
        if clear is None:
            continue
        try:
            clear(sid)
            done.append(key)
        except OSError as exc:                    # 边界：文件删不掉不等于页面要崩
            logger.warning("about_clear_failed kind=%s error=%s",
                           key, type(exc).__name__)
    return done


def _data(sid: str) -> None:
    """我的数据：计数 + 勾选删除；角色卡记忆只说明在哪删。"""
    c = counts(sid)
    st.subheader("我存了什么")
    turn = c["summary_at_turn"]
    st.markdown(
        f"- 对话记忆：概况 {c['summary_len']} 字"
        + (f"，更新于第 {turn} 轮" if turn else "，还没更新过")
        + f"\n- 情景记忆：{c['episodes']} 段（只存转述，不存原话）"
        + f"\n- 测试记录：{c['quiz']} 次（只有结果名与分数，没有答案）"
        + "\n- 角色卡记忆：按卡存在角色卡页面，那里有「清空这张卡的记忆」"
        + "\n- 聊天记录：只在当前页面，刷新就没了")
    st.caption(DATA_NOTE)
    picks = st.multiselect("勾选要删除的内容", list(OPTIONS),
                           format_func=OPTIONS.get, key=f"about_picks_{sid}")
    confirm = st.checkbox("我确认删除勾选的内容，删了找不回来",
                          key=f"about_confirm_{sid}")
    if st.button("删除", type="primary", key=f"about_delete_{sid}",
                 disabled=not (picks and confirm)):
        st.session_state["about_deleted"] = len(delete(sid, picks))
        st.rerun()
    if st.session_state.pop("about_deleted", 0):
        st.success("已删除。下一轮对话会重新开始积累。")


def render(sid: str | None = None) -> None:
    """一页讲清边界与数据；不需要登录，也不读聊天原文。"""
    sid = sid or get_session_id()
    st.subheader("心屿是什么，不是什么")
    st.caption("先说清楚边界，比事后解释有用。")
    for title, items in (("它能做的", CAN_DO), ("它不做的", CANNOT_DO)):
        st.markdown(f"**{title}**")
        for item in items:
            st.markdown(f"- {item}")
    st.markdown("**这几件事，请直接找真人**")
    for item in SEE_A_PERSON:
        st.markdown(f"- {item}")
    st.caption("校心理中心 86878592 · 12356 · 110 / 120")
    st.divider()
    _data(sid)
