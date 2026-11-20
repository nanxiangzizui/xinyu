"""help_pages.py — 七张静态页：自己危险 / 朋友出事 / 咨询前 / 咨询后一周 /
跟辅导员说 / 请假缓考休学 / 陪别人去机构。

[SAFE] 不调用 agent / orchestrator / guardian，不判级、不写记忆、不联网。
文案写死在 crisis_plan 与本文件里；号码只从 resources 取，页面不拼新号。
"""
from __future__ import annotations

import streamlit as st

import crisis_plan
from resources import CAMPUS_PHONE, pick_resources
from ui_common import home_enabled

# 朋友页的三组话：能照着说、别说的、必须立刻找人的信号。
FRIEND_SAY = (
    ("先开口：让他知道你在", "我在。你说，我听着。不用一次说完。"),
    ("他问你会不会告诉别人",
     "我不会到处说。但如果你有危险，我会去找能帮上忙的人——我会先告诉你。"),
    ("他已经很危险", "我现在过去找你。你先别一个人待着，等我。"),
)
FRIEND_DONT = (
    "别急着问「为什么」——很多人自己也不知道。",
    "别说「想开点」「这有什么」「别人比你还难」，他会闭嘴。",
    "别答应「我绝对不告诉任何人」：真到危险时你做不到，也不该做。",
    "别自己判断他是不是抑郁——你不是医生，这句话帮不上忙。",
)
DANGER_SIGNS = (
    "说得很具体：今晚、几点、在哪里、怎么做。",
    "说「这是最后一次」「都安排好了」「以后不用管我了」。",
    "已经在做：吃了药、割了手、站在高处或水边。",
    "把东西送人、写告别的话，或者突然异常平静。",
)
FRIEND_ACTION = (
    "打 120 / 110；同时联系辅导员、宿管或他的家人。",
    "能过去就过去，不要让他一个人待着。",
    "他要你保密时，先说「我会陪你去」，别答应瞒着。",
)
SELF_CARE = (
    "你会累、会怕、会不知道说什么，这很正常，不是你做得不好。",
    "你能做的只有三件：陪着、听着、帮他找到能负责的大人。",
    "你也可以打 12356，说说你自己的感受——不是只有当事人才需要被听。",
)

# 咨询前：降低“必须准备好”的门槛；咨询后：把“没有立刻变好”解释掉。
BEFORE = (
    ("不知道怎么开口",
     "先说最近的变化：睡不好、吃不下、提不起劲、总在想同一件事。"
     "不用先证明自己“够严重”。"),
    ("可以带三行字",
     "想说的第一件事；最近一周最难受的时刻；你希望被怎么帮——"
     "先有人听，还是想要具体办法。"),
    ("可能会被问",
     "最近怎么了、多久了、睡得怎么样、有没有伤害自己的想法、之前有没有看过。"),
    ("可以拒绝回答，也可以先问清楚",
     "不想说的可以说“这个我先不说”。也可以问：哪些内容会告诉别人？"),
    ("第一次去，不用决定长期",
     "先见一面；觉得不合适可以换时间或换人。这不是签约。"),
)
AFTER = (
    ("说完可能会有点空",
     "也可能轻松、想哭、累，或者什么都没感觉。这些反应都常见，不代表你说错了。"),
    ("这一周先做一件小事",
     "把咨询里说定的那一件事做一次；做不到也不算失败。"),
    ("记一句下次想说的",
     "想到什么记一行就够，不用写成日记。"),
    ("什么时候再约",
     "如果已经影响上课、睡觉、吃饭，或者你一直在等下一次，就再约；"
     "拿不准就打校心理中心问。"),
    ("如果这次不合适",
     "可以换时间、换人，或者先停一停；不合适不等于你有问题。"),
)
BEFORE_WHERE = (
    f"校心理中心 {CAMPUS_PHONE}（工作日）。具体怎么约，以首页资源卡上的说明为准。"
)

# 机构衔接（P30）：只给“怎么问、问什么、怎么陪”，不写具体政策、不替人做决定。
# [SAFE] 三张页都不判断“该不该办”，不承诺“一定批”，也不替学校解释规定。
TEACHER_OPEN = (
    ("先说状态，不用先解释原因",
     "老师，我最近状态不太好，已经影响到上课和睡觉了。想跟您说一下。"),
    ("说在咨询，问流程",
     "我在校心理中心做咨询。想问问请假或者缓考需要什么材料。"),
    ("先问保密边界",
     "我想先问清楚：我跟您说的哪些内容会被记录？哪些情况需要告诉家长？"),
)
TEACHER_ASK = (
    ("保密到哪一步", "哪些会记录、谁知道、什么情况必须通知家长或学院。"),
    ("能帮上什么", "请假、缓考、调宿、减课——哪一项归您管，哪一项要找别人。"),
    ("要什么材料", "心理中心的证明、医院的证明，还是本人写个申请就行。"),
    ("下一步找谁", "如果这件事不归您，我应该去找哪个办公室、哪个人。"),
)
TEACHER_NOTE = (
    "对方可能只是记录、建议你去心理中心，或者在涉及安全时联系家长和学院。"
    "这些不是你能完全决定的，但可以先问清楚。"
    "「必须告知」的情形通常和安全有关，具体以学校规定为准。"
)
LEAVE_PREP = (
    ("时间线", "从哪一天开始影响到上课、考试或睡觉，大概持续了多久。"),
    ("已经试过什么", "找过老师、去过心理中心、调整过课表——说一句就够。"),
    ("你想要的结果", "先休息两周、减一门课、缓考，还是只想先问问流程。"),
)
LEAVE_ASK = (
    ("找谁办", "辅导员、教务办还是学院办公室；需不需要本人到场。"),
    ("要什么材料", "心理中心或医院的证明、本人申请、家长签字——哪一样是必须的。"),
    ("截止到什么时候", "申请窗口、考试前多久、错过还能不能补。"),
    ("会影响什么", "奖学金、评优、保研、宿舍、医保、助学贷款，逐项问。"),
    ("回来怎么接", "缓考安排、补课、复学手续，回来第一个月找谁。"),
)
LEAVE_SAY = (
    ("先问流程，不急着决定",
     "我想先了解一下办理缓考需要什么材料、找谁、截止到什么时候，可以吗？"),
    ("问影响",
     "如果这学期先减一门课，奖学金或者保研资格会受影响吗？"),
    ("问后续",
     "办完之后，我回来第一个月需要找谁对接？"),
)
LEAVE_NOTE = ("政策以学校当年文件为准。这里只帮你把问题问清楚，"
              "不替你判断该不该办，也不承诺一定批。")
ACCOMPANY_BEFORE = (
    ("先确认对方愿意", "是「我陪你去」，不是「我替你去」；时间和方式让对方选。"),
    ("带什么", "学生证、身份证、医保卡，以机构要求为准；不确定就先打电话问。"),
    ("谁来说", "让当事人自己说为主；你只在对方说不下去时补一句。"),
)
ACCOMPANY_SAY = (
    ("到前台",
     "我陪同学来的，他最近状态不太好，想找老师或者医生聊聊。"
     "我们是第一次来，需要先登记吗？"),
    ("对方说不下去时",
     "他刚才说的是最近睡不好、不太想出门；具体的让他自己跟您说。"),
)
ACCOMPANY_CAN = (
    "在旁边坐着，不催。",
    "帮忙记下时间、地点、下一次什么时候来。",
    "回来的路上不追问；想说的时候再听。",
)
ACCOMPANY_CANT = (
    "不替对方描述症状，也不替对方做决定。",
    "不替对方答应「绝对保密」——你做不到，也不该做。",
    "不把这件事当谈资，包括在群里。",
)
ACCOMPANY_SELF = (
    "陪完你会累，这是正常的；给自己留十分钟，喝口水再走。",
    "你也可以打 12356，说说你自己的感受。",
)
ACCOMPANY_NOTE = "如果对方已经在伤害自己，或者你找不到人帮忙：打 110 / 120。"

TITLES = {
    "self": "如果现在很危险",
    "friend": "我朋友出事了",
    "before": "去咨询前，可以准备什么",
    "after": "咨询后这一周",
    "teacher": "要跟辅导员 / 老师说",
    "leave": "请假 / 缓考 / 休学：去问之前",
    "accompany": "陪别人去心理中心 / 医院",
}


def _back() -> None:
    """首页开关关掉时侧栏没有「回首页」，这里补一个；开着就不放两个一样的按钮。"""
    if home_enabled():
        return
    if st.button("回首页", key="help_home"):
        st.session_state["mode"] = "companion"
        st.rerun()


def _copy(label: str, text: str) -> None:
    """一行标签 + 可复制的整句：st.code 自带复制按钮，不依赖任何前端脚本。"""
    st.markdown(f"**{label}**")
    st.code(text, language=None)


def _resources() -> None:
    for item in pick_resources("L3", []):
        st.info(f"{item['title']}：{item['detail']}")


def _self() -> None:
    """自己危险时的页：先给一个号，再给一句能发出去的话。"""
    st.caption("先不用想别的。选一件现在能做的，做完就算。")
    step = crisis_plan.first_step()
    st.markdown(f"### 先打这一个：{step['title']}")
    st.info(f"{step['detail']}\n\n{step['why']}")
    for line in step["backup"]:
        st.markdown(f"- {line}")
    st.divider()
    st.markdown("### 说不出口，就把这句发出去")
    for label, text in crisis_plan.MESSAGES:
        _copy(label, text)
    st.divider()
    st.markdown("### 打不了电话")
    st.markdown(crisis_plan.ONE_SMALL_THING)
    st.caption("做完一件就够，不用全做。")
    _resources()
    st.caption("如果只是有点难受、还没到这一步，回首页选一个轻一点的入口也可以。")


def _friend() -> None:
    """朋友危险时的页：先教怎么开口，再给"什么时候必须交给人"的硬线。"""
    st.caption("先做三件事：别让他一个人；先听；危险时立刻找人。")
    st.markdown("### 1. 先接住（可以照着说）")
    for label, text in FRIEND_SAY:
        _copy(label, text)
    st.markdown("### 2. 这几句别说")
    for line in FRIEND_DONT:
        st.markdown(f"- {line}")
    st.markdown("### 3. 出现这些，立刻找人")
    for line in DANGER_SIGNS:
        st.markdown(f"- {line}")
    st.error("立刻做：\n\n" + "\n\n".join(f"- {line}" for line in FRIEND_ACTION))
    st.caption("不是你一个人负责：辅导员、宿管、家人，任何一个能到场的大人都算。")
    st.divider()
    st.markdown("### 4. 你自己也需要被照顾")
    for line in SELF_CARE:
        st.markdown(f"- {line}")
    _resources()


def _plain(intro: str, items, note: str = "") -> None:
    """一页固定内容：小标题 + 一段话；不读用户状态，也不生成新句子。"""
    st.caption(intro)
    for head, body in items:
        st.markdown(f"**{head}**")
        st.markdown(body)
    if note:
        st.info(note)


def _before() -> None:
    """咨询前：门槛放低，把“可以问什么、可以拒绝什么”说清楚。"""
    _plain("不用准备得很完整；带上你现在最想说的那件事就够了。",
           BEFORE, BEFORE_WHERE)


def _after() -> None:
    """咨询后一周：先解释常见反应，再给一个再约的判断标准。"""
    _plain("接下来这一周，不用马上变好。", AFTER,
           "如果这一周出现伤害自己的想法，回首页点「我现在很难受」，"
           "那里有更直接的步骤。")


def _teacher() -> None:
    """跟辅导员/老师说：说多少由学生决定；先问保密边界，再问能帮什么。"""
    st.caption("说多少、说到哪一步，由你决定；可以分几次说。")
    st.markdown("### 1. 不用一次说完")
    st.markdown("- 第一档：只说「最近状态不好，影响到上课」。\n"
                "- 第二档：说「我在心理中心咨询」。\n"
                "- 第三档：说具体的困难，以及你想要的支持。")
    st.markdown("### 2. 可以怎么开口（照抄也行）")
    for label, text in TEACHER_OPEN:
        _copy(label, text)
    st.markdown("### 3. 把这四件事问清楚")
    for head, body in TEACHER_ASK:
        st.markdown(f"- **{head}**：{body}")
    st.info(TEACHER_NOTE)
    st.caption("如果聊完更难受，或者出现伤害自己的想法：回首页点「我现在很难受」。")


def _leave() -> None:
    """请假/缓考/休学：不写政策，只给去问之前的准备和五个问题。"""
    st.caption("不写具体政策——每个学校、每一年的规定都不一样；先帮你把问题问清楚。")
    st.markdown("### 1. 去之前，先想三件事")
    for head, body in LEAVE_PREP:
        st.markdown(f"- **{head}**：{body}")
    st.markdown("### 2. 把这五个问题问完")
    for head, body in LEAVE_ASK:
        st.markdown(f"- **{head}**：{body}")
    st.info(LEAVE_NOTE)
    st.markdown("### 3. 不知道怎么说，抄这三句")
    for label, text in LEAVE_SAY:
        _copy(label, text)
    st.caption("问完还是拿不准，可以带着这些问题去校心理中心，请老师一起帮你梳理。")


def _accompany() -> None:
    """陪别人去机构：能做什么、不能做什么、你自己怎么收尾。"""
    st.caption("你是陪同，不是负责人；能做的比你想的少，但已经很有用。")
    st.markdown("### 1. 去之前")
    for head, body in ACCOMPANY_BEFORE:
        st.markdown(f"- **{head}**：{body}")
    st.markdown("### 2. 到了可以这样说")
    for label, text in ACCOMPANY_SAY:
        _copy(label, text)
    st.markdown("### 3. 你能做的")
    for line in ACCOMPANY_CAN:
        st.markdown(f"- {line}")
    st.markdown("### 4. 别做的")
    for line in ACCOMPANY_CANT:
        st.markdown(f"- {line}")
    st.markdown("### 5. 你自己")
    for line in ACCOMPANY_SELF:
        st.markdown(f"- {line}")
    st.warning(ACCOMPANY_NOTE)
    _resources()


def next_step_block(key: str) -> None:
    """聊天 / 角色卡 L3 当轮用：一个号 + 一句能发出去的话 + 完整页入口。

    为什么不放完整页：L3 当轮已经把资源卡铺开了，再堆三屏会把回复淹掉；
    真要细看，点一下进独立页。
    """
    step = crisis_plan.first_step()
    st.success(f"下一步：先打 {step['title']}（{step['detail']}）")
    st.caption("说不出口，就把这句发出去：")
    st.code(crisis_plan.MESSAGES[0][1], language=None)
    if st.button("看完整的求助页", key=f"help_open_{key}"):
        st.session_state["mode"] = "help"
        st.session_state["help_page"] = "self"
        st.rerun()


def render() -> None:
    """按 help_page 画一页；缺省是自己那页（最坏情况下少一次点击）。"""
    page = st.session_state.get("help_page", "self")
    st.subheader(TITLES.get(page, TITLES["self"]))
    _back()
    if page == "friend":
        _friend()
    elif page == "before":
        _before()
    elif page == "after":
        _after()
    elif page == "teacher":
        _teacher()
    elif page == "leave":
        _leave()
    elif page == "accompany":
        _accompany()
    else:
        _self()
