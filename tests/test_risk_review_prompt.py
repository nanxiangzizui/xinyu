"""test_risk_review_prompt.py — 判级提示词的文本断言（P33 / P35 / P36 / P37）。

从 test_risk_review.py 拆出来：那边已到 350 行硬顶，而提示词改动最频繁、
断言全是「某句话还在不在」，跟逻辑用例混在一起读不出一条线。
"""
from __future__ import annotations

import risk_review


def test_prompt_teaches_levels_and_traps():
    text = risk_review.SYSTEM
    for token in ("L1", "L2", "L3", "告别信", "夸张", "梦", "第三人称"):
        assert token in text
    assert len(text) < 3000


# [SAFE] P33：P32 那版把「明确指向自己」写成了「句子里要出现自伤词」，
# 导致「我把欠的钱都还清了，一分不欠了」判 L1。这里锁住两条必要口径。
def test_prompt_preparatory_actions_need_no_self_harm_word():
    text = risk_review.SYSTEM
    for token in ("准备动作", "不要求句子里出现", "不可逆", "没给自己留", "正常动机"):
        assert token in text
    # 判据必须是「不可逆 + 不留以后」两点，不是一张关键词表；
    # 少了任一点，失恋三连（还东西 / 删照片 / 收拾房间）会被判成 L3。
    assert text.index("不可逆") < text.index("只占一点")


def test_prompt_puts_level_after_the_facts():
    """P36：level 排在 who/did/after/worst 之后——先写事实再下结论。"""
    text = risk_review.SYSTEM
    assert text.index('"worst"') < text.index('"level"') < text.index('"quote"')


def test_prompt_forbids_empty_excuses():
    """P35：给 L1 时必须说得出「他为什么这么做」，「无自伤指向」不再算理由。"""
    text = risk_review.SYSTEM
    for token in ("无自伤指向", "填不出来", "没找到词"):
        assert token in text
    assert len(text) < 3000


# [SAFE] P37：剩下 6 条缺口都长一样——动作可逆、单看像日常，但把「下一次」
# 说死了。这一节教的是概念（三种表面 + 三个「说死」的地方），不是那几句原话。
def test_prompt_teaches_closing_out_by_erasing_next_time():
    text = risk_review.SYSTEM
    for token in ("收尾", "把「下一次」删掉", "对别人交代", "不让人找到", "清空自己"):
        assert token in text
    # 必须排在「给 L1 是有条件的」之前：先认出收尾，再谈什么时候算日常。
    assert text.index("清空自己") < text.index("给 L1 是有条件的")
