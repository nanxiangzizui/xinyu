"""风格指纹：30 条固定输入 × 5 人设，量「AI 味」的六个可复现指标。

为什么要有它：改口吻最容易变成「我觉得自然多了」。先量基线，改，再量一次，
两份 JSON 并排看，才知道是真起了作用，还是把一种腔调换成了另一种。
指标全是代码算的，不用人脑记；判断仍然留给人（见 docs/evidence/P23-*）。

跑法：
    .\\.venv\\Scripts\\python.exe docs\\evidence\\style_fingerprint.py --tag before
    .\\.venv\\Scripts\\python.exe docs\\evidence\\style_fingerprint.py --tag after
    .\\.venv\\Scripts\\python.exe docs\\evidence\\style_fingerprint.py `
        --compare docs\\evidence\\style_fingerprint_before.json `
                  docs\\evidence\\style_fingerprint_after.json

没有 LLM_API_KEY 时自动退到 MOCK：只验证脚本和指标能跑通，数字没有意义（会警告）。
输入是本项目自造的泛化场景，不含任何真人倾诉；不写仓库 data/，不用真实 key 落盘。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "evidence"

# agent.py 也会 load_dotenv()，但那是在 import 之后；这里要先读 .env 才知道有没有 key。
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

# 30 条 = 5 人设 × 6 个场景。全是 L1 的日常话：L2/L3 由模板与安全确认接管，
# 不该拿风格指标去评——那两档的第一目标是别出错，不是好听。
SITUATIONS = (
    "今天有点累，什么都不想干。",
    "我妈又打电话来了，问我什么时候回家。",
    "昨天跟室友吵了一架，现在还在想这件事。",
    "马上要交的东西还没做完，心里发慌。",
    "今天下课一个人去吃了饭，感觉还行。",
    "躺了一个小时了，还是睡不着。",
)

# 具体物代理指标：数字、时间词、身体动作。只是代理，不比真值更准，胜在两次跑口径一致。
_CONCRETE = re.compile(
    r"[0-9０-９]|点半|分钟|小时|今天|今晚|明天|早上|中午|下午|晚上|现在|马上|"
    r"喝|吃|睡|躺|走|站|坐|洗|开|关|拿|写|发|晒|呼吸"
)
_END = re.compile(r"[。！？!?…]+[”’」』）)\]]*")

# 基线（v3.1）还没有 style.stale_hits；这份副本只为让 before/after 用同一把尺。
_FALLBACK_STALE = (
    "首先", "其次", "总之", "总而言之", "希望对你有帮助", "希望能帮到你",
    "你可以试试", "慢慢来", "相信自己", "你能做到的", "一切都会好的",
    "我理解你的感受", "建议你",
)


def stale_count(text: str) -> int:
    """有 style.stale_hits 就用它，没有（基线）就用副本，口径保持一致。"""
    if hasattr(style, "stale_hits"):
        return len(style.stale_hits(text))
    return sum(1 for p in _FALLBACK_STALE if p in text)


def sentences(text: str) -> list[str]:
    """按句末标点切句（与 style._sentences 同口径，但探针不复用私有函数）。"""
    return [s for s in _END.split(text or "") if s.strip()]


def longest_common(a: str, b: str) -> int:
    """最长公共子串长度：量「对方的词被原样接回来多少」。"""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for ch in a:
        cur = [0] * (len(b) + 1)
        for j, other in enumerate(b, 1):
            if ch == other:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def metrics(reply: str, user_text: str) -> dict:
    """一条回复的六个指标；空回复返回 0，不当成「完美」。"""
    sents = sentences(reply)
    lens = [len(s) for s in sents]
    mean = statistics.fmean(lens) if lens else 0.0
    cv = (statistics.pstdev(lens) / mean) if len(lens) > 1 and mean else 0.0
    return {
        "chars": len(reply),
        "sents": len(sents),
        "sent_mean": round(mean, 1),
        "sent_cv": round(cv, 3),
        "q_end": 1 if reply.rstrip().endswith(("？", "?")) else 0,
        "stale": stale_count(reply),
        "echo": longest_common(user_text, reply),
        "concrete": len(_CONCRETE.findall(reply)),
    }


def listener_hint_of(history: list[dict]) -> str:
    """同一份探针要能跑基线（v3.1，没有 level 参数）与工作树两版。"""
    try:
        return style.listener_hint(history, "L1")
    except TypeError:
        return style.listener_hint(history)


def run_turn(persona_id: str, text: str, sid: str, history: list[dict],
             state: dict) -> dict:
    """跑一轮真实管线；异常记成一项，不中断 30 条里的其余样本。"""
    try:
        res = orchestrator.handle(text, sid, history, persona_id, state)
    except Exception as exc:                        # 探针要把失败记下来，不伪装成回复
        return {"reply": "", "error": f"{type(exc).__name__}: {exc}",
                "role": "", "level": "", "template_fallback": False}
    return {"reply": res.get("reply", ""), "error": "", "role": res.get("role", ""),
            "level": res.get("level", ""),
            "template_fallback": bool(res.get("template_fallback"))}


def collect(mock: bool) -> dict:
    """跑 30 条单轮 + 一段 4 轮议程对话，返回可落盘的记录。"""
    samples: list[dict] = []
    for persona_id in roles.PERSONAS:
        for i, text in enumerate(SITUATIONS):
            sid = f"fp-{persona_id}-{i}"
            got = run_turn(persona_id, text, sid, [{"role": "user", "content": text}], {})
            row = {"persona": persona_id, "user": text, **got}
            row["metrics"] = metrics(row["reply"], text)
            samples.append(row)
            print(f"  {persona_id:<16} {text[:12]}… -> {row['reply'][:40]}")

    dialog, history = [], []
    state: dict = {}
    for text in ("今天有点累", "不知道，就是提不起劲", "试过了，没用", "嗯"):
        history.append({"role": "user", "content": text})
        hint = listener_hint_of(history)
        got = run_turn("sister_heart", text, "fp-dialog", history, state)
        dialog.append({"user": text, "hint": hint, **got})
        print(f"  [对话] {text} -> {got['reply'][:60]}")
        if hint:
            print(f"         hint={hint[:50]}…")
        history.append({"role": "assistant", "content": got["reply"]})

    return {
        "tag": "", "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mock": mock, "model": os.getenv("LLM_MODEL", ""),
        "agenda": bool(getattr(style, "AGENDA", False)),
        "samples": samples, "dialog": dialog,
    }


def summarize(samples: list[dict]) -> dict:
    """只统计真正走模型的 L1 样本；L3 / 模板兜底 / 报错的样本单独计数。"""
    used = [r for r in samples
            if r["level"] == "L1" and not r["template_fallback"] and not r["error"]]
    skipped = len(samples) - len(used)
    if not used:
        return {"n": 0, "skipped": skipped}
    out = {"n": len(used), "skipped": skipped,
           "roles": {r: sum(1 for x in used if x["role"] == r)
                     for r in ("listener", "guide")}}
    for key in ("chars", "sent_mean", "sent_cv", "q_end", "stale", "echo", "concrete"):
        vals = [x["metrics"][key] for x in used]
        out[key] = round(statistics.fmean(vals), 2)
    return out


# 方向：True 表示越大越好。只给改前改后看趋势用，不是评分。
DIRECTION = {"chars": None, "sent_mean": None, "sent_cv": None,
             "q_end": False, "stale": False, "echo": True, "concrete": True}


def compare(path_a: Path, path_b: Path) -> int:
    """两份 JSON 并排打印差值与方向；不改文件、不判好坏。"""
    a = json.loads(path_a.read_text(encoding="utf-8"))
    b = json.loads(path_b.read_text(encoding="utf-8"))
    sa, sb = summarize(a["samples"]), summarize(b["samples"])
    print(f"{'指标':<12}{'改前':>10}{'改后':>10}{'差':>9}  方向")
    for key in ("chars", "sent_mean", "sent_cv", "q_end", "stale", "echo", "concrete"):
        if key not in sa or key not in sb:
            continue
        diff = sb[key] - sa[key]
        good = DIRECTION[key]
        mark = "" if good is None else ("↑好" if (diff > 0) == good else "↓差")
        print(f"{key:<12}{sa[key]:>10}{sb[key]:>10}{diff:>+9.2f}  {mark}")
    print(f"\n样本 {sa.get('n')} / {sb.get('n')}；标签 {a.get('tag')} → {b.get('tag')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="心屿风格指纹")
    ap.add_argument("--tag", default="run", help="输出文件名后缀，如 before / after")
    ap.add_argument("--mock", action="store_true", help="强制离线（数字无意义）")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"), help="比较两份 JSON")
    args = ap.parse_args()
    if args.compare:
        return compare(Path(args.compare[0]), Path(args.compare[1]))

    has_key = bool(os.getenv("LLM_API_KEY"))
    mock = args.mock or not has_key
    tmp = Path(tempfile.mkdtemp(prefix="fp-"))
    os.environ["MOCK_LLM"] = "1" if mock else "0"
    os.environ.setdefault("AGENT_LOOP", "1")
    os.environ.setdefault("ALLOW_WEB", "0")
    os.environ["DATA_DIR"] = str(tmp / "memory")
    os.environ["LOG_DIR"] = str(tmp / "logs")
    (tmp / "memory").mkdir(parents=True, exist_ok=True)
    (tmp / "logs").mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))

    global orchestrator, roles, style
    import orchestrator  # noqa: E402
    import roles  # noqa: E402
    import style  # noqa: E402

    if mock:
        print("[WARN] 没有 LLM_API_KEY 或指定了 --mock：以下数字仅验证脚本，不可用于对比。")
    print(f"[info] model={os.getenv('LLM_MODEL')} agenda={getattr(style, 'AGENDA', None)} "
          f"temp=0.7 samples={len(roles.PERSONAS) * len(SITUATIONS)}")
    data = collect(mock)
    data["tag"] = args.tag
    data["summary"] = summarize(data["samples"])
    out = OUT_DIR / f"style_fingerprint_{args.tag}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + json.dumps(data["summary"], ensure_ascii=False, indent=2))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
