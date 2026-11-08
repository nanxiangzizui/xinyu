"""guardian.py — 安全审查层：规则 → 豁免 → 分级 → 复核，一票否决。"""
from __future__ import annotations

import re
import threading
import time

import agent
from roles import COMPILED, RULES

# 切小句：中英文标点都要覆盖。豁免只在一个小句内生效，绝不跨句。
CLAUSE_SPLIT = re.compile(r"[，。！？；、,.!?;~～\n\r]+")

# [SAFE] 这些词只要出现在 X 命中范围之外，就拒绝豁免——它们是“真的要出事”的信号。
HARD_WORDS = ("不想活", "活不下去", "自杀", "自残", "割腕", "遗书", "撑不下去", "熬不下去")

RANK = {"L1": 1, "L2": 2, "L3": 3}

# [SAFE] L3 一律发这段常量，不许模型生成、改写或让人设插手：
# 危机时刻的自由发挥就是风险本身。文案 ≤140 字，必须含 12356 与校心理中心电话。
# 换行用 \n，不用 markdown 列表符号（Streamlit 会渲染成列表）。
CRISIS_REPLY = (
    "听到你这么说，我很在意你现在的安全。\n\n"
    "先做一件事：找一个此刻能陪着你的人，或打 12356（24 小时热线）。\n"
    "情况紧急请打 110 或 120。\n"
    "校心理中心 0571-87713518（工作日）。\n\n"
    "我不问你发生了什么，也不劝你什么。你想说的时候，我在这儿。"
)


def split_clauses(text: str) -> list[str]:
    """按中英文标点切成小句；丢掉空白句。"""
    return [c.strip() for c in CLAUSE_SPLIT.split(text or "") if c.strip()]


def _hits(clause: str, group: str) -> list[dict]:
    """返回该小句命中的某个组的规则（按 RULES 里的顺序）。"""
    out = []
    for rule in RULES:
        if rule["group"] != group:
            continue
        rx = COMPILED.get(rule["rule_id"])
        if rx is None:                      # 坏正则已在 S08 校验拦截；运行时跳过不崩
            continue
        match = rx.search(clause)
        if match:
            out.append({"rule": rule, "span": (match.start(), match.end())})
    return out


def _covered(clause: str, hard: str, span: tuple[int, int]) -> bool:
    """硬词是否落在豁免命中范围内（在范围内才允许被豁免）。"""
    for match in re.finditer(re.escape(hard), clause):
        if not (span[0] <= match.start() and match.end() <= span[1]):
            return False
    return True


def _dedup(items: list[str]) -> list[str]:
    """去重且保序：dict.fromkeys 保留首次出现的位置。"""
    return list(dict.fromkeys(items))


def _raise(current: str, new: str) -> str:
    """等级只升不降：只有 new 更高才替换，否则保持 current。"""
    return new if RANK[new] > RANK[current] else current


def _exemption(clause: str, x_hits: list[dict]) -> tuple[bool, dict | None]:
    """X 组豁免判定：硬词只要有一个落在豁免 span 外，就当没豁免。"""
    if not x_hits:
        return False, None
    hit = x_hits[0]
    if not all(_covered(clause, h, hit["span"]) for h in HARD_WORDS if h in clause):
        return False, None
    return True, hit


def _judge_clause(clause: str) -> dict:
    """单个小句：X 豁免 → H → W；返回本句等级 / 命中 / 是否已被豁免。"""
    ids: list[str] = []
    reasons: list[str] = []
    level = "L1"

    exempt, x_hit = _exemption(clause, _hits(clause, "X"))
    if exempt:
        ids.append(x_hit["rule"]["rule_id"])
        reasons.append(x_hit["rule"]["why"])
        if x_hit["rule"]["action"] == "floor_l2":
            # X05 是降级不是豁免：命中要记录，等级抬到 L2。
            return {"level": _raise(level, "L2"), "ids": ids, "reasons": reasons,
                    "exempt_hit": False, "has_hit": True}
        return {"level": level, "ids": ids, "reasons": reasons,
                "exempt_hit": True, "has_hit": False}

    for group in ("H", "W"):
        hits = _hits(clause, group)
        if not hits:
            continue
        for hit in hits:
            ids.append(hit["rule"]["rule_id"])
            reasons.append(hit["rule"]["why"])
            # 等级只升不降：H 组命中一律 L3；W 组按规则自身的 level 抬地板。
            level = _raise(level, hit["rule"]["level"])
        return {"level": level, "ids": ids, "reasons": reasons,
                "exempt_hit": False, "has_hit": True}
    return {"level": level, "ids": ids, "reasons": reasons,
            "exempt_hit": False, "has_hit": False}


def scan(user_text: str) -> dict:
    """小句级扫描：X 豁免只在本小句内生效，H 命中即 L3，W 按规则抬地板。"""
    level = "L1"
    ids: list[str] = []
    reasons: list[str] = []
    any_exempt = False
    all_hits_exempt = True

    for clause in split_clauses(user_text):
        part = _judge_clause(clause)
        level = _raise(level, part["level"])
        ids += part["ids"]
        reasons += part["reasons"]
        any_exempt = any_exempt or part["exempt_hit"]
        all_hits_exempt = all_hits_exempt and not part["has_hit"]

    return {
        "level": level,
        "rule_ids": _dedup(ids),
        # 只有“整段唯一的命中都被豁免”才算 exempted：W 命中过就不算。
        "exempted": any_exempt and all_hits_exempt and level == "L1",
        "reason": "；".join(_dedup(reasons)) or "未命中规则",
    }


def guardian_pre_check(user_text: str) -> dict:
    """安全检查入口：只判等级，不生成回复。纯函数。"""
    return scan(user_text)


# [SAFE] 回复侧检查：诊断词、L3 缺资源、空回复。复检必须调用同一个函数，不许放水。
DIAG = re.compile(r"(你(得|患)了|你有.{0,6}倾向|你是.{0,4}症|抑郁症|焦虑症|建议服药|吃药)", re.I)
RESOURCE = re.compile(r"(12356|110|120|校心理中心)", re.I)
# [SAFE] 说教词只是体验层：不进 RULES、不改等级、不进召回/误拦分母。
# 它只做一件事——给重写加一条理由；重写不出来也允许原句发出（说教不是安全事故）。
SAYING = re.compile(r"(你应该|你必须|别想太多|这没什么|我当年|你要坚强|振作起来)")

# [SAFE] 兜底模板：crisis 直接复用 CRISIS_REPLY。
# 兜底与短路必须同一句话，否则同一个危机在两条路径上给出两种说法，口径会漂。
SAFE_FALLBACK = {
    "listener": "我在。你愿意说多少都可以，不想说也没关系。",
    "guide": "我不急着给你答案。你更想先理清哪一件事？",
    "crisis": CRISIS_REPLY,
}


def _violations(reply: str, level: str) -> list[str]:
    """检查回复本身的问题；返回原因列表。原回复与重写都过这一关。"""
    bad = []
    if not (reply or "").strip():
        bad.append("empty_reply")
    if DIAG.search(reply or ""):
        bad.append("diagnosis_language")
    if level == "L3" and not RESOURCE.search(reply or ""):
        bad.append("crisis_missing_resource")
    if SAYING.search(reply or ""):
        bad.append("preachy")
    return bad


# [SAFE] 复核 + 重写的总时间预算：卡住的模型等于没通过，不该再吃第二次等待。
LLM_BUDGET_S = 5.0


def _bounded_call(messages: list[dict], temperature: float, budget_s: float):
    """[SAFE] 按墙钟卡住一次模型调用：超时就返回 None，不让界面陪着等 15 秒。

    客户端 timeout=15 只是兜底（S04 口径），演示体验要的是 5 秒内有结果，
    所以这里用守护线程 join(budget)；超时的线程自己会随 15 秒超时结束，不阻塞退出。
    """
    if budget_s <= 0:
        return None
    box: dict = {}

    def run() -> None:
        try:
            box["out"] = agent.call_llm(messages, temperature)
        except Exception as exc:        # 边界：LLM 调用，异常交给调用方分类
            box["err"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(budget_s)
    if worker.is_alive():               # 预算用完 = 没有结果，按“不通过”处理
        return None
    if "err" in box:
        raise box["err"]
    return box.get("out")


def _review_messages(user_text: str, reply: str, level: str) -> list[dict]:
    """复核只看这一句回复与这一句用户输入：不带记忆、不带历史。"""
    return [
        {"role": "system", "content": agent.REVIEW_SYS},
        {"role": "user",
         "content": f"用户说：{user_text}\n助手回复：{reply}\n风险等级：{level}"},
    ]


def llm_review(user_text: str, reply: str, level: str, *, budget_s: float = LLM_BUDGET_S) -> dict:
    """模型自查回复；超时 / 调用失败 / 解析失败 / 字段缺失一律 pass=False。"""
    try:
        out = _bounded_call(_review_messages(user_text, reply, level), 0.2, budget_s)
        if not isinstance(out, dict) or not out.get("ok"):
            return {"pass": False, "reason": "review_call_failed"}
        data = agent.safe_json(out.get("text") or "")
        # 只认真正的布尔：模型给 "true" / "yes" 这类字符串一律当解析失败，
        # 否则“判据不可执行”会被读成“模型说没问题”。
        if not isinstance(data, dict) or not isinstance(data.get("pass"), bool):
            return {"pass": False, "reason": "review_parse_failed"}
        return {"pass": data["pass"], "reason": str(data.get("reason") or "")[:60]}
    except Exception as exc:            # 边界：LLM 调用（超时 / 网络 / 缺 Key）
        return {"pass": False, "reason": f"review_error_{type(exc).__name__}"}


def llm_rewrite(user_text: str, reply: str, reasons: list[str], role: str,
                *, budget_s: float = LLM_BUDGET_S) -> str | None:
    """带拒因重写一次；任何失败（含超预算）返回 None，由 post_check 走兜底。"""
    msgs = [
        {"role": "system", "content": agent.REWRITE_SYS},
        {"role": "user",
         "content": (f"用户说：{user_text}\n原回复：{reply}\n"
                     f"需要修正：{','.join(reasons)}\n角色：{role}")},
    ]
    try:
        out = _bounded_call(msgs, 0.5, budget_s)
    except Exception:                   # 边界：LLM 调用
        return None
    if not isinstance(out, dict) or not out.get("ok"):
        return None
    text = (out.get("text") or "").strip()
    return text or None


def _blocking(bad: list[str]) -> list[str]:
    """剔除体验层的 preachy：说教不是安全事故，不参与“能不能发出”的判定。"""
    return [item for item in bad if item != "preachy"]


def _rewrite_once(user_text: str, reply: str, bad: list[str], role: str,
                  rewriter, t0: float) -> str | None:
    """预算内重写一次：注入的 rewriter 优先，任何异常都当没写成。

    重写只此一次——循环重试会把“模型反复犯规”变成“跑到超时”。
    复核已经吃掉多少，重写就只剩多少：总预算 5 秒是硬要求，不是建议。
    """
    remaining = LLM_BUDGET_S - (time.monotonic() - t0)
    if remaining <= 0:
        return None
    try:
        if rewriter:
            return rewriter(user_text, reply, bad, role)
        return llm_rewrite(user_text, reply, bad, role, budget_s=remaining)
    except Exception:                   # 边界：注入的 rewriter（含测试替身）
        return None


def guardian_post_check(user_text: str, reply: str, level: str, role: str, rewriter=None) -> dict:
    """五步：复查 → 复核 → 重写 1 次 → 复检 → 兜底。不通过就不发。

    pass=False 的含义是“原回复不可用”，不是“不发消息”：永远要发一句安全的话，
    所以三段返回都带 fixed_reply 或可用的原文。
    """
    t0 = time.monotonic()
    bad = _violations(reply, level)
    if bad and not _blocking(bad):
        # [SAFE] 只有说教词：体验问题，重写一次；写不出来也允许原句发出。
        # 这条路径不升级、不兜底、不调复核——把体验问题当安全事故会让系统变成“处处拦”。
        fixed = _rewrite_once(user_text, reply, bad, role, rewriter, t0)
        if fixed and not _blocking(_violations(fixed, level)):
            return {"pass": True, "reason": "preachy", "fixed_reply": fixed,
                    "rewrite": 1, "template_fallback": False}
        return {"pass": True, "reason": "preachy", "fixed_reply": None,
                "rewrite": 0, "template_fallback": False}
    if not bad:
        # [SAFE] L3 是固定模板，复核只多一次等待；模板哨兵由 test 保证它自己过复检。
        # 没有规则问题、又不需要复核 / 复核通过 → 直接放行，不能掉进重写分支。
        review = None if level == "L3" else llm_review(
            user_text, reply, level, budget_s=LLM_BUDGET_S)
        if review is None or review["pass"]:
            return {"pass": True, "reason": "", "fixed_reply": None,
                    "rewrite": 0, "template_fallback": False}
        # 模型说不过 = 有问题，转去重写；判据用模型给的原因，缺了就写死标记。
        bad = [review["reason"] or "llm_review_rejected"]

    fixed = _rewrite_once(user_text, reply, bad, role, rewriter, t0)
    # 重写句只剩说教词时照发（体验问题不阻塞），但 rewrite=1 要记账。
    if fixed and not _blocking(_violations(fixed, level)):
        return {"pass": True, "reason": ",".join(bad), "fixed_reply": fixed,
                "rewrite": 1, "template_fallback": False}

    # role 来自 coordinator（内部），仍取不到就退 listener：兜底句永远不能缺。
    return {"pass": False, "reason": ",".join(bad),
            "fixed_reply": SAFE_FALLBACK.get(role) or SAFE_FALLBACK["listener"],
            "rewrite": 1 if fixed else 0, "template_fallback": True}
