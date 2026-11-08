"""test_roles.py — S07 的 4 条：安全区同文、红线在 prompt 里、未知人设回退、空事实不留空标题。"""
from __future__ import annotations

from agent import build_system_prompt
from roles import PERSONAS

CARD_FIELDS = {"name", "tone", "address", "sentence_len", "emoji",
               "boundaries", "taboos", "mes_example", "post_history_instructions"}

# 示例句里一旦出现这些，人设就开始"给建议 / 下诊断"，比规则更容易带歪模型。
BANNED_IN_EXAMPLES = ("你可以试试", "建议你", "试试看", "应该", "必须",
                      "你得了", "倾向", "抑郁", "焦虑症")


def test_safety_block_identical():
    """1. 五张卡结构一致，[安全守则] + [说话边界] 段逐字相同。"""
    assert len(PERSONAS) == 5
    for pid, card in PERSONAS.items():
        assert set(card) == CARD_FIELDS, pid
        assert card["boundaries"] == PERSONAS["sister_heart"]["boundaries"]
        assert len(card["mes_example"]) == 3
    heads = {build_system_prompt(pid, {}, []).split("[你的说话方式]")[0]
             for pid in PERSONAS}
    assert len(heads) == 1


def test_prompt_keeps_red_lines():
    """2. 每个 prompt 都带"不承诺保密"与"3 句以内"，示例里没有建议句与诊断词。"""
    for pid, card in PERSONAS.items():
        prompt = build_system_prompt(pid, {}, [])
        assert "不承诺保密" in prompt and "3 句以内" in prompt
        for _user, bot in card["mes_example"]:
            for word in BANNED_IN_EXAMPLES:
                assert word not in bot, f"{pid} 的示例出现「{word}」"


def test_unknown_persona_falls_back():
    """3. 未知 persona_id 回退到知心姐姐，不抛异常。"""
    assert build_system_prompt("no_such_person", {}, []) == \
        build_system_prompt("sister_heart", {}, [])


def test_prompt_within_budget():
    """5. 含记忆与 lore 时整段 prompt ≤ 1200 字，且安全区不被挤掉。"""
    memory = {"preferred_tone": "温和", "emotion_tags": ["学业", "失眠"],
              "unresolved_issues": ["期末"], "rolling_summary": "在聊考试压力" * 5}
    for pid in PERSONAS:
        prompt = build_system_prompt(pid, memory, ["校心理中心工作日可预约"])
        assert len(prompt) <= 1200, (pid, len(prompt))
        assert "不承诺保密" in prompt


def test_coping_preferences_reach_prompt():
    """6. 用户在面板里改的安抚偏好要进事实区（不能只吃常量种子）。"""
    prompt = build_system_prompt("sister_heart", {"coping_preferences": ["听歌", "散步"]}, [])
    assert "对方愿意试的办法：听歌、散步" in prompt


def test_empty_facts_section_omitted():
    """4. 空 memory + 空 lore 时不出现空标题；有内容时才出现。"""
    assert "[你记得的事]" not in build_system_prompt("sister_heart", {}, [])
    filled = build_system_prompt(
        "sister_heart",
        {"emotion_tags": ["学业"], "rolling_summary": "在聊考试压力"},
        ["校心理中心工作日 8 点后仍可预约"],
    )
    assert "[你记得的事]" in filled
    assert "学业" in filled and "考试压力" in filled
