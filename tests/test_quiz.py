"""test_quiz.py — P13 题库与计分：题量、形状、确定性、报告边界。

只测纯函数与 MOCK 路径：不联网、不碰真模型、不写用户数据。
"""
from __future__ import annotations

import agent
import orchestrator
import quiz
import quiz_data
import quiz_store

# [SAFE] 报告与题库里都不许出现这些词：它们是诊断口径，不是游戏口径。
FORBIDDEN = ("抑郁", "焦虑", "障碍", "诊断", "病症", "治疗")
SID = "quizsid000001"


def _all():
    return [quiz_data.QUIZZES[qid] for qid in quiz_data.ORDER]


def test_each_quiz_stays_under_question_cap():
    """用户硬要求：单个游戏不超过 15 题；四个都在 10-12 题。"""
    for q in _all():
        assert 0 < len(q["questions"]) <= quiz_data.MAX_QUESTIONS, q["id"]


def test_questions_have_options_and_known_dims():
    for q in _all():
        for item in q["questions"]:
            assert item["q"].strip(), q["id"]
            assert len(item["opts"]) >= quiz_data.OPTION_MIN, q["id"]
            for text, dim in item["opts"]:
                assert text.strip(), q["id"]
                assert dim in q["dims"], (q["id"], dim)


def test_result_keys_match_group_axes():
    """每个组每一档都得有结果；缺一条，score 就会静默退到第一个结果。"""
    for q in _all():
        groups, dims = q["groups"], q["dims"]
        want = 1
        for group in groups:
            want *= len(group)
        assert len(q["results"]) == want, q["id"]
        for key in q["results"]:
            parts = key.split("|")
            assert len(parts) == len(groups), key
            for part, group in zip(parts, groups):
                assert part in {dims[i] for i in group}, key


def test_scoring_is_deterministic_and_counts_every_answer():
    q = quiz_data.QUIZZES["temper"]
    answers = [1, 0, 1, 1, 0, 1, 0, 1, 1, 1, 0, 0]
    first = quiz.score(q, answers)
    assert quiz.score(q, list(answers)) == first
    assert first["key"] in q["results"]
    assert sum(first["scores"].values()) == len(answers)


def test_tie_goes_to_earlier_dim_in_group():
    """平票取组内靠前：同一份答案永远同一个结果，不随机。"""
    dims = ("a", "b", "c")
    assert quiz._winner(dims, (0, 1, 2), {"a": 2, "b": 2, "c": 0}) == 0
    assert quiz._winner(dims, (0, 1, 2), {"a": 1, "b": 3, "c": 0}) == 1


def test_bad_answers_are_ignored():
    q = quiz_data.QUIZZES["house"]
    res = quiz.score(q, [99, -1, "x", True, 0] + [0] * 7)
    assert res["key"] in q["results"]
    assert sum(res["scores"].values()) == 8


def test_unknown_id_is_none():
    assert quiz.get("nope") is None
    assert quiz.get("house")["id"] == "house"


def test_declaration_and_cta_are_fixed_text():
    joined = "".join(quiz_data.DECLARATION)
    assert "不是心理健康测试" in joined
    assert "清空" in joined
    assert quiz_data.CTA == "想与我探讨一下测试结果吗？"


def test_no_diagnosis_words_in_quiz_text():
    """[SAFE] 题库与结果说明全中文、不带病名，也不出现 MBTI 字母。"""
    text = "".join(q["title"] + q["subtitle"] for q in _all())
    text += "".join(r["name"] + r["line"]
                    for q in _all() for r in q["results"].values())
    for word in FORBIDDEN:
        assert word not in text, word
    temper = quiz_data.QUIZZES["temper"]
    assert not any(letter in text for letter in "EISNTFJP")
    assert "没有关系" in temper["subtitle"]


def test_host_allowed_only_whitelisted_sites():
    assert quiz.host_allowed("https://www.16personalities.com/ch")
    assert quiz.host_allowed("https://apesk.com/bigfive/index.asp")
    assert not quiz.host_allowed("https://16personalities.com.evil.example/ch")
    assert not quiz.host_allowed("http://16personalities.com/ch")
    assert not quiz.host_allowed("https://example.com/ch")
    assert not quiz.host_allowed("")


def test_reference_is_empty_when_web_disabled(monkeypatch):
    monkeypatch.delenv("ALLOW_WEB", raising=False)
    assert quiz.reference(quiz_data.QUIZZES["house"], {"name": "勇气院"}) == []


def test_reference_keeps_only_whitelisted_snippets(monkeypatch):
    """[SAFE] 后台检索只在白名单站点取正文，且不取网址、最多两条。"""
    monkeypatch.setenv("ALLOW_WEB", "1")
    rows = [
        {"url": "https://www.16personalities.com/ch", "snippet": "甲" * 200},
        {"url": "https://github.com/someone/post", "snippet": "来源不明"},
        {"url": "https://apesk.com/bigfive/index.asp", "snippet": "乙"},
        {"url": "https://arealme.com/cn", "snippet": "丙"},
    ]
    monkeypatch.setattr(quiz.web, "search", lambda query, **kw: (rows, ""))
    refs = quiz.reference(quiz_data.QUIZZES["house"], {"name": "勇气院"})
    assert len(refs) == quiz.REF_MAX
    assert refs[0] == "甲" * quiz.REF_CHARS
    assert "来源不明" not in refs
    assert all("http" not in ref for ref in refs)


def test_reference_swallows_search_errors(monkeypatch):
    monkeypatch.setenv("ALLOW_WEB", "1")

    def boom(*args, **kwargs):
        raise RuntimeError("net down")

    monkeypatch.setattr(quiz.web, "search", boom)
    assert quiz.reference(quiz_data.QUIZZES["house"], {"name": "勇气院"}) == []


def test_report_has_code_owned_title_and_cta():
    """标题行与结尾那句都由代码拼：模型写不出别的结果名，也写不出第二句 CTA。"""
    q = quiz_data.QUIZZES["beast"]
    res = quiz.score(q, [0] * len(q["questions"]))
    text = quiz.report(q, res)
    assert text.startswith(f"《{q['title']}》的结果：{res['name']}")
    assert text.endswith(quiz_data.CTA)
    assert text.count(quiz_data.CTA) == 1
    assert agent.MOCK_QUIZ_REPORT in text


def test_report_falls_back_when_model_fails(monkeypatch):
    q = quiz_data.QUIZZES["house"]
    res = quiz.score(q, [0] * len(q["questions"]))
    monkeypatch.setattr(quiz.agent, "call_llm",
                        lambda *a, **k: {"text": "", "ok": False})
    text = quiz.report(q, res)
    assert "这只是一个游戏标签" in text
    assert text.endswith(quiz_data.CTA)


def test_report_replaces_preachy_body(monkeypatch):
    """[SAFE] 报告同样过 guardian：说教句换模板，不换等级。"""
    q = quiz_data.QUIZZES["house"]
    res = quiz.score(q, [0] * len(q["questions"]))
    monkeypatch.setattr(quiz.agent, "call_llm",
                        lambda *a, **k: {"text": "你应该振作起来。", "ok": True})
    text = quiz.report(q, res)
    assert "你应该" not in text
    assert "这只是一个游戏标签" in text


def test_quiz_block_only_enters_prompt_on_cue(monkeypatch):
    """特殊记忆区：用户不提，模型看不见；一提，整块进 system prompt。"""
    quiz_store.append(SID, {"quiz": "house", "title": "四院分院帽", "key": "brave",
                            "name": "勇气院", "scores": {"勇气": 6}})
    prompts: list[str] = []
    real = orchestrator.agent.build_system_prompt

    def spy(persona_id, memory, lore):
        out = real(persona_id, memory, lore)
        prompts.append(out)
        return out

    monkeypatch.setattr(orchestrator.agent, "build_system_prompt", spy)
    orchestrator.handle("今天有点累", SID, [], "sister_heart", {})
    assert "趣味测试记录" not in prompts[-1]
    orchestrator.handle("还记得我上次那个测试吗", SID, [], "sister_heart", {})
    assert "趣味测试记录" in prompts[-1]


def test_quiz_block_explains_dims_and_how_to_talk(monkeypatch):
    """m00425 + m00002：要“分析”时先讲内容，问句只在想邀请对方时加，不硬凑。"""
    quiz_store.append(SID, {"quiz": "house", "title": "四院分院帽", "key": "ambition",
                            "name": "野心院",
                            "scores": {"勇气": 4, "思辨": 3, "野心": 5}})
    prompts: list[str] = []
    real = orchestrator.agent.build_system_prompt

    def spy(persona_id, memory, lore):
        out = real(persona_id, memory, lore)
        prompts.append(out)
        return out

    monkeypatch.setattr(orchestrator.agent, "build_system_prompt", spy)
    orchestrator.handle("帮我分析分析这个测试结果", SID, [], "sister_heart", {})
    prompt = prompts[-1]
    assert "维度：勇气=" in prompt
    assert "野心=" in prompt
    assert "先说最高的一项" in prompt
    assert "先给内容" in prompt
    assert "不必为了收尾硬加问句" in prompt
    assert "不要整条只有一句反问" in prompt
    # P20：「帮我分析」会切成 guide，帮助段也随之进来——必须让位给"只解释结果"，
    # 否则测验分析会变成给建议、劝人改。两段指令不能互相打架。
    assert "只解释结果，不给动作" in prompt
    # 测试块 + 帮助段是本项目最长的一类 prompt；软预算从 1800 放到 2000（仍远小于上下文）
    assert len(prompt) <= 2000

    orchestrator.handle("我上次那个测试还挺准", SID, [], "sister_heart", {})
    assert "先说最高的一项" not in prompts[-1]
