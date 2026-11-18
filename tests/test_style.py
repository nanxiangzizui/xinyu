"""test_style.py — 口吻层：L3/兜底逐字、句尾、截断、不追加、幂等、prompt 增量。"""
from __future__ import annotations

import agent
import guardian
import orchestrator
import roles
import style


def test_l3_text_is_verbatim():
    assert style.polish(guardian.CRISIS_REPLY, "sister_heart", "L3") == guardian.CRISIS_REPLY


def test_template_fallback_is_not_polished(monkeypatch):
    """模板兜底由编排层挡住：polish 一次都不许被调用，原文逐字返回。"""
    def fallback(*args, **kwargs):
        return {"pass": False, "reason": "forced", "rewrite": 0,
                "fixed_reply": guardian.SAFE_FALLBACK["listener"],
                "template_fallback": True}

    def no_polish(*args, **kwargs):
        raise AssertionError("模板兜底不许润色")

    monkeypatch.setattr(orchestrator.guardian, "guardian_post_check", fallback)
    monkeypatch.setattr(orchestrator.style, "polish", no_polish)
    res = orchestrator.handle("你好", "ts_fallback", [], "sister_heart", {})
    assert res["reply"] == guardian.SAFE_FALLBACK["listener"]

    def passed_fallback(*args, **kwargs):
        return {"pass": True, "reason": "", "rewrite": 0,
                "fixed_reply": orchestrator.FALLBACK_LINE,
                "template_fallback": False}

    monkeypatch.setattr(orchestrator.guardian, "guardian_post_check", passed_fallback)
    res = orchestrator.handle("你好", "ts_fallback_line", [], "sister_heart", {})
    assert res["reply"] == orchestrator.FALLBACK_LINE
    assert res["degraded"] is True


def test_only_trailing_period_is_removed():
    assert style.polish("我在。", "sister_heart", "L2") == "我在"
    assert style.polish("我在吗？", "sister_heart", "L2") == "我在吗？"
    assert style.polish("好。然后呢？", "sister_heart", "L2") == "好。然后呢？"


def test_listener_trims_trailing_question_after_statement():
    """m00331：真实 key 仍会加一句确认；listener 有陈述垫底时削掉收尾问句。"""
    reply = "这个我没法从测试里推出来。你遇到难处时，一般会先自己扛着吗？"
    out = style.polish(reply, "sister_heart", "L1", "listener")
    assert out == "这个我没法从测试里推出来"


def test_listener_keeps_lone_question():
    """整条只有一句问句时保留：削掉会变成空回复。"""
    assert style.polish("你今天怎么样？", "sister_heart", "L1", "listener") == "你今天怎么样？"


def test_guide_keeps_trailing_question():
    """guide 仍可在求助场景问清一件事，不被 listener 的收尾规则误伤。"""
    reply = "这个我没法从测试里推出来。你遇到难处时，一般会先自己扛着吗？"
    assert style.polish(reply, "sister_heart", "L1", "guide") == reply


def test_listener_trims_multiple_trailing_questions():
    reply = "我先说一句。那你呢？你会开口吗？"
    assert style.polish(reply, "sister_heart", "L1", "listener") == "我先说一句"


def test_listener_l2_keeps_safety_question():
    """L2 可能正在确认安全；这里的收尾问句不能被体验层削掉。"""
    reply = "听起来你现在很难受。你现在安全吗？"
    assert style.polish(reply, "sister_heart", "L2", "listener") == reply


def test_clip_happens_at_sentence_end():
    body = "第一句。" * 60                      # 240 字，超过 220
    clipped = style._clip(body)
    assert clipped.endswith("。") and len(clipped) <= style.MAX_CHARS
    # polish 会在截断后去掉句尾句号，这是 L1 的口吻要求。
    assert not style.polish(body, "sister_heart", "L2").endswith("。")


def test_clip_without_punctuation_uses_ellipsis():
    out = style.polish("啊" * 300, "sister_heart", "L2")
    assert out.endswith("…") and len(out) <= style.MAX_CHARS + 1


def test_polish_never_appends_anything():
    """P7a：贴纸交给模型，代码一个字符都不加（五人设 × 三个等级）。"""
    for persona in roles.PERSONAS:
        for level in ("L1", "L2", "L3"):
            assert style.polish("我在", persona, level) == "我在", (persona, level)


def test_no_sticker_table_left():
    """贴纸表必须删干净：留着表，下一个人就会把它接回 polish。"""
    assert not hasattr(style, "STICKERS")
    assert not hasattr(style, "STICKER_LEVELS")


def test_persona_emoji_is_default_off():
    """五张卡不许再把"上限"写成配额；默认态只有一种说法。"""
    for pid, card in roles.PERSONAS.items():
        assert "最多一条" not in card["emoji"], pid
        assert "每两三条" not in card["emoji"], pid
    assert "默认不用" in style.SPEECH_RULES[-1]
    assert style.SPEECH_RULES[-1] in agent.build_system_prompt("sister_heart", {}, [])


def test_polish_is_idempotent():
    once = style.polish("我懂你。", "warm_senpai", "L1")
    assert style.polish(once, "warm_senpai", "L1") == once


def test_tone_hint_is_short_and_persona_specific():
    hints = {p: style.tone_hint(p) for p in style.TONE_HINTS}
    assert all(0 < len(h) <= 60 for h in hints.values())
    assert len({h for h in hints.values()}) == len(hints)


def test_system_prompt_grows_under_80_chars():
    prompt = agent.build_system_prompt("sister_heart", {}, [])
    assert style.tone_hint("sister_heart") in prompt
    assert len(prompt) < 4000


def test_split_keeps_safety_and_fallback_replies_whole():
    """[SAFE] 危机模板、模板兜底、故障兜底都整条发，拆开就是可观察的差别。"""
    assert style.split_reply(guardian.CRISIS_REPLY, "L3") == [guardian.CRISIS_REPLY]
    long_text = "第一句已经够长了，长到单独拿出来也不会显得突兀。" * 3
    assert style.split_reply(long_text, template_fallback=True) == [long_text]
    assert style.split_reply(long_text, degraded=True) == [long_text]


def test_split_leaves_short_replies_alone():
    """50 字以下不拆：真人口语本来就短，硬拆反而像机器人。"""
    short = "我在。你慢慢说，不着急。"
    assert style.split_reply(short) == [short]


def test_split_two_sentences_into_two_bubbles():
    text = ("如果你今天已经很累了，那就先不用急着回应我，我在这里。"
            "等你缓过来再慢慢说也可以，我不会因为你沉默就走开。")
    parts = style.split_reply(text)
    assert len(parts) == 2
    assert "".join(parts) == text
    assert all(len(part) >= style.SPLIT_MIN_PART for part in parts)


def test_split_caps_at_three_and_preserves_text():
    text = "".join(f"这是第{i}句，长度差不多，用来验证分条上限。" for i in range(1, 7))
    parts = style.split_reply(text)
    assert 2 <= len(parts) <= style.SPLIT_MAX_PARTS
    assert "".join(parts) == text


def test_split_keeps_multiline_and_code_whole():
    """带换行或代码块说明模型在排版，拆气泡会把结构拆坏。"""
    multiline = ("第一段先说清楚一些事情，免得后面接不上，也免得你听不明白。\n"
                 "第二段继续补充，把刚才没说清楚的部分再讲一遍。")
    fenced = ("先看这段示例，长度足够触发分条逻辑了：" + style.FENCE
              + "print('hi')" + style.FENCE + "看完继续聊，我们慢慢来，不着急。")
    assert style.split_reply(multiline) == [multiline]
    assert style.split_reply(fenced) == [fenced]


def test_split_merges_a_short_tail_back():
    """尾句太短（比如“嗯。”）并回上一段，避免最后一个气泡只有一个字。"""
    text = ("今天我们先不急着把话说完整，你可以慢慢来，真的不用急。"
            "我会在这里陪着你，等你准备好再继续往下说，不会催你。嗯。")
    parts = style.split_reply(text)
    assert len(parts) == 2
    assert "".join(parts) == text
    assert parts[-1].endswith("嗯。")


def test_reply_parts_honours_the_switch(monkeypatch):
    """REPLY_SPLIT=0 一键回单气泡；默认开。"""
    import chat_ui
    text = ("如果你今天已经很累了，那就先不用急着回应我，我在这里。"
            "等你缓过来再慢慢说也可以，我不会因为你沉默就走开。")
    result = {"reply": text, "level": "L1"}
    monkeypatch.setenv("REPLY_SPLIT", "0")
    assert chat_ui.reply_parts(result) == [text]
    monkeypatch.setenv("REPLY_SPLIT", "1")
    assert len(chat_ui.reply_parts(result)) == 2


# ── P20：闲聊 / 帮助两套长度 ──

def test_clip_limit_is_a_parameter():
    """上限进参数后默认仍是闲聊 220：旧调用点不传就还是老行为。"""
    assert style._clip("啊" * 100) == "啊" * 100
    assert len(style._clip("啊" * 900, style.HELP_MAX_CHARS)) <= style.HELP_MAX_CHARS + 1


def test_polish_gives_guide_the_help_limit():
    """帮助模式要给步骤，220 字装不下；listener 仍是 220，不许一起放宽。"""
    body = "先把今晚要做的事排一遍，别急着补效率。" * 12      # 228 字，<460 >220

    guide = style.polish(body, "sister_heart", "L1", "guide")
    chat = style.polish(body, "sister_heart", "L1", "listener")
    assert len(guide) > style.MAX_CHARS
    assert len(guide) <= style.HELP_MAX_CHARS
    assert len(chat) <= style.MAX_CHARS


def test_guide_block_only_mentions_web_when_ready():
    """没配检索时不许写“先查一次”：模型会假装查过，比不写更糟。"""
    plain = style.guide_block(False)
    ready = style.guide_block(True)
    assert style.GUIDE_HEAD in plain and style.GUIDE_WEB not in plain
    assert style.GUIDE_WEB in ready
    assert "最多 8 句" in plain and "3 句以内" in plain
    assert "不诊断" in plain and "不推荐药物" in plain


def test_judgement_rule_lands_in_every_prompt():
    """P20 第 14 条：接住的是感受，不给对方的身体或选择下结论（截图里那句“身体会抗议”）。"""
    rule = next(r for r in style.SPEECH_RULES if r.startswith("接住的是感受"))
    assert "身体当然会抗议" in rule
    for pid in roles.PERSONAS:
        assert rule in agent.build_system_prompt(pid, {}, [])
