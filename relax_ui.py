"""relax_ui.py — P17 六个放松页 + 三个文字游戏页的路由与页面。

[SAFE] 这些页面不调用 agent / orchestrator / guardian，不判级、不写记忆；
“写下来”只留在 st.session_state，刷新或点“撕掉”就没了。
"""
from __future__ import annotations

import random

import streamlit as st

import relax_data
import relax_media
import word_games
from ui_common import home_enabled


def _back() -> None:
    if st.button("回首页", key="relax_home"):
        st.session_state["mode"] = "home"
        st.rerun()


def _breath() -> None:
    st.caption("跟着圆圈就好，不用屏息；头晕或不舒服就停下来。")
    relax_media.render_breath()
    st.caption("这是固定的动画，不会根据你的状态调整节奏。")


def _ground() -> None:
    step = st.session_state.setdefault("relax_ground_step", 0)
    if step < len(relax_data.GROUNDING):
        st.progress((step + 1) / len(relax_data.GROUNDING),
                    text=f"第 {step + 1} / {len(relax_data.GROUNDING)} 步")
        st.markdown(f"### {relax_data.GROUNDING[step]}")
    else:
        st.success("五步走完了。能回到这里，已经够了。")
    cols = st.columns(3)
    if cols[0].button("上一步", key="ground_prev", disabled=step == 0):
        st.session_state["relax_ground_step"] = max(0, step - 1)
        st.rerun()
    if cols[1].button("下一步", key="ground_next",
                      disabled=step >= len(relax_data.GROUNDING)):
        st.session_state["relax_ground_step"] = step + 1
        st.rerun()
    if cols[2].button("从头来", key="ground_reset"):
        st.session_state["relax_ground_step"] = 0
        st.rerun()
    st.caption("漏掉一两样也没关系，做多少算多少。")


def _break() -> None:
    idx = st.session_state.setdefault(
        "relax_micro_idx", random.randrange(len(relax_data.MICRO_ACTIONS)))
    st.markdown(f"### {relax_data.MICRO_ACTIONS[idx]}")
    st.caption(relax_data.GENTLE_LINES[idx % len(relax_data.GENTLE_LINES)])
    relax_media.render_timer(30, "微休息")
    if st.button("换一个小动作", key="break_next"):
        st.session_state["relax_micro_idx"] = (
            idx + random.randrange(1, len(relax_data.MICRO_ACTIONS))) % len(
                relax_data.MICRO_ACTIONS)
        st.rerun()


def _journal() -> None:
    st.caption("只在这页；不会保存到磁盘，也不会发给心屿。想清掉就点“撕掉”。")
    for key, prompt in (("relax_worry", relax_data.JOURNAL_PROMPTS[0]),
                        ("relax_control", relax_data.JOURNAL_PROMPTS[1])):
        st.markdown(f"**{prompt[0]}**")
        st.caption(prompt[1])
        st.text_area("写在这里", key=key, height=100,
                     label_visibility="collapsed")
    if st.button("撕掉", key="relax_tear"):
        for key in ("relax_worry", "relax_control"):
            st.session_state.pop(key, None)
        st.rerun()
    st.caption("如果写完还是很难受，可以回首页找“与心屿聊聊天”，或者联系首页的资源。")


def _sound() -> None:
    st.caption("默认是静的；点一个声音才会开始，可以调音量、设定时。")
    relax_media.render_sound()
    with st.expander("声音来源与许可"):
        st.markdown(
            "- 雨：Public domain，ezwa / Wikimedia Commons\n"
            "- 风：CC BY-SA 4.0，Wikimedia Commons\n"
            "- 海浪：Public domain，Wikimedia Commons\n\n"
            "音频由浏览器从 Wikimedia Commons 加载；加载不了就换一个，"
            "不会影响其它页面。")
        for label, url in (
            ("雨 · Rain (1).ogg",
             "https://commons.wikimedia.org/wiki/File:Rain_(1).ogg"),
            ("风 · Strong winds before the Rain.ogg",
             "https://commons.wikimedia.org/wiki/File:Strong_winds_before_the_Rain.ogg"),
            ("海浪 · On a pebble beach.ogg",
             "https://commons.wikimedia.org/wiki/File:On_a_pebble_beach.ogg"),
        ):
            st.link_button(label, url, use_container_width=True)


def _links() -> None:
    st.caption("这些网站会离开心屿；它们有自己的隐私政策和广告。")
    for item in relax_data.safe_links():
        st.link_button(f"{item['label']} ↗", item["url"], use_container_width=True)
        st.caption(f"{item['note']} 将离开本站。")
    st.caption("如果不想开新页面，也可以回到首页选一个本地的小练习。")


def render() -> None:
    """按 relax_page 画一页；默认呼吸页。"""
    if not home_enabled():
        st.session_state["mode"] = "companion"
        st.rerun()
    page = st.session_state.get("relax_page", "breath")
    pages = {
        "breath": ("跟着呼吸", _breath),
        "ground": ("5-4-3-2-1 接地", _ground),
        "break": ("一分钟微休息", _break),
        "journal": ("写下来", _journal),
        "sound": ("环境音", _sound),
        "links": ("看看别处", _links),
        "brain": ("脑筋急转弯", lambda: word_games.render("brain")),
        "riddle": ("猜谜语", lambda: word_games.render("riddle")),
        "idiom": ("成语接龙", lambda: word_games.render("idiom")),
    }
    title, draw = pages.get(page, pages["breath"])
    st.subheader(title)
    _back()
    st.caption("这里不判断你的状态，也不打分；随时可以停。")
    draw()
