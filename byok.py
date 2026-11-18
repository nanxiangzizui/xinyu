"""byok.py — 访客自带 Key（BYOK）：只收 Key，不收地址。

为什么只收 Key：让服务端替用户请求任意 base_url 等于开放 SSRF，
项目红线也写着"工具不接受任意 URL"；模型名同样由服务端写死。
Key 只进 st.session_state：不落盘、不写日志、不进 prompt / memory / trace，
刷新页面即失效（Streamlit 本来就是刷新即重置）。
"""
from __future__ import annotations

import os
import re

import streamlit as st

FIELD = "byok_key"
_KEY_RE = re.compile(r"^sk-[A-Za-z0-9_-]{16,200}$")
_PLACEHOLDER = "sk-..."
_BAD = "格式不对：应以 sk- 开头，后面 16–200 位字母、数字、下划线或连字符。"
_HINT = "只对本浏览器会话有效；不落盘、不写日志、不进对话内容。"


def _state(state=None):
    """测试可以直接传 dict，不必起 Streamlit 运行时。"""
    return st.session_state if state is None else state


def clean(text: str) -> str:
    """去掉首尾空白和引号：从聊天窗口复制过来常带这些。"""
    return (text or "").strip().strip('"').strip("'").strip()


def valid(text: str) -> bool:
    """只认 sk- 形状；格式不对就不启用，避免把别的串当 Key 发出去。"""
    return bool(_KEY_RE.match(clean(text)))


def current(state=None) -> str:
    """当前会话的 Key；没填就是空串。"""
    return str(_state(state).get(FIELD, ""))


def set_key(text: str, state=None) -> bool:
    """校验通过才写入会话，返回是否启用。"""
    key = clean(text)
    if not valid(key):
        return False
    _state(state)[FIELD] = key
    return True


def clear(state=None) -> None:
    """删掉会话里的 Key；下一次调用就回到站点 Key / 演示模式。"""
    _state(state).pop(FIELD, None)


def mode_label(state=None) -> str:
    """三态：自己的 Key / 站点额度 / 本地演示。"""
    if current(state):
        return "你自己的 Key"
    if os.getenv("LLM_API_KEY"):
        return "站点演示额度"
    return "本地演示（无 Key）"


def render() -> None:
    """侧栏「模型设置」：填 Key、启用、清除；用户不点就不发任何请求。"""
    with st.sidebar.expander("模型设置（可选）", expanded=False):
        st.caption(f"当前模型来源：{mode_label()}。")
        typed = st.text_input("DeepSeek API Key", type="password",
                              placeholder=_PLACEHOLDER, key=f"{FIELD}_input")
        use, reset = st.columns(2)
        if use.button("使用这个 Key", key=f"{FIELD}_use"):
            if set_key(typed):
                st.rerun()
            st.warning(_BAD)
        if reset.button("清除", key=f"{FIELD}_clear"):
            clear()
            st.rerun()
        st.caption(_HINT)
