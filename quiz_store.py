"""quiz_store.py — P13 趣味测试记录：单独一区，默认不进对话。

[SAFE] 只存游戏名、结果名、各维度分，不存答案、不存用户原话、不存网址。
只有用户自己在话里提到测试（或结果名）时，recall 才把这块交给 prompt；
清空对话时与 memory.json / episodes 一起删。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import episode_store as es
import memory
import quiz_data

logger = logging.getLogger(__name__)

SUBDIR = "quiz"
MAX_ATTEMPTS = 20      # 留 20 次够了；再多也没人翻
SHOW_LAST = 3          # 塞进 prompt 只带最近 3 次，别把上下文撑爆
BLOCK_MAX = 640
TEXT_MAX = 24
KEY_MAX = 40
# 只有这些话头算“对方自己提起测试”；不问就永远不出现。
# “这个结果”这类指向自己在聊的那份结果的短句也算——但不能只收“结果”两个字，
# 否则“结果我还是没去”这种日常句会把测试块勾出来，成了 AI 主动想起。
CUES = ("测试", "测验", "小游戏", "答题", "问卷", "做过的题", "那个题",
        "这个结果", "这份结果", "那份结果")
# 对方想聊结果时多给一条“怎么聊”的指令；否则只按原样摆着，别主动展开。
ANALYZE_CUES = ("分析", "聊聊", "说说", "探讨", "怎么看", "什么意思", "准吗", "解读", "讨论")
ANALYZE_LINE = (
    "对方要聊这份结果：先说最高的一项是什么样，再说最低的一项，最后把两项放一起说一句；"
    "3–5 句、200 字以内，比平时长一点没关系。先给内容；最后想邀请对方说时再问一句，"
    "不必为了收尾硬加问句；不要整条只有一句反问，不要下结论说对方就是某种人，也不要建议对方改变。"
)


def _path(sid: str) -> Path:
    if not isinstance(sid, str) or not memory.ID_RE.match(sid):
        raise ValueError("session id 不合法")
    return memory.DATA_DIR / SUBDIR / f"{sid}.json"


def _clean_counts(raw: object) -> dict[str, int]:
    """维度分只留 0-99 的整数，最多 8 个；其他一律丢掉。"""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, val in raw.items():
        if len(out) >= 8:
            break
        name = es.clean_text(key, 8)
        if not name or isinstance(val, bool) or not isinstance(val, int):
            continue
        out[name] = max(0, min(99, val))
    return out


def _clean(raw: object) -> dict | None:
    """校验一条记录；形状不对就丢，脏数据不许进 prompt。"""
    if not isinstance(raw, dict):
        return None
    quiz_id = es.clean_text(raw.get("quiz"), TEXT_MAX)
    title = es.clean_text(raw.get("title"), TEXT_MAX)
    name = es.clean_text(raw.get("name"), TEXT_MAX)
    key = es.clean_text(raw.get("key"), KEY_MAX)
    if not (quiz_id and title and name and key):
        return None
    ts = raw.get("ts")
    ts = ts if isinstance(ts, int) and not isinstance(ts, bool) else 0
    return {"quiz": quiz_id, "title": title, "name": name, "key": key,
            "scores": _clean_counts(raw.get("scores")), "ts": max(0, ts)}


def read_store(sid: str) -> dict:
    """读这一区；文件坏了当空，读失败不许影响聊天。"""
    try:
        raw = es.read_json(_path(sid))
    except (OSError, ValueError) as exc:
        logger.warning("quiz_read_failed error=%s", type(exc).__name__)
        raw = None
    items = (raw or {}).get("attempts")
    rows = items if isinstance(items, list) else []
    attempts = [rec for rec in map(_clean, rows) if rec]
    return {"attempts": attempts[-MAX_ATTEMPTS:]}


def write_store(sid: str, store: dict) -> bool:
    """原子写；写失败只记类型名，不阻塞本轮。"""
    attempts = [rec for rec in map(_clean, store.get("attempts") or []) if rec]
    try:
        es.atomic_write(_path(sid), {"attempts": attempts[-MAX_ATTEMPTS:]})
        return True
    except OSError as exc:
        logger.warning("quiz_write_failed error=%s", type(exc).__name__)
        return False


def append(sid: str, result: dict) -> bool:
    """记一次结果；最多留 20 次，旧的先走。"""
    store = read_store(sid)
    rec = _clean({"quiz": result.get("quiz"), "title": result.get("title"),
                  "name": result.get("name"), "key": result.get("key"),
                  "scores": result.get("scores"), "ts": int(time.time())})
    if not rec:
        return False
    store["attempts"].append(rec)
    return write_store(sid, store)


def _fmt(rec: dict) -> str:
    """一行一次：日期 + 游戏 + 结果 + 非零维度。"""
    day = time.strftime("%m-%d", time.localtime(rec["ts"])) if rec["ts"] else ""
    scores = "、".join(f"{k} {v}" for k, v in rec["scores"].items() if v)
    line = f"- {day}《{rec['title']}》：{rec['name']}"
    return line + (f"（{scores}）" if scores else "")


def _note_line(rec: dict) -> str:
    """最近一次结果的维度解释；只解释有分的项，给模型一点抓手，不下定义。"""
    notes = (quiz_data.QUIZZES.get(rec["quiz"]) or {}).get("dim_notes") or {}
    parts = [f"{name}={notes[name]}" for name, val in rec["scores"].items()
             if val and name in notes]
    return ("维度：" + "；".join(parts)) if parts else ""


def _block(attempts: list[dict], analyze: bool = False) -> str:
    """给 prompt 的那一小块；语气上先按住“别主动提”，再按需要补怎么聊。"""
    lines = ["[趣味测试记录]（只在对方自己提起测试时用；不要主动提，不要拿结果评价对方）"]
    lines += [_fmt(rec) for rec in attempts[-SHOW_LAST:]]
    notes = _note_line(attempts[-1])
    if notes:
        lines.append(notes)
    if len(attempts) >= 2:
        lines.append("对方想对比时，把两次结果并排说清楚哪项高了、哪项低了；只当游戏，不给对方定性。")
    else:
        lines.append("只当游戏，不给对方定性；不要主动提起别的测试。")
    if analyze:
        lines.append(ANALYZE_LINE)
    return "\n".join(lines)[:BLOCK_MAX]


def recall(sid: str, text: str) -> str:
    """用户自己提起测试/结果名时才返回这块；否则空串（AI 不会主动想起）。"""
    if not text:
        return ""
    attempts = read_store(sid)["attempts"]
    if not attempts:
        return ""
    hit = any(cue in text for cue in CUES) or any(
        rec["title"] in text or rec["name"] in text for rec in attempts)
    if not hit:
        return ""
    return _block(attempts, analyze=any(cue in text for cue in ANALYZE_CUES))


def clear(sid: str) -> bool:
    """删正文 / .bak / .tmp；与 memory.clear_memory 一起由“清空”调用。"""
    path = _path(sid)
    removed = False
    for cand in (path, path.with_suffix(".json.bak"), path.with_suffix(".json.tmp")):
        if cand.exists():
            cand.unlink(missing_ok=True)
            removed = True
    return removed


def count(sid: str) -> int:
    """这一区存了几次；侧栏与测试用。"""
    return len(read_store(sid)["attempts"])
