"""_p23b_probe.py — P23 ①② 的真 key 探针：情境示例进 prompt 后的长度/人设差异 + 建卡示例生成。

用法：.venv/Scripts/python.exe docs/evidence/_p23b_probe.py
只读：不写 memory.json / 日志进临时目录；卡是虚构的。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ["MOCK_LLM"] = "0"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="p23b-mem-")
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="p23b-log-")

import agent  # noqa: E402
import examples  # noqa: E402
import style  # noqa: E402
from roles import PERSONAS  # noqa: E402

TEXT = "今天有点累，什么都不想干"
CARD = {
    "name": "守夜人", "identity": "负责在夜里巡灯的守夜人，话少，习惯先看再说",
    "setting": "一座靠海的小城，冬天风很大，灯塔由守夜人轮值",
    "voice": "短句，不用感叹号，偶尔提一句天气或灯",
    "address": "你", "user_role": "用户", "taboos": ["我懂你", "你应该"],
}


def tag_and_prompt(out: list[str]) -> None:
    out.append("== ① 情境示例 ==")
    out.append(f"tag_of: {examples.tag_of(TEXT)}")
    for pid in PERSONAS:
        prompt = agent.build_system_prompt(pid, {"_situation": "tired"}, [])
        out.append(f"{pid}: len={len(prompt)} has_block={'[同类情境]' in prompt}")
    out.append("== 五人设第一句（真 key，temperature=0.7）==")
    target = examples.SITUATIONS["tired"]["replies"]
    got = []
    for pid in PERSONAS:
        messages = [{"role": "system", "content": agent.build_system_prompt(pid, {"_situation": "tired"}, [])},
                    {"role": "user", "content": TEXT}]
        resp = agent.call_llm(messages, temperature=0.7)
        text = resp.get("text", "")
        got.append(text.strip())
        out.append(f"{pid}: {text!r} | 照抄示例={'YES' if text.strip() == target[pid] else 'no'}")
    out.append(f"五人设互不相同: {len(set(got))}/5")


def card_examples(out: list[str]) -> None:
    out.append("== ② 建卡示例候选 ==")
    pairs = examples.card_candidates(CARD)
    out.append(f"count: {len(pairs)}")
    for user_text, role_text in pairs:
        out.append(f"- 用户：{user_text} / 角色：{role_text}")


if __name__ == "__main__":
    lines: list[str] = []
    tag_and_prompt(lines)
    card_examples(lines)
    lines.append(f"AGENDA={getattr(style, 'AGENDA', None)} MOCK={agent._is_mock()}")
    path = Path(__file__).with_name("_p23b_probe_out.txt")
    path.write_text("\n".join(lines), encoding="utf-8")
    print("written:", path)

