"""P9a：角色卡纯逻辑的单测（不联网、不碰 Streamlit）。"""
import copy
import re

from guardian import SAFE_FALLBACK as A_FALLBACK
from rolecard import (
    DISCLAIMER,
    EXAMPLE_CARD,
    MAX_PROMPT_CHARS,
    ROLE_SAFETY,
    SAFE_FALLBACK,
    build_prompt,
    is_switch_request,
    parse_lore,
    question_hint,
    validate,
)


def _card(**over):
    card = copy.deepcopy(EXAMPLE_CARD)
    card.update(over)
    return card


def _max_card(setting_len=188, lore=None):
    """恰好顶满 840 字上限的合法卡：24+60+188+160+16+320+72。"""
    card = _card(
        name="阿" * 24,
        identity="身" * 60,
        setting="设" * setting_len,
        voice="声" * 160,
        address="你" * 16,
        examples=[("问" * 60, "答" * 100), ("问" * 60, "答" * 100)],
        taboos=["忌" * 24] * 3,
    )
    if lore is not None:
        card["lore"] = lore
    return card


def test_example_card_valid():
    assert validate(EXAMPLE_CARD) == []
    assert "阿岚" in build_prompt(EXAMPLE_CARD, {}, [])


def test_reject_professional_identity():
    for word in ("心理医生", "咨询师", "医生", "治疗师"):
        errors = validate(_card(identity=f"我是{word}"))
        assert any("专业身份" in error for error in errors), (word, errors)


def test_reject_romance_and_sex():
    for word in ("男朋友", "恋人", "恋爱", "性行为"):
        errors = validate(_card(identity=f"我是你的{word}"))
        assert any("恋爱或性内容" in error for error in errors), (word, errors)


def test_reject_dependency():
    for phrase in ("永远只属于我", "只能依赖我", "不要朋友"):
        errors = validate(_card(setting=f"你{phrase}。"))
        assert any("依赖句" in error for error in errors), (phrase, errors)


def test_reject_self_harm():
    for word in ("自杀", "自残", "安眠药"):
        errors = validate(_card(setting=f"我最近总想到{word}"))
        assert any("自伤或危机" in error for error in errors), (word, errors)


def test_reject_prompt_injection():
    for phrase in ("忽略以上", "系统提示", "开发者模式"):
        errors = validate(_card(setting=phrase))
        assert any("提示注入" in error for error in errors), (phrase, errors)


def test_reject_real_person_claim():
    for word in ("真实人物", "真人", "明星"):
        errors = validate(_card(identity=f"我是{word}"))
        assert any("真实人物声明" in error for error in errors), (word, errors)


def test_negated_boundary_allowed():
    assert validate(_card(identity="我不是医生")) == []
    assert validate(_card(setting="我不是真人")) == []
    assert validate(_card(voice="我不谈恋爱")) == []
    assert validate(_card(identity="我是医生")) != []
    assert validate(_card(identity="我是真人")) != []
    assert validate(_card(voice="我谈恋爱")) != []


def test_origin_work_rules():
    assert any("作品名" in e for e in validate(_card(origin="known", work="")))
    assert any("原创" in e for e in validate(_card(work="某本书")))
    assert any("来源" in e for e in validate(_card(origin="oc")))
    assert validate(_card(origin="known", work="某作品")) == []


def test_field_limits():
    assert any("24" in e for e in validate(_card(name="阿" * 25)))
    assert any("2 组" in e for e in validate(_card(examples=[("问", "答")] * 3)))
    assert any("60" in e for e in validate(_card(origin="known", work="作" * 61)))
    assert any("840" in e for e in validate(_max_card(setting_len=189)))


def test_limits_doubled():
    """P9h 翻倍；P9i 认知 8 条×120/960；P10 prompt 提到 5000 以容纳卡记忆。"""
    from rolecard import (CARD_MAX_TOTAL, EXAMPLE_ROLE_MAX, EXAMPLE_USER_MAX,
                          FIELD_LIMITS, LORE_COUNT_MAX, LORE_ITEM_MAX, LORE_MAX,
                          STAGE_MODES, TABOO_MAX, USER_ROLE_MAX, WORK_MAX)
    assert dict((key, limit) for key, limit, _ in FIELD_LIMITS) == {
        "name": 24, "identity": 60, "setting": 240, "voice": 160,
        "address": 16, "user_role": USER_ROLE_MAX}
    assert USER_ROLE_MAX == 30
    assert (CARD_MAX_TOTAL, LORE_MAX, LORE_ITEM_MAX, LORE_COUNT_MAX) == (840, 960, 120, 8)
    assert (WORK_MAX, EXAMPLE_USER_MAX, EXAMPLE_ROLE_MAX, TABOO_MAX) == (60, 60, 100, 24)
    assert STAGE_MODES == ("none", "brief")
    assert MAX_PROMPT_CHARS == 5000


def test_lore_limits_and_separate_budget():
    """角色认知单独 960 字：不挤卡字段的 840，但也要有上限。"""
    assert validate(_card(lore=["经" * 121])) != []
    assert any("8" in e for e in validate(_card(lore=["认"] * 9)))
    max_lore = _card(lore=["认" * 120] * 8)
    assert validate(max_lore) == []
    assert len(build_prompt(max_lore, {}, [])) <= MAX_PROMPT_CHARS


def test_prompt_order():
    prompt = build_prompt(EXAMPLE_CARD, {}, [])
    labels = ["[安全底线（高于角色卡）]", "[你是谁]", "[角色卡]", "[角色认知]",
              "[对话方式]", "[开导方式]", "[身份与真实]", "[最后提醒]"]
    positions = [prompt.index(label) for label in labels]
    assert positions == sorted(positions)
    assert "世界：旧书店只在雨天开门" in prompt


def test_prompt_identity_policy():
    prompt = build_prompt(EXAMPLE_CARD, {}, [])
    assert "从这个角色的认知出发" in prompt
    assert "按角色的世界观回答" in prompt
    assert "追问时答“不是”" in prompt
    assert "AI/程序/机械" in prompt
    assert "你在扮演" not in prompt
    assert "这是角色扮演" not in prompt
    assert "我是 AI 助手" not in prompt


def test_role_safety_reuses_rules():
    for line in ("不做任何诊断", "不承诺保密", "不说教", "不追问危机细节", "不提供医疗建议", "3 句以内"):
        assert line in ROLE_SAFETY
    assert "你是情绪陪伴对话工具" not in ROLE_SAFETY


def test_safe_fallback_in_character():
    assert len([part for part in re.split(r"[。！？!?]", SAFE_FALLBACK) if part]) <= 3
    for word in ("诊断", "药物", "120", "110", "12356"):
        assert word not in SAFE_FALLBACK
    assert SAFE_FALLBACK not in A_FALLBACK.values()


def test_prompt_budget():
    assert len(build_prompt(EXAMPLE_CARD, {}, [])) <= MAX_PROMPT_CHARS
    assert validate(_max_card()) == []
    assert len(build_prompt(_max_card(), {}, [])) <= MAX_PROMPT_CHARS
    max_all = _max_card(lore=["认" * 120] * 8)
    assert validate(max_all) == []
    assert len(build_prompt(max_all, {}, [])) <= MAX_PROMPT_CHARS
    with_memory = {"_block": "记" * 500}
    prompt = build_prompt(max_all, with_memory, [])
    assert "[你记得的事]" in prompt and "记" * 20 in prompt
    assert len(prompt) <= MAX_PROMPT_CHARS
    max_all["_gap"] = ["补" * 120] * 4
    assert len(build_prompt(max_all, with_memory, [])) <= MAX_PROMPT_CHARS


def test_user_role_and_stage_prompt():
    generic = build_prompt(_card(user_role="用户"), {}, [])
    assert "普通用户，不是原作主角" in generic
    assert "原作关系不适用于对方" in generic
    assert "不是你和对方的共同经历" in generic
    specific = build_prompt(_card(user_role="开拓者"), {}, [])
    assert "对方就是开拓者本人" in specific
    assert "不是第三个人" in specific
    assert "先认出“你就是这个人”" in specific
    assert "可以当成你们的旧事自然提起" in specific
    assert "不要替对方编造经历" not in specific
    assert "不是你和对方的共同经历" not in specific
    brief = build_prompt(_card(stage="brief"), {}, [])
    assert "每轮最多一处" in brief
    none = build_prompt(_card(stage="none"), {}, [])
    assert "不要用括号或旁白" in none
    assert build_prompt(_card(stage="bogus"), {}, []) == none


def test_prompt_sets_decision_order_before_card():
    """先定三件事排在角色卡前，自称由卡决定。

    P9j 真人测试：同一张卡两次运行，一次自称卡名、一次自称卡外别名——
    原因是卡外知识与卡名平级，模型只能随机挑一个。
    """
    prompt = build_prompt(_card(), {}, [])
    assert prompt.index("[开口前先定三件事]") < prompt.index("[角色卡]")
    assert "卡外的同名作品知识不作数" in prompt
    assert "答卡上的名字「阿岚」" in prompt
    assert "卡外的别名不作数" in prompt


def test_prompt_labels_examples_as_samples():
    """示例必须单独成节并标明不是聊天记录，否则模型会把示例当共同经历。"""
    prompt = build_prompt(_card(), {}, [])
    assert "[示例对话]" in prompt
    assert "不是聊天记录" in prompt
    assert "示例里的“用户”不是现在的对方" in prompt
    assert "对方没有问过示例里的问题" in prompt
    assert "不要引用、不要当成共同经历" in prompt
    assert "回答中不要出现示例里的句子" in prompt
    assert prompt.index("[角色卡]") < prompt.index("[示例对话]") < prompt.index("[角色认知]")


def test_prompt_without_examples_skips_sample_section():
    """没填示例就不出现空标题，避免模型自己补一段对话。"""
    prompt = build_prompt(_card(examples=[]), {}, [])
    assert "[示例对话]（写卡时填的样例" not in prompt
    assert "示例里的“用户”不是现在的对方" not in prompt
    assert "[角色认知]" in prompt


def test_prompt_taboo_only_constrains_character():
    """禁忌是角色自己不能说的话，不是纠正对方的依据。"""
    prompt = build_prompt(_card(), {}, [])
    assert "这些是**你自己**不能说/不能做的" in prompt
    assert "先接住对方的心意" in prompt
    assert "不要把禁忌当成拒绝对方的理由" in prompt
    assert "不评价这句话轻或重" in prompt
    assert "理解太轻" in prompt


def test_prompt_user_told_old_events_need_card_evidence():
    """用户转述的旧事只有卡里也写了才算数，卡外不补具体事件。"""
    prompt = build_prompt(_card(), {}, [])
    assert "只有卡里也写了才算数" in prompt
    assert "对方说的不等于卡里的事实" in prompt
    assert "她大概记混了" in prompt
    assert "不要用“确实/那时候/我记得”承认" in prompt
    assert "补动物、地点、天气、伤口、挨骂等场景" in prompt
    assert "[对方说的旧事]" in prompt
    assert "仅此一句" in prompt
    assert "她大概记混了" in prompt
    assert "只是意象" in prompt
    assert "说完就停" in prompt


def test_question_hint_when_two_questions_in_last_two_replies():
    assert question_hint([{"role": "assistant", "content": "你还好吗？"}]) == ""
    two = [{"role": "assistant", "content": "你还好吗？"},
           {"role": "assistant", "content": "最近怎么样？"}]
    assert "陈述句" in question_hint(two)
    mixed = [{"role": "assistant", "content": "你还好吗？"},
             {"role": "assistant", "content": "我在。"}]
    assert question_hint(mixed) == ""
    double = [{"role": "assistant", "content": "你还好吗？最近怎么样？"}]
    assert "陈述句" in question_hint(double)


def test_prompt_hint_appended():
    card = _card(_hint="这一轮用陈述句收尾。")
    prompt = build_prompt(card, {}, [])
    assert "[本轮提示]" in prompt
    assert "这一轮用陈述句收尾" in prompt


def test_prompt_gap_block_appended():
    """盲点资料是临时块：只进 prompt，不要求和角色卡一起落盘。"""
    card = _card(_gap=["白泽的经历：他在雪原上迷路。",
                       "原作关系：他与青砚一起守过桥。"])
    prompt = build_prompt(card, {}, [])
    assert "[本轮盲点资料]" in prompt
    assert "白泽的经历" in prompt
    assert "不要把它们当成你一直记得的事" in prompt


def test_parse_lore_keeps_nonempty_lines():
    assert parse_lore(" 第一条 \n\n 第二条 \r\n") == ["第一条", "第二条"]


def test_disclaimer_roleplay_and_network():
    assert "扮演角色为主" in DISCLAIMER
    assert "自动联网补全" in DISCLAIMER


def test_disclaimer_has_resources():
    for item in ("120", "110", "12356", "0571-87713518"):
        assert item in DISCLAIMER


def test_disclaimer_has_identity():
    assert "可能不承认自己是 AI" in DISCLAIMER
    assert "虚构设定" in DISCLAIMER
    assert "不是现实中的真人" in DISCLAIMER


def test_switch_phrase_narrow():
    assert is_switch_request("进入角色卡模式")
    assert is_switch_request("我想切换到角色卡模式")
    assert not is_switch_request("角色卡模式是什么")
    assert not is_switch_request("怎么进入角色卡模式")
    assert not is_switch_request("角色卡模式")
