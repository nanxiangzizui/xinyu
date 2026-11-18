"""app.py — P17 路由：首屏列表 / 陪伴 / 角色卡 / 测试 / 放松页。

页面只做路由与配置；聊天管线在 orchestrator，A 页在 companion_ui，
B 页在 rolecard_ui，放松页在 relax_ui。这里不判级、不拼 prompt。
"""
from __future__ import annotations

import logging
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# 线上（Streamlit Cloud）没有 .env，密钥只放在平台的 Secrets 里，读法是 `st.secrets`，
# 不是环境变量。必须在 import memory / agent 之前铺好：memory.py 的 DATA_DIR 是模块级常量。
_SECRET_KEYS = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "MOCK_LLM",
                "DATA_DIR", "LOG_DIR", "ALLOW_WEB", "WEB_PROVIDER",
                "BOCHA_API_KEY", "BOCHA_ENDPOINT",
                "TAVILY_API_KEY", "TAVILY_ENDPOINT",
                "WEB_API_KEY", "WEB_ENDPOINT", "ROLECARD", "HOME_HUB")


def _bridge_secrets() -> None:
    """把 st.secrets 铺进环境变量，只补空缺，不覆盖已有值。

    [SAFE] 这里必须兜底：本地没有 secrets.toml 时读取会抛异常，
    线上没配 Secrets 时也不该崩——真正缺 Key 由 _config_gate 报，不在这里报两遍。
    """
    try:
        items = st.secrets.to_dict() if hasattr(st.secrets, "to_dict") else dict(st.secrets)
    except Exception:                       # 边界：没有 Secrets 是正常情况
        return
    for key in _SECRET_KEYS:
        val = items.get(key)
        if val is not None and not os.getenv(key):
            os.environ[key] = str(val)


_bridge_secrets()

from theme import inject_theme, theme_picker
from ui_common import (DEFAULT_PERSONA, DISCLAIMER, get_session_id,
                       home_enabled, rolecard_enabled)
import agent
import byok
import companion_ui
import home
import quiz_ui
import relax_ui
import rolecard_ui
import web

logger = logging.getLogger(__name__)


def _sync_model() -> bool:
    """把会话 Key 交给 agent，并决定这一轮是否走显式演示模式。

    [SAFE] 公开实例没有 Key 时不再整页 st.stop：页面能开，回复由本地脚本生成。
    危机路径本来就不依赖 LLM，断网、欠费、没 Key 都照样出模板与资源卡，
    这正是"断网仍出危机卡"要演示的行为。
    """
    key = byok.current()
    agent.set_session_key(key)
    demo = (not key and not os.getenv("LLM_API_KEY")
            and os.getenv("MOCK_LLM", "0").strip() != "1")
    agent.set_demo_mode(demo)
    return demo


def _config_gate() -> None:
    """配置状态写在第一屏：有 Key 不打扰，没 Key 明确说这是演示。"""
    if _sync_model():
        st.info("演示模式：当前没有配置模型 Key，回复由本地脚本生成。"
                "在侧栏「模型设置」填入你自己的 DeepSeek Key 即可开启真实对话。")


def _rolecard_enabled() -> bool:
    """兼容旧调用；开关定义在 ui_common。"""
    return rolecard_enabled()


def _nav() -> None:
    """侧栏导航：首页不显示返回；聊天与角色卡互切；测试/放松只回首页。"""
    mode = st.session_state.get("mode", "home")
    with st.sidebar:
        if mode != "home" and home_enabled():
            if st.button("回首页", key="home_back"):
                st.session_state["mode"] = "home"
                st.rerun()
        if mode == "companion" and rolecard_enabled():
            if st.button("角色卡模式", key="rc_to_rolecard"):
                st.session_state["mode"] = "rolecard"
                rolecard_ui.ensure_state()
                st.rerun()
        elif mode == "rolecard":
            if st.button("返回陪伴模式", key="rc_to_companion"):
                st.session_state["mode"] = "companion"
                st.rerun()


def _current_mode() -> str:
    """决定首屏：HOME_HUB=0 或 B 被关掉时回退，不让页面停在空路由。"""
    mode = st.session_state.get("mode")
    if not mode:
        mode = "home" if home_enabled() else "companion"
    if mode == "home" and not home_enabled():
        mode = "companion"
    if mode == "rolecard" and not rolecard_enabled():
        mode = "home" if home_enabled() else "companion"
    st.session_state["mode"] = mode
    return mode


def main() -> None:
    st.set_page_config(page_title="心屿 · 情绪陪伴", layout="centered")
    st.title("心屿")
    st.caption(DISCLAIMER)                         # 第一屏常驻，不折叠
    _config_gate()
    web.register_tools()   # 注册 ≠ 暴露：ALLOW_WEB=0 时模型看不到网络工具

    # 主题注入必须早于聊天区渲染；选择器是侧栏第一项，导航按钮排在它后面。
    inject_theme(theme_picker())
    mode = _current_mode()
    _nav()
    byok.render()          # 侧栏「模型设置」：访客自带 Key 只影响本会话
    sid = get_session_id()
    if mode == "home":
        home.render()
    elif mode == "rolecard":
        rolecard_ui.render()
    elif mode == "quiz":
        quiz_ui.render_page(sid)
    elif mode == "relax":
        relax_ui.render()
    else:
        companion_ui.render(sid)


if __name__ == "__main__":
    main()
