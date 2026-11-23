"""help_index.py — P44/P45「我遇到的是…」索引页：26 个入口，接住 32 个时刻。

[SAFE] 不判级、不调 agent / guardian、不写记忆、不联网。点错最坏也只是落到
一页静态内容或已有入口，不存在“该给资源却没给”的路径。

为什么不放进 help_pages.py：那里已经 345 行、还装着 17 张页的文案；这里只加
一张目录，放进去会把「内容」和「导航」搅在一起。
"""
from __future__ import annotations

import streamlit as st

import quiz_ui

# (按钮文字, 一句说明, mode, page, key)：顺序 = 今晚 → 这几天 → 人 → 不说 → 关于。
# key 显式写死：同一目标出现两次（关于页）时，靠下标生成 key 会撞车。
GROUPS = (
    ("今晚就要", (
        ("我现在很难受", "先给一个号，再给一句能发出去的话。",
         "help", "self", "idx_self"),
        ("刚挺过来，不知道怎么过这一晚", "今晚谁陪、东西交给谁、明早打给谁。",
         "help", "aftermath", "idx_aftermath"),
        ("躺下睡不着，脑子停不下来", "20 分钟睡不着就起来，别算时间。",
         "help", "sleep", "idx_sleep"),
        ("失恋 / 被拒了", "先过今晚，不在半夜做不可逆的决定。",
         "help", "love", "idx_love"),
        ("今晚就想找个人说话", "不用组织语言，想到哪说到哪。",
         "companion", "", "idx_chat"),
    )),
    ("这几天", (
        ("考砸了 / 出分那天", "48 小时内先不做决定，今晚只做三件事。",
         "help", "exam", "idx_exam"),
        ("要去咨询了，不知道说什么", "带三行字去，可以拒绝回答。",
         "help", "before", "idx_before"),
        ("咨询完这一周", "有点空也算正常，什么时候再约。",
         "help", "after", "idx_after"),
        ("要跟辅导员 / 老师说", "先说多少、再问四件要问清楚的事。",
         "help", "teacher", "idx_teacher"),
        ("请假 / 缓考 / 休学", "带五个问题去问，不替你做决定。",
         "help", "leave", "idx_leave"),
        ("生活费不够 / 兼职被坑", "先算一个最小数字；别碰校园贷。",
         "help", "money", "idx_money"),
        ("毕业 / 考研 / 找工作", "先缩小问题，再查一个截止日期。",
         "help", "future", "idx_future"),
        ("拖延 / 论文 / 毕设", "先写 15 分钟；延期 / 重修问辅导员。",
         "help", "thesis", "idx_thesis"),
    )),
    ("跟别人有关", (
        ("朋友出事了", "先接住，再给硬线，你自己也要被照顾。",
         "help", "friend", "idx_friend"),
        ("陪他去医院 / 心理中心", "你能做什么、不能做什么。",
         "help", "accompany", "idx_accompany"),
        ("有人在群里挂我 / 发我照片", "先存证、别对骂，什么时候打 110。",
         "help", "online", "idx_online"),
        ("室友 / 宿舍住不下去", "先提一件具体的事；换宿要问什么。",
         "help", "roommate", "idx_roommate"),
        ("和家里吵完 / 要不要告诉家里", "先保今晚安全，再决定说多少。",
         "help", "family", "idx_family"),
        ("当众被说 / 社恐", "先离开现场，再决定要不要解释。",
         "help", "shame", "idx_shame"),
        ("亲人重病 / 去世", "先允许自己乱，前两周不做重大决定。",
         "help", "grief", "idx_grief"),
    )),
    ("不想说话也可以", (
        ("呼吸 / 接地 / 微休息", "三分钟，先让身体慢下来。",
         "relax", "breath", "idx_relax"),
        ("写下来", "写完不保存，也不回显。",
         "relax", "journal", "idx_journal"),
        ("给心屿一张角色卡", "不谈现实，只陪一会儿。",
         "rolecard", "", "idx_rolecard"),
        ("做个小测试 / 玩个游戏", "四个小测试、三个文字游戏。",
         "quiz", "", "idx_quiz"),
    )),
    ("关于心屿", (
        ("它是什么、记了什么、怎么删", "先说边界，再说存了什么。",
         "about", "", "idx_about"),
        ("什么情况该找真人", "四个问题，帮你想清楚要不要去。",
         "about", "", "idx_seek"),
    )),
)

HEAD = ("这里列的是 26 个入口，接住 32 个时刻。没列到的，可能还没做——"
        "那也是一种诚实。")

# 搜索词只用于索引过滤，不进 prompt、不落盘；顺序与 GROUPS 无关。
KEYWORDS = {
    "idx_self": "难受 危险 自杀 不想活 撑不住 危机 自伤",
    "idx_aftermath": "刚挺过来 危机之后 今晚 陪 72 小时 劝下来",
    "idx_sleep": "睡不着 失眠 凌晨 睡眠 早醒 半夜",
    "idx_love": "失恋 分手 被拒 前任 表白 感情",
    "idx_chat": "聊天 说话 没人 孤独 想说说",
    "idx_exam": "考砸 挂科 退学 出分 补考 重修 成绩 学业预警",
    "idx_before": "咨询 心理中心 第一次 不知道说什么 预约",
    "idx_after": "咨询后 空 复诊 这一周",
    "idx_teacher": "辅导员 老师 保密 家长 通知 披露",
    "idx_leave": "请假 缓考 休学 手续 材料",
    "idx_money": "钱 生活费 兼职 工资 校园贷 诈骗 困难补助 借钱",
    "idx_friend": "朋友 出事 自杀 不想活 劝 不肯去 旁观者",
    "idx_accompany": "陪 医院 心理中心 陪同 朋友",
    "idx_online": "网暴 挂人 照片 隐私 举报 旁观者 群",
    "idx_roommate": "室友 宿舍 作息 卫生 吵 孤立 换宿",
    "idx_family": "家里 父母 家长 吵 比较 催 告诉家里 回家",
    "idx_future": "毕业 考研 找工作 秋招 春招 offer 延毕 退学 考公 实习 就业",
    "idx_thesis": "拖延 论文 毕设 开题 查重 答辩 导师 延期 重修 写不完",
    "idx_shame": "当众 被说 点名 社恐 发言 演讲 出丑 丢脸 发抖 社交",
    "idx_grief": "亲人 去世 重病 丧亲 哀伤 葬礼 生病 住院 死亡",
    "idx_relax": "呼吸 接地 放松 身体 微休息",
    "idx_journal": "写下来 日记 不保存 记录",
    "idx_rolecard": "角色卡 陪伴 虚拟 角色",
    "idx_quiz": "测试 游戏 趣味 小测试",
    "idx_about": "关于 边界 数据 删除 隐私 记忆",
    "idx_seek": "找真人 咨询 什么时候 判断",
}


def _enter(mode: str, page: str) -> None:
    """与 home.goto 同口径；不 import home，免得首页 ↔ 索引互相引用。"""
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


def _matches(query: str):
    """按标签、说明、关键词过滤；空格分隔的多个词要全中。"""
    terms = [t for t in query.lower().split() if t]
    out = []
    for _title, items in GROUPS:
        for item in items:
            hay = f"{item[0]} {item[1]} {KEYWORDS.get(item[4], '')}".lower()
            if all(t in hay for t in terms):
                out.append(item)
    return out


def _cards(items) -> None:
    """两列卡片；抽出来给分组与搜索结果共用。"""
    for start in range(0, len(items), 2):
        cols = st.columns(2)
        for col, (label, desc, mode, page, key) in zip(
                cols, items[start:start + 2]):
            with col.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(desc)
                if st.button("去这里", key=key, use_container_width=True):
                    _enter(mode, page)


def render_body() -> None:
    """五组卡片 + 一个关键词搜索；搜不到就给聊天入口。"""
    st.caption(HEAD)
    query = st.text_input(
        "搜一个词", key="idx_search",
        placeholder="室友、失眠、钱、分手、家里、挂科……")
    if query.strip():
        items = _matches(query)
        if not items:
            st.info("没找到。可能这一页还没做——你可以去聊天里说说这件事。")
            if st.button("去和心屿说这件事", key="idx_no_match_chat"):
                _enter("companion", "")
            return
        st.caption(f"找到 {len(items)} 个")
        _cards(items)
        return
    for title, items in GROUPS:
        st.markdown(f"**{title}**")
        _cards(items)
