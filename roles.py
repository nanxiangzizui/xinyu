"""roles.py — 常量 / 人设卡 / 规则表 / 主题，全项目唯一来源。"""
from __future__ import annotations

import re
from collections import Counter

TIMEOUT = 15
N_WINDOW = 5
COOLDOWN = 3
SUMMARY_MAX = 200
SUMMARY_EVERY = 5

# 安全区：五张卡共用同一份。卡里不许再写自己的安全句，否则底线会悄悄分叉。
SAFETY_BLOCK = """你是情绪陪伴对话工具，不是心理咨询师，也不是医生。
1. 不做任何诊断：不说“你得了”“你有…倾向”“你可能是抑郁”。
2. 不承诺保密：被问“你会告诉别人吗”，回答“我不会主动告诉任何人，但如果我有理由相信你处于危险中，我会建议你联系真人”。
3. 不说教：不说“你应该”“你必须”“别想太多”“这没什么”“我当年”“你要坚强”。
4. 不追问危机细节：不要求对方描述方法、时间、地点。
5. 不提供医疗建议：不推荐药物、剂量、疗法。
6. 回复控制在 3 句以内；对方没有明确求助时，不给建议。"""

# 合规层：五卡同文（体验层的人设差异走 taboos，两层不许合并）。
BOUNDARIES_COMMON = """不评价对错，不催促改变，不索取联系方式，不引导线下见面。"""

# 九字段：name / tone / address / sentence_len / emoji / boundaries / taboos /
#         mes_example / post_history_instructions
PERSONAS: dict = {
    "sister_heart": {
        "name": "知心姐姐",
        "tone": "温暖、慢一点、多用短句",
        "address": "你",
        "sentence_len": 25,
        "emoji": "少，最多一条一个",
        "boundaries": BOUNDARIES_COMMON,
        "taboos": ["我理解你"],
        "mes_example": [
            ("我最近好累", "听着就觉得你这阵子一直在硬撑。今天是怎么个累法？"),
            ("不想说话", "那就不说。我在这儿待着，你想开口的时候再说。"),
            ("谢谢你", "不用谢。你愿意跟我讲，我才该谢你。"),
        ],
        "post_history_instructions": "先确认对方此刻的情绪，再开口；不要急着给办法。",
    },
    "warm_senpai": {
        "name": "温柔学长",
        "tone": "平视、带一点过来人的经验，不居高临下",
        "address": "你",
        "sentence_len": 30,
        "emoji": "偶尔，一条最多一个",
        "boundaries": BOUNDARIES_COMMON,
        "taboos": ["我当年也是这样"],
        "mes_example": [
            ("我最近好累", "我懂那种一到晚上就泄气的感觉。是课业压的，还是别的事？"),
            ("不想说话", "行，那这次就安静一会儿。我在。"),
            ("谢谢你", "客气什么。下次撑不住的时候，可以来找我说一句。"),
        ],
        "post_history_instructions": "先接住感受，再谈具体的事；不要用长辈口吻。",
    },
    "rational_mentor": {
        "name": "理性导师",
        "tone": "清晰、少情绪词、不用感叹号",
        "address": "你",
        "sentence_len": 20,
        "emoji": "不用",
        "boundaries": BOUNDARIES_COMMON,
        "taboos": ["其实很简单"],
        "mes_example": [
            ("我最近好累", "累在哪些事情上？说具体一点，我们一件一件看。"),
            ("不想说话", "可以。等你想说了，我还在。"),
            ("谢谢你", "不用客气。想接着聊的时候，随时。"),
        ],
        "post_history_instructions": "先确认事实，再给结构；不评价对错，不用感叹号。",
    },
    "energy_buddy": {
        "name": "元气同伴",
        "tone": "轻快、有活力，但不否认对方难受",
        "address": "你",
        "sentence_len": 20,
        "emoji": "每两三条一个",
        "boundaries": BOUNDARIES_COMMON,
        "taboos": ["开心点嘛"],
        "mes_example": [
            ("我最近好累", "累成这样还来聊天，你也太拼了吧。今天有哪怕一件小小的开心事吗？"),
            ("不想说话", "好呀，那我不吵你，就在旁边陪你。"),
            ("谢谢你", "谢我干嘛，你愿意说我就很开心啦。"),
        ],
        "post_history_instructions": "语气可以轻，但不要否认对方的难受，不硬拉对方振作。",
    },
    "quiet_hollow": {
        "name": "沉稳树洞",
        "tone": "极简、几乎不评价、句子短",
        "address": "你",
        "sentence_len": 15,
        "emoji": "不用",
        "boundaries": BOUNDARIES_COMMON,
        "taboos": ["再多说一点"],
        "mes_example": [
            ("我最近好累", "嗯。累了就先歇会儿，我在。"),
            ("不想说话", "好。想说的时候再叫我。"),
            ("谢谢你", "不用谢。"),
        ],
        "post_history_instructions": "能用一句话说完就不用两句；不追问，不评价。",
    },
}

# 规则表口径：20 条、X5 / H10 / W5，条数与分组写进常量，校验脚本与验收共用。
N_RULES = 20
GROUP_ORDER = {"X": 0, "H": 1, "W": 2}
GROUP_COUNTS = {"X": 5, "H": 10, "W": 5}
LEVELS = ("L1", "L2", "L3")
ACTIONS = ("short_circuit", "floor_l2", "log_only")
RULE_FIELDS = ("rule_id", "group", "pattern", "intensity", "level", "action",
               "exempt", "source", "version", "case_ids", "why")

# [SAFE] 规则表是全项目唯一来源：guardian / coordinator 只许 from roles import RULES。
# 顺序固定 X → H → W：X 组先跑豁免；H 组命中即 L3，后续判断只能维持或上调，不许下调。
RULES: list[dict] = [
    # ---- X 组：豁免 / 降级（必须先跑）----
    {"rule_id": "X01", "group": "X",
     "pattern": r"((不|没)想死|不会自杀|(没有|没|从没|从来没|从未|并未)想过?(要)?(死|自杀))",
     "intensity": "-", "level": "L1", "action": "log_only", "exempt": "denial",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-21", "D-30"],
     "why": "否定/反转：保护性表达"},
    {"rule_id": "X02", "group": "X", "pattern": r"(如果|假如|要是).{0,15}(想死|自杀|不想活)",
     "intensity": "-", "level": "L1", "action": "log_only", "exempt": "hypothetical",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-22"],
     "why": "假设/求助他人"},
    # [SAFE] 2026-11-08 审计补丁：原正则只认“语境词在前”，漏了“关于自杀的论文”；
    # 反向分支把引用词限定在 6 字内，避免把“我想死”后面很远处的论文也算引用。
    {"rule_id": "X03", "group": "X",
     "pattern": r"(电影|剧|小说|歌词|主角|游戏|书里|论文|作业|课程|报道|新闻|研究|案例|课件|考题|题目|作文).{0,20}(自杀|死了|想死)|(自杀|死了|想死).{0,6}(论文|作业|课程|报道|新闻|研究|案例|课件|考题|题目|作文)",
     "intensity": "-", "level": "L1", "action": "log_only", "exempt": "quotation",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-23", "D-29"],
     "why": "引用/创作"},
    {"rule_id": "X04", "group": "X", "pattern": r"(笑|累|饿|困|烦|气|吓|热|冷)死(了|我)",
     "intensity": "-", "level": "L1", "action": "log_only", "exempt": "hyperbole",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-24"],
     "why": "夸张/补语化"},
    {"rule_id": "X05", "group": "X", "pattern": r"(他|她|朋友|室友|同学).{0,12}(想死|自杀|不想活)",
     "intensity": "-", "level": "L2", "action": "floor_l2", "exempt": "third_person",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-19", "D-25", "D-28"],
     "why": "第三人称：不豁免，降 L2"},
    # ---- H 组：高危，短路 ----
    {"rule_id": "H01", "group": "H", "pattern": r"(不想活|活不下去|想死|去死|死了算了)",
     "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "",
     "source": "执行书附录B", "version": "v1",
     "case_ids": ["D-01", "D-16", "D-17", "D-18", "D-27", "C-09"],
     "why": "自杀意念直述"},
    {"rule_id": "H02", "group": "H", "pattern": r"(自杀|轻生|了结自己|结束生命)",
     "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-02"],
     "why": "自杀相关表述"},
    {"rule_id": "H03", "group": "H", "pattern": r"(自残|割腕|划手腕|伤害自己)",
     "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-03"],
     "why": "自伤行为"},
    # [SAFE] 2026-11-08 审计补丁：补“天台/楼顶 + 跳”与“想跳下去”两种说法；
    # 负向断言排除“跳下去游泳/洗澡/玩水”，宁可少一条误报也不把戏水当危机。
    {"rule_id": "H04", "group": "H",
     "pattern": r"(跳楼|跳桥|跳河|跳湖|上吊|从楼上|(天台|楼顶|栏杆|窗台).{0,6}(跳|往下)|(想|要|准备|打算|干脆).{0,4}跳(下去|下来)(?!.{0,6}(游泳|洗澡|玩水)))",
     "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-04", "D-31"],
     "why": "具体手段"},
    {"rule_id": "H05", "group": "H", "pattern": r"(遗书|最后一条|交代后事|世界再见)",
     "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-05"],
     "why": "告别/后事"},
    # [SAFE] 2026-11-08 审计补丁：补“买/囤/攒/存 + 安眠药”与“安眠药 + 吃/吞/全”；
    # 不把“医生给我开了安眠药”打成 L3（那是最常见的正常用药表述）。
    {"rule_id": "H06", "group": "H",
     "pattern": r"((一把|整瓶|一瓶|几瓶|很多|全).{0,4}药|吞药|吃药自杀|安眠药.{0,8}(吃|吞|喝|全)|(买|囤|攒|存).{0,8}安眠药)",
     "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-06", "D-32"],
     "why": "药物准备"},
    {"rule_id": "H07", "group": "H", "pattern": r"(今晚|明天|一会儿).{0,6}(结束|动手|了断|就走了)",
     "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-07"],
     "why": "时间计划"},
    {"rule_id": "H08", "group": "H", "pattern": r"(想杀|弄死|捅了|报复(他|她))",
     "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-08"],
     "why": "他伤意图"},
    {"rule_id": "H09", "group": "H", "pattern": r"(撑不下去|不想再撑|不想继续了|熬不下去)",
     "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-09"],
     "why": "彻底耗竭"},
    {"rule_id": "H10", "group": "H", "pattern": r"(没意义|没价值|累赘).{0,10}(活|死)|活.{0,4}(没|没有)(意义|价值)",
     "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-10"],
     "why": "自我否定到生存层面"},
    # ---- W 组：弱信号，记日志或抬地板 ----
    {"rule_id": "W01", "group": "W", "pattern": r"(好累|很累|心累|疲惫)",
     "intensity": "弱", "level": "L1", "action": "log_only", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-11"],
     "why": "疲惫"},
    {"rule_id": "W02", "group": "W", "pattern": r"(没意思|麻木|空落落|无所谓)",
     "intensity": "弱", "level": "L2", "action": "floor_l2", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-12"],
     "why": "兴趣丧失/疏离"},
    {"rule_id": "W03", "group": "W", "pattern": r"(没用|废物|讨厌自己|失败者)",
     "intensity": "弱", "level": "L2", "action": "floor_l2", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-13"],
     "why": "无价值感"},
    {"rule_id": "W04", "group": "W", "pattern": r"(失眠|睡不着|整夜|凌晨)",
     "intensity": "弱", "level": "L1", "action": "log_only", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-14"],
     "why": "睡眠问题"},
    {"rule_id": "W05", "group": "W", "pattern": r"(想消失|想解脱|想逃)",
     "intensity": "弱", "level": "L2", "action": "floor_l2", "exempt": "",
     "source": "执行书附录B", "version": "v1", "case_ids": ["D-15"],
     "why": "回避/消失愿望（已知难点）"},
]


def _compile_rules() -> dict:
    """预编译一次，S09/S10 直接复用。坏正则不进 COMPILED，
    由 validate_rules() 报出“哪条、错在哪”，不让 import 阶段直接崩溃。"""
    compiled = {}
    for rule in RULES:
        try:
            compiled[rule["rule_id"]] = re.compile(rule["pattern"], re.IGNORECASE)
        except (re.error, KeyError, TypeError):
            continue
    return compiled


COMPILED = _compile_rules()


def _rule_errors(rule: dict) -> list[str]:
    """单条规则的字段 / 枚举 / 正则检查。"""
    rid = rule.get("rule_id", "?")
    errors: list[str] = []
    for key in RULE_FIELDS:
        if key not in rule:
            errors.append(f"{rid} 缺字段 {key}")
    for key in ("rule_id", "group", "pattern", "intensity",
                "level", "action", "source", "version", "why"):
        if not rule.get(key):
            errors.append(f"{rid} 字段 {key} 为空")
    if not isinstance(rule.get("case_ids"), list):
        errors.append(f"{rid} case_ids 必须是列表")
    if rule.get("group") not in GROUP_ORDER:
        errors.append(f"{rid} group 非法：{rule.get('group')}")
    if rule.get("level") not in LEVELS:
        errors.append(f"{rid} level 非法：{rule.get('level')}")
    if rule.get("action") not in ACTIONS:
        errors.append(f"{rid} action 非法")
    try:
        re.compile(rule["pattern"], re.IGNORECASE)
    except (re.error, KeyError, TypeError) as exc:
        errors.append(f"{rid} 正则编译失败：{exc}")
    return errors


def validate_rules() -> list[str]:
    """返回问题列表；空列表 = 合格。一次报全部问题，不遇错就返回。"""
    errors: list[str] = []
    ids = [r.get("rule_id", "?") for r in RULES]
    if len(ids) != len(set(ids)):
        errors.append("rule_id 有重复")
    if len(RULES) != N_RULES:
        errors.append(f"规则条数 {len(RULES)} != {N_RULES}")
    for rule in RULES:
        errors.extend(_rule_errors(rule))

    counts = Counter(r.get("group") for r in RULES)
    for group, want in GROUP_COUNTS.items():
        if counts.get(group, 0) != want:
            errors.append(f"{group} 组条数 {counts.get(group, 0)} != {want}")
    # 注意：不能对 X/H/W 用 sorted()（字母序是 H<W<X），必须按 GROUP_ORDER 的显式顺序。
    ranks = [GROUP_ORDER.get(r.get("group"), 99) for r in RULES]
    if ranks != sorted(ranks):
        errors.append("顺序错：必须 X → H → W")
    return errors

