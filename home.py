"""home.py — P17 首屏：把「聊天 / 角色卡 / 放松工具 / 文字游戏」摆成一张列表。

P26 在前面加了两个求助入口（自己危险 / 朋友出事），后面加了「关于心屿」。
P27 把两个入口换成四选一分诊；「我只是逛逛」只收起分诊卡片，不放宽求助路径。
P30 加了「要跟学校打交道时」三张静态页（辅导员 / 请假流程 / 陪同）。
这里只做导航与静态文案：不调用 agent、orchestrator、guardian，也不写任何记忆。
"""
from __future__ import annotations

import random

import streamlit as st

import quiz_ui
from resources import pick_resources
from ui_common import DISCLAIMER, home_enabled, rolecard_enabled

# (分组标题, [(按钮文字, 一句说明, mode, relax_page, key)])
GROUPS = [
    ("先说说话", [
        ("与心屿聊聊天", "不用组织语言，想到哪说到哪。", "companion", "", "home_chat"),
        ("给心屿一张角色卡", "带一个角色来，按卡里的设定聊。", "rolecard", "", "home_rolecard"),
    ]),
    ("先让身体慢一点", [
        ("跟着呼吸", "4 秒吸气，6 秒呼气，做 5 轮。", "relax", "breath", "home_breath"),
        ("5-4-3-2-1 接地", "用五感把注意力放回现在。", "relax", "ground", "home_ground"),
        ("一分钟微休息", "随机一个小动作，做 30 秒就好。", "relax", "break", "home_break"),
    ]),
    ("不用说话也可以", [
        ("写下来", "写在纸上，再撕掉；只在这页。", "relax", "journal", "home_journal"),
        ("环境音", "雨、风、海浪；默认不自动播放。", "relax", "sound", "home_sound"),
        ("看看别处", "几个安静的外部网站，会离开本站。", "relax", "links", "home_links"),
    ]),
    ("动动脑子，不费劲", [
        ("趣味小测试", "四个小游戏，没有对错。", "quiz", "", "home_quiz"),
        ("脑筋急转弯", "看答案，不评分。", "relax", "brain", "home_brain"),
        ("猜谜语", "卡住了可以看提示。", "relax", "riddle", "home_riddle"),
        ("成语接龙", "按读音接，接不上就换一个开头。", "relax", "idiom", "home_idiom"),
    ]),
    ("要跟学校打交道时", [
        ("跟辅导员 / 老师说", "不用一次说完；先问清楚保密范围。", "help", "teacher", "home_teacher"),
        ("请假 / 缓考 / 休学", "带五个问题去问，不替你做决定。", "help", "leave", "home_leave"),
        ("陪别人去心理中心 / 医院", "你能做什么、不能做什么。", "help", "accompany", "home_accompany"),
    ]),
    ("关于心屿", [
        ("它是什么、记了什么", "先说边界，再说存了什么。", "about", "", "home_about"),
        ("去咨询前，可以准备什么", "第一次去，不知道说什么也正常。", "help", "before", "home_before"),
        ("咨询后这一周", "说完之后有点空，也算正常。", "help", "after", "home_after"),
    ]),
]

# 四选一分诊（P27）：只做路由，不判级。key 沿用 P26 的两个求助入口，
# 测试、侧栏、熟客都不用重学；「逛逛」不跳页，只把这块卡片收起来。
TRIAGE = (("我现在很难受", "help", "self", "home_help_self"),
          ("我想说说", "companion", "", "home_talk"),
          ("我朋友出事了", "help", "friend", "home_help_friend"),
          ("我只是逛逛", "", "", "home_browse"))

# 收起状态单独一个键：不能和按钮自己的 key 同名，否则写不进去（widget 拥有它）。
BROWSE_KEY = "home_browse_on"

LOCAL_PAGES = ("breath", "ground", "break", "journal", "sound", "links",
               "brain", "riddle", "idiom")


def enabled() -> bool:
    """HOME_HUB=0 时回退旧的 companion 首屏。"""
    return home_enabled()


def goto(mode: str, page: str = "") -> None:
    """切 mode；角色卡要初始化 rc_*，测试页要先把声明卡准备好。"""
    if mode == "rolecard":
        import rolecard_ui
        rolecard_ui.ensure_state()
    if mode == "quiz":
        quiz_ui.prepare()
    if mode == "relax" and page:
        st.session_state["relax_page"] = page
    if mode == "help":
        st.session_state["help_page"] = page or "self"
    st.session_state["mode"] = mode
    st.rerun()


def _card(col, label: str, desc: str, mode: str, page: str, key: str) -> None:
    with col.container(border=True):
        st.markdown(f"**{label}**")
        st.caption(desc)
        if st.button("进去看看", key=key, use_container_width=True):
            goto(mode, page)


def _groups() -> list[tuple[str, list[tuple[str, str, str, str, str]]]]:
    """按开关过滤角色卡入口；其余 12 项始终在。"""
    out = []
    for title, items in GROUPS:
        kept = [it for it in items
                if not (it[4] == "home_rolecard" and not rolecard_enabled())]
        if kept:
            out.append((title, kept))
    return out


def pick_random() -> None:
    """只在 9 个本地放松页里挑，不把用户突然丢进聊天或角色卡。"""
    page = random.choice(LOCAL_PAGES)
    goto("relax", page)


def _enter(mode: str, page: str, key: str) -> None:
    """「逛逛」只收卡片；其余三种直接换页。"""
    if key == "home_browse":
        st.session_state[BROWSE_KEY] = True
        st.rerun()
        return
    goto(mode, page)


def _triage() -> None:
    """四选一：难受 / 想说说 / 朋友出事 / 逛逛；这里不判级，只负责路由。"""
    if st.session_state.get(BROWSE_KEY):
        _compact()
        return
    with st.container(border=True):
        st.markdown("**你现在想做哪件事？**")
        st.caption("点一个就到，不用先解释。")
        for start in range(0, len(TRIAGE), 2):
            cols = st.columns(2)
            for col, (label, mode, page, key) in zip(cols, TRIAGE[start:start + 2]):
                if col.button(label, key=key, use_container_width=True):
                    _enter(mode, page, key)


def _compact() -> None:
    """收起后两个求助入口原地保留：安全路径不能因为「逛逛」多一次点击。"""
    cols = st.columns(3)
    if cols[0].button("我现在很难受", key="home_help_self", use_container_width=True):
        goto("help", "self")
    if cols[1].button("我朋友出事了", key="home_help_friend", use_container_width=True):
        goto("help", "friend")
    if cols[2].button("展开四个入口", key="home_triage_on", use_container_width=True):
        st.session_state.pop(BROWSE_KEY, None)
        st.rerun()


def render() -> None:
    """首屏列表：不渲染 chat_input，用户先选一个入口。"""
    st.subheader("今天想怎么待一会儿？")
    st.caption("不用选对，随便点一个；随时可以回这里。")
    _triage()
    for title, items in _groups():
        st.markdown(f"**{title}**")
        for start in range(0, len(items), 2):
            cols = st.columns(2)
            for col, item in zip(cols, items[start:start + 2]):
                _card(col, *item)
    if st.button("不知道选哪个？随便来一个", key="home_random",
                 use_container_width=True):
        pick_random()

    st.divider()
    st.caption(DISCLAIMER)
    # [SAFE] 首页常驻资源，不折叠、不靠用户点开：这是第一屏就能看到的求助入口。
    for item in pick_resources("L3", []):
        st.info(f"{item['title']}：{item['detail']}")
