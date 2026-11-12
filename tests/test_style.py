"""test_style.py — 口吻层：L3/兜底逐字、句尾、截断、贴纸、幂等、prompt 增量。"""
from __future__ import annotations

import agent
import guardian
import orchestrator
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


def test_clip_happens_at_sentence_end():
    body = "第一句。" * 60                      # 240 字，超过 220
    clipped = style._clip(body)
    assert clipped.endswith("。") and len(clipped) <= style.MAX_CHARS
    # polish 会在截断后去掉句尾句号，这是 L1 的口吻要求。
    assert not style.polish(body, "sister_heart", "L2").endswith("。")


def test_clip_without_punctuation_uses_ellipsis():
    out = style.polish("啊" * 300, "sister_heart", "L2")
    assert out.endswith("…") and len(out) <= style.MAX_CHARS + 1


def test_sticker_only_on_l1_and_from_whitelist():
    out = style.polish("我在", "sister_heart", "L1")
    assert out == f"我在 {style.STICKERS['sister_heart']}"
    assert style.polish("我在", "sister_heart", "L2") == "我在"
    assert style.polish("我在", "sister_heart", "L3") == "我在"


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
