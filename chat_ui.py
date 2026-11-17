"""chat_ui.py — 聊天区渲染与连发合并（P9c 从 app.py 搬出，A/B 共用）。

为什么搬家：B 模式也要"连发合并 + 先落库再渲染"，在 app 里抄第二份必然漂移。
"""
from __future__ import annotations

import streamlit as st


def render_gap(gap: dict | None) -> None:
    """盲点补全的提示：成功给来源，失败说原因；不展示原查询。"""
    if not gap:
        return
    focus = gap.get("focus") or ""
    if gap.get("error"):
        st.caption(f"没能补全「{focus}」：{gap['error']}")
        return
    note = gap.get("note") or ""
    count = int(gap.get("count") or 0)
    if count:
        suffix = f"（{note}）" if note else ""
        st.caption(f"已为「{focus}」补全 {count} 条认知{suffix}，这一轮起生效。")
    elif note:
        st.caption(f"「{focus}」：{note}")
    else:
        st.caption(f"已为「{focus}」补全 0 条认知。")
    for src in gap.get("sources") or []:
        if src.get("url"):
            st.markdown(f"- [{src.get('title') or src['url']}]({src['url']})")


def render_history(messages: list[dict]) -> None:
    """按顺序渲染历史；来源链接只来自代码过滤后的 sources，不解析模型正文。"""
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            for src in msg.get("sources") or []:
                if src.get("url"):
                    st.markdown(f"- [{src.get('title') or src['url']}]({src['url']})")
            if msg.get("role") == "assistant":
                render_gap(msg.get("gap"))


def merge_tail(messages: list[dict]) -> tuple[list[dict], str]:
    """连发合并：把末尾连续的 user 拼成一段，喂模型的 history 里只留一条。

    为什么要动 history 而不是只改入参：`agent_loop` 把 history 直接当上下文
    （当前这句就在 history 末条），多留一条 user 会让同一句话出现两次。
    """
    count = 0
    for msg in reversed(messages):
        if msg.get("role") != "user":
            break
        count += 1
    if not count:
        return list(messages), ""
    merged = "\n".join(m.get("content") or "" for m in messages[-count:])
    return [*messages[:-count], {"role": "user", "content": merged}], merged


def accept(messages: list[dict], text: str) -> tuple[list[dict], str, int]:
    """收下这句输入：连发合并成一段，轮次按"已有几条 assistant"推出来。

    为什么轮次不能 += 1：连发时前一轮被 Streamlit 中断（没写成 assistant），
    按输入条数计轮会让侧栏和日志虚涨；只看已答条数，重跑一次还是同一轮。
    """
    messages.append({"role": "user", "content": text})
    history, merged = merge_tail(messages)
    turn = sum(1 for m in history if m.get("role") == "assistant") + 1
    return history, merged, turn
