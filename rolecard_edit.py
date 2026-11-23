"""rolecard_edit.py — P39 对话中查看/修改当前角色卡。

只改“当前这一段对话”的卡：名字、作品名、来源锁死——它们决定
rolecard_memory 的 card_key，改了会静默切到另一份长期记忆。
保存前仍走 rolecard.validate 与 build_prompt 预算，非法内容不进下一轮。
"""
from __future__ import annotations

import streamlit as st

import rolecard
import rolecard_memory


def _split_taboos(text: str) -> list[str]:
    for sep in ("；", ";", "\n"):
        text = text.replace(sep, "|")
    return [part.strip() for part in text.split("|") if part.strip()]


def _seed(card: dict) -> None:
    """把卡写进 rc_edit_* 草稿；只在点“编辑”时做一次。"""
    s = st.session_state
    for key in ("identity", "setting", "voice", "address", "user_role"):
        s[f"rc_edit_{key}"] = card.get(key, "")
    s.rc_edit_stage = card.get("stage", "none")
    pairs = list(card.get("examples") or [])[:2]
    for idx in (1, 2):
        user, role = pairs[idx - 1] if idx <= len(pairs) else ("", "")
        s[f"rc_edit_ex{idx}_user"] = user
        s[f"rc_edit_ex{idx}_role"] = role
    s.rc_edit_taboos = "；".join(card.get("taboos") or [])
    s.rc_edit_lore_text = "\n".join(card.get("lore") or [])
    s.rc_edit_errors = []


def _summary(card: dict) -> None:
    """只读展示；字段为空也显式写出来，避免用户以为漏了一行。"""
    rows = (("身份", card.get("identity")), ("设定", card.get("setting")),
            ("口吻", card.get("voice")), ("称呼", card.get("address")),
            ("对方身份", card.get("user_role")), ("动作", rolecard.STAGE_LABELS.get(card.get("stage"), "不用")))
    for label, value in rows:
        st.markdown(f"**{label}**：{value or '（空）'}")
    examples = card.get("examples") or []
    if examples:
        st.markdown("**示例**：" + " ／ ".join(f"{u} → {r}" for u, r in examples))
    st.markdown("**禁忌**：" + ("；".join(card.get("taboos") or []) or "（无）"))
    lore = card.get("lore") or []
    if lore:
        st.markdown("**角色认知**：")
        for item in lore:
            st.markdown(f"- {item}")


def _raw(card: dict) -> dict:
    """从 rc_edit_* 拼卡；name/work/origin 永远取原卡，界面只读。"""
    s = st.session_state
    return {
        "kind": "rolecard", "origin": card.get("origin", "original"),
        "work": card.get("work", ""), "name": card.get("name", ""),
        "identity": s.get("rc_edit_identity", ""),
        "setting": s.get("rc_edit_setting", ""),
        "voice": s.get("rc_edit_voice", ""),
        "address": s.get("rc_edit_address", ""),
        "user_role": s.get("rc_edit_user_role", "用户"),
        "stage": s.get("rc_edit_stage", "none"),
        "examples": [(s.get("rc_edit_ex1_user", ""), s.get("rc_edit_ex1_role", "")),
                     (s.get("rc_edit_ex2_user", ""), s.get("rc_edit_ex2_role", ""))],
        "taboos": _split_taboos(s.get("rc_edit_taboos", "")),
        "lore": rolecard.parse_lore(s.get("rc_edit_lore_text", "")),
    }


def _errors(card: dict, new_card: dict) -> list[str]:
    """校验卡本身，再用当前长期记忆预演一次 prompt 预算。"""
    errors = rolecard.validate(new_card)
    if errors:
        return errors
    mem = rolecard_memory.read(card, "").get("_block", "")
    try:
        rolecard.build_prompt(new_card, {"_block": mem}, [])
    except ValueError as exc:
        return [f"这张卡放不进提示词：{exc}。请删短一点。"]
    return []


def _form(card: dict) -> dict | None:
    """编辑表单；保存成功返回新卡，失败把错误留在 rc_edit_errors。"""
    s = st.session_state
    st.caption("名字、作品名和来源不能在对话中改：它们决定长期记忆归到哪张卡。"
               "要换请新建对话。")
    st.text_input("角色名（锁定）", value=card.get("name", ""), disabled=True)
    if card.get("origin") == "known":
        st.text_input("作品名（锁定）", value=card.get("work", ""), disabled=True)
    st.text_input("来源（锁定）", disabled=True,
                  value="原创角色" if card.get("origin") == "original" else "已知虚构角色")
    limits = {key: (limit, label) for key, limit, label in rolecard.FIELD_LIMITS}
    for key, label in (("identity", "身份"), ("setting", "设定"),
                       ("voice", "说话风格"), ("address", "称呼")):
        limit = limits[key][0]
        if key == "setting":
            st.text_area(f"{label}（{limit} 字以内，可空）", key="rc_edit_setting",
                         max_chars=limit, height=90)
        else:
            st.text_input(f"{label}（{limit} 字以内）", key=f"rc_edit_{key}",
                          max_chars=limit)
    st.text_input("你的身份（对方身份）", key="rc_edit_user_role",
                  max_chars=rolecard.USER_ROLE_MAX)
    st.radio("动作描写", rolecard.STAGE_MODES, key="rc_edit_stage", horizontal=True,
             format_func=lambda v: rolecard.STAGE_LABELS.get(v, v))
    for idx in (1, 2):
        cols = st.columns(2)
        with cols[0]:
            st.text_input(f"示例 {idx} · 你说", key=f"rc_edit_ex{idx}_user",
                          max_chars=rolecard.EXAMPLE_USER_MAX)
        with cols[1]:
            st.text_input(f"示例 {idx} · 角色说", key=f"rc_edit_ex{idx}_role",
                          max_chars=rolecard.EXAMPLE_ROLE_MAX)
    st.text_input(f"禁忌（用；分隔，最多 {rolecard.TABOO_COUNT_MAX} 条）",
                  key="rc_edit_taboos")
    st.text_area(f"角色认知（每行一条，最多 {rolecard.LORE_COUNT_MAX} 条）",
                 key="rc_edit_lore_text", height=100,
                 max_chars=rolecard.LORE_MAX + rolecard.LORE_COUNT_MAX)
    for error in s.get("rc_edit_errors", []):
        st.error(error)
    cols = st.columns(2)
    if cols[0].button("保存角色卡", key="rc_edit_save", type="primary"):
        new_card = rolecard.normalize(_raw(card))
        errors = _errors(card, new_card)
        if errors:
            s.rc_edit_errors = errors
            st.rerun()             # 让错误在表单原位显示，而不是等下一轮对话
        s.rc_edit_errors = []
        s.rc_edit_open = False
        st.success("已保存；下一轮就用这张卡。")
        return new_card
    if cols[1].button("取消", key="rc_edit_cancel"):
        s.rc_edit_open = False
        s.rc_edit_errors = []
        st.rerun()
    return None


def render(card: dict) -> dict | None:
    """聊天页顶部入口；返回新卡表示本帧已保存，调用方负责落盘。"""
    s = st.session_state
    with st.expander(f"当前角色卡 · {card.get('name', '未命名')}",
                     expanded=bool(s.get("rc_edit_open"))):
        _summary(card)
        if not s.get("rc_edit_open"):
            if st.button("编辑这张卡", key="rc_edit_btn"):
                _seed(card)
                s.rc_edit_open = True
                s.rc_edit_errors = []
                st.rerun()
            return None
        return _form(card)
