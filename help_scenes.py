"""help_scenes.py — P40 四张静态页：危机之后 / 睡不着 / 被挂网暴 / 考砸。

[SAFE] 纯文案 + 静态路由；不调 agent / guardian / orchestrator，不判级、
不写记忆、不联网。号码只从 resources 取，页面不拼新号。
四页同一结构：先接住 → 可照抄的话 → 硬线 → 不该做 → 资源。
为什么不并进 help_pages.py：那里 332 行，再加四页会顶破 350 行硬顶。
"""
from __future__ import annotations

import streamlit as st

from resources import CAMPUS_PHONE
from ui_common import copy_block, resource_lines

# ---------- ① 危机之后：那一晚，和等咨询的这两周 ----------
AFTERMATH_TONIGHT = (
    "让一个人来陪你——室友、朋友、家里人都行，不用解释太多。",
    "宿舍里让你不放心的东西，先交给别人收着。",
    "手机充上电，水放在手边，定一个明早的闹钟。",
)
AFTERMATH_SAY = (
    ("跟室友说", "我昨天状态很差，现在好一点了。你不用做什么，陪着我就行。"),
    ("请假", "我想请半天假，回头把落下的补上。"),
    ("约咨询", "我想约一次咨询；第一次去，需要准备什么吗？"),
)
AFTERMATH_DONT = (
    "别一个人硬扛到「想清楚了再说」。",
    "别把这次当成「我完了」的证据——它是这一晚的事，不是结论。",
    "退学、分手、删号、搬家这类决定，先放 72 小时。",
)
AFTERMATH_LINE = (
    "那个念头又回来了，或者一个人待不下去。",
    "连续两周睡不着、吃不下，白天撑不住。",
    "又开始做「交代」的事：送东西、清空东西、把话说完。",
)

# ---------- ② 躺下睡不着 ----------
SLEEP_STEPS = (
    "躺下 20 分钟还醒着，就起来：到别的地方坐一会儿，灯调暗。",
    "做一件无聊的事：叠衣服、听单调的声音、翻一本看不进去的书。",
    "困了再回床上；又睡不着就再起来，不用跟自己较劲。",
)
SLEEP_DONT = (
    "别看钟、别算「我还能睡几个小时」——越算越清醒。",
    "别在床上刷手机、写作业、开会：床只用来睡。",
    "别用酒助眠，也别自己加药。",
)
SLEEP_DAY = (
    "固定起床时间，哪怕昨晚只睡了三小时。",
    "白天补觉不超过 20 分钟；下午三点后不碰咖啡、茶、功能饮料。",
    "把明天要做的事写在纸上——写下来就不用一直记着。",
)
SLEEP_LINE = "连续两周以上睡不着，白天明显受影响（上课听不进去、骑车开车犯困）。"

# ---------- ③ 被挂 / 网暴 / 隐私被传 ----------
ONLINE_KEEP = (
    "截图要带时间、群名、发帖人的主页；链接也复制出来。",
    "别只截一句话——前后几条一起截，才有上下文。",
    "原始聊天记录先别删。",
)
ONLINE_DONT = (
    "不要对骂：对骂会把你也变成事件的一部分。",
    "不要删号跑路：会丢证据，也会让对方觉得你怕了。",
    "不要私下去见对方；也不要相信「帮你删帖」的私信和付费服务。",
)
ONLINE_SAY = (
    ("跟辅导员说",
     "老师，有人在群里发我的照片 / 挂我。我保存了截图，想问问学校这边能怎么处理。"),
    ("跟一个朋友说", "我不太想一个人待着，今晚能不能陪我一会儿。"),
)
ONLINE_LINE = (
    "威胁人身安全、说要来找你。",
    "传播隐私照片或视频。",
    "跟踪、蹲守、上门。",
)
ONLINE_AFTER = (
    "退出那个群，关掉陌生人私信。",
    "找一个人陪着，别一个人反复刷。",
    "这几天不用逼自己「正常」：能上课就上，上不了就请假。",
)
ONLINE_WITNESS = (
    "不转发、不二次传播；不下载、不保存隐私照片。",
    "私信当事人：「我看到了，你还好吗？需要我帮你存证或告诉老师吗？」",
    "帮存证：截图带时间、群名、链接；只交给当事人或学校，不公开发。",
    "对方有危险：打 110 / 120；只是网暴：平台举报 + 找辅导员。",
    "别对骂、别人肉、别把「帮忙」变成二次曝光。",
)

# ---------- ④ 考砸了 / 出分那天 ----------
EXAM_48H = (
    "退学、删好友、通宵重来、跟家里摊牌——今晚都不做。",
    "难受是真的，但今晚的判断不一定准：先睡一觉再说。",
)
EXAM_TONIGHT = ("吃一口东西。", "洗个澡。", "告诉一个人：「我考砸了，难受。」")
EXAM_ASK = (
    ("能不能补考 / 重修", "问教务办或辅导员，问清楚截止时间。"),
    ("要不要跟家里说", "由你决定；什么时候说，也由你决定。"),
    ("这次是「没复习」还是「一直这样」", "后者才需要找人聊；前者是方法问题。"),
)
EXAM_SAY = (
    ("跟辅导员", "老师，我这次 XX 没过，想问问补考或者重修怎么安排。"),
    ("跟家里",
     "我这次没考好。我知道你们会失望，我想先自己处理一下，需要的时候我会说。"),
)
EXAM_FAIL = (
    ("先分清", "一门挂科：先问补考 / 重修；多门挂科或收到退学警告："
                "找教务办 / 辅导员问学籍。"),
    ("问三件", "补考什么时候；重修怎么算；对毕业和学位有什么影响。"),
    ("可以照抄", "老师，我收到了学业预警 / 退学警告，想问问现在有哪些选择，"
                  "最晚什么时候办。"),
    ("别做", "别拖过截止日；别信「花钱消记录」；别一个人猜政策。"),
    ("如果撑不住", "冒出「没脸见人」「不如不活了」：打 12356，"
                    "或回首页点「我现在很难受」。"),
)

# ---------- ⑤ 朋友页补充：还没到出事，但最近不太对 ----------
# [SAFE] 只教「怎么问、别做什么、什么时候升级」；不评估、不诊断、不替人判断。
FRIEND_EARLY = (
    ("值得问一句的信号",
     "突然不来上课、推掉所有约、说话变少；或者反过来，突然特别亢奋、话说个不停。"
     "把东西送人、开始交代事情；提到「没什么意思」「不想麻烦别人」。"),
    ("怎么问",
     "单独找他，别绕弯：「你最近是不是不太好？」比「你要不要去看看心理医生」"
     "更容易被接住。问完先别给建议，先说一句「我在」。"),
    ("别做的",
     "别答应「我谁都不告诉」——真出事时这句话会把你一个人架在那儿；"
     "别一次叫一群人围着他；别说「想开点」「比你惨的人多了」。"),
    ("什么时候升级",
     "出现自伤或伤人的话、开始交代后事、突然异常平静：打 120 / 110，"
     "或者立刻叫辅导员、宿管、家人到场——别一个人扛。"),
)

# [SAFE] 他不肯去：只教怎么问、怎么陪、边界在哪；不诊断、不替人做决定。
FRIEND_REFUSE = (
    ("先问一句", "你不想去，是怕什么？怕被记录、怕被当成有病、怕花钱，还是怕家里知道？"),
    ("可以照抄", "我陪你去，到了你不用说什么，我帮你问流程。"),
    ("再退一步", "不想去咨询也行，那我们今晚先找个地方坐一会儿。"),
    ("边界", "我不逼你；但如果你有危险，我会去找能帮上忙的人。"),
)
FRIEND_ONLINE = (
    ("先私信一句", "我在，你还好吗？不用马上回，看到回我一下。"),
    ("如果是公开动态", "别在评论区问细节；私信他，或者找平台客服。"),
    ("立刻打 110 / 120", "说清楚时间、地点、方式；正在直播；已经吃药或受伤。"),
    ("别做", "别围观、别截图转发、别说「你敢不敢」；别把截图发到群里。"),
    ("你自己", "别一个人扛：找一个能负责的大人，或者打 12356 问怎么处理。"),
)


def friend_extras() -> None:
    """朋友页的两个补充折叠面板：他不肯去 / 网上旁观者。"""
    st.divider()
    with st.expander("他不肯去，我怎么劝"):
        for head, body in FRIEND_REFUSE:
            st.markdown(f"**{head}**")
            st.markdown(body)
    with st.expander("网上看到有人想不开，我是旁观者"):
        for head, body in FRIEND_ONLINE:
            st.markdown(f"**{head}**")
            st.markdown(body)


def aftermath() -> None:
    """先过今晚，再讲过几天；不描述方法，只给能照做的一步。"""
    st.caption("今晚不用解决所有事，先让自己安全地过完这一晚。")
    st.markdown("### 1. 今晚")
    for line in AFTERMATH_TONIGHT:
        st.markdown(f"- {line}")
    st.markdown("### 2. 明天可以照说的三句")
    for label, text in AFTERMATH_SAY:
        copy_block(label, text)
    st.markdown("### 3. 这 72 小时先不做的事")
    for line in AFTERMATH_DONT:
        st.markdown(f"- {line}")
    st.markdown("### 4. 等咨询的这两周")
    st.markdown(f"- 校心理中心 {CAMPUS_PHONE}（工作日）；拿不准就先打电话问流程。")
    st.markdown("- 第一次去带三行字：这周最难受的时候 / 睡了几个小时 /"
                " 有没有想过伤害自己。")
    st.error("出现下面任何一条，别等预约：\n\n"
             + "\n\n".join(f"- {line}" for line in AFTERMATH_LINE)
             + "\n\n- 打 12356，或者去校医院 / 急诊（120）。")
    resource_lines()


def sleep() -> None:
    """睡不着：给可执行的动作，不给「放松点」这种话。"""
    st.caption("今晚的目标不是「必须睡着」，是「别在床上跟自己较劲」。")
    st.markdown("### 1. 躺下 20 分钟还醒着")
    for line in SLEEP_STEPS:
        st.markdown(f"- {line}")
    st.markdown("### 2. 这三件别做")
    for line in SLEEP_DONT:
        st.markdown(f"- {line}")
    st.markdown("### 3. 白天怎么调")
    for line in SLEEP_DAY:
        st.markdown(f"- {line}")
    # 只放「出现这一条」的条件；「别自己加药 / 别用酒助眠」已在第 2 节，
    # 塞进红框会让人以为那句也是就医条件。
    st.error(f"出现下面这一条，别再硬扛，去校心理中心 {CAMPUS_PHONE} 或医院睡眠门诊：\n\n"
             f"- {SLEEP_LINE}")
    resource_lines()


def online() -> None:
    """网暴：先存证，再决定；不承诺处理结果，也不替人判断。"""
    st.caption("先把证据留住，再决定怎么处理；不用今晚就想清楚。")
    st.markdown("### 1. 先保存")
    for line in ONLINE_KEEP:
        st.markdown(f"- {line}")
    st.markdown("### 2. 别做这三件")
    for line in ONLINE_DONT:
        st.markdown(f"- {line}")
    st.markdown("### 3. 可以找谁、怎么说")
    for label, text in ONLINE_SAY:
        copy_block(label, text)
    st.markdown("### 4. 平台内举报")
    st.markdown("- 走 App 或网站里的「举报」，选「人身攻击 / 泄露隐私」，"
                "把截图一起提交。")
    st.error("出现下面任何一条，直接打 110：\n\n"
             + "\n\n".join(f"- {line}" for line in ONLINE_LINE)
             + "\n\n- 受伤、吃药过量：打 120。")
    st.markdown("### 5. 如果你是旁观者")
    for line in ONLINE_WITNESS:
        st.markdown(f"- {line}")
    st.markdown("### 6. 这几天怎么过")
    for line in ONLINE_AFTER:
        st.markdown(f"- {line}")
    st.caption("以平台规则和学校规定为准。这里不替你判断，也不承诺处理结果。")
    resource_lines()


def exam() -> None:
    """考砸：先拖住不可逆的决定，再给明天能问的三个问题。"""
    st.caption("今晚先不做决定。难受是真的，但今晚的判断不一定准。")
    st.markdown("### 1. 这 48 小时")
    for line in EXAM_48H:
        st.markdown(f"- {line}")
    st.markdown("### 2. 今晚只做三件事")
    for line in EXAM_TONIGHT:
        st.markdown(f"- {line}")
    st.markdown("### 3. 明天再看这三个问题")
    for head, body in EXAM_ASK:
        st.markdown(f"- **{head}**：{body}")
    st.markdown("### 4. 可以照抄的话")
    for label, text in EXAM_SAY:
        copy_block(label, text)
    st.markdown("### 5. 如果收到挂科 / 退学警告")
    for head, body in EXAM_FAIL:
        st.markdown(f"- **{head}**：{body}")
    st.error("如果冒出「没脸见人」「不如不活了」「对不起所有人」这类念头："
             "回首页点「我现在很难受」，或者打 12356。")
    resource_lines()


# help_pages.render 按这张表分派；键与 TITLES 保持一致。
RENDERERS = {
    "aftermath": aftermath,
    "sleep": sleep,
    "online": online,
    "exam": exam,
}
