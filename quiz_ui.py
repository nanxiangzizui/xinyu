"""quiz_ui.py — P13 侧栏入口 + 声明 + 答题 + 结果卡。

不新增 mode：内联卡片与 P11 首屏问答同形，不挡 chat_input。
[SAFE] 结果只进 quiz_store 这一区：不进 memory.json、不进日志、不进 trace。
报告写进 messages 时带 quiz 标记，chat_ui 靠它不把报告算成一轮对话。
"""
from __future__ import annotations

import streamlit as st

import quiz
import quiz_data
import quiz_store

STATE = "quiz_state"
KEYS = (STATE, "quiz_pick", "quiz_id", "quiz_answers", "quiz_result", "quiz_ack")


def reset_state() -> None:
    """清空页内状态；声明也要重新勾一次。"""
    for key in KEYS:
        st.session_state.pop(key, None)


def prepare() -> None:
    """首页点进测试页时先摆出声明卡；不在首页直接抽题。"""
    st.session_state[STATE] = "ack"
    st.session_state["quiz_ack"] = False


def clear(sid: str) -> None:
    """清空对话时一起删：小本子文件 + 页内状态。"""
    quiz_store.clear(sid)
    reset_state()


def entry() -> None:
    """侧栏入口：一句邀请 + 一个按钮；点开只准备卡片，什么都不写。"""
    if st.session_state.get(STATE):
        return
    st.caption("想放松心情？可以来做些趣味测试小游戏哦！")
    if st.button("来做个小测试", key="quiz_entry"):
        st.session_state[STATE] = "ack"
        st.session_state["quiz_ack"] = False
        st.rerun()


def _close() -> None:
    """关掉卡片：下次点开要重新看一遍声明。"""
    reset_state()
    st.rerun()


def _declaration() -> None:
    """先声明，再选一个游戏；不勾选就不给开始。"""
    st.markdown("**先选一个，玩着看**")
    for line in quiz_data.DECLARATION:
        st.caption(line)
    picks = [quiz_data.QUIZZES[qid] for qid in quiz_data.ORDER]
    labels = [f"{q['title']}（{len(q['questions'])} 题）" for q in picks]
    pick = st.radio("玩哪个", labels, key="quiz_pick", index=0)
    ack = st.checkbox("我知道了，这只是个小游戏", key="quiz_ack")
    left, right = st.columns(2)
    if left.button("开始", key="quiz_start", disabled=not ack, type="primary"):
        st.session_state["quiz_id"] = picks[labels.index(pick)]["id"]
        st.session_state["quiz_answers"] = []
        st.session_state[STATE] = "run"
        st.rerun()
    if right.button("先不测", key="quiz_close"):
        _close()


def _finish(sid: str, quiz_obj: dict, answers: list[int]) -> None:
    """算分 → 记小本子 → 生成报告 → 落进聊天 → 重绘。"""
    result = quiz.score(quiz_obj, answers)
    with st.spinner("我看看这次的结果…"):
        message = quiz.report(quiz_obj, result)
    quiz_store.append(sid, result)
    st.session_state["quiz_result"] = result
    st.session_state[STATE] = "done"
    st.session_state.setdefault("messages", []).append(
        {"role": "assistant", "content": message,
         "quiz": True, "quiz_id": quiz_obj["id"]})
    st.rerun()


def _questions(sid: str) -> None:
    """一次一题；答完最后一道就出报告。"""
    quiz_obj = quiz.get(str(st.session_state.get("quiz_id") or ""))
    if not quiz_obj:
        _close()
    answers = list(st.session_state.get("quiz_answers") or [])
    total = len(quiz_obj["questions"])
    if len(answers) >= total:
        _finish(sid, quiz_obj, answers)
        return
    idx = len(answers)
    st.progress(idx / total, text=f"{quiz_obj['title']} · 第 {idx + 1} / {total} 题")
    st.markdown(f"**{quiz_obj['questions'][idx]['q']}**")
    labels = [opt[0] for opt in quiz_obj["questions"][idx]["opts"]]
    pick = st.radio("选一个更接近的", labels, key=f"quiz_q{idx}", index=None,
                    label_visibility="collapsed")
    last = idx + 1 >= total
    if st.button("看结果" if last else "下一题", key=f"quiz_next{idx}",
                 disabled=pick is None, type="primary"):
        st.session_state["quiz_answers"] = [*answers, labels.index(pick)]
        st.rerun()
    if st.button("不测了", key=f"quiz_quit{idx}"):
        _close()


def _done(standalone: bool = False) -> None:
    """做完之后只留一张小卡：结果 + 换一个 + 关掉/聊一聊。"""
    result = st.session_state.get("quiz_result") or {}
    st.markdown(f"**{result.get('name') or '结果'}**")
    if result.get("line"):
        st.caption(result["line"])
    st.caption("结果已经单独记下了，我不会主动提起；想聊就直接在下面说。")
    left, right = st.columns(2)
    if left.button("再玩一个", key="quiz_more"):
        prepare()
        st.rerun()
    if not standalone:
        if right.button("关掉", key="quiz_done_close"):
            _close()
        return
    if right.button("聊一聊", key="quiz_chat"):
        # 不在这里直接调模型：把一句话交给 companion 页，走同一条 safe_run 管线。
        st.session_state["pending_turn"] = "帮我分析分析这个结果"
        st.session_state["mode"] = "companion"
        reset_state()
        st.rerun()
    if st.button("回首页", key="quiz_home"):
        reset_state()
        st.session_state["mode"] = "home"
        st.rerun()


def render(sid: str, standalone: bool = False) -> None:
    """主区卡片：声明 → 逐题 → 结果；没打开就什么都不画。"""
    state = st.session_state.get(STATE, "")
    if state not in ("ack", "run", "done"):
        return
    with st.container(border=True):
        if state == "ack":
            _declaration()
        elif state == "run":
            _questions(sid)
        else:
            _done(standalone)


def render_page(sid: str) -> None:
    """独立页：侧栏入口之外的第二个入口，进来先看声明。"""
    st.subheader("趣味小测试")
    st.caption("四个小游戏，没有对错，也不算命。结果会单独记下，只有你提起时才会聊到。")
    if st.button("回首页", key="quiz_page_home"):
        reset_state()
        st.session_state["mode"] = "home"
        st.rerun()
    if st.session_state.get(STATE) not in ("ack", "run", "done"):
        st.session_state.setdefault("messages", [])
        if st.button("开始选一个", key="quiz_page_start", type="primary"):
            prepare()
            st.rerun()
        return
    render(sid, standalone=True)
