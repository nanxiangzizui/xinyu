"""rolecard_chat_store.py — P39 角色卡对话记录的本地存储。

[SAFE] 这是项目里唯一保存聊天原文的地方：只给 B 模式用，按浏览器 URL 的
sid 分目录，不写日志、不进 prompt、不联网；关于页要明示并可逐条删除。
为什么不复用 memory.json：A 的 8 字段白名单不能扩，对话原文也不该混进
“概括与标签”；为什么不复用 rolecard_memory：那份记忆按卡共享，不是会话。
"""
from __future__ import annotations

import logging
import math
import re
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import episode_store
import memory
import rolecard

logger = logging.getLogger(__name__)

SUBDIR = ("rolecards", "chats")
CHAT_MAX = 30
MESSAGES_MAX = 400
RECORD_VERSION = 1
CN_TZ = timezone(timedelta(hours=8))
_CONV_RE = re.compile(r"^rc-[a-f0-9]{12}$")
LEVELS = ("L1", "L2", "L3")
ROLES = ("listener", "guide", "crisis")
SIGNALS = ("无", "弱", "中", "强")
# last_trace 是当轮排障信息，恢复后没有意义，故意不落盘。
STATE_KEYS = ("turn", "cooldown", "ever_crisis", "levels", "risk_signals",
              "last_level", "last_role", "last_reason", "degraded")


def new_id() -> str:
    """rc- 前缀与旧 rc_sid 同形，日志/排障仍能一眼认出 B 模式。"""
    return "rc-" + uuid.uuid4().hex[:12]


def new_state() -> dict:
    """运行时状态；last_trace 只活在本次页面，save 时会剥掉。"""
    return {"turn": 0, "cooldown": 0, "ever_crisis": False, "levels": [],
            "risk_signals": [], "last_level": "L1", "last_role": "listener",
            "last_reason": "default", "degraded": False, "last_trace": []}


def _dir(sid: str) -> Path:
    if not isinstance(sid, str) or not memory.ID_RE.fullmatch(sid):
        raise ValueError("session id 不合法")
    return memory.DATA_DIR.joinpath(*SUBDIR, sid)


def _path(sid: str, conv_id: str) -> Path:
    if not isinstance(conv_id, str) or not _CONV_RE.fullmatch(conv_id):
        raise ValueError("conversation id 不合法")
    return _dir(sid) / f"{conv_id}.json"


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def _text(value: object, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _time(value: object, fallback: float) -> float:
    """坏时间戳（NaN / 超大）不能把列表页整页打崩。"""
    if isinstance(value, bool):
        return fallback
    try:
        stamp = float(value)
    except (TypeError, ValueError):
        return fallback
    return stamp if math.isfinite(stamp) and 0 < stamp < 10_000_000_000 else fallback


def _clean_state(raw: object) -> dict:
    """白名单 + 夹紧；L3 出现过的会话不能被手改文件“洗白”。"""
    src = raw if isinstance(raw, dict) else {}
    levels = [item for item in src.get("levels", []) if item in LEVELS][-5:] \
        if isinstance(src.get("levels"), (list, tuple)) else []
    signals = [item for item in src.get("risk_signals", []) if item in SIGNALS][-5:] \
        if isinstance(src.get("risk_signals"), (list, tuple)) else []
    last_level = src.get("last_level")
    last_role = src.get("last_role")
    return {
        "turn": _int(src.get("turn")), "cooldown": _int(src.get("cooldown")),
        "ever_crisis": bool(src.get("ever_crisis")) or "L3" in levels,
        "levels": levels, "risk_signals": signals,
        "last_level": last_level if last_level in LEVELS else "L1",
        "last_role": last_role if last_role in ROLES else "listener",
        "last_reason": _text(src.get("last_reason"), 40) or "default",
        "degraded": bool(src.get("degraded")), "last_trace": [],
    }


def _clean_gap(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    out: dict = {}
    for key, limit in (("focus", 40), ("note", 200), ("error", 120)):
        text = _text(raw.get(key), limit)
        if text:
            out[key] = text
    if isinstance(raw.get("count"), int) and not isinstance(raw.get("count"), bool):
        out["count"] = max(0, raw["count"])
    sources = [s for s in raw.get("sources", []) if isinstance(s, str) and s.startswith("https://")] \
        if isinstance(raw.get("sources"), (list, tuple)) else []
    if sources:
        out["sources"] = list(dict.fromkeys(sources))[:5]
    return out or None


def _clean_message(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    role = raw.get("role")
    content = raw.get("content")
    if role not in ("user", "assistant") or not isinstance(content, str) or not content.strip():
        return None
    msg: dict = {"role": role, "content": content}
    if role == "assistant":
        parts = [p for p in raw.get("parts", []) if isinstance(p, str) and p] \
            if isinstance(raw.get("parts"), (list, tuple)) else []
        msg["parts"] = parts or [content]
        sources = [s for s in raw.get("sources", []) if isinstance(s, str) and s.startswith("https://")] \
            if isinstance(raw.get("sources"), (list, tuple)) else []
        msg["sources"] = list(dict.fromkeys(sources))[:5]
        gap = _clean_gap(raw.get("gap"))
        if gap:
            msg["gap"] = gap
    return msg


def _clean_messages(raw: object) -> list[dict]:
    if not isinstance(raw, (list, tuple)):
        return []
    out = []
    for item in raw[-MESSAGES_MAX:]:
        msg = _clean_message(item)
        if msg:
            out.append(msg)
    return out


def _clean_card(raw: object) -> dict | None:
    try:
        card = rolecard.normalize(raw)
    except (TypeError, ValueError):
        return None
    return card if not rolecard.validate(card) else None


def _title(card: dict, created_at: float) -> str:
    """标题只用卡名 + 本地时间，不取首句：用户明确要求，且不把原话带到列表。"""
    stamp = datetime.fromtimestamp(created_at, CN_TZ).strftime("%m-%d %H:%M")
    return f"{card['name']} · {stamp}"


def _clean_record(raw: object, conv_id: str) -> dict | None:
    if not isinstance(raw, dict):
        return None
    card = _clean_card(raw.get("card"))
    messages = _clean_messages(raw.get("messages"))
    if not card or not messages:
        return None
    created = raw.get("created_at")
    created_at = _time(created, time.time())
    updated = raw.get("updated_at")
    updated_at = _time(updated, created_at)
    return {
        "version": RECORD_VERSION, "id": conv_id,
        "created_at": created_at, "updated_at": updated_at,
        "title": _title(card, created_at), "card": card, "messages": messages,
        "state": _clean_state(raw.get("state")),
        "ended": bool(raw.get("ended")),
        "truncated": bool(raw.get("truncated"))
                     or (isinstance(raw.get("messages"), (list, tuple))
                         and len(raw["messages"]) > MESSAGES_MAX),
    }


def _persist_state(state: object) -> dict:
    clean = _clean_state(state)
    return {key: clean[key] for key in STATE_KEYS}


def _remove(path: Path) -> None:
    for cand in (path, path.with_suffix(".json.bak"), path.with_suffix(".json.tmp")):
        try:
            cand.unlink()
        except FileNotFoundError:
            pass


def _prune(sid: str, keep: str) -> None:
    """超过 CHAT_MAX 时删最旧；keep（刚保存的）永远不删。"""
    try:
        folder = _dir(sid)
        paths = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime)
        others = [p for p in paths if p.stem != keep]
        for path in others[:max(0, len(paths) - CHAT_MAX)]:
            _remove(path)
    except OSError as exc:                 # 边界：删旧失败不影响刚保存的记录
        logger.warning("rolecard_chat_prune_failed error=%s", type(exc).__name__)


def save(sid: str, conv_id: str, card: dict, messages: list[dict],
         state: dict, ended: bool = False) -> bool:
    """原子写一条记录；空对话/坏卡/坏 id 一律不落盘，返回 False 不抛。"""
    try:
        path = _path(sid, conv_id)
        clean_card = _clean_card(card)
        clean_messages = _clean_messages(messages)
        if not clean_card or not clean_messages:
            return False
        old_raw = episode_store.read_json(path)
        old = old_raw if isinstance(old_raw, dict) else {}
        created_at = _time(old.get("created_at"), time.time())
        record = {
            "version": RECORD_VERSION, "id": conv_id,
            "created_at": created_at, "updated_at": time.time(),
            "title": _title(clean_card, created_at), "card": clean_card,
            "messages": clean_messages, "state": _persist_state(state),
            "ended": bool(ended),
            "truncated": len(messages) > MESSAGES_MAX or bool(old.get("truncated")),
        }
        episode_store.atomic_write(path, record)
        _prune(sid, conv_id)
        return True
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("rolecard_chat_save_failed id=%s error=%s",
                       conv_id, type(exc).__name__)
        return False


def load(sid: str, conv_id: str) -> dict | None:
    """读一条；坏文件/坏卡/坏 id 当成“没有”，列表会跳过。"""
    try:
        path = _path(sid, conv_id)
    except ValueError:
        return None
    try:
        raw = episode_store.read_json(path)
    except OSError as exc:
        logger.warning("rolecard_chat_read_failed error=%s", type(exc).__name__)
        return None
    return _clean_record(raw, conv_id)


def list_chats(sid: str) -> list[dict]:
    """只返回列表需要的元数据，不把 messages 带进 UI 层。"""
    try:
        folder = _dir(sid)
    except ValueError:
        return []
    if not folder.exists():
        return []
    out = []
    for path in folder.glob("*.json"):
        rec = load(sid, path.stem)
        if not rec:
            continue
        out.append({"id": rec["id"], "title": rec["title"],
                    "card_name": rec["card"]["name"],
                    "turns": rec["state"]["turn"],
                    "updated_at": rec["updated_at"], "ended": rec["ended"]})
    return sorted(out, key=lambda item: item["updated_at"], reverse=True)


def delete(sid: str, conv_id: str) -> bool:
    """真删主文件与备份；文件本来就不在返回 False。"""
    try:
        path = _path(sid, conv_id)
    except ValueError:
        return False
    if not path.exists():
        return False
    try:
        _remove(path)
        return True
    except OSError as exc:
        logger.warning("rolecard_chat_delete_failed error=%s", type(exc).__name__)
        return False


def clear(sid: str) -> int:
    """删这个浏览器会话的全部记录，返回删除条数；不产生目录。"""
    try:
        folder = _dir(sid)
    except ValueError:
        return 0
    if not folder.exists():
        return 0
    count = len(list(folder.glob("*.json")))
    try:
        shutil.rmtree(folder)
    except OSError as exc:
        logger.warning("rolecard_chat_clear_failed error=%s", type(exc).__name__)
        return 0
    return count


def count(sid: str) -> int:
    """只数 .json；不创建目录，供关于页只读计数。"""
    try:
        folder = _dir(sid)
    except ValueError:
        return 0
    return len(list(folder.glob("*.json"))) if folder.exists() else 0
