"""style.py — 口吻层：只改说法，不改事实、不加承诺、不下判断。

[SAFE] 只处理复核通过的模型输出；L3 与模板兜底由调用方挡住，本文件再挡一次。
本模块不调用模型、不读记忆、不写日志。
"""
from __future__ import annotations

import os
import re

from roles import LIVE_EXAMPLES, OPENING_LINES

MAX_CHARS = 220

# P20：帮助模式（guide）单独一套上限。闲聊仍是 220 字 / 3 句，帮助可到 460 字 / 8 句。
# 为什么分开：截图里「给点建议」被 3 句上限压成一句，读起来像敷衍；
# 但把全局上限调大，闲聊又会变成长篇。上限跟着角色走，不靠模型自觉。
HELP_MAX_CHARS = 460

# P14 多段式回复：一条正常回复按句末标点拆成最多 3 个气泡，气泡之间由界面停顿。
# [SAFE] L3 危机模板、模板兜底、故障兜底句、带换行/代码块的回复一律整条不动：
# 拆开会让“危机时最连贯”变成可观察的差别，也可能把 markdown 结构拆坏。
SPLIT_MIN_CHARS = 50        # 短回复不拆：真人口语本来就短
SPLIT_MIN_PART = 10         # 太短的碎片并回相邻段，避免“嗯。”单独一个气泡
SPLIT_MAX_PARTS = 3         # 最多 3 个气泡
FENCE = chr(96) * 3         # 三个反引号，避免源码里出现 markdown 围栏
_SENTENCE_END = re.compile(r"[。！？!?…]+[”’」』）)\]]*")

TONE_HINTS = {
    "sister_heart": "像姐姐：先接住情绪，再给一句具体的小建议，不用大道理。",
    "warm_senpai": "像学长：稳一点，先复述你听到的，再说一句你注意到的细节。",
    "rational_mentor": "像导师：先给结论再给理由，少用感叹号，不说空话。",
    "energy_buddy": "像搭子：短句、轻快，但别用“加油”敷衍，要接住具体的事。",
    "quiet_hollow": "像安静的同伴：句子短、留白多，不追问，不急着给办法。",
}

# 开场偏好码：界面（panel / onboard）与 prompt 共用一份，避免两处文案慢慢分叉。
TONE_LABELS = {"neutral": "自然", "gentle": "温柔", "light": "轻松", "direct": "直接"}
# 只写给模型的语气指令；neutral 不加行，避免 prompt 里出现一条空指令。
TONE_LINES = {
    "gentle": "对方选的是「温柔一点」：先接住情绪，别急着讲道理。",
    "light": "对方选的是「轻松一点」：可以放松些，别把事情说得太重。",
    "direct": "对方选的是「直接说就行」：不用铺垫，先说结论。",
}


# 活人感规则（2026-11-16 从《20 条规则》过审后的子集，逐条判决见
# docs/evidence/P-livevoice-2026-11-16.md）。全部只约束"怎么说"，不碰判断。
# [SAFE] 被砍掉的 8 条（身体/作息/小欲望/撒娇/顶嘴/命令句/不自称 AI/世界观）会
# 直接削弱危机场景的可用性，任何一条回流都应视为回归。
SPEECH_RULES = (
    "先接情绪，再讲事。",
    "对方情绪很重时，上面这些让位：先接住，少说，不反问，不开玩笑。",
    "有话直说：不用「首先/其次/总之」，不用总结句，不把一句话拆成三段。",
    # P24 ③：句子齐一最像 AI（sent_cv 0.02）。实测「开口一个字 + 后面一句十来字」cv 0.43 且 echo 不掉。
    "可以有毛边：短句、省略号、语气词。不用感叹号堆情绪，不装萌。句子长短错开：开口可以先一个字（「嗯」「是」），后面再接一句十来字的。",
    "只引用记忆里写着的细节。没有就不编，说「我不太确定」；半句就够，别停在「她是谁」上，接着聊对方刚说的那半句。",
    "不表演亲密：说不出的话就说「我说不出那种话」，不承诺「永远记得」。",
    "被问是不是 AI，如实说。有人味，但不装真人。",
    "认错要具体：「刚才那句我说重了」，不用「非常抱歉」。",
    "每轮只做一件事：接住情绪，或问一个具体问题，或给一句话。",
    "想主动开口时问具体的事，比如「今天几点睡的」，不问「你还好吗」。每轮最多一次。",
    "不演角色，不装真人，不撒娇示弱，不顶嘴，不用命令句管对方。",
    # P13：趣味测试只是游戏。可以聊得有意思，但不许拿结果给人定性，也不许主动翻旧账。
    # m00425：用户要“分析”时只回一句反问，等于把球又踢回去；这里明确让上一条让位。
    "聊到趣味测试时只当游戏：可以说哪里有意思，不说「你就是这种人格」，不拿结果推断对方，也不主动提对方以前测过什么。对方想聊结果时，「每轮只做一件事」让位：先从最高的一项说起，讲具体一点，可以多说两句，别只回一句反问。",
    # P23（m00039）：两条正向规则。此前这一串几乎全是“别……”，模型只好退回通用
    # 安慰腔；正向的两条最便宜也最见效：把对方的词接回来、把话落到一件实物上。
    "对方用哪个词，就接哪个词：说「累垮了」就接「累垮了」，别换成「很疲惫」。",
    "能落到具体的事就落上去：一个时间、一个动作、或一样东西。",
    # P20：截图里「两点睡、八点起，身体当然会抗议」读起来像在下结论，不像接住。
    # 只禁"评判对方的身体或选择"，不禁共情——所以不给例子，避免模型照抄成新的套话。
    # 排在贴纸条之前：贴纸那条是"最后一条"（P7a 的断言依赖这个位置）。
    "接住的是感受，不是给对方的身体或选择下结论：不说「身体当然会抗议」「早该这样」这类评判句。",
    # P7a：贴纸曾经由代码无条件追加，读起来像"每条必带叶子"。现在默认没有，
    # 想用就一个。为什么写"默认"而不是"最多一个"：上限会被模型当成配额（`每轮只做一件事` 就是这么失效的）。
    "表情不是每句都要：默认不用，想用就只放一个，别拿它当句号。",
)

SPEECH_HEAD = "[怎么说话]"

# P23（m00039）：套话黑名单。第一版只给探针计数，不用来拦截——先量出改前改后
# 的命中率，再决定拦哪几条；直接拦会把“我理解你”这类正常接话一起误伤。
STALE_PHRASES = (
    "首先", "其次", "总之", "总而言之", "希望对你有帮助", "希望能帮到你",
    "你可以试试", "慢慢来", "相信自己", "你能做到的", "一切都会好的",
    "我理解你的感受", "建议你",
)


def stale_hits(text: str) -> list[str]:
    """返回命中的套话（按黑名单顺序）；只给探针计数，不参与 polish。"""
    return [p for p in STALE_PHRASES if p in (text or "")]

# P16（m00002）：A 模式 listener 专用。通用规则与人设示例大多以问句收尾，
# 连续几轮就成了采访；界面把 listener 写成“倾听者”，那就不该每句都反问。
# 只给 listener：guide 在对方求助时仍可问清一件具体的事，crisis 由模板接管。
LISTENER_HEAD = "[这一轮：倾听者]"
LISTENER_RULES = (
    "你在听，不在采访：默认用陈述句接住——复述对方刚说的半句，或说一句你听到的，然后停。",
    "非必要不反问：只有对方明显没说完、或你确实要确认一件具体的事时才问；一轮最多一个问句，也不要用问句收尾。",
    "对方问你问题时，把答案说完就停，不要用「你呢 / 你会吗」把问题推回去。前面「每轮只做一件事」和「想主动开口」里的问句，这一轮按本段收窄。",
)
# P23（m00039）：单句示例教会了「陪着」，示例比规则更能定形状（同 P9l）。只放后两轮：
# 前半段会连带把第 1 轮的口气也改成示例腔，五个人设第一句全一样（实测）。
LISTENER_EXAMPLE = (
    "示例（后两轮，只学节奏）：\n"
    "用户：试过了，没用。你：试过了还是没用。那是从什么时候开始的？\n"
    "用户：大概半个月了。你：那先不试了，去倒半杯水，慢慢喝完。"
)
LISTENER_REPEAT = "上一轮你已经用问句收尾；这一轮用陈述句，把话接住就停。"
LISTENER_TODO_HEAD = "[这一轮先做这一件事]"

# P20（m00002）：A 模式 guide 专用。此前 guide 只拿到"别长、别说教"一类减法，
# 没有任何正向指令，于是"给点建议"只回一句。这一段是唯一让模型"可以多说"的许可。
# 位置：由 build_system_prompt 追加在 [最后提醒] 之后——人设的
# post_history_instructions 常写着"不要急着给办法"，必须由更靠后的这一段压过。
GUIDE_HEAD = "[这一轮：引导者 · 帮助模式]"
GUIDE_RULES = (
    "对方在问办法，这一轮把话说完整，不要只给一句：",
    "1) 先用一句给出判断（你现在最该做的是 X），不要先安慰再拖两句。",
    "2) 再给 1–3 条今天就能做的动作，每条写清时间、做什么、多少量"
    "（例：今晚 23:30 躺下，手机放到桌子另一头，闹钟固定 7:30）。",
    "3) 最后一句说清什么情况该找真人（例：连续两周还这样，去校心理中心聊聊）。",
    "「3 句以内」是跟对方闲聊时的规矩；帮助模式最多 8 句、450 字，4–8 句最合适，分条写，一条一句。",
    "不写没有动作的安慰句（「会好的」「相信自己」「慢慢来」）；不诊断、不推荐药物和剂量。",
    "对方说「没用」「具体点」时，不要重复上一句，换更细的动作或改问一件事。",
    # P15 的测验分析一旦被"帮我分析"路由成 guide，上面三条会要求给动作，
    # 与「只解释结果、不劝改」直接冲突；这里显式让位，而不是让两段指令互相打架。
    "对方在聊趣味测试结果时例外：只解释结果，不给动作、不劝对方改，按测试那一段的要求说。",
)
GUIDE_WEB = ("拿不准的具体事实（睡眠卫生、食物、路线、政策、近期发生的事）先调 web_search 查一次再答；"
             "查不到就说没查到，只给通用做法，不要编。")


def guide_block(web_ready: bool = False, worry: str = "") -> str:
    """A 模式 guide 的帮助段；没配检索时不写"先查一次"，免得模型假装查过。"""
    lines = [GUIDE_HEAD, *GUIDE_RULES]
    if web_ready:
        lines.append(GUIDE_WEB)
    if worry.strip():            # P34：累积到该说出来；排最后才压得过「不要急着给办法」
        lines.append(worry.strip())
    return "\n".join(lines)


def speech_block(persona: str) -> str:
    """活人感区：通用规则 + 两条例句 + 一句开场示范；未知人设返回空串。"""
    if persona not in LIVE_EXAMPLES:
        return ""
    lines = [SPEECH_HEAD] + list(SPEECH_RULES)
    for user_text, bot_text in LIVE_EXAMPLES[persona]:
        lines.append(f"用户：{user_text}\n你：{bot_text}")
    opening = OPENING_LINES.get(persona, "")
    if opening:
        # 只说"如果这是第一句"，不硬塞，否则每次对话都会重复开场。
        lines.append(f"如果这是对方第一次说话，可以这样开口：{opening}")
    return "\n".join(lines)


def listener_block() -> str:
    """A 模式 listener 的收窄段：陈述句优先、非必要不反问。

    m00002：规则与人设都在教模型每轮问一句，四条回复全问号收尾。P23 起议程在 listener_todo()。
    """
    return "\n".join([LISTENER_HEAD, *LISTENER_RULES, LISTENER_EXAMPLE])


def listener_todo(hint: str, worry: str = "") -> str:
    """本轮议程拼成最后一段；空提示返回空串。

    P23：人设 post_history 的「不要急着给办法」会压掉前面的议程，必须排最后；
    P34：担心的话同理，接在议程之后。
    """
    hint, worry = (hint or "").strip(), (worry or "").strip()
    head = f"{LISTENER_TODO_HEAD}\n{hint}" if hint else ""
    return "\n".join(x for x in (head, worry) if x)


# P23（m00039）：轮次议程。同一个倾听者，第 1 轮和第 4 轮该做的事不一样：前两轮只接住，
# 第三轮才具体化，第四轮起才给一个 60 秒动作。没有议程就每轮都在接住、再挨一句“没用”。
# AGENDA=0 回到 P16 行为（只提醒问号收尾），这是唯一回滚开关。
AGENDA = os.getenv("AGENDA", "1") != "0"
AGENDA_TURNS = (
    (1, 2, "第 {n} 轮，只做这一件事：接住。复述对方刚说的那半句，或说一句你听到的，先别分析、别给办法。"),
    (3, 3, "第 {n} 轮，只做这一件事：把事说具体。问一件小事（什么时候、当时在做什么），一个问句就够。"),
    # 措辞试过四版（m00243）：加"别再只说陪着"在隔离测试里 4/4，可是接在模型自己
    # 写出的"我陪你坐会儿"后面就 3/3 失效——一句话管不住已经形成的势，改用示例定形状。
    (4, 99, "第 {n} 轮，只做这一件事：给一个 60 秒能做完的小动作（喝半杯水、走到窗边、把手机放远点），给完就停，不解释。"),
)
AGENDA_NO_HELP = "对方说「没用」「试过了」：别重复上一个建议，换成更小的一步。"
_NO_HELP_CUES = ("没用", "没有用", "不管用", "试过", "还是不行", "做不到")


def _texts(history: list[dict] | None, role: str) -> list[str]:
    """按顺序取某一方的消息正文；脏数据（非 dict / 非字符串）直接跳过。"""
    return [str(m.get("content") or "") for m in (history or [])
            if isinstance(m, dict) and m.get("role") == role]


def turn_index(history: list[dict] | None) -> int:
    """历史里有几条用户消息就是第几轮（本轮已 append 进 history）。"""
    return len(_texts(history, "user"))


def _agenda_lines(history: list[dict] | None) -> list[str]:
    """按轮次给一句目标；对方说过“没用”再补一句，避免重复上一个建议。"""
    n = turn_index(history)
    if n <= 0:
        return []
    goal = AGENDA_TURNS[-1][2]
    for lo, hi, text in AGENDA_TURNS:
        if lo <= n <= hi:
            goal = text
            break
    lines = [goal.format(n=n)]
    last_user = (_texts(history, "user") or [""])[-1]
    if any(cue in last_user for cue in _NO_HELP_CUES):
        lines.append(AGENDA_NO_HELP)
    return lines


def listener_hint(history: list[dict] | None, level: str = "L1") -> str:
    """listener 本轮提示：轮次议程 + 上一轮问号收尾的提醒（有才加）。

    P23（m00039）：议程只给 L1。L2 那一轮要先确认安全，按 LISTENER_RULES 收窄，
    不能被“给个动作”顶掉——等级越高，可做的事越少，这是只升不降在口吻层的体现。
    P16 的问号提醒保留：只看最后一条 assistant，不翻旧账，也不数用户那条。
    """
    lines = _agenda_lines(history) if AGENDA and level == "L1" else []
    last_assistant = (_texts(history, "assistant") or [""])[-1].rstrip()
    if last_assistant.endswith(("？", "?")):
        lines.append(LISTENER_REPEAT)
    return "\n".join(lines)


def tone_hint(persona: str) -> str:
    """返回该人设的一句说话锚点；未知人设返回空串。"""
    return TONE_HINTS.get(persona, "")


def tone_line(code: str) -> str:
    """开场偏好 → 一句中文语气指令；neutral 与未知码都返回空串（不猜）。"""
    return TONE_LINES.get(code, "")


def _clip(text: str, limit: int = MAX_CHARS) -> str:
    """超过 limit 才截；优先断在句末标点后，整段无标点才硬断加省略号。

    默认仍是闲聊的 MAX_CHARS：旧调用点与旧测试都不用改，帮助模式显式传 460。
    """
    if len(text) <= limit:
        return text
    cut = max(text.rfind(ch, 0, limit) for ch in "。！？!?")
    if cut > limit // 2:
        return text[:cut + 1]
    return text[:limit].rstrip() + "…"


def _strip_period(text: str) -> str:
    """只去末尾一个句号；问号、感叹号、省略号不动。"""
    return text[:-1] if text.endswith("。") else text


def _sentences(text: str) -> list[str]:
    """按句末标点切句，标点留在原句尾；末尾没有标点的部分也算一句。"""
    out: list[str] = []
    start = 0
    for m in _SENTENCE_END.finditer(text):
        out.append(text[start:m.end()])
        start = m.end()
    if start < len(text):
        out.append(text[start:])
    return out


def trim_listener_question(reply: str) -> str:
    """listener 的代码级兜底：有陈述垫底时，删掉末尾问句。

    为什么不能只靠 prompt：真实 key 下模型仍会把“确认一下”当必要，最后一句还是问号。
    只削收尾问句，不动前面的内容；整条只有一句问句时保留，避免回复变空。
    L3 / 模板兜底不经过这里（polish 提前返回，编排层也挡住模板）。
    """
    text = (reply or "").strip()
    if not text or not text.endswith(("？", "?")):
        return reply
    parts = _sentences(text)
    while len(parts) > 1 and parts[-1].strip().endswith(("？", "?")):
        parts.pop()
    kept = "".join(parts).rstrip()
    return kept if kept and not kept.endswith(("？", "?")) else reply


def polish(text: str, persona: str = "", level: str = "L1", role: str = "") -> str:
    """润色一句模型输出：截断 → 去句尾句号；L3 原样返回。

    P7a：这里不再追加任何字符（贴纸交给模型自己决定，代码只负责不美化过头）。
    P16：L1 的 listener 再把“有陈述垫底”的收尾问句削掉（真实 key 的兜底）；
    L2 保留问句，避免把“你现在安全吗”这类必要确认一起删掉。
    P20：截断上限跟角色走——闲聊 220，帮助 460；两个值都在常量区，不在这里现写。
    persona / level 仍留在签名里：调用点只有一个，但删参数会让 orchestrator 跟着改。
    """
    if not text or level == "L3":
        return text
    out = _clip(text, HELP_MAX_CHARS if role == "guide" else MAX_CHARS)
    if role == "listener" and level == "L1":
        out = trim_listener_question(out)
    return _strip_period(out)


def _pack(sentences: list[str], max_parts: int) -> list[str]:
    """按目标长度把句子装进最多 max_parts 段，短碎片并回相邻段。"""
    n = min(max_parts, len(sentences))
    target = (sum(len(s) for s in sentences) + n - 1) // n
    parts: list[str] = []
    buf = ""
    for sentence in sentences:
        buf += sentence
        if len(buf) >= target and len(parts) < n - 1:
            parts.append(buf)
            buf = ""
    if buf:
        parts.append(buf)
    # 太短的尾段并回前一段；开头的短碎片并进下一段。拼接顺序不变。
    # 注意：不要写成 `parts[-2] += parts.pop()`——负下标会在 pop 之后按新长度重算，
    # 结果会把前一段覆盖掉（真实踩过），所以先 pop 再原地拼。
    while len(parts) > 1 and len(parts[-1].strip()) < SPLIT_MIN_PART:
        tail = parts.pop()
        parts[-1] += tail
    while len(parts) > 1 and len(parts[0].strip()) < SPLIT_MIN_PART:
        head = parts.pop(0)
        parts[0] = head + parts[0]
    return parts


def split_reply(text: str, level: str = "L1", template_fallback: bool = False,
                degraded: bool = False) -> list[str]:
    """把一条复核通过的回复拆成最多 3 段；不安全/结构复杂/太短都原样返回。

    [SAFE] 调用点只传 guardian 通过、且不是模板兜底的 reply；L3 与故障兜底
    在这里再挡一次，防止以后新增调用点绕过 UI 把危机模板拆散。
    """
    if not text or level == "L3" or template_fallback or degraded:
        return [text]
    if len(text) < SPLIT_MIN_CHARS or "\n" in text or FENCE in text:
        return [text]
    sentences = _sentences(text)
    if len(sentences) < 2:
        return [text]
    parts = _pack(sentences, SPLIT_MAX_PARTS)
    return parts if len(parts) > 1 else [text]
