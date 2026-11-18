"""ui_common.py — 页面共用的文案、会话 id 与开关。

不承载任何业务判断：只把三处都会用到的字符串和两个 feature flag 放在一起，
免得 app / companion / home 各写一份免责声明。
"""
from __future__ import annotations

import os
import re
import uuid

import streamlit as st

DISCLAIMER = (
    "这是一个情绪陪伴工具，不是心理咨询，也不能替代真人帮助。"
    "如果你或身边的人有危险，请拨打 120 / 110 或 12356。"
)
NET_HINT = "网络不稳定：刚才那条是兜底回复"
DEFAULT_PERSONA = "sister_heart"

# 与 memory.py 的 ID_RE 同口径：会话 id 来自 URL，必须先校验再交给磁盘层。
SID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")


def get_session_id() -> str:
    """会话 id 只放 URL：session_state 刷新即空，放那里记忆就断了。"""
    raw = st.query_params.get("u")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if isinstance(raw, str) and SID_RE.fullmatch(raw):
        return raw
    sid = uuid.uuid4().hex[:12]
    st.query_params["u"] = sid
    return sid


def rolecard_enabled() -> bool:
    """D9-8：ROLECARD=0 时彻底隐藏 B 入口；默认开启。"""
    return os.getenv("ROLECARD", "1").strip() != "0"


def home_enabled() -> bool:
    """P17：HOME_HUB=0 回退到旧的 companion 首屏。"""
    return os.getenv("HOME_HUB", "1").strip() != "0"
