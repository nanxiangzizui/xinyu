"""examples.py — 按情境挑示例（P23 ①），以及建卡期的示例对话生成（P23 ②）。

为什么单开一个文件：roles / style / agent 都已顶到 350 行硬上限，12 个情境 × 5 人设
塞进任何一个都会超；§5.6「不再加文件」在这里记一次例外，理由就是行数，不是想拆。

示例只示范「这一轮怎么开口」；分寸仍由 RULES 与 style 的规则管：
不诊断、不给命令、不劝人振作、不用「你可以试试 / 建议你」这类词。
"""
from __future__ import annotations

import json

import rolecard

# 每人设一句，长度都在 40 字以内：示例只定形状，不替规则做判断。
# cues 是「这一轮对方在说什么」的关键词，顺序即优先级：具体情境在前，最泛的「累」在最后。
SITUATIONS: dict[str, dict] = {
    "body": {
        "user": "眼睛很酸，坐了一整天",
        "cues": ("眼睛", "肩", "腰", "胃", "头疼", "坐了一天"),
        "replies": {
            "sister_heart": "坐了一整天，眼睛都酸了。",
            "warm_senpai": "一整天没动，眼睛先抗议了。",
            "rational_mentor": "坐了一天，眼睛酸。中间起来过几次？",
            "energy_buddy": "坐一天下来眼睛酸，身体在提醒你了。",
            "quiet_hollow": "嗯。坐太久了。",
        },
    },
    "insomnia": {
        "user": "躺了一个小时了，还是睡不着",
        "cues": ("睡不着", "失眠", "躺了", "没睡"),
        "replies": {
            "sister_heart": "躺了一个小时，脑子还转着吧。",
            "warm_senpai": "一个小时了还没睡，越想睡越清醒。",
            "rational_mentor": "躺了一小时还没睡。这个点最难熬。",
            "energy_buddy": "躺了一个小时还醒着，脑子肯定在开会。",
            "quiet_hollow": "嗯。躺着也难熬。",
        },
    },
    "conflict": {
        "user": "今天被人当众说了几句，心里堵",
        "cues": ("当众", "被人说", "吵", "误会", "针对"),
        "replies": {
            "sister_heart": "当着那么多人被说，堵得慌吧。",
            "warm_senpai": "当众被说，那口气到现在还堵着。",
            "rational_mentor": "当着人说的。堵的是那几句，还是当着人？",
            "energy_buddy": "当众来这么几句，换谁都得堵。",
            "quiet_hollow": "嗯。堵得厉害。",
        },
    },
    "study": {
        "user": "下周要考试，书还没怎么看",
        "cues": ("考试", "期末", "复习", "论文", "作业"),
        "replies": {
            "sister_heart": "下周就考，书还翻得不多，心里发紧吧。",
            "warm_senpai": "下周考，书才翻了几页，时间不够用的感觉。",
            "rational_mentor": "下周考，还没看。现在能坐下来的是哪几天？",
            "energy_buddy": "下周就考了，这周得熬一熬。",
            "quiet_hollow": "嗯。还来得及看一点。",
        },
    },
    "family": {
        "user": "我妈又打电话来了，问我什么时候回家",
        "cues": ("我妈", "我爸", "家里", "父母", "又问"),
        "replies": {
            "sister_heart": "又问什么时候回吧。问一次，心里沉一下。",
            "warm_senpai": "又来问什么时候回了。每次问完都不好受。",
            "rational_mentor": "又问了一次。你还没想好怎么回。",
            "energy_buddy": "又问了，这事儿问一次烦一次。",
            "quiet_hollow": "嗯。问完不好受。",
        },
    },
    "breakup": {
        "user": "分手三个月了，还是会想起",
        "cues": ("分手", "前任", "失恋", "还是会想起"),
        "replies": {
            "sister_heart": "三个月了还会想起。不是没放下，是还没淡。",
            "warm_senpai": "三个月了，还是会想起来。这事急不来。",
            "rational_mentor": "三个月，还会想起。想起的时候多在做什么？",
            "energy_buddy": "三个月还会想起来，这太正常了。",
            "quiet_hollow": "嗯。想起来就会停一会儿。",
        },
    },
    "selfblame": {
        "user": "我觉得什么都做不好",
        "cues": ("做不好", "真没用", "我很笨", "失败", "干什么都不行"),
        "replies": {
            "sister_heart": "什么都做不好的时候，人是真的会这么想。",
            "warm_senpai": "最近什么都不顺，就容易这么看自己。",
            "rational_mentor": "「什么都做不好」这个结论下得快了。先说最近的一件。",
            "energy_buddy": "这话对自己太狠了。",
            "quiet_hollow": "嗯。这几天都不顺。",
        },
    },
    "flat": {
        "user": "做什么都提不起劲",
        "cues": ("提不起劲", "没意思", "没意义", "麻木", "空的"),
        "replies": {
            "sister_heart": "提不起劲，连想玩的都不想碰吧。",
            "warm_senpai": "什么都提不起劲，那天是灰的。",
            "rational_mentor": "提不起劲。是一直这样，还是这几天？",
            "energy_buddy": "什么都没劲，这种时候谁都会有。",
            "quiet_hollow": "嗯。那就先不做什么。",
        },
    },
    "anxious": {
        "user": "心里一直慌，静不下来",
        "cues": ("心慌", "很慌", "慌得", "发慌", "紧张", "静不下", "心跳"),
        "replies": {
            "sister_heart": "一直慌着，静不下来，坐着也难受吧。",
            "warm_senpai": "心一直慌，坐也坐不住。",
            "rational_mentor": "慌是一直在，还是一阵一阵？",
            "energy_buddy": "慌到静不下来，脑子停不了吧。",
            "quiet_hollow": "嗯。慌着。",
        },
    },
    "escapism": {
        "user": "想找个地方躲起来，谁也别找我",
        "cues": ("躲起来", "想消失", "逃走", "不想见人"),
        "replies": {
            "sister_heart": "想躲起来，谁也别找。这个念头我记下了。",
            "warm_senpai": "想躲一躲，不想被人找到。",
            "rational_mentor": "想躲起来。想躲开的是人，还是那件事？",
            "energy_buddy": "想躲一躲，这不丢人。",
            "quiet_hollow": "嗯。想躲就躲会儿。",
        },
    },
    "goodnews": {
        "user": "今天有件小事挺开心的",
        "cues": ("开心", "好事", "考过了", "拿到了", "通过了"),
        "replies": {
            "sister_heart": "有件小事让你开心，说来听听。",
            "warm_senpai": "哦？什么小事，说来我听听。",
            "rational_mentor": "说来看看，是什么事。",
            "energy_buddy": "快说快说，什么好事！",
            "quiet_hollow": "嗯，说说。",
        },
    },
    "tired": {
        "user": "今天有点累，什么都不想干",
        "cues": ("好累", "很累", "太累", "累了", "累到", "累死", "疲惫", "心累",
                 "没劲", "不想动", "不想干", "撑不住"),
        "replies": {
            "sister_heart": "累到什么都不想干了吧。那就先什么都别干。",
            "warm_senpai": "今天是真的被榨干了。先坐下，别急着安排。",
            "rational_mentor": "累到不想动。是哪件事最耗你？",
            "energy_buddy": "累成这样还撑着，先躺十分钟，我守着。",
            "quiet_hollow": "嗯。累了就歇着。",
        },
    },
}


def tag_of(text: str) -> str:
    """按关键词给这一轮贴情境标签；命中不了返回空串（不猜）。"""
    body = text or ""
    for tag, item in SITUATIONS.items():
        for cue in item["cues"]:
            if cue in body:
                return tag
    return ""


def situational(persona: str, tag: str) -> str:
    """把「这个情境下这一轮怎么开口」拼成一小段 prompt；没有就返回空串。

    只给「对方上一句 + 该做什么」，不给角色的回话：一旦给出成品句，模型会照抄
    （真 key 实测 4/5 逐字相同，比不给更糟；见 docs/evidence/P23b-examples-2026-11-20.md）。
    """
    item = SITUATIONS.get(tag or "")
    if not item or persona not in item["replies"]:
        return ""
    return (f"[同类情境]\n对方上一句：{item['user']}\n"
            "（先接住这一句里的那个词，再落一件具体的小事；不问为什么，也不劝。）")


# ---- ② 建卡期示例对话：让模型按卡上的身份与口吻先写 6 组，用户挑两组 ----

MAX_CANDIDATES = 6
CARD_SCENES = ("第一次见面打招呼", "对方说今天很累", "对方只回了一个「嗯」",
               "对方分享了开心的事", "对方问你是不是真人", "对方道谢要走")

CARD_BANNED = ("建议你", "你可以试试", "试试看", "应该", "必须",
               "你得了", "抑郁", "焦虑症", "自杀", "轻生")

CARD_SYS = (
    "你在帮人写角色卡里的示例对话。示例只示范这个角色的口吻与句长，不出戏、不解释。\n"
    "只输出一个 JSON 数组，不要任何说明：[{\"user\": \"...\", \"role\": \"...\"}]\n"
    f"user 是对方说的话（{rolecard.EXAMPLE_USER_MAX} 字以内），"
    f"role 是角色回的话（{rolecard.EXAMPLE_ROLE_MAX} 字以内）。\n"
    "不写建议、不诊断、不评价对错，不用「建议你 / 你可以试试 / 应该」；"
    "不复制禁忌句；不写真实人名、地名、学校名。"
)


def _brief(card: dict) -> str:
    """把卡上跟「怎么开口」有关的字段压成一段说明。"""
    rows = [
        ("名称", card.get("name")), ("身份", card.get("identity")),
        ("世界设定", card.get("setting")), ("口吻", card.get("voice")),
        ("称呼对方", card.get("address")), ("对方是谁", card.get("user_role")),
        ("禁忌", "；".join(card.get("taboos") or [])),
    ]
    body = "\n".join(f"{label}：{value}" for label, value in rows if value)
    scenes = "；".join(CARD_SCENES)
    return f"{body}\n\n按这些情境各写一组，共 {MAX_CANDIDATES} 组：{scenes}。"


def _clean_pair(row: dict, taboos: tuple[str, ...]) -> tuple[str, str] | None:
    """一条候选要同时过：非空、长度、建议/诊断词、禁忌句。"""
    user_text = str(row.get("user") or "").strip()
    role_text = str(row.get("role") or "").strip()
    if not user_text or not role_text:
        return None
    if len(user_text) > rolecard.EXAMPLE_USER_MAX or len(role_text) > rolecard.EXAMPLE_ROLE_MAX:
        return None
    joined = user_text + role_text
    if any(word in joined for word in CARD_BANNED):
        return None
    if any(taboo in role_text for taboo in taboos if taboo):
        return None
    return user_text, role_text


def _parse(text: str, card: dict) -> list[tuple[str, str]]:
    """从模型输出里抠出数组；解析失败返回空列表（UI 只提示，不报错）。"""
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        rows = json.loads(text[start:end + 1])
    except (ValueError, TypeError):
        return []
    taboos = tuple(str(t).strip() for t in (card.get("taboos") or []) if str(t).strip())
    pairs, seen = [], set()
    for row in rows if isinstance(rows, list) else []:
        pair = _clean_pair(row, taboos) if isinstance(row, dict) else None
        if pair and pair[0] not in seen:
            seen.add(pair[0])
            pairs.append(pair)
    return pairs


def card_candidates(card: dict, n: int = MAX_CANDIDATES) -> list[tuple[str, str]]:
    """按卡上的身份与口吻生成候选对话；离线 / 失败 / 解析失败一律返回 []。"""
    # 局部 import：agent 顶层 import examples，模块级 import 会成环。
    import agent

    if not (card.get("identity") or card.get("setting")):
        return []
    resp = agent.call_llm(
        [{"role": "system", "content": CARD_SYS},
         {"role": "user", "content": _brief(card)}],
        temperature=0.4,
    )
    if not resp.get("ok"):
        return []
    return _parse(str(resp.get("text") or ""), card)[:n]

