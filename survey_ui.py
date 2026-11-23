"""survey_ui.py — P44 匿名问卷页：声明 → 勾选 → 10 题 → 提交，回收数据只在管理页出现。

不调 agent / orchestrator / guardian，不读也不写 memory，不发任何网络请求；
页面上说的「不调用 AI、不进记忆」由 tests/test_survey.py 用桩证明。
"""
from __future__ import annotations

import hmac
import os
from datetime import date

import streamlit as st

import survey_data as D
import survey_store as store

DONE_KEY = "survey_done"
N_KEY = "survey_n"


def enabled() -> bool:
    """SURVEY=0 隐藏入口（回滚用），默认开。"""
    return os.getenv("SURVEY", "1").strip() != "0"


def _admin_password() -> str:
    return (os.getenv("SURVEY_ADMIN") or "").strip()


def _notice() -> None:
    st.caption("10 题，约 3 分钟；全部是选择题，最后一题可以空着。")
    st.markdown(D.PURPOSE)
    for line in D.NOTICE:
        st.markdown(f"- {line}")


def _suffix() -> int:
    """换一个人填时 +1，让 10 个控件的 key 全换新的，等于清空整张表。"""
    return int(st.session_state.get(N_KEY, 0))


def _ask() -> None:
    """一屏 10 题：单选用 radio（不预选），多选用 multiselect。"""
    n = _suffix()
    with st.form(f"survey_form_{n}"):
        for qid, text, options, multi, _max in D.QUESTIONS:
            if qid == D.Q10_ID:
                st.text_area(text, key=f"{qid}_{n}", max_chars=D.Q10_MAX,
                             placeholder="可以空着")
            elif multi:
                st.multiselect(text, list(options), key=f"{qid}_{n}",
                               help="可多选，最多两项" if qid in D.MAX_PICK else None)
            else:
                st.radio(text, list(options), index=None, key=f"{qid}_{n}")
        submit = st.form_submit_button("提交")
    if not submit:
        return
    answers = {qid: st.session_state.get(f"{qid}_{n}") for qid in D.IDS}
    over = [qid for qid in D.MAX_PICK
            if len(answers.get(qid) or []) > D.MAX_PICK[qid]]
    if over:
        st.error(f"第 {over[0][1:]} 题最多选两项，请去掉一项再提交。")
        return
    clean = store.normalise(answers)
    if not clean:
        st.warning("你还没选任何一项。可以直接关掉页面，也可以至少选一题再提交。")
        return
    store.append(clean)
    st.session_state[DONE_KEY] = True
    st.rerun()


def _thanks() -> None:
    st.success("收到了，谢谢。")
    st.markdown("你的答案只用于汇总人数、用来改进心屿，**不会写进聊天记忆**，"
                "也不会改变心屿之后跟你说话的方式。")
    if st.button("换一个人填", key="survey_again"):
        st.session_state[DONE_KEY] = False
        st.session_state[N_KEY] = int(st.session_state.get(N_KEY, 0)) + 1
        st.rerun()


def _admin() -> None:
    """没配 SURVEY_ADMIN 时整块不渲染（不是显示密码错误）。"""
    password = _admin_password()
    if not password:
        return
    with st.expander("我是发放人：查看回收情况"):
        typed = st.text_input("管理密码", type="password", key="survey_admin_pwd")
        if not typed:
            return
        if not hmac.compare_digest(typed, password):
            st.error("密码不对。")
            return
        rows = store.read_all()
        stats = store.count_all(rows)
        st.markdown(f"**回收份数**：{stats['n']}")
        st.caption("每题只数人数；多选题各项之和可以大于份数。")
        for qid, options, _multi, _max in [(q[0], q[2], q[3], q[4]) for q in D.QUESTIONS]:
            if not options:
                st.markdown(f"- 第 10 题（开放）写了的人数：{stats['q10']}")
                continue
            counts = stats["by"].get(qid, {})
            detail = " / ".join(f"{opt} {counts.get(opt, 0)}" for opt in options)
            st.markdown(f"- 第 {qid[1:]} 题：{detail}")
        cross = store.crosses(rows)
        st.markdown(f"- 有过难受、且没去求助：**{cross['had_and_quiet']} 人**")
        st.markdown(f"- 想要「下一步找谁」、且会 / 可能会去：**{cross['step_and_would']} 人**")
        day = date.today().isoformat()
        left, right = st.columns(2)
        with left:
            st.download_button("下载 CSV", data=store.csv_text(rows),
                               file_name=f"xinyu-survey-{day}.csv",
                               mime="text/csv", key="survey_csv")
        with right:
            st.download_button("下载 JSONL", data=store.jsonl_text(rows),
                               file_name=f"xinyu-survey-{day}.jsonl",
                               mime="application/jsonl", key="survey_jsonl")
        st.caption("下载是浏览器行为，文件存到你自己电脑的「下载」文件夹；服务端不另存一份。")


def render() -> None:
    st.subheader("匿名问卷：晚上难受的时候，大家一般怎么办")
    _notice()
    if st.session_state.get(DONE_KEY):
        _thanks()
    else:
        agreed = st.checkbox("我明白上面这些，开始填", key="survey_consent")
        if agreed:
            _ask()
    _admin()


# P44 修订：入口从首页「关于心屿」挪到侧栏底部（模型设置之后），任何页面都能进；
# 和 talk_button 一样：已在问卷页时禁用而不是隐藏，位置固定。
SURVEY_LABEL = "匿名问卷（帮我们做研究）"


def sidebar_entry() -> None:
    """侧栏最下面的入口；SURVEY=0 时整条不渲染。"""
    if not enabled():
        return
    here = st.session_state.get("mode") == "survey"
    with st.sidebar:
        if st.button(SURVEY_LABEL, key="nav_survey", disabled=here,
                     use_container_width=True,
                     help="已经在这一页" if here else "10 题，不记名字"):
            # 不写 nav_last：让下一帧 nav_record 把来路压栈，返回键才能退回原页面。
            st.session_state["mode"] = "survey"
            st.rerun()
