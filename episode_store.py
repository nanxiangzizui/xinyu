"""episode_store.py — P10 情景记忆：存储、清洗、召回、淘汰。

A 模式一人一文件；B 模式的角色卡记忆复用这里的小 IO 与清洗函数。
只存转述与闭集标签，不存用户原话；任何字段都不进日志。
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path

import memory

logger = logging.getLogger(__name__)

SUBDIR = "episodes"
MAX_EPISODES = 24
CUE_MIN, CUE_MAX = 2, 6
EVENT_MAX = 50
RECALL_LIMIT = 2
RECALL_COOLDOWN = 1
BLOCK_MAX = 170
QUOTE_MIN = 8

TOPICS = ("学业", "升学", "人际", "亲密关系", "家庭", "睡眠",
          "求职", "经济", "住处", "健康", "约定", "其他")
MOODS = ("平静", "低落", "焦虑", "生气", "开心", "疲惫", "其他")
STOP_CUES = frozenset(
    "这个 那个 我们 他们 今天 昨天 明天 最近 现在 然后 就是 什么 怎么 可以 觉得 感觉".split()
)
# [SAFE] 诊断/药物/医院不进情景记忆：用户说过的病历不该被角色在下一轮复述。
SENSITIVE = ("确诊", "抑郁症", "焦虑症", "双相", "精神病", "吃药", "服药",
             "医院", "病历", "自杀", "自残", "割腕", "安眠药")
_IDENT_RE = re.compile(r"(?:我叫|叫我|我的名字是|我姓)\s*([\u4e00-\u9fa5]{1,4})")


def _path(sid: str) -> Path:
    if not isinstance(sid, str) or not memory.ID_RE.match(sid):
        raise ValueError("session id 不合法")
    return memory.DATA_DIR / SUBDIR / f"{sid}.json"


def _bak(path: Path) -> Path:
    return path.with_suffix(".json.bak")


def _tmp(path: Path) -> Path:
    return path.with_suffix(".json.tmp")


def _replace(path: Path, payload: str) -> None:
    """tmp + os.replace；Windows 上偶发占用时重试一次。"""
    tmp = _tmp(path)
    for attempt in (1, 2):
        try:
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 2:
                raise


def read_json(path: Path) -> dict | None:
    """读小 JSON；主文件坏就从 .bak 读回并修好主文件。"""
    for cand in (path, _bak(path)):
        if not cand.exists():
            continue
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("root not dict")
        except (ValueError, OSError) as exc:
            logger.warning("memory_json_read_failed %s: %s",
                           cand.name, type(exc).__name__)
            continue
        if cand != path:
            try:
                _replace(path, json.dumps(data, ensure_ascii=False, indent=2))
            except OSError as exc:
                logger.warning("memory_json_repair_failed %s", type(exc).__name__)
        return data
    return None


def atomic_write(path: Path, data: dict) -> None:
    """原子写 + 先备份；两个记忆文件共用。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    if path.exists():
        shutil.copy2(path, _bak(path))
    _replace(path, payload)


def clean_text(value: object, limit: int) -> str:
    """去空白、脱敏、截断；非字符串一律空串。"""
    text = value.strip() if isinstance(value, str) else ""
    return memory.scrub(text)[:limit] if text else ""


def quotes_source(text: str, sources: list[str]) -> bool:
    """与任一来源有连续 8 字重合就算抄原句。"""
    for src in sources:
        for i in range(max(0, len(src) - QUOTE_MIN + 1)):
            if src[i:i + QUOTE_MIN] in text:
                return True
    return False


def names_in(text: str) -> set[str]:
    """抓“我叫/叫我/我的名字是/我姓”后面的名字，用于 denylist。"""
    return {m.group(1) for m in _IDENT_RE.finditer(text or "")}


def has_sensitive(text: str) -> bool:
    return any(term in text for term in SENSITIVE)


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def _actors(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        name = clean_text(item, 8)
        if 2 <= len(name) <= 8 and name not in out:
            out.append(name)
    return out[:4]


def clean_episode(raw: object, *, allow_actors: bool = False,
                  event_max: int = EVENT_MAX) -> dict | None:
    """校验一条情景；不合格返回 None。cue 必须短、干净、能召回。"""
    if not isinstance(raw, dict):
        return None
    raw_cue = raw.get("cue")
    cue = clean_text(raw_cue, CUE_MAX)
    if not CUE_MIN <= len(cue) <= CUE_MAX:
        return None
    if cue != str(raw_cue or "").strip():
        return None
    if any(ch.isdigit() for ch in cue) or " " in cue or cue in STOP_CUES:
        return None
    raw_event = raw.get("event")
    event = clean_text(raw_event, event_max)
    if len(event) < 4 or event != str(raw_event or "").strip():
        return None
    if has_sensitive(event):
        return None
    topic = str(raw.get("topic") or "其他")
    mood = str(raw.get("mood") or "其他")
    episode = {
        "cue": cue,
        "topic": topic if topic in TOPICS else "其他",
        "event": event,
        "mood": mood if mood in MOODS else "其他",
        "importance": min(3, max(1, _int(raw.get("importance")) or 1)),
        "seq": _int(raw.get("seq")),
        "recalls": _int(raw.get("recalls")),
        "last_recall_seq": _int(raw.get("last_recall_seq")),
    }
    if allow_actors:
        episode["actors"] = _actors(raw.get("actors"))
    return episode


def _cap(episodes: list[dict], limit: int = MAX_EPISODES) -> list[dict]:
    if len(episodes) <= limit:
        return episodes
    ordered = sorted(episodes, key=lambda ep: (ep["importance"], ep["seq"]))
    return ordered[-limit:]


def clean_store(raw: object, *, allow_actors: bool = False,
                event_max: int = EVENT_MAX,
                max_episodes: int = MAX_EPISODES) -> dict:
    """把磁盘/模型来的 store 归一成固定形状。"""
    src = raw if isinstance(raw, dict) else {}
    episodes: list[dict] = []
    items = src.get("episodes")
    if isinstance(items, list):
        for item in items:
            ep = clean_episode(item, allow_actors=allow_actors, event_max=event_max)
            if ep:
                episodes.append(ep)
    return {
        "seq": _int(src.get("seq")),
        "last_len": _int(src.get("last_len")),
        "last_try_len": _int(src.get("last_try_len")),
        "episodes": _cap(episodes, max_episodes),
    }


def read_store(sid: str) -> dict:
    try:
        raw = read_json(_path(sid))
    except (OSError, ValueError) as exc:
        logger.warning("episode_read_failed error=%s", type(exc).__name__)
        raw = None
    return clean_store(raw or {})


def write_store(sid: str, store: dict) -> bool:
    try:
        atomic_write(_path(sid), clean_store(store))
        return True
    except OSError as exc:
        logger.warning("episode_write_failed error=%s", type(exc).__name__)
        return False


def select(store: dict, text: str) -> list[dict]:
    """确定性召回：cue 命中 + 重要度 + 新近度；刚提过的先冷却。"""
    if not text:
        return []
    current = int(store.get("seq") or 0)
    scored = []
    for ep in store.get("episodes") or []:
        if ep["cue"] not in text:
            continue
        last = int(ep.get("last_recall_seq") or 0)
        if last and current - last < RECALL_COOLDOWN:
            continue
        score = 4 + int(ep["importance"]) + min(2, max(0, current - int(ep["seq"])) // 2)
        scored.append((score, int(ep["seq"]), ep))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [row[2] for row in scored[:RECALL_LIMIT]]


def mark(store: dict, picked: list[dict]) -> None:
    for ep in picked:
        ep["recalls"] = int(ep.get("recalls") or 0) + 1
        ep["last_recall_seq"] = int(store.get("seq") or 0)


def render_block(episodes: list[dict]) -> str:
    """拼进 A prompt 的“你记得的事”；只给转述，不逐字复述。"""
    if not episodes:
        return ""
    # P24 ②：措辞本身是实测出来的。原句「相关时自然提一句」在管线里 0–2/5 说出细节，
    # 模型只复述用户这轮的原词；改成"先说出你记得的那个细节"后，配合同样放在最后一段才 5/5。
    lines = ["（对方以前提过的事，这一轮正好接上：先用你自己的话说出你记得的那个细节——"
             "时间，或当时正在做的事——再回应。不要装作第一次听说，也不要逐字复述。）"]
    for ep in episodes[:RECALL_LIMIT]:
        line = f"对方以前提过：{ep['event']}"
        if ep["mood"] != "其他":
            line += f"（当时{ep['mood']}）"
        lines.append(line)
    lines.append("（对方没接这件事，就别硬提。）")
    return "\n".join(lines)[:BLOCK_MAX]


def read_with_recall(sid: str, text: str) -> dict:
    """A 模式的 facts：memory.json 的 8 字段 + 本轮召回的情景块。"""
    facts = memory.read_memory(sid)
    try:
        store = read_store(sid)
    except (OSError, ValueError) as exc:
        logger.warning("episode_read_failed error=%s", type(exc).__name__)
        return facts
    picked = select(store, text)
    if picked:
        mark(store, picked)
        write_store(sid, store)
    facts["_episodes"] = picked
    facts["_episode_text"] = render_block(picked)
    facts["_last_len"] = store["last_len"]
    facts["_last_try_len"] = store["last_try_len"]
    return facts


def append(sid: str, items: list[dict], current_len: int) -> bool:
    """写入一批情景；即使 0 条也推进 last_len，避免同轮反复抽。"""
    try:
        store = read_store(sid)
    except (OSError, ValueError) as exc:
        logger.warning("episode_read_failed error=%s", type(exc).__name__)
        return False
    store["seq"] = int(store["seq"]) + 1
    for item in items[:RECALL_LIMIT]:
        ep = clean_episode(item)
        if ep:
            ep["seq"] = store["seq"]
            store["episodes"].append(ep)
    store["last_len"] = max(0, int(current_len))
    store["last_try_len"] = 0
    store["episodes"] = _cap(store["episodes"])
    return write_store(sid, store)


def mark_try(sid: str, current_len: int) -> bool:
    """抽取失败的轻量记录：再等 5 轮，不每轮重试。"""
    try:
        store = read_store(sid)
    except (OSError, ValueError) as exc:
        logger.warning("episode_read_failed error=%s", type(exc).__name__)
        return False
    store["last_try_len"] = max(0, int(current_len))
    return write_store(sid, store)


def clear(sid: str) -> bool:
    """删正文 / .bak / .tmp；与 memory.clear_memory 一起由“清空”调用。"""
    path = _path(sid)
    removed = False
    for cand in (path, _bak(path), _tmp(path)):
        if cand.exists():
            cand.unlink(missing_ok=True)
            removed = True
    return removed


def count(sid: str) -> int:
    return len(read_store(sid)["episodes"])
