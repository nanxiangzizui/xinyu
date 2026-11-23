"""paper.py — P40「带一页纸去咨询」：把已有记忆拼成一页可念、可复制的字。

[SAFE] 只读：memory / episodes / quiz 三类已有文件；不加字段、不落盘、不上传、
不写日志。数据不存在时给空段落，不创建任何文件——记忆是用户点过「清空」就
该真的没有的东西，这一页不能因为「我想看看」替他把文件造回来。
"""
from __future__ import annotations

import re

import streamlit as st

import episode_store
import memory
import quiz_store
from style import TONE_LABELS
from ui_common import copy_block, resource_lines

TEXT_MAX = 600
MAX_EPISODES = 6
MAX_QUIZ = 3
MAX_TAGS = 4
HEAD = ("这不是病历，也不是量表。它只是你愿意带去的一页字——"
        "想给谁看、给多少，由你决定。")
PLACEHOLDER = "（今天想让它记住的一件事）"


def _exists(sid: str) -> bool:
    """read_memory 读不到时会写默认文件；先看文件在不在，免得看一眼就产生数据。"""
    return (memory.DATA_DIR / f"{sid}.json").exists()


def _clean(text: object, limit: int) -> str:
    """单行化 + 去数字 + 截断：不带日期、电话、门牌这类东西。"""
    line = " ".join(str(text or "").split())
    line = re.sub(r"\d{2,}", "", line)
    return line[:limit].strip(" ，。、；,")


def _state(mem: dict) -> list[str]:
    """三个标签字段 + 摘要末几句；没有就返回空，不补空话。"""
    tags = [_clean(t, 6) for t in (mem.get("emotion_tags") or [])][:MAX_TAGS]
    tags = [t for t in tags if t]
    out = []
    if tags:
        out.append("最近常出现的感受：" + "、".join(tags))
    tone = mem.get("preferred_tone") or ""
    if tone in TONE_LABELS:
        out.append("希望被怎样对待：" + TONE_LABELS[tone])
    summary = mem.get("rolling_summary") or ""
    for line in [l for l in summary.split("。") if l.strip()][-3:]:
        cleaned = _clean(line, 40)
        if cleaned:
            out.append(cleaned)
    return out


def _episodes(sid: str) -> list[str]:
    """按新近度取 6 条转述；event 是已过闸门的转述，不是原话。"""
    rows = episode_store.read_store(sid).get("episodes") or []
    rows = sorted(rows, key=lambda ep: ep.get("seq", 0), reverse=True)
    return [f"{ep.get('topic', '其他')}：{_clean(ep.get('event'), 44)}"
            for ep in rows[:MAX_EPISODES]]


def _quiz(sid: str) -> list[str]:
    """只取测试名与结果名；分数、答案、原话都不带。"""
    rows = quiz_store.read_store(sid).get("attempts") or []
    rows = sorted(rows, key=lambda a: a.get("ts", 0), reverse=True)
    return [f"{_clean(a.get('title'), 20)} → {_clean(a.get('name'), 20)}"
            for a in rows[:MAX_QUIZ]]


def build(sid: str) -> dict:
    """返回 {"state": [...], "episodes": [...], "quiz": [...]}，全部已清洗。"""
    mem = memory.read_memory(sid) if _exists(sid) else {}
    return {"state": _state(mem), "episodes": _episodes(sid), "quiz": _quiz(sid)}


def to_text(sid: str, extra: str = "") -> str:
    """拼成可复制 / 可下载的纯文本；没有内容时也给出可用的空白骨架。"""
    data = build(sid)
    lines = ["给咨询师的一页（我自己写的）", ""]
    sections = (("我这阵子的状态", data["state"]),
                ("最近提过的事", data["episodes"]),
                ("做过的小测试", data["quiz"]))
    for title, rows in sections:
        lines.append(f"【{title}】")
        if rows:
            lines.extend(f"- {row}" for row in rows)
        else:
            lines.append("（还没写）")
        lines.append("")
    note = _clean(extra, TEXT_MAX)
    lines.append("【我想补的一句】")
    lines.append(note or "（还没写）")
    return "\n".join(lines)


def _section(title: str, rows: list[str], empty: str) -> None:
    """一页三块共用：有就列，没有就说清楚为什么空。"""
    st.markdown(f"### {title}")
    for row in rows:
        st.markdown(f"- {row}")
    if not rows:
        st.caption(empty)


def render(sid: str) -> None:
    """只读渲染；编辑只发生在 text_area（session_state），不进任何文件。"""
    st.caption(HEAD)
    data = build(sid)
    _section("1. 我这阵子的状态", data["state"], "（还没有记录。聊过几轮之后这里会有。）")
    _section("2. 最近提过的事", data["episodes"], "（还没有能接上的事。）")
    _section("3. 做过的小测试", data["quiz"], "（还没做过，或者没存下来。）")
    st.text_area("4. 我想补一句", key="paper_note", max_chars=TEXT_MAX,
                 placeholder=PLACEHOLDER, height=120)
    text = to_text(sid, st.session_state.get("paper_note", ""))
    st.caption("这一页只在这里；关掉就没了。想带走可以用下面两个按钮。")
    copy_block("复制这一页", text)
    st.download_button("下载成 .txt", data=text.encode("utf-8"),
                       file_name="给咨询师的一页.txt", mime="text/plain",
                       key="paper_dl")
    st.markdown("到咨询室可以先说一句：「我写了一页，怕说不清楚，"
                "可以照着念吗？」——多数人不会因为这句话被为难。")
    resource_lines()
