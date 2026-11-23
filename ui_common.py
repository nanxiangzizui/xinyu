"""ui_common.py — 页面共用的文案、会话 id 与开关。  # P48LOOP

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


# P40：求助页与四个新场景页都要「一行标签 + 可复制的整句」与危机资源卡。
# 第二个模块要用，才搬到公共层（规则 8.1）；resources 延迟导入避免顶层互相拖。
def copy_block(label: str, text: str) -> None:
    """一行标签 + 可复制的整句：st.code 自带复制按钮，不依赖前端脚本。"""
    st.markdown(f"**{label}**")
    st.code(text, language=None)


def resource_lines() -> None:
    """危机资源卡：号码只从 resources 取，页面不拼新号。"""
    from resources import pick_resources

    for item in pick_resources("L3", []):
        st.info(f"{item['title']}：{item['detail']}")


# P45：help_daily / help_more 共用同一套排版，避免两份 _bullets / _say / _hard。
def bullets(items: tuple[str, ...] | list[str]) -> None:
    """一组短句：每条一行，不拼成长段。"""
    for line in items:
        st.markdown(f"- {line}")


def say(items: tuple[tuple[str, str], ...] | list[tuple[str, str]]) -> None:
    """一组「标签 + 可复制整句」：st.code 自带复制按钮。"""
    for label, text in items:
        copy_block(label, text)


def hard(lines: tuple[str, ...] | list[str], extra: str) -> None:
    """硬线：红框里只放「出现什么」+「打给谁」。"""
    st.error("出现下面任何一条，别再一个人扛：\n\n"
             + "\n\n".join(f"- {line}" for line in lines)
             + f"\n\n- {extra}")


# P41：全局「返回上一级」。页面最上方（主区、侧栏分界线右侧）一个按钮，每个页面都有。
# 用会话内的页面栈记来路，而不是给每页写死父页面：同一个页面可以从首页、
# 索引页或聊天进来，写死父级会把其中两条路带回错的地方。栈只活在本会话，
# 刷新即空；空栈时的上一级是首页（HOME_HUB=0 时是聊天）。
NAV_STACK = "nav_stack"
NAV_LAST = "nav_last"
NAV_MAX = 20


def nav_page() -> tuple[str, str]:
    """当前页面签名：mode + 子页；只有 help / relax 有子页。"""
    mode = st.session_state.get("mode", "home")
    if mode == "help":
        return mode, st.session_state.get("help_page", "self")
    if mode == "relax":
        return mode, st.session_state.get("relax_page", "breath")
    return mode, ""


def nav_root() -> tuple[str, str]:
    """最上一级：没有来路时退到这里；首页关掉时是聊天。"""
    return ("home", "") if home_enabled() else ("companion", "")


def nav_record() -> None:
    """每帧开头对一次账：页面真的变了才把上一页压栈，来路只活在本次会话。"""
    current = nav_page()
    last = st.session_state.get(NAV_LAST)
    if last is None:
        st.session_state[NAV_LAST] = current
        return
    if tuple(last) == current:
        return
    stack = [tuple(p) for p in st.session_state.get(NAV_STACK, ())]
    stack.append(tuple(last))
    st.session_state[NAV_STACK] = stack[-NAV_MAX:]
    st.session_state[NAV_LAST] = current


def _nav_apply(page: tuple[str, str]) -> None:
    """把页面签名写回 session_state；角色卡要补 rc_*，否则渲染缺状态。"""
    mode, sub = page
    if mode == "help":
        st.session_state["help_page"] = sub or "self"
    elif mode == "relax":
        st.session_state["relax_page"] = sub or "breath"
    elif mode == "rolecard":
        import rolecard_ui

        rolecard_ui.ensure_state()
    st.session_state["mode"] = mode
    st.session_state[NAV_LAST] = page


def nav_back() -> None:
    """回上一页：有来路就退一格，没有就回最上一级；已在最上一级则不动。"""
    stack = [tuple(p) for p in st.session_state.get(NAV_STACK, ())]
    target = stack.pop() if stack else nav_root()
    st.session_state[NAV_STACK] = stack
    if target == nav_page():
        return
    _nav_apply(target)
    st.rerun()


def back_button() -> None:
    """页面顶部的「返回上一级」（主区、分界线右侧）；最上一级且没有来路时不可用。"""
    at_root = not st.session_state.get(NAV_STACK) and nav_page() == nav_root()
    if st.button("← 返回上一级", key="nav_back", disabled=at_root,
                 help="已经在最上一级" if at_root else "回到刚才那一页"):
        nav_back()


# P42：侧栏常驻「与心屿交流一下」——任何页面都能一步回到陪伴模式（A 模式）。
# 和「返回上一级」分工不同：返回退一步、看页栈；这个是不看来路的固定入口。
# 已经在陪伴模式时禁用，而不是隐藏：入口位置不变，用户不必满页找它。
TALK_LABEL = "与心屿交流一下"


def in_companion() -> bool:
    """当前是否就在陪伴模式（A 模式），不看 rolecard。"""
    return nav_page() == ("companion", "")


def talk_button() -> None:
    """侧栏第一个入口：跳到陪伴模式；已经在那里时禁用。"""
    here = in_companion()
    with st.sidebar:
        if st.button(TALK_LABEL, key="nav_talk", disabled=here,
                     use_container_width=True,
                     help="已经在这里了" if here else "回到陪伴模式，接着说"):
            # 不写 nav_last：让下一帧 nav_record 把来路压栈，返回键才能退回原页面。
            st.session_state["mode"] = "companion"
            st.rerun()
