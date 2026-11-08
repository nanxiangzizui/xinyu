"""logger.py — 结构化日志：每轮一行 JSONL，只记字段，不记原文。

红线：用户原句 / 回复原文 / 人设 prompt 永远不进日志；字段白名单之外的键直接丢弃。
日志是旁路：写失败只警告一行，绝不影响这一轮对话。
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime

LOG_DIR = os.getenv("LOG_DIR", "data/logs")

# 字段白名单（执行书 §5 / step/README §3.5）：顺序即写入顺序，不许增减。
FIELDS = ("ts", "session_hash", "turn", "level", "role", "rule_ids",
          "action", "rewrite", "latency_ms")


def session_hash(session_id: str) -> str:
    """session_id 的短哈希：能区分会话，不能反推原始 id。"""
    return hashlib.sha256((session_id or "anon").encode("utf-8")).hexdigest()[:12]


def log_turn(**fields) -> None:
    """追加一行日志；白名单过滤，写失败不影响对话。"""
    row = {key: fields[key] for key in FIELDS if key in fields}
    row.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        path = os.path.join(LOG_DIR, datetime.now().strftime("%Y-%m-%d") + ".jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError) as exc:
        # [SAFE] 日志是旁路：磁盘满 / 只读 / 值不可序列化，都不许让对话失败。
        print(f"[WARN] 日志写入失败：{type(exc).__name__}")
