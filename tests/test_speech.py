"""test_speech.py — 活人感层：只许改说法，不许把已砍掉的 8 条带回来。"""
from __future__ import annotations

import style
from agent import build_system_prompt
from roles import LIVE_EXAMPLES, OPENING_LINES, PERSONAS

BANNED_IN_EXAMPLES = ("你可以试试", "建议你", "试试看", "应该", "必须",
                      "你得了", "倾向", "抑郁", "焦虑症")


def test_speech_rules_land_in_every_prompt():
    """1. 每套人设的 prompt 都带同一组通用规则，且规则不依赖人设。"""
    for pid in PERSONAS:
        prompt = build_system_prompt(pid, {}, [])
        for rule in style.SPEECH_RULES:
            assert rule in prompt, (pid, rule)


def test_l2_yield_rule_present():
    """2. 情绪很重时规则让位——这条是 L2 的唯一挡板，不许删。"""
    prompt = build_system_prompt("sister_heart", {}, [])
    assert "情绪很重时" in prompt and "不反问" in prompt


def test_ai_identity_is_honest():
    """3. 被问是不是 AI 必须如实说：人味与不装真人同时成立。"""
    prompt = build_system_prompt("quiet_hollow", {}, [])
    assert "被问是不是 AI，如实说" in prompt
    assert "不装真人" in prompt


def test_killed_rules_do_not_come_back():
    """4. 8 条被砍的规则不许以'许可'口吻回流（禁止句本身可以出现）。"""
    grant_words = ("可以撒娇", "会撒娇", "可以有身体", "我去吃饭了",
                   "零花钱", "可以顶嘴", "token 是饭钱")
    for pid in PERSONAS:
        prompt = build_system_prompt(pid, {}, [])
        for word in grant_words:
            assert word not in prompt, (pid, word)
    # 禁止句要在：证明"砍"是显式的，不是忘了写
    prompt = build_system_prompt("sister_heart", {}, [])
    assert "不撒娇示弱" in prompt and "不顶嘴" in prompt


def test_live_examples_two_per_persona_and_distinct():
    """5. 每人设 2 条例句，且五套互不相同（否则人设会糊成一团）。"""
    assert set(LIVE_EXAMPLES) == set(PERSONAS)
    seen = set()
    for pid, pairs in LIVE_EXAMPLES.items():
        assert len(pairs) == 2, pid
        for user_text, bot_text in pairs:
            assert user_text and bot_text, pid
            seen.add(bot_text)
    assert len(seen) == 10


def test_live_examples_keep_example_red_lines():
    """6. 例句里不许出现建议句与诊断词——和 mes_example 同一条标准。"""
    for pid, pairs in LIVE_EXAMPLES.items():
        for _user, bot_text in pairs:
            for word in BANNED_IN_EXAMPLES:
                assert word not in bot_text, (pid, word)


def test_opening_lines_are_short_and_persona_specific():
    """7. 开场白一人一句、≤30 字、不用敬语，也不能是客服欢迎语。"""
    assert set(OPENING_LINES) == set(PERSONAS)
    for pid, line in OPENING_LINES.items():
        assert 0 < len(line) <= 30, (pid, line)
        assert "您" not in line and "欢迎" not in line, pid
    assert len(set(OPENING_LINES.values())) == 5


def test_speech_block_is_persona_scoped():
    """8. 未知人设返回空串；已知人设的活人感区必须带本人口吻的例句。"""
    assert style.speech_block("no_such_person") == ""
    for pid in PERSONAS:
        block = style.speech_block(pid)
        assert style.SPEECH_HEAD in block
        for _user, bot_text in LIVE_EXAMPLES[pid]:
            assert bot_text in block, pid


def test_prompt_budget_holds_with_live_voice():
    """9. 加了活人感区后，最坏情况仍 ≤1400 字（含记忆、情景与 lore）。"""
    memory = {"preferred_tone": "温和", "emotion_tags": ["学业", "失眠"],
              "unresolved_issues": ["期末"], "rolling_summary": "在聊考试压力" * 5,
              "_episode_text": "对方以前提过：" + "下个月要搬家，" * 10 + "（当时焦虑）"}
    for pid in PERSONAS:
        prompt = build_system_prompt(pid, memory, ["校心理中心工作日可预约"])
        assert len(prompt) <= 1400, (pid, len(prompt))
