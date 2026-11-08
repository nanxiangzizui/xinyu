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

from agent import SUMMARY_SYS, call_llm
from roles import SUMMARY_EVERY, SUMMARY_MAX

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

# [SAFE] 摘要的两道隐私闸门：送进模型前只给 scrub 过的 40 字短句；
# 模型输出里若出现任一句 8 字以上原句，整次压缩作废（宁可摘要不更新，也不留原句）。
LINE_MAX = 40
QUOTE_MIN = 8
CRISIS_NOTE = "本会话出现过危机信号，需要保持关注。"

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

# S20 迷你 Lorebook：只写"能去哪问"，不写结论、不写政策解读、不写医疗建议。
# 每条 ≤25 字；子串匹配、最多 2 条、单轮总长 ≤100 字、同会话最多注入 3 次。
LORE_SEED = [
    {"keys": ["考试", "期末", "挂科"], "text": "多数课程有补考或重修，具体看教务通知。"},
    {"keys": ["保研", "绩点", "排名"], "text": "保研看综合成绩，各院系细则不同。"},
    {"keys": ["宿舍", "室友", "矛盾"], "text": "宿舍矛盾可找辅导员或宿管协调。"},
    {"keys": ["心理咨询", "心理中心", "预约"], "text": "校心理中心一般免费，需提前预约。"},
    {"keys": ["失眠", "睡不着", "熬夜"], "text": "长期失眠建议先看校医院，别自行用药。"},
    {"keys": ["实习", "找工作", "简历"], "text": "学校就业中心提供简历修改与模拟面试。"},
    {"keys": ["家里", "父母", "经济"], "text": "经济困难可申请助学金或临时困难补助。"},
    {"keys": ["转专业", "休学", "退学"], "text": "学籍变动须走教务流程，先问辅导员。"},
]
LORE_INJECT_MAX = 100
LORE_USED_MAX = 3
LORE_MAX_ITEMS = 2
# [SAFE] 模块级可变状态的唯一例外：只影响"少说两句"，不影响风险等级与发不发。
_lore_used: dict[str, int] = {}


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


def scrub(text: str) -> str:
    """对外脱敏入口（面板展示 / 导出用）：覆盖五类标识 + 200 字截断。"""
    return _scrub(text if isinstance(text, str) else "")


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


def should_compress(turn: int, summary_len: int, summary_at_turn: int, level: str) -> bool:
    """三个条件任一成立就压：满 5 轮 / 超 200 字 / 首次进入 L3 留档。"""
    if level == "L3" and summary_at_turn == 0:
        return True
    if turn - summary_at_turn >= SUMMARY_EVERY:
        return True
    return summary_len > SUMMARY_MAX


def recent_lines(history: list[dict]) -> list[str]:
    """把最近的对话切成短句**并 scrub**；绝不把完整原话交给摘要模型。"""
    out: list[str] = []
    for msg in (history or [])[-(SUMMARY_EVERY * 2):]:
        text = msg.get("content") if isinstance(msg, dict) else ""
        if isinstance(text, str) and text.strip():
            out.append(_scrub(text.strip())[:LINE_MAX])
    return out


def _quotes_source(summary: str, sources: list[str]) -> bool:
    """摘要里是否出现源句的 8 字以上片段；命中说明模型在抄原话。"""
    for src in sources:
        for i in range(max(0, len(src) - QUOTE_MIN + 1)):
            if src[i:i + QUOTE_MIN] in summary:
                return True
    return False


def compress_summary(old_summary: str, lines: list[str]) -> str | None:
    """压一次摘要；失败 / 抄原句 / 无新内容都返回 None，调用方保留旧值。"""
    recent = [_scrub(str(x))[:LINE_MAX] for x in (lines or [])[-SUMMARY_EVERY * 2:]
              if str(x).strip()]
    if not recent:
        # 没有新对话就拿旧摘要自压，只会越压越空（SKILL §3.3 的坑）。
        return None
    prompt = ("旧摘要：" + (old_summary or "无") + "\n近期对话：\n" + "\n".join(recent))
    out = call_llm([{"role": "system", "content": SUMMARY_SYS},
                    {"role": "user", "content": prompt}], temperature=0.3)
    if not out.get("ok") or not out.get("text"):
        logger.warning("summary_call_failed")
        return None
    summary = " ".join(str(out["text"]).split())
    if not summary:
        return None
    if _quotes_source(summary, recent):
        logger.warning("summary_quote_blocked")
        return None
    if len(summary) > SUMMARY_MAX:
        logger.warning("summary_truncated len=%s", len(summary))
        summary = summary[:SUMMARY_MAX]
    return summary


def mark_crisis_summary(session_id: str, turn: int) -> str:
    """首次 L3 的留档：不调模型，只追加一行标记——断网也必须能留档。"""
    mem = read_memory(session_id)
    base = mem["rolling_summary"].strip()
    mem["rolling_summary"] = ((base + "；" + CRISIS_NOTE) if base else CRISIS_NOTE)[:SUMMARY_MAX]
    mem["summary_at_turn"] = turn
    write_memory(session_id, mem)
    return mem["rolling_summary"]


def clear_memory(session_id: str) -> bool:
    """真删：正文、备份、临时文件三个都删，否则“清空”是假的。"""
    path = _path(session_id)
    removed = False
    for cand in (path, _bak(path), _tmp(path)):
        if cand.exists():
            cand.unlink(missing_ok=True)
            removed = True
    _lore_used.pop(session_id, None)      # 清空记忆也要让"最多 3 次"的计数归零
    return removed


def match_lore(user_text: str, session_id: str = "") -> list[str]:
    """命中关键词返回 1–2 条校园常识；同会话最多注入 3 次，防复读。"""
    if not user_text:
        return []
    sid = session_id if isinstance(session_id, str) else ""
    if sid and _lore_used.get(sid, 0) >= LORE_USED_MAX:
        return []
    out: list[str] = []
    total = 0
    for entry in LORE_SEED:
        if not any(k in user_text for k in entry["keys"]):
            continue
        text = entry["text"]
        if total + len(text) > LORE_INJECT_MAX:
            break
        out.append(text)
        total += len(text)
        if len(out) >= LORE_MAX_ITEMS:
            break
    if out and sid:
        _lore_used[sid] = _lore_used.get(sid, 0) + 1
    return out
