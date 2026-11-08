"""panel.py — 侧栏“我记住了什么”面板：8 字段只读 + 两字段可改 + 导出 + 确认清空。

[SAFE] 展示与导出都过 memory.scrub：记忆文件即便混进联系方式，也不在界面上出现。
"""
from __future__ import annotations

import json
import re
from datetime import datetime

import streamlit as st

from memory import read_memory, scrub, write_memory

# 给人看的标签：L1/L2/L3 与枚举码不出现在界面上（演示时不刺激用户，也不外泄规则）。
LEVEL_LABELS = {"L1": "平稳", "L2": "留意", "L3": "危机"}
ROLE_LABELS = {"listener": "倾听者", "guide": "引导者", "crisis": "危机支持"}
REASON_LABELS = {"default": "自然延续", "user_ask_advice": "你明确问了办法",
                 "crisis_shortcircuit": "需要优先保证安全",
                 "crisis_cooldown": "危机后的缓冲期",
                 "after_crisis": "本会话出现过危机",
                 "sustained_negative": "持续低落"}
TONE_LABELS = {"neutral": "自然", "gentle": "温柔", "light": "轻松", "direct": "直接"}

# 8 个白名单字段的中文名；last_updated 对用户无意义，不展示（S18 §5.1）。
LABELS = {
    "preferred_tone": "希望的说话方式",
    "current_role": "当前角色",
    "role_switch_reason": "为什么换角色",
    "emotion_tags": "情绪标签",
    "unresolved_issues": "还没解决的事",
    "coping_preferences": "有用的安抚方式",
    "rolling_summary": "近期概况",
    "summary_at_turn": "概况更新于第几轮",
}
TONE_CODES = tuple(TONE_LABELS)
ITEM_SPLIT = re.compile(r"[，,、;；/]+")
EMPTY = "—"


def _join(value: object) -> str:
    """列表用顿号拼、空值显示破折号；每一项都先 scrub。"""
    if isinstance(value, (list, tuple)):
        items = [scrub(str(v)) for v in value if str(v).strip()]
        return "、".join(items) or EMPTY
    text = scrub(str(value or "")).strip()
    return text or EMPTY


def _shown(key: str, value: object) -> str:
    """单字段转成人话：角色 / 原因 / 语气走中文标签，其余交给 _join。"""
    if key == "preferred_tone":
        return TONE_LABELS.get(str(value), str(value or "")) or EMPTY
    if key == "current_role":
        return ROLE_LABELS.get(str(value), str(value or "")) or EMPTY
    if key == "role_switch_reason":
        return REASON_LABELS.get(str(value), str(value or "")) or EMPTY
    if key == "summary_at_turn":
        return f"第 {value} 轮" if isinstance(value, int) and value > 0 else EMPTY
    return _join(value)


def panel_view(memory: dict) -> dict[str, str]:
    """面板数据：8 个字段全部过 scrub 后再交给界面（滚动摘要可能来自模型）。"""
    return {label: scrub(_shown(key, memory.get(key)))
            for key, label in LABELS.items()}


def export_payload(memory: dict) -> dict:
    """导出内容：只含本会话记忆白名单字段，全部过 scrub；不含日志与对话。"""
    payload: dict = {}
    for key in (*LABELS, "last_updated"):
        value = memory.get(key)
        if isinstance(value, list):
            payload[key] = [scrub(str(v)) for v in value]
        elif isinstance(value, int) and not isinstance(value, bool):
            payload[key] = value
        else:
            payload[key] = scrub(str(value or ""))
    return payload


def render_panel(sid: str, on_clear) -> None:
    """渲染侧栏面板；on_clear 由 app.py 注入（清 session_state + 换会话 id + rerun）。"""
    memory = read_memory(sid)
    with st.expander("我记住了什么"):
        for label, shown in panel_view(memory).items():
            st.caption(label)
            st.write(shown)

        tone = st.selectbox(
            "希望的说话方式（可修改）", TONE_CODES,
            index=TONE_CODES.index(memory["preferred_tone"])
            if memory["preferred_tone"] in TONE_CODES else 0,
            format_func=lambda code: TONE_LABELS.get(code, code),
            key=f"panel_tone_{sid}",
        )
        prefs = st.text_input("有用的安抚方式（可修改，用逗号分隔）",
                              value="、".join(memory["coping_preferences"]),
                              key=f"panel_prefs_{sid}")
        if st.button("保存偏好", key=f"panel_save_{sid}"):
            memory["preferred_tone"] = tone
            memory["coping_preferences"] = [x.strip() for x in ITEM_SPLIT.split(prefs)
                                            if x.strip()]
            write_memory(sid, memory)
            st.rerun()

        st.download_button(
            "导出我的记忆",
            data=json.dumps(export_payload(memory), ensure_ascii=False, indent=2),
            file_name=f"memory-{datetime.now():%Y%m%d}.json",
            mime="application/json",
            key=f"panel_export_{sid}",
        )
        st.caption("只记标签与摘要，不存聊天原文；刷新后聊天记录不会恢复。")
        if st.checkbox("我确认要清除全部记忆", key=f"panel_confirm_{sid}"):
            if st.button("清除", type="primary", key=f"panel_clear_{sid}"):
                on_clear(sid)
