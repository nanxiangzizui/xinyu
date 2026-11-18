"""onboard.py — 开场偏好：五个固定选项的小问题，只预设「怎么说话」。

[SAFE] 三条不许破：
1. 只写风格偏好（preferred_tone / emotion_tags / coping_preferences），不判等级。
   L1/L2/L3 永远由 guardian 规则层对用户真实发言判定；开场答案不参与，也不能降级。
2. 不出分数、等级、结论；界面不出现「测评 / 测试 / 评估」字样。
3. 选项是固定短语，不收自由文本；答案不进日志、不进 trace、不进 URL。
"""
from __future__ import annotations

import streamlit as st

import memory
import roles
import style

HEAD = "先聊两句"
NOTE = "几个开场小问题，不是测评；答不答都行，之后也能在侧栏改。"
START = "先这样，开始聊"
SKIP = "跳过"
EDIT = "改一下"

# 五题：前三题问状态，后两题问说话方式。答案只可能是下面这些常量键。
QUESTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("mood", "今天过得怎么样？", ("挺好", "一般", "有点闷", "挺难的")),
    ("topic", "最占心思的是哪一块？",
     ("学习或工作", "和人相处", "家里的事", "身体状态", "说不上来")),
    ("company", "现在想找人说说话，还是先自己待会儿？",
     ("想找人说说话", "先自己待会儿", "说不好")),
    ("style", "想被怎么对待？", ("听我说", "给我点办法", "轻松一点", "直说就行")),
    ("start", "想我怎么开口？", ("先问我一句", "先给我一句", "我自己说")),
)

# 选项 → 记忆字段。查不到就不写：猜错比不写更糟（尤其不能把「挺难的」翻译成等级）。
MOOD_TAGS = {"挺好": ("平稳",), "一般": (), "有点闷": ("低落",), "挺难的": ("低落", "疲惫")}
TOPIC_TAGS = {"学习或工作": "学业", "和人相处": "人际",
              "家里的事": "家庭", "身体状态": "身体"}
COMPANY_PREFS = {"想找人说说话": "想找人说话", "先自己待会儿": "先自己待会儿，不用追问"}
STYLE_RULES = {
    "听我说": ("gentle", "先听我说完"),
    "给我点办法": ("neutral", "想要具体办法"),
    "轻松一点": ("light", "想轻松一点"),
    "直说就行": ("direct", "喜欢直接说"),
}
START_PREFS = {"先问我一句": "先问我一句再聊", "先给我一句": "先接我一句"}


def derive(answers: dict) -> dict:
    """把选中的常量键翻成要写入的字段；没答或答了表外值一律不写。"""
    tags = list(MOOD_TAGS.get(answers.get("mood"), ()))
    topic = TOPIC_TAGS.get(answers.get("topic"))
    if topic:
        tags.append(topic)
    tone, pref = STYLE_RULES.get(answers.get("style"), ("neutral", ""))
    prefs = [pref] if pref else []
    for key, table in (("company", COMPANY_PREFS), ("start", START_PREFS)):
        item = table.get(answers.get(key))
        if item:
            prefs.append(item)
    return {"tone": tone, "tags": tags, "prefs": prefs}


def apply(sid: str, answers: dict) -> dict:
    """只写白名单里的两个字段：语气覆盖，标签与偏好并入历史，不删旧的。"""
    plan = derive(answers)
    mem = memory.read_memory(sid)
    mem["preferred_tone"] = plan["tone"]
    # 用 memory 的合并口径，避免标签去重逻辑在两处慢慢分叉。
    mem["emotion_tags"] = memory._merge(
        mem["emotion_tags"], plan["tags"], memory.ITEM_CAPS["emotion_tags"])
    mem["coping_preferences"] = memory._merge(
        mem["coping_preferences"], plan["prefs"], memory.ITEM_CAPS["coping_preferences"])
    memory.write_memory(sid, mem)
    return plan


def summary(sid: str) -> str:
    """一行可见的预设结果：只说语气，不出现任何评估结论。"""
    mem = memory.read_memory(sid)
    tone = style.TONE_LABELS.get(mem["preferred_tone"], "自然")
    return f"开场偏好：{tone}"


def opening_line(kind: str, persona_id: str) -> str:
    """把「想我怎么开口」翻成一句开场白；「我自己说」与未答返回空串。"""
    if kind == "先问我一句":
        return roles.OPENING_LINES.get(persona_id, "")
    if kind == "先给我一句":
        return roles.OPENING_STATEMENTS.get(persona_id, "")
    return ""


def render(sid: str) -> None:
    """首屏引导：一屏五题、可答可跳；不挡聊天输入，打字就能直接开始。"""
    if st.session_state.get("onboard_done"):
        _render_done(sid)
        return
    with st.container(border=True):
        st.markdown(f"**{HEAD}**")
        st.caption(NOTE)
        prev = st.session_state.get("ob_answers", {})
        answers = {}
        for key, label, options in QUESTIONS:
            chosen = prev.get(key)
            answers[key] = st.radio(
                label, options, horizontal=True, key=f"ob_{key}",
                index=options.index(chosen) if chosen in options else None)
        if st.button(START, key="ob_submit", type="primary"):
            picked = {k: v for k, v in answers.items() if v}
            if picked:
                apply(sid, picked)
                # 记下选择：点「改一下」回来时控件已被销毁，靠这份回填。
                st.session_state["ob_answers"] = picked
                st.session_state["onboard_used"] = True
            # 改答案时先撤掉上一句开场白，否则两句会叠在聊天记录里。
            st.session_state["messages"] = [
                m for m in st.session_state.get("messages", [])
                if not m.get("opening")]
            st.session_state["ob_open"] = picked.get("start", "")
            st.session_state["onboard_done"] = True
            st.rerun()
        if st.button(SKIP, key="ob_skip"):
            st.session_state["onboard_done"] = True
            st.rerun()


def _render_done(sid: str) -> None:
    """答完之后只留一行提示；「改一下」重新展开，跳过的不留空结论。"""
    if st.session_state.get("onboard_used"):
        st.caption(summary(sid))
    if st.button(EDIT, key="ob_edit"):
        st.session_state["onboard_done"] = False
        st.rerun()
