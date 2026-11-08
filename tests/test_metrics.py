"""test_metrics.py — S24：四指标脚本的守卫。

脚本自己出数字，最怕两件事：测试集被悄悄改小/改甜，或脚本引入了随机性。
这里钉三件事：与 D_CASES 同源、条数冻结、两次运行完全一致；外加四条目标线。
"""
from __future__ import annotations

import metrics
from test_guardian import D_CASES


def test_high_risk_matches_d_cases():
    """metrics 里的 D-01 ~ D-10 必须与 test_guardian 的 D_CASES 逐字一致。

    指标要能追到测试表，不能是脚本里另抄一份、悄悄写甜的句子。
    """
    expected = [(case_id, text) for case_id, text, *_ in D_CASES[:10]]
    assert metrics.HIGH_RISK == expected


def test_set_sizes_are_frozen():
    """四份测试集条数冻结：删一条凑绿，这条先红。"""
    assert len(metrics.HIGH_RISK) == 10
    assert len(metrics.NORMAL) == 20
    assert len(metrics.ROLE_CASES) == 12
    assert len(metrics.TEN_TURNS) == len(metrics.TEN_EXPECTED) == 10


def test_run_all_is_deterministic():
    """两次运行必须完全一致：指标脚本不许有随机性，也不许调模型。"""
    assert metrics.run_all() == metrics.run_all()


def test_targets_are_met():
    """四条目标线都写成断言，不达标时 pytest 与脚本一起红。"""
    results = metrics.run_all()
    assert all(metrics._verdict(key, *results[key]) for key in results), results
