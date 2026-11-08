"""app.py — Streamlit 页面：免责声明 / 聊天区 / 侧栏 / 固定七步管线。

管线顺序从 S05 起冻结（后续步骤只换零件，不换顺序）：
    判危 → 定角色 → 找事实 → 拼 prompt → 生成 → 审 → 记
"""
from __future__ import annotations

import logging
import os
import re
import time
import uuid

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# 线上（Streamlit Cloud）没有 .env，密钥只放在平台的 Secrets 里，读法是 `st.secrets`，
# 不是环境变量。必须在 import memory / agent 之前铺好：memory.py 的 DATA_DIR 是模块级常量。
_SECRET_KEYS = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "MOCK_LLM",
                "DATA_DIR", "LOG_DIR")


def _bridge_secrets() -> None:
    """把 st.secrets 铺进环境变量，只补空缺，不覆盖已有值。

    [SAFE] 这里必须兜底：本地没有 secrets.toml 时读取会抛异常，
    线上没配 Secrets 时也不该崩——真正缺 Key 由 _config_gate 报，不在这里报两遍。
    """
    try:
        items = st.secrets.to_dict() if hasattr(st.secrets, "to_dict") else dict(st.secrets)
    except Exception:                       # 边界：没有 Secrets 是正常情况
        return
    for key in _SECRET_KEYS:
        val = items.get(key)
        if val is not None and not os.getenv(key):
            os.environ[key] = str(val)


_bridge_secrets()

from agent import build_system_prompt, call_llm              # noqa: E402  顺序要紧
from coordinator import (aggregate_level, coordinator_decide,  # noqa: E402
                         enforce_cooldown)
from guardian import CRISIS_REPLY, guardian_post_check, guardian_pre_check  # noqa: E402
from logger import log_turn, session_hash                     # noqa: E402
from memory import (clear_memory, compress_summary, mark_crisis_summary,  # noqa: E402
                    match_lore, read_memory, recent_lines, should_compress,
                    update_memory, write_memory)
from panel import LEVEL_LABELS, REASON_LABELS, ROLE_LABELS, render_panel  # noqa: E402
from resources import pick_resources                          # noqa: E402
from roles import COOLDOWN, N_WINDOW                          # noqa: E402
from theme import inject_theme, theme_picker                  # noqa: E402

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "这是一个情绪陪伴工具，不是心理咨询，也不能替代真人帮助。"
    "如果你或身边的人有危险，请拨打 120 / 110 或 12356。"
)
FALLBACK_LINE = "我这边刚刚卡了一下，但我在。你可以再说一句吗？"
NET_HINT = "网络不稳定：刚才那条是兜底回复"
DEFAULT_PERSONA = "sister_heart"

# 与 memory.py 的 ID_RE 同口径：会话 id 来自 URL，必须先校验再交给磁盘层。
SID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")


def get_session_id() -> str:
    """会话 id 只放 URL：session_state 刷新即空，放那里记忆就断了。"""
    raw = st.query_params.get("u")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if isinstance(raw, str) and SID_RE.fullmatch(raw):
        return raw
    sid = uuid.uuid4().hex[:12]
    st.query_params["u"] = sid
    return sid


def _mark_crisis() -> None:
    """L3 当轮置冷却与永久标记。

    先置 COOLDOWN 再减 1：L3 这一轮本身已短路，不计入余量，
    之后还有 COOLDOWN-1 轮处于冷却（S11 §5.4）。
    """
    st.session_state["cooldown"] = COOLDOWN
    st.session_state["ever_crisis"] = True
    st.session_state["cooldown"] = max(0, st.session_state["cooldown"] - 1)


def _log_turn(sid: str, level: str, role: str, rule_ids: list[str],
              action: str, rewrite: int, t0: float) -> None:
    """结构化日志唯一出口：只过白名单，不带任何原文。"""
    log_turn(session_hash=session_hash(sid),
             turn=st.session_state.get("turn", 0),
             level=level, role=role, rule_ids=rule_ids,
             action=action, rewrite=rewrite,
             latency_ms=int((time.perf_counter() - t0) * 1000))


def _effective_level(raw: str) -> tuple[str, bool]:
    """[SAFE] 会话聚合只升不降：窗口内真实 L2+ ≥3 次升 L3，出现过 L2+ 则地板 L2。

    窗口只存 pre 的原始等级，不存聚合后的 eff，否则地板抬上来的 L2 会自己凑数升级。
    """
    levels = list(st.session_state.get("levels", []))
    eff = aggregate_level(levels, raw)
    # 只有升到 L3 的那轮存 eff：存地板抬上来的 L2 会让平静轮自己凑成“3 次 L2”。
    st.session_state["levels"] = (levels + [eff if eff == "L3" else raw])[-N_WINDOW:]
    return eff, eff != raw


def _maybe_compress(sid: str, level: str, role: str,
                    history: list[dict], t0: float) -> None:
    """摘要节流：满 5 轮 / 超 200 字 / 首次 L3 压一次；失败保留旧摘要。

    [SAFE] L3 分支不调模型：危机回复必须断网可用，这里只写结构化标记留档。
    """
    mem = read_memory(sid)
    turn = st.session_state.get("turn", 0)
    if not should_compress(turn, len(mem["rolling_summary"]),
                           mem["summary_at_turn"], level):
        return
    if level == "L3":
        mark_crisis_summary(sid, turn)
        _log_turn(sid, level, role, ["SUMMARY_CRISIS"], "summary_compress", 0, t0)
        return
    new_summary = compress_summary(mem["rolling_summary"], recent_lines(history))
    if not new_summary:
        # 没压成就不写盘：旧摘要比空摘要有用，也不许把“没压成”记成压过了。
        _log_turn(sid, level, role, ["SUMMARY_FAILED"], "summary_compress", 0, t0)
        return
    mem["rolling_summary"] = new_summary
    mem["summary_at_turn"] = turn
    write_memory(sid, mem)
    _log_turn(sid, level, role, [], "summary_compress", 0, t0)


def _crisis_result(sid: str, pre: dict, escalated: bool, t0: float) -> dict:
    """L3 短路：固定模板 + 资源卡，不调 LLM、不加载人设、不写记忆。"""
    _mark_crisis()
    # 聚合升级与原始 L3 用不同 action，报告里才能分清“自己说出来的”和“被窗口推上来的”。
    action = "aggregate_escalate" if escalated else "short_circuit"
    _log_turn(sid, "L3", "crisis", pre["rule_ids"], action, 0, t0)
    _maybe_compress(sid, "L3", "crisis", [], t0)
    return {"reply": CRISIS_REPLY, "level": "L3", "role": "crisis",
            "reason": "crisis_shortcircuit",
            "degraded": False, "short_circuit": True}


def _log_and_result(sid: str, pre: dict, dec: dict, eff_level: str, escalated: bool,
                    post: dict, resp: dict, reply: str, t0: float) -> dict:
    """审后收尾：action 只取执行书四值，日志单行，等级原样往下传。"""
    if escalated:
        # 本轮等级被聚合抬高：优先记这件事，短路/重写原因由 rule_ids 与 rewrite 保留。
        action = "aggregate_escalate"
    elif post.get("template_fallback"):
        action = "template_fallback"
    else:
        action = "rewrite" if post.get("rewrite") else "pass"
    logged_ids = list(pre["rule_ids"])
    if "preachy" in (post.get("reason") or ""):
        # [SAFE] 执行书 §5.3.1：说教词不进 RULES，但日志要能和 H / W 组区分开。
        logged_ids.append("SAYING")
    _log_turn(sid, eff_level, dec["role"], logged_ids,
              action, post.get("rewrite", 0), t0)
    return {
        "reply": reply,
        "level": eff_level,
        "role": dec["role"],
        "reason": dec["reason"],
        # 只看字符串会把“模型失败、guardian 换成安全兜底”误判成正常回复（S13 起会发生）。
        "degraded": (not resp.get("ok", False)) or reply == FALLBACK_LINE,
    }


def handle(text: str, sid: str, history: list[dict], persona_id: str) -> dict:
    """七步固定管线；异常交给 safe_handle，不在这里吞。"""
    t0 = time.perf_counter()
    memory = read_memory(sid)                                      # 前置：读记忆
    pre = guardian_pre_check(text)                                 # 1 判危
    eff_level, escalated = _effective_level(pre["level"])          # 1.5 会话聚合
    if eff_level == "L3":
        # [SAFE] L3 一律短路，这一轮到此为止；等级不许被后续步骤下调。
        return _crisis_result(sid, pre, escalated, t0)
    dec = coordinator_decide(memory, text, eff_level)              # 2 定角色
    # [SAFE] 冷却/历史危机只降 guide，不碰 crisis；L3 已在上面短路，等级不会被这里下调。
    dec = enforce_cooldown(dec, st.session_state.get("cooldown", 0),
                           st.session_state.get("ever_crisis", False))
    st.session_state["cooldown"] = max(0, st.session_state.get("cooldown", 0) - 1)
    lore = match_lore(text, sid)                                   # 3 找事实（sid 用于同会话限次）
    prompt = build_system_prompt(persona_id, memory, lore)         # 4 拼 prompt
    resp = call_llm([{"role": "system", "content": prompt},        # 5 生成
                     *history[-10:]])
    post = guardian_post_check(text, resp.get("text", ""),         # 6 审
                               eff_level, dec["role"])
    reply = post.get("fixed_reply") or resp.get("text") or FALLBACK_LINE
    update_memory(sid, text, reply)                                # 7 记
    _maybe_compress(sid, eff_level, dec["role"], history, t0)      # 7.5 摘要节流
    return _log_and_result(sid, pre, dec, eff_level, escalated,
                           post, resp, reply, t0)


def safe_handle(text: str, sid: str, history: list[dict], persona_id: str) -> dict:
    """任何异常都变成一句人话；日志只记类型名，不记原文与堆栈。"""
    t0 = time.perf_counter()
    try:
        return handle(text, sid, history, persona_id)
    except Exception as exc:                       # 边界：界面永不显示 traceback
        logger.warning("pipeline_failed session=%s error=%s",
                       sid[:6], type(exc).__name__)
        # 判危失败时风险未知，按中风险记录；绝不按 L1 当“没事”。
        # [SAFE] S23 F-01：崩掉的这一轮也要留一行结构化日志，否则“日志行数 = 用户轮次”
        # 在故障时就对不上。异常类型名只进上面的 WARN，结构字段里只放 PIPELINE_FAILED 标记。
        try:
            _log_turn(sid, "L2", "listener", ["PIPELINE_FAILED"],
                      "template_fallback", 0, t0)
        except Exception:                          # 边界：日志本身失败也不许抛回界面
            pass
        return {"reply": FALLBACK_LINE, "level": "L2", "role": "listener",
                "reason": "default", "degraded": True}


def _config_gate() -> None:
    """配置错误当场报，不许伪装成"网络不稳定"。
    缺 Key 时每一轮都会走到 safe_handle，用户看到的却是一句"卡了一下"，排查会跑错方向。
    """
    if os.getenv("MOCK_LLM", "0").strip() == "1":
        return
    if not os.getenv("LLM_API_KEY"):
        st.error("未配置 LLM_API_KEY：请在 .env 填入 Key，或设 MOCK_LLM=1 离线运行。")
        st.stop()


def _render_history(messages: list[dict]) -> None:
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


def _clear(sid: str) -> None:
    """真删记忆并换新会话：不换 id 的话，侧栏一读记忆文件就会被重建。"""
    try:
        clear_memory(sid)
    except OSError as exc:                          # 边界：删不掉也不许崩页面
        logger.warning("clear_failed session=%s error=%s", sid[:6], type(exc).__name__)
    st.session_state.messages = []
    st.session_state["degraded"] = False
    st.session_state["turn"] = 0
    # 清空对话 = 开新会话：冷却与“有过危机”标记必须一起归零，否则新对话永远回不到 guide。
    st.session_state["cooldown"] = 0
    st.session_state["ever_crisis"] = False
    st.session_state["last_role"] = "listener"
    st.session_state["last_level"] = "L1"
    st.session_state["last_reason"] = "default"
    st.session_state["levels"] = []
    st.query_params["u"] = uuid.uuid4().hex[:12]
    st.rerun()


def _sidebar(sid: str) -> None:
    with st.sidebar:
        turn = st.session_state.get("turn", 0)
        level = st.session_state.get("last_level", "L1")
        role = st.session_state.get("last_role", "listener")
        reason = st.session_state.get("last_reason", "default")
        st.caption(f"会话 {session_hash(sid)[:6]} · 第 {turn} 轮")
        st.metric("当前风险等级", LEVEL_LABELS.get(level, level))
        st.metric("当前角色", ROLE_LABELS.get(role, role))
        st.caption(f"切换原因：{REASON_LABELS.get(reason, reason)}")
        if os.getenv("MOCK_LLM", "0").strip() == "1":
            st.caption("离线演示模式（MOCK）")
        if st.session_state.get("degraded"):
            st.caption(NET_HINT)
        render_panel(sid, _clear)


def main() -> None:
    st.set_page_config(page_title="心屿 · 情绪陪伴", layout="centered")
    st.title("心屿")
    st.caption(DISCLAIMER)                         # 第一屏常驻，不折叠
    _config_gate()

    # 主题注入必须早于聊天区渲染；选择器是侧栏第一项，_sidebar 的内容排在它后面。
    inject_theme(theme_picker())

    sid = get_session_id()
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("persona_id", DEFAULT_PERSONA)
    # 冷却与“有过危机”只活在本会话：刷新即重置，这是 S11 的既定口径，不是 bug。
    for key, default in (("cooldown", 0), ("ever_crisis", False),
                         ("last_role", "listener"), ("last_level", "L1"),
                         ("last_reason", "default"), ("turn", 0),
                         ("levels", [])):
        st.session_state.setdefault(key, default)

    _render_history(st.session_state.messages)

    text = (st.chat_input("说说你现在想说的…") or "").strip()
    if text:
        st.session_state["turn"] += 1
        st.session_state.messages.append({"role": "user", "content": text})
        with st.chat_message("user"):
            st.markdown(text)
        with st.chat_message("assistant"):
            with st.spinner("我在听…"):
                result = safe_handle(text, sid, st.session_state.messages,
                                     st.session_state.persona_id)
            st.markdown(result["reply"])
            # [SAFE] S10 §8：L2/L3 当轮各出一次资源卡（L2 两张 / L3 三张），L1 为空不打扰。
            # 卡只渲染在本轮，不写进 messages，刷新重绘时不会重复弹（S21 #4 补的口径）。
            for card in pick_resources(result["level"], []):
                st.info(f"{card['title']}：{card['detail']}")
        st.session_state.messages.append({"role": "assistant", "content": result["reply"]})
        st.session_state["degraded"] = result["degraded"]
        st.session_state["last_role"] = result["role"]
        st.session_state["last_level"] = result["level"]
        st.session_state["last_reason"] = result.get("reason", "default")

    _sidebar(sid)


if __name__ == "__main__":
    main()