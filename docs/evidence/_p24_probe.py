"""_p24_probe.py — P24 ① 真 key 探针：有这个钟点 vs 没有，模型答"现在几点"差在哪。

用法：.venv/Scripts/python.exe docs/evidence/_p24_probe.py
只读：不写 memory.json / 日志进临时目录；不发任何用户真实内容。
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ["MOCK_LLM"] = "0"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="p24-mem-")
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="p24-log-")

import agent  # noqa: E402
from roles import PERSONAS  # noqa: E402

ASK = "现在几点了？"
CTX = "都这个点了，我还没睡，明天早上八点的课。"
CN_DIGIT = "零一二三四五六七八九"
_CLOCK = datetime.now(agent.CN_TZ)


def _cn_hour(h: int) -> str:
    """18 → 十八，6 → 六，0 → 零；只用来认模型爱写的中文钟点。"""
    if h < 10:
        return CN_DIGIT[h]
    if h < 20:
        return "十" + (CN_DIGIT[h % 10] if h % 10 else "")
    return "二十" + (CN_DIGIT[h % 10] if h % 10 else "")


HOUR_CN = _cn_hour(_CLOCK.hour)


def ask(prompt: str, user_text: str) -> str:
    messages = [{"role": "system", "content": prompt},
                {"role": "user", "content": user_text}]
    return str(agent.call_llm(messages, temperature=0.7).get("text", "")).strip()


def strip_clock(prompt: str) -> str:
    """把 [现在] 段整个删掉，作为对照组（模拟 P24 之前）。"""
    head, sep, tail = prompt.partition("\n\n[现在]\n")
    if not sep:
        return prompt
    rest = tail.split("\n\n[最后提醒]", 1)
    return head + "\n\n[最后提醒]" + rest[1] if len(rest) == 2 else head


def says_clock(text: str) -> bool:
    """认中文或阿拉伯数字的钟点：六点四十 / 十八点 / 18:43 都算。"""
    h12 = _cn_hour(_CLOCK.hour % 12 or 12)   # 18 点模型常写成"六点"
    if any(f"{h}点" in text for h in (HOUR_CN, h12)):
        return True
    return bool(re.search(rf"\b{_CLOCK.hour}[:：]", text)) or f"{_CLOCK.hour}点" in text


def refuses(text: str) -> bool:
    return any(w in text for w in ("看不到", "不知道", "不确定", "没有钟", "查不到"))


def main() -> None:
    out: list[str] = []
    out.append(f"本机时钟 = {_CLOCK:%Y-%m-%d %H:%M}（UTC+8，中文小时={HOUR_CN}）")
    out.append("== A. 直接问时间（同一句系统提示，只差 [现在] 段）==")
    hit, refused = 0, 0
    for pid in PERSONAS:
        prompt = agent.build_system_prompt(pid, {}, [])
        with_clock = ask(prompt, ASK)
        without = ask(strip_clock(prompt), ASK)
        hit += 1 if says_clock(with_clock) else 0
        refused += 1 if refuses(without) else 0
        out.append(f"{pid}: 有钟点={with_clock!r} | 无钟点={without!r}")
    out.append(f"有钟点说出正确钟点: {hit}/5；无钟点承认看不到: {refused}/5")

    out.append("== B. 带时间的语境（五人设，检查有没有自己编钟点）==")
    for pid in PERSONAS:
        prompt = agent.build_system_prompt(pid, {}, [])
        reply = ask(prompt, CTX)
        out.append(f"{pid}: {reply!r} | 提到钟点={says_clock(reply)}")

    text = "\n".join(out)
    print(text)
    (ROOT / "docs" / "evidence" / "_p24_probe_out.txt").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
