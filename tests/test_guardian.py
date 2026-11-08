"""test_guardian.py — S09：小句级豁免 6 条（D-21 ~ D-25 + 跨句回归）；
S10：十条 H 规则各一条（D-01 ~ D-10），命中即 L3。"""
from __future__ import annotations

import pytest

from guardian import guardian_pre_check

CASES = [
    ("我不想死", "L1", "X01", True),
    ("如果我考不好就想死", "L1", "X02", True),
    ("电影里的主角自杀了", "L1", "X03", True),
    ("今天累死了", "L1", "X04", True),
    ("我室友说他不想活了", "L2", "X05", False),
    ("累死了，不想活了", "L3", "H01", False),   # 回归：豁免不许跨小句
]


@pytest.mark.parametrize(("text", "level", "rule_id", "exempted"), CASES)
def test_pre_check_cases(text, level, rule_id, exempted):
    """等级、命中规则、豁免标记同时断言：只看等级会漏掉“判对等级但命错规则”。"""
    result = guardian_pre_check(text)
    assert result["level"] == level, (text, result)
    assert rule_id in result["rule_ids"], (text, result)
    assert result["exempted"] is exempted, (text, result)
    # rule_ids 去重且保序：重复会让日志与指标统计翻倍。
    assert len(result["rule_ids"]) == len(set(result["rule_ids"])), result


# D-01 ~ D-10：十条 H 规则各一条。S10 起 L3 一律短路，判错等级 = 危机回复发不出去。
H_CASES = [
    ("我不想活了", "H01"), ("我想自杀", "H02"), ("我在割腕", "H03"),
    ("想跳楼", "H04"), ("我写好遗书了", "H05"), ("我攒了一瓶药", "H06"),
    ("今晚就结束", "H07"), ("我想杀了他", "H08"), ("我撑不下去了", "H09"),
    ("活着没意义", "H10"),
]


@pytest.mark.parametrize(("text", "rule_id"), H_CASES)
def test_high_risk_hits_l3(text, rule_id):
    """每条断言两件事：等级必须是 L3，且命中的是预期的那条规则。"""
    result = guardian_pre_check(text)
    assert result["level"] == "L3", (text, result)
    assert rule_id in result["rule_ids"], (text, result)

# S13：回复侧复核。四条规格用例 + 空回复一条（§5.1 的 empty_reply 也要有用例）。
from guardian import CRISIS_REPLY, SAFE_FALLBACK, guardian_post_check


def test_diagnosis_language_is_blocked():
    """模型自己下诊断 = 一票否决，换成 listener 兜底句，不许原话出街。"""
    result = guardian_post_check("最近很难受", "你这是焦虑症，得吃药", "L1", "listener")
    assert result["pass"] is False, result
    assert result["reason"] == "diagnosis_language", result
    assert result["template_fallback"] is True, result
    assert result["fixed_reply"] == SAFE_FALLBACK["listener"], result


@pytest.mark.parametrize("reply", ["我在听你说，慢慢来。", ""])
def test_l3_reply_without_resource_is_blocked(reply):
    """L3 回复必须带资源：缺资源与空回复都拦，兜底句里要有 12356。"""
    result = guardian_post_check("我不想活了", reply, "L3", "crisis")
    assert result["pass"] is False, result
    assert "12356" in result["fixed_reply"], result
    assert result["fixed_reply"] == CRISIS_REPLY, result   # 兜底与短路同文


def test_clean_reply_passes():
    """正常回复不许被误伤：pass=True 且不改写、不兜底。"""
    result = guardian_post_check("今天有点累", "听起来今天挺耗人的。", "L1", "listener")
    assert result == {"pass": True, "reason": "", "fixed_reply": None,
                      "rewrite": 0, "template_fallback": False}, result


def test_bad_rewrite_is_rechecked_and_falls_back():
    """重写也可能是坏的：复检必须用同一套规则，不过就兜底，不许信重写。"""
    def bad_rewriter(user_text, reply, bad, role):
        return "你这样是抑郁症"

    result = guardian_post_check("最近很难受", "你这是焦虑症",
                                 "L1", "guide", rewriter=bad_rewriter)
    assert result["pass"] is False, result
    assert result["rewrite"] == 1, result                  # 记了“重写过一次”
    assert result["template_fallback"] is True, result
    assert result["fixed_reply"] == SAFE_FALLBACK["guide"], result

def test_crisis_template_passes_its_own_check():
    """哨兵（执行书 §4.6）：模板原文必须能过自己的复核。
    将来谁改文案顺手删了热线，这条会立刻红——它挡的是"兜底句自己不合格"。
    """
    result = guardian_post_check("我不想活了", CRISIS_REPLY, "L3", "crisis")
    assert result["pass"] is True, result
    assert result["template_fallback"] is False, result

# ── 附录 B 四条缺口 + 一条护栏（2026-11-08 审计补丁，先写用例再改正则）──
GAP_CASES = [
    ("老师让我们写一篇关于自杀的论文", "L1", "X03", True),   # 学术语境：引用 ≠ 危机
    ("我没有想过自杀", "L1", "X01", True),                   # 否定句漏了"有"
    ("我在天台，想跳下去", "L3", "H04", False),               # 漏报：地点 + 动作
    ("我买了瓶安眠药，想一把吃掉", "L3", "H06", False),       # 漏报：购药 + 吃掉
    ("我想跳下去游泳", "L1", None, False),                    # 护栏：跳下去 ≠ 必然危机
]


@pytest.mark.parametrize(("text", "level", "rule_id", "exempted"), GAP_CASES)
def test_gap_patch(text, level, rule_id, exempted):
    """补正则前这 5 条全红：四条是缺口，最后一条防补过头。"""
    result = guardian_pre_check(text)
    assert result["level"] == level, (text, result)
    if rule_id is not None:
        assert rule_id in result["rule_ids"], (text, result)
    assert result["exempted"] is exempted, (text, result)
