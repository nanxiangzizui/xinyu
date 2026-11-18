"""chat_ui.py — 聊天区渲染与连发合并（P9c 从 app.py 搬出，A/B 共用）。

为什么搬家：B 模式也要"连发合并 + 先落库再渲染"，在 app 里抄第二份必然漂移。
"""
from __future__ import annotations

import os
import time

import streamlit as st

import style

# P14：气泡之间只停一下，不做逐字流式；停顿是节奏，不是加载等待。
REPLY_PAUSE_S = 0.35


def split_enabled() -> bool:
    """REPLY_SPLIT=0 一键关回单气泡；默认开，现场觉得碎可以随时关。"""
    return os.getenv("REPLY_SPLIT", "1").strip() != "0"


def reply_parts(result: dict) -> list[str]:
    """按等级与兜底标记决定拆几段；只拆复核通过的正常回复。"""
    reply = result.get("reply") or ""
    if not split_enabled():
        return [reply]
    return style.split_reply(reply, result.get("level", "L1"),
                             bool(result.get("template_fallback")),
                             bool(result.get("degraded")))


def render_reply(parts: list[str], role: str = "assistant",
                 animate: bool = False, extra=None) -> None:
    """每段一个气泡；extra 只在最后一个气泡里画（来源/资源卡/补全备注）。"""
    shown = [part for part in parts if part] or [""]
    for i, part in enumerate(shown):
        if i and animate:
            time.sleep(REPLY_PAUSE_S)
        with st.chat_message(role):
            st.markdown(part)
            if i == len(shown) - 1 and extra is not None:
                extra()


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


def render_sources(sources) -> None:
    """来源只渲染代码过滤过的链接：模型自己写的 URL 一个都不认。

    P20：A 模式原来只在历史重绘时画来源，当轮看不到；抽出来给两处共用。
    """
    for src in sources or []:
        if src.get("url"):
            st.markdown(f"- [{src.get('title') or src['url']}]({src['url']})")


def render_history(messages: list[dict]) -> None:
    """按顺序渲染历史；多段回复按存下的 parts 复原，来源链接只来自代码过滤后的 sources。"""
    for msg in messages:
        parts = msg.get("parts") or [msg["content"]]

        def extra(m=msg) -> None:
            render_sources(m.get("sources"))
            if m.get("role") == "assistant":
                render_gap(m.get("gap"))

        render_reply(parts, role=msg["role"], extra=extra)


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
    # 开场白与趣味测试报告虽标了 assistant，但都不是一轮回复：算进去会让轮次虚涨，
    # 摘要节流（P10 每 5 轮）也会提前触发。
    turn = sum(1 for m in history
               if m.get("role") == "assistant"
               and not m.get("opening") and not m.get("quiz")) + 1
    return history, merged, turn
