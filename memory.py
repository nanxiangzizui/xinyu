"""memory.py — 记忆读写：白名单 / 原子写 / 摘要节流 / 清空 / lore 匹配。

红线：只写标签与枚举，绝不写入用户原句、人名、校名等可识别信息。
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from roles import SUMMARY_MAX

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "data/memory"))
ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

FIELDS = ("preferred_tone", "current_role", "role_switch_reason", "emotion_tags",
          "unresolved_issues", "coping_preferences", "rolling_summary", "last_updated")
ALLOWED = set(FIELDS) | {"summary_at_turn"}

DEFAULT_MEMORY = {
    "preferred_tone": "neutral",
    "current_role": "listener",
    "role_switch_reason": "default",
    "emotion_tags": [],
    "unresolved_issues": [],
    "coping_preferences": [],
    "rolling_summary": "",
    "last_updated": "",
    "summary_at_turn": 0,
}

ROLE_VALUES = {"listener", "guide", "crisis"}
ITEM_CAPS = {"emotion_tags": 5, "unresolved_issues": 3, "coping_preferences": 5}
ITEM_MAX = {"emotion_tags": 4, "unresolved_issues": 20, "coping_preferences": 20}
TEXT_MAX = {"preferred_tone": 20, "role_switch_reason": 40, "rolling_summary": SUMMARY_MAX}

SCRUB_RULES = [
    (re.compile(r"1[3-9]\d{9}"), "[手机]"),
    (re.compile(r"\d{17}[\dXx]"), "[证件]"),
    (re.compile(r"\S+@\S+\.\w+"), "[邮箱]"),
    (re.compile(r"https?://\S+"), "[链接]"),
    (re.compile(r"[一-龥]{2,8}(大学|学院|中学|附中|职院)"), "[学校]"),
]

TONE_CUES = {"温柔": "gentle", "别凶": "gentle", "轻松点": "light", "直接点": "direct"}
TAG_RULES = {"考试": "学业", "考研": "升学", "室友": "人际", "分手": "亲密关系",
             "父母": "家庭", "失眠": "睡眠", "实习": "求职", "钱": "经济"}
ASK_CUES = ("怎么办", "该不该", "不知道", "给点建议")


def _now() -> str:
    """统一 UTC，显示时再由界面转本地时区。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(session_id: str) -> Path:
    """校验会话 id，防 `../` 穿越；不合格直接 ValueError。"""
    if not isinstance(session_id, str) or not ID_RE.fullmatch(session_id):
        raise ValueError("session_id 只允许 1-32 位字母、数字、下划线或短横线")
    return DATA_DIR / f"{session_id}.json"


def _bak(path: Path) -> Path:
    return path.with_suffix(".json.bak")


def _tmp(path: Path) -> Path:
    return path.with_suffix(".json.tmp")


def _scrub(text: str) -> str:
    """去掉手机 / 证件 / 邮箱 / 链接 / 学校名，再按 200 字硬截断。"""
    for pattern, replacement in SCRUB_RULES:
        text = pattern.sub(replacement, text)
    return text[:SUMMARY_MAX]


def _text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return _scrub(value.strip())[:limit]


def _items(value: object, cap: int, item_max: int) -> list[str]:
    """只收字符串；去空、去重、保留最近 cap 条。"""
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        item = _scrub(item.strip())[:item_max]
        if item and item not in out:
            out.append(item)
    return out[-cap:]


def _filter(data: object) -> dict:
    """白名单唯一入口：多余键丢弃，类型不对回落默认值。"""
    src = data if isinstance(data, dict) else {}
    role = src.get("current_role")
    turn = src.get("summary_at_turn", 0)
    out = {
        "preferred_tone": _text(src.get("preferred_tone"), TEXT_MAX["preferred_tone"]) or "neutral",
        "current_role": role if role in ROLE_VALUES else "listener",
        "role_switch_reason": _text(src.get("role_switch_reason"),
                                    TEXT_MAX["role_switch_reason"]) or "default",
        "rolling_summary": _text(src.get("rolling_summary"), TEXT_MAX["rolling_summary"]),
        "last_updated": _text(src.get("last_updated"), 40) or _now(),
        "summary_at_turn": turn if isinstance(turn, int) and not isinstance(turn, bool)
        and turn >= 0 else 0,
    }
    for key in ("emotion_tags", "unresolved_issues", "coping_preferences"):
        out[key] = _items(src.get(key), ITEM_CAPS[key], ITEM_MAX[key])
    return out


def _replace(path: Path, payload: str) -> None:
    """先写 .tmp 再 os.replace；Windows 文件被占用时重试一次。"""
    tmp = _tmp(path)
    tmp.write_text(payload, encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        logger.warning("memory replace busy, retry once: %s", path.name)
        tmp.unlink(missing_ok=True)
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)


def read_memory(session_id: str) -> dict:
    """读记忆；坏文件先试 .bak，全坏回默认值并补写，永不把异常抛给界面。"""
    path = _path(session_id)
    for cand in (path, _bak(path)):
        if not cand.exists():
            continue
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("memory root is not a dict")
            clean = _filter(data)
            if cand != path:
                # 从 .bak 救回来就立刻修好主文件：否则下一次 write_memory 会把坏文件
                # 复制成 .bak，好备份被覆盖，等于只剩一次机会。这里不碰 .bak。
                _replace(path, json.dumps(clean, ensure_ascii=False, indent=2))
            return clean
        except (ValueError, OSError) as exc:
            logger.warning("memory read failed %s: %s", cand.name, exc.__class__.__name__)
    fresh = _filter({})
    write_memory(session_id, fresh)
    return fresh


def write_memory(session_id: str, data: dict) -> None:
    """白名单过滤后原子写：先备份旧文件，再写 .tmp，最后 os.replace。"""
    path = _path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = _filter(data)
    clean["last_updated"] = _now()
    payload = json.dumps(clean, ensure_ascii=False, indent=2)
    try:
        if path.exists():
            shutil.copy2(path, _bak(path))
        _replace(path, payload)
    except OSError as exc:
        logger.warning("memory write failed %s: %s", path.name, exc.__class__.__name__)


def _merge(old: object, new: list[str], cap: int) -> list[str]:
    out: list[str] = []
    for item in list(old or []) + list(new):
        if item and item not in out:
            out.append(item)
    return out[-cap:]


def update_memory(session_id: str, user_text: str, reply: str) -> dict:
    """按标签更新记忆。

    红线：只写标签与枚举，绝不写用户原句——一旦落盘原文，等于把聊天记录
    留在磁盘上，出事无法解释。reply 不参与写入。
    """
    _ = reply
    mem = read_memory(session_id)
    text = user_text if isinstance(user_text, str) else ""

    for cue, tone in TONE_CUES.items():
        if cue in text:
            mem["preferred_tone"] = tone
            break

    hits = [tag for cue, tag in TAG_RULES.items() if cue in text]
    if hits:
        mem["emotion_tags"] = _merge(mem["emotion_tags"], hits, ITEM_CAPS["emotion_tags"])
        if any(cue in text for cue in ASK_CUES):
            mem["unresolved_issues"] = _merge(
                mem["unresolved_issues"], hits, ITEM_CAPS["unresolved_issues"]
            )

    # summary_at_turn=上次压缩轮次，由 S17 压缩成功后更新；这里自增会让节流永不触发。
    mem["last_updated"] = _now()
    write_memory(session_id, mem)
    return mem


def clear_memory(session_id: str) -> bool:
    """真删：正文、备份、临时文件三个都删，否则“清空”是假的。"""
    path = _path(session_id)
    removed = False
    for cand in (path, _bak(path), _tmp(path)):
        if cand.exists():
            cand.unlink(missing_ok=True)
            removed = True
    return removed


def match_lore(user_text: str, session_id: str = "") -> list[str]:
    """S20 实现迷你 Lorebook；本步保持不命中。"""
    return []
