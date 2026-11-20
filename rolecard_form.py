"""rolecard_form.py — B 模式的建卡表单、角色认知与建卡期检索补全。

只负责表单状态与候选合并；开始对话的回调由 rolecard_ui 传入，避免把
gate / 聊天 / 侧栏 / 表单挤进同一个文件。最近一张卡落盘只为「继承上一张」：
只存卡字段，不存对话、不进 memory.json、不进日志。
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path

import streamlit as st

import examples
import rolecard
import rolecard_enrich

logger = logging.getLogger(__name__)
LAST_CARD_REL = ("rolecards", "last.json")


def fact_label(fact: dict) -> str:
    """候选事实的勾选文案：字段 + 来源等级（建卡页与盲点补全共用）。"""
    label = rolecard_enrich.FIELD_LABELS.get(fact["field"], fact["field"])
    authority = rolecard_enrich.AUTHORITY_LABELS.get(fact.get("authority", ""), "")
    badge = f"（{authority}）" if authority else ""
    return f"{label}{badge}：{fact['text']}"


def conflict_text(conflict: dict) -> str:
    """权威覆盖、额度满、格式错分开说；用户要知道下一步做什么。"""
    if conflict.get("kind") == "override":
        return (f"已用权威来源覆盖 {conflict['field']}："
                f"{conflict['current']} → {conflict['suggested']}")
    reason = conflict.get("reason")
    if reason == "lore_full":
        return (f"保留你的 {conflict['field']}：角色认知已满 "
                f"{rolecard.LORE_COUNT_MAX} 条或 {rolecard.LORE_MAX} 字的额度；"
                f"删一条再加（候选：{conflict['suggested']}）")
    if reason == "invalid_lore":
        return (f"保留你的 {conflict['field']}：角色认知格式不对，"
                f"需按“字段：事实”写成一行（候选：{conflict['suggested']}）")
    if reason == "taboo_full":
        return (f"保留你的 {conflict['field']}：禁忌已满 "
                f"{rolecard.TABOO_COUNT_MAX} 条；先删一条（候选：{conflict['suggested']}）")
    if reason == "invalid":
        return (f"未写入 {conflict['field']}：会超出上限或不合规"
                f"（候选：{conflict['suggested']}）")
    if reason == "filled":
        return (f"保留你的 {conflict['field']}：{conflict['current']}"
                f"（已有内容，未覆盖；候选：{conflict['suggested']}）")
    return (f"保留你的 {conflict['field']}：{conflict['current']}"
            f"（候选：{conflict['suggested']}）")



def _split_taboos(text: str) -> list[str]:
    """把“；/;/换行”分隔的禁忌拆成列表；空串不留下空条目。"""
    for sep in ("；", ";", "\n"):
        text = text.replace(sep, "|")
    return [part.strip() for part in text.split("|") if part.strip()]


def _lore_text(card: dict) -> str:
    """角色认知列表 → 多行文本（表单控件用）。"""
    return "\n".join(card.get("lore") or [])


def last_card_path() -> Path:
    """最近一张卡的落盘位置：跟 DATA_DIR 同根，测试里天然隔离到临时目录。"""
    return Path(os.getenv("DATA_DIR", "data")).joinpath(*LAST_CARD_REL)


def load_last() -> dict | None:
    """读上一张卡；缺文件/坏 JSON 都当成“没有”，绝不让建卡页崩。"""
    try:
        raw = json.loads(last_card_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):          # 边界：文件读写 / JSON 解析
        return None
    return rolecard.normalize(raw) if isinstance(raw, dict) else None


def save_last(card: dict) -> None:
    """记下刚用过的卡，供下次继承；失败只影响继承，不挡开始对话。"""
    path = last_card_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)              # 原子写，与 memory.py 同口径
    except OSError as exc:                 # 边界：文件读写
        logger.warning("rolecard_save_failed error=%s", type(exc).__name__)


def _fill_form(card: dict) -> None:
    """把一张卡写回控件状态；载入示例、继承上一张、清空表单共用这一处。"""
    known = card.get("origin") == "known"
    st.session_state.rc_origin = "known" if known else "original"
    st.session_state.rc_work = card.get("work", "") if known else ""
    for key in ("name", "identity", "setting", "voice", "address"):
        st.session_state[f"rc_{key}"] = card.get(key, "")
    st.session_state.rc_user_role = card.get("user_role", "用户")
    st.session_state.rc_stage = card.get("stage", "none")
    pairs = list(card.get("examples") or [])[:2]
    for idx in (1, 2):
        user, role = pairs[idx - 1] if idx <= len(pairs) else ("", "")
        st.session_state[f"rc_ex{idx}_user"] = user
        st.session_state[f"rc_ex{idx}_role"] = role
    st.session_state.rc_taboos = "；".join(card.get("taboos") or [])
    st.session_state.rc_lore_text = _lore_text(card)
    st.session_state.rc_errors = []
    st.session_state.rc_enrich_result = None
    st.session_state.rc_enrich_note = ""


def reset_form() -> None:
    """换一张卡：整表回空；想沿用上一张就点「继承上一张角色卡」。"""
    _fill_form({})


def _remembered() -> dict | None:
    """会话里缓存一份，避免每次重跑都读盘；刷新后第一次从文件恢复。"""
    if "rc_last_card" not in st.session_state:
        st.session_state["rc_last_card"] = load_last()
    return st.session_state["rc_last_card"]


def _raw() -> dict:
    """从控件状态拼回一张卡；原创卡不带作品名，避免 validate 误报。"""
    s = st.session_state
    origin = s.get("rc_origin", "original")
    return {"origin": origin, "work": s.get("rc_work", "") if origin == "known" else "",
            "name": s.get("rc_name", ""), "identity": s.get("rc_identity", ""),
            "setting": s.get("rc_setting", ""), "voice": s.get("rc_voice", ""),
            "address": s.get("rc_address", ""),
            "user_role": s.get("rc_user_role", "用户"),
            "stage": s.get("rc_stage", "none"),
            "examples": [(s.get("rc_ex1_user", ""), s.get("rc_ex1_role", "")),
                         (s.get("rc_ex2_user", ""), s.get("rc_ex2_role", ""))],
            "taboos": _split_taboos(s.get("rc_taboos", "")),
            "lore": rolecard.parse_lore(s.get("rc_lore_text", ""))}


def _load_example() -> None:
    """回调里改控件状态：按钮点击后、下一次脚本运行前执行，不会撞 widget。"""
    _fill_form(rolecard.EXAMPLE_CARD)


def _inherit() -> None:
    """回调：把上一张卡写回表单；没有就什么都不做。"""
    card = _remembered()
    if card:
        _fill_form(card)


def _render_inherit() -> None:
    """表单最上方：上次用过的卡一键回填，省得重填一遍。"""
    card = _remembered()
    if not card:
        return
    work = (card.get("work") or "").strip()
    name = (card.get("name") or "未命名").strip()
    label = f"继承上一张角色卡（{work} · {name}）" if work else f"继承上一张角色卡（{name}）"
    st.button(label, key="rc_inherit", on_click=_inherit)


def _render_origin() -> None:
    """来源与作品名：只有已知虚构角色才需要作品名。"""
    st.radio("来源", rolecard.CARD_ORIGINS, horizontal=True, key="rc_origin",
             format_func=lambda v: "原创角色" if v == "original" else "已知虚构角色")
    if st.session_state.get("rc_origin", "original") == "known":
        st.text_input("作品名", key="rc_work", max_chars=rolecard.WORK_MAX,
                      placeholder="例如：某个虚构作品的名字")


def _render_fields() -> None:
    """五个角色字段 + 对方身份 + 动作描写开关。"""
    limits = {key: (limit, label) for key, limit, label in rolecard.FIELD_LIMITS}
    for key, placeholder in (
        ("name", "例如：阿岚"),
        ("identity", "例如：一家只在雨天开门的旧书店店主"),
        ("setting", f"角色的世界与处境，{limits['setting'][0]} 字以内"),
        ("voice", "句子长短、常用比喻、不说什么"),
        ("address", "角色怎么称呼你，例如：你 / 客人"),
    ):
        limit, label = limits[key]
        if key == "setting":
            st.text_area(f"{label}（{limit} 字以内，可空）", key=f"rc_{key}",
                         max_chars=limit, placeholder=placeholder)
        else:
            st.text_input(f"{label}（{limit} 字以内）", key=f"rc_{key}",
                          max_chars=limit, placeholder=placeholder)
    limit, label = limits["user_role"]
    st.text_input(f"{label}（{limit} 字以内；不代入原作就填「用户」）",
                  key="rc_user_role", max_chars=limit,
                  placeholder="例如：用户 / 开拓者")
    st.radio("动作描写", rolecard.STAGE_MODES, key="rc_stage", horizontal=True,
             format_func=lambda v: rolecard.STAGE_LABELS.get(v, v))


def _fill_example(slot: int, pair: tuple[str, str]) -> None:
    """回调里改控件状态；直接赋值会撞「控件已实例化」。"""
    st.session_state[f"rc_ex{slot}_user"], st.session_state[f"rc_ex{slot}_role"] = pair


def _render_examples() -> None:
    """两组示例 + 禁忌 + 可手填的角色认知。"""
    st.markdown("**两组示例对话**（让角色知道怎么开口）")
    for idx in (1, 2):
        cols = st.columns(2)
        with cols[0]:
            st.text_input(f"示例 {idx} · 你说", key=f"rc_ex{idx}_user",
                          max_chars=rolecard.EXAMPLE_USER_MAX)
        with cols[1]:
            st.text_input(f"示例 {idx} · 角色说", key=f"rc_ex{idx}_role",
                          max_chars=rolecard.EXAMPLE_ROLE_MAX)
    if st.button("让心屿先写 6 组示例", key="rc_gen_examples",
                 help="按卡上的身份与口吻先写 6 组，挑一组填进去再自己改。"):
        st.session_state.rc_example_candidates = examples.card_candidates(_raw())
    pairs = st.session_state.get("rc_example_candidates") or []
    if pairs:
        idx = st.selectbox("挑一组", range(len(pairs)), key="rc_ex_pick",
                           format_func=lambda i: f"{pairs[i][0]} → {pairs[i][1]}")
        for slot in (1, 2):
            st.button(f"填到示例 {slot}", key=f"rc_fill_ex{slot}",
                      on_click=_fill_example, args=(slot, pairs[idx]))
    st.text_input(f"禁忌（用；分隔，最多 {rolecard.TABOO_COUNT_MAX} 条，"
                  f"每条 {rolecard.TABOO_MAX} 字以内）", key="rc_taboos",
                  placeholder="例如：我懂你；你应该")
    st.text_area(
        f"角色认知（可选，每行一条，最多 {rolecard.LORE_COUNT_MAX} 条、"
        f"每条 {rolecard.LORE_ITEM_MAX} 字）",
        key="rc_lore_text", height=120,
        max_chars=rolecard.LORE_MAX + rolecard.LORE_COUNT_MAX,
        placeholder="例如：她曾被请求记住一个名字；她与开拓者在某个站台告别。")


def _apply_facts() -> None:
    """回调里合并选中事实：权威来源覆盖身份/设定，其余只补空。"""
    result = st.session_state.get("rc_enrich_result") or {}
    facts = [fact for idx, fact in enumerate(result.get("facts", []))
             if st.session_state.get(
                 f"rc_fact_{idx}",
                 fact.get("authority") in rolecard_enrich.AUTHORITATIVE)]
    st.session_state.rc_enrich_result = None
    if not facts:
        st.session_state.rc_enrich_note = "没有选中任何条目。"
        st.session_state.rc_enrich_note_level = "warning"
        return
    card = rolecard.normalize(_raw())
    merged, conflicts = rolecard_enrich.merge(card, facts)
    for key in ("identity", "setting", "voice", "address"):
        st.session_state[f"rc_{key}"] = merged.get(key, "")
    st.session_state.rc_taboos = "；".join(merged.get("taboos") or [])
    st.session_state.rc_lore_text = _lore_text(merged)
    overrides = [item for item in conflicts if item.get("kind") == "override"]
    kept = len(conflicts) - len(overrides)
    # len(facts) 是勾选数，不是写入数；只说“已选/未写入”，别把选中当成功。
    st.session_state.rc_enrich_note = (
        f"已选 {len(facts)} 条；覆盖 {len(overrides)} 项；"
        f"{kept} 条未写入（原因见下）；其余已写入或与原有内容相同。")
    st.session_state.rc_enrich_note_level = "success" if kept < len(facts) else "warning"


def render_enrich(card: dict) -> None:
    """仅已知虚构角色：联网一次取回候选设定，勾选后合并。"""
    if card.get("origin") != "known":
        return
    st.divider()
    st.caption("可以从公开资料补全；官方/Wiki 会覆盖身份与设定，社区来源只补空；"
               "世界与经历放进「角色认知」。")
    if not card.get("name") or not card.get("work"):
        st.caption("先填作品名和角色名，再检索。")
        return
    lore = card.get("lore") or []
    if lore:
        st.caption(f"当前角色认知（{len(lore)}/{rolecard.LORE_COUNT_MAX} 条）：")
        st.text("\n".join(f"· {item}" for item in lore))
    if st.button("检索补全（联网一次）", key="rc_enrich"):
        for key in [key for key in st.session_state if key.startswith("rc_fact_")]:
            del st.session_state[key]
        with st.spinner("正在检索公开资料…"):
            st.session_state.rc_enrich_result = rolecard_enrich.enrich(card)
        st.session_state.rc_enrich_note = ""
        st.session_state.rc_enrich_note_level = ""

    note = st.session_state.get("rc_enrich_note")
    if note:
        if st.session_state.get("rc_enrich_note_level") == "warning":
            st.warning(note)
        else:
            st.success(note)
    _render_enrich_result(st.session_state.get("rc_enrich_result"))


def _render_enrich_result(result: dict | None) -> None:
    """渲染候选事实、冲突与来源；勾选后由 _apply_facts 合并。"""
    if not result:
        return
    if not result.get("ok"):
        code = result.get("error") or "empty"
        st.warning("没能补全：" + rolecard_enrich.ERROR_LABELS.get(code, code))
        return

    st.caption("候选设定（勾选后应用；官方/Wiki 默认勾选，社区/其他默认不选；"
               "口吻/称呼/禁忌不动）：")
    for idx, fact in enumerate(result.get("facts", [])):
        st.checkbox(fact_label(fact),
                    value=fact.get("authority") in rolecard_enrich.AUTHORITATIVE,
                    key=f"rc_fact_{idx}")
    for conflict in result.get("conflicts", []):
        st.caption(conflict_text(conflict))
    for src in result.get("sources", []):
        st.markdown(f"- [{src.get('title') or src['url']}]({src['url']})")
    st.button("应用选中的设定", key="rc_apply_facts", on_click=_apply_facts)


def _render_actions(on_start: Callable[[dict], None]) -> None:
    """载入示例 / 开始对话；开始前先跑一遍校验。"""
    cols = st.columns(2)
    with cols[0]:
        st.button("载入示例卡", key="rc_load_example", on_click=_load_example)
    with cols[1]:
        if st.button("开始角色对话", key="rc_start", type="primary"):
            card = rolecard.normalize(_raw())
            errors = rolecard.validate(card)
            st.session_state.rc_errors = errors
            if errors:
                # 错误在表单上方渲染：本帧按钮之后才拿到错误，重跑一次才看得见。
                st.rerun()
            save_last(card)                 # 只在校验通过后才记，半成品不覆盖上一张
            st.session_state["rc_last_card"] = card
            on_start(card)
            st.rerun()


def render_form(on_start: Callable[[dict], None]) -> None:
    """建卡表单：继承上一张 → 来源 → 字段 → 示例/认知 → 补全 → 开始。"""
    st.subheader("建一张角色卡")
    st.caption("只收虚构角色；不收真实人物、专业身份和恋爱关系。")
    _render_inherit()
    _render_origin()
    _render_fields()
    _render_examples()
    st.checkbox("遇到卡里没有的人物时自动联网补全（只发专名）", key="rc_auto_gap")
    render_enrich(rolecard.normalize(_raw()))
    for error in st.session_state.get("rc_errors", []):
        st.error(error)
    _render_actions(on_start)
