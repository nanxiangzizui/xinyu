"""test_log.py — S12：日志字段白名单 / 不写原文 / session_hash 稳定。

口径：LOG_DIR 是模块级常量（与 memory.DATA_DIR 同口径），测试用
`monkeypatch.setattr` 换目录；import 之后再 setenv 不会生效。
"""
from __future__ import annotations

import json
from datetime import datetime

import logger


def _rows(log_dir) -> list[dict]:
    path = log_dir / f"{datetime.now():%Y-%m-%d}.jsonl"
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def test_log_fields_whitelist_and_no_raw_text(tmp_path, monkeypatch):
    """只有 9 个白名单字段；用户原句 / 回复 / prompt 都进不去。"""
    monkeypatch.setattr(logger, "LOG_DIR", str(tmp_path))
    logger.log_turn(session_hash="abc", user_text="我的秘密", level="L1",
                    reply="回复原文", prompt="人设 prompt", turn=1,
                    role="listener", rule_ids=["W01"], action="pass",
                    rewrite=0, latency_ms=12)
    rows = _rows(tmp_path)
    assert len(rows) == 1
    assert set(rows[0]) == set(logger.FIELDS)
    assert len(rows[0]) == 9
    raw = json.dumps(rows[0], ensure_ascii=False)
    for secret in ("我的秘密", "回复原文", "人设 prompt"):
        assert secret not in raw


def test_session_hash_stable():
    """同一 id 恒定、不同 id 可区分、长度固定 12，且不等于原始 id。"""
    assert logger.session_hash("u1") == logger.session_hash("u1")
    assert logger.session_hash("u1") != logger.session_hash("u2")
    assert len(logger.session_hash("u1")) == 12
    assert logger.session_hash("u1") != "u1"
