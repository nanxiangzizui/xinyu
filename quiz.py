"""quiz.py — P13 趣味测试：计分、结果、报告与静默参考。

[SAFE] 结果只是游戏标签：不参与判危、不写 memory.json、不改等级。
报告正文过 guardian 一票否决；标题行与结尾那句由代码拼，不让模型编结果。
后台检索只为补常识，结果不进聊天、不显示来源。
"""
from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

import agent
import guardian
import quiz_data
import web

logger = logging.getLogger(__name__)

REPORT_MAX = 200      # 正文上限：一段总结，不是小作文
REPORT_TEMP = 0.8
REF_MAX = 2           # 一次最多两条参考
REF_CHARS = 120


def get(qid: str) -> dict | None:
    """按 id 取题库；未知 id 返回 None，界面当没点过处理。"""
    return quiz_data.QUIZZES.get(qid)


def _winner(dims: tuple[str, ...], group: tuple[int, ...],
            counts: dict[str, int]) -> int:
    """组内取分最高；平票取组内靠前那个，同一份答案永远同一个结果。"""
    best = group[0]
    for idx in group[1:]:
        if counts[dims[idx]] > counts[dims[best]]:
            best = idx
    return best


def score(quiz: dict, answers: list[int]) -> dict:
    """按选项累加维度分，返回结果键、名字、说明与各维度分。"""
    dims = quiz["dims"]
    counts = {name: 0 for name in dims}
    for qi, pick in enumerate(answers or []):
        if qi >= len(quiz["questions"]):
            break
        opts = quiz["questions"][qi]["opts"]
        if isinstance(pick, bool) or not isinstance(pick, int):
            continue
        if not 0 <= pick < len(opts):
            continue
        counts[opts[pick][1]] += 1
    key = "|".join(dims[_winner(dims, group, counts)] for group in quiz["groups"])
    res = quiz["results"].get(key) or next(iter(quiz["results"].values()))
    return {"key": key, "name": res["name"], "line": res["line"],
            "scores": counts, "quiz": quiz["id"], "title": quiz["title"]}


def host_allowed(url: str) -> bool:
    """只认白名单站点；子域算命中，http 与内网一律不信。"""
    try:
        if not web.is_safe_url(url):
            return False
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    if not host:
        return False
    return any(host == dom or host.endswith("." + dom)
               for dom in quiz_data.LOOKUP_DOMAINS)


def reference(quiz: dict, result: dict) -> list[str]:
    """后台静默检索：只留白名单站点的短句，失败就当没有（报告照写）。

    为什么不展示：用户要的是"拿不准时自己去查"，不是一屏链接；
    来源也不该由模型编，所以这里干脆只取正文、不取网址。
    """
    if os.getenv("ALLOW_WEB", "0").strip() != "1":
        return []
    query = quiz.get("lookup") or quiz["title"]
    try:
        data, err = web.search(query)
    except Exception as exc:                   # 边界：网络失败不影响报告
        logger.warning("quiz_lookup_failed error=%s", type(exc).__name__)
        return []
    if err or not isinstance(data, list):
        return []
    refs: list[str] = []
    for row in data:
        url = str((row or {}).get("url") or "")
        if not host_allowed(url):
            continue
        snippet = str((row or {}).get("snippet") or "").strip()[:REF_CHARS]
        if snippet:
            refs.append(snippet)
        if len(refs) >= REF_MAX:
            break
    return refs


def _score_line(quiz: dict, result: dict) -> str:
    """把各维度分拼成一行；0 分的不写，免得多出一串数字。"""
    names = quiz.get("dim_names") or {}
    parts = [f"{names.get(k, k)} {v}" for k, v in result["scores"].items() if v]
    return "、".join(parts)


def _report_prompt(quiz: dict, result: dict, refs: list[str]) -> str:
    """报告用的 user 消息：结果、分数、静默参考、边界要求。"""
    rows = [f"这次玩的小游戏：{quiz['title']}。",
            f"结果：{result['name']}。游戏自带的说明：{result['line']}"]
    line = _score_line(quiz, result)
    if line:
        rows.append(f"每道选择累计：{line}。")
    for ref in refs:
        rows.append(f"参考资料（只作背景，不要提来源、不要报网址）：{ref}")
    rows.append("请用 2-4 句给这次答题做个总结，像陪着做完随口说两句。")
    rows.append("只总结这次的结果：不引导、不追问、不给建议、不下判断、不承诺疗效；"
                "不说「你就是这样的人」「你应该」；不出现心理疾病名。")
    return "\n".join(rows)


def _clean_body(text: str) -> str:
    """去掉模型可能自己加的 CTA，再按句末截断。"""
    body = (text or "").replace(quiz_data.CTA, "").strip()
    if len(body) <= REPORT_MAX:
        return body
    cut = max(body.rfind(ch, 0, REPORT_MAX) for ch in "。！？")
    return body[:cut + 1] if cut > REPORT_MAX // 2 else body[:REPORT_MAX].rstrip() + "…"


def _template(result: dict) -> str:
    """模型失败或复核不过时的兜底：只说游戏自己的话。"""
    return f"{result['line']}\n这只是一个游戏标签，不代表你是什么样的人。"


def report(quiz: dict, result: dict) -> str:
    """生成整条报告消息：代码拼标题与 CTA，模型只写中间那段总结。"""
    refs = reference(quiz, result)
    prompt = _report_prompt(quiz, result, refs)
    out = agent.call_llm([{"role": "system", "content": agent.QUIZ_REPORT_SYS},
                          {"role": "user", "content": prompt}],
                         temperature=REPORT_TEMP)
    body = str(out.get("text") or "").strip()
    # [SAFE] 报告同样过一票否决：说教、下判断、追问都换模板，不换等级。
    # 说教词在 guardian 里只算体验问题（pass=True），但报告本来就不该给建议，所以一并换掉。
    post = guardian.guardian_post_check(prompt, body, "L1", "listener")
    if (not post.get("pass") or post.get("template_fallback")
            or post.get("reason") == "preachy"):
        body = ""
    body = _clean_body(body) or _template(result)
    return f"《{quiz['title']}》的结果：{result['name']}\n\n{body}\n\n{quiz_data.CTA}"
