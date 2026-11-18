"""P16 探针：A 模式 listener 的问句收窄是否真的进了 system prompt。

离线运行：monkeypatch agent.call_llm，只捕获 prompt，不联网、不调真模型。
用法：.\.venv\Scripts\python.exe docs\evidence\_p16_listener_probe.py
"""

import os
import sys
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="p16-"))
os.environ["DATA_DIR"] = str(_tmp / "memory")
os.environ["LOG_DIR"] = str(_tmp / "logs")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import agent  # noqa: E402
import orchestrator  # noqa: E402
import style  # noqa: E402

captured: dict[str, str] = {}


def _fake_call_llm(messages, **kwargs):  # noqa: ANN001, ANN003
    captured["system"] = messages[0]["content"]
    return {"ok": True, "text": "我在。"}


orchestrator.AGENT_LOOP = False
agent.call_llm = _fake_call_llm


def _run(text: str, sid: str, history: list[dict]) -> tuple[dict, str]:
    captured.clear()
    result = orchestrator.handle(text, sid, history, "sister_heart", {})
    return result, captured.get("system", "")


report_history = [
    {"role": "user", "content": "做个测试"},
    {"role": "assistant",
     "content": "《阵营小坐标》的结果：随性·自守。想与我探讨一下测试结果吗？"},
]
res, prompt = _run("分析一下结果", "p16-listener", report_history)
print("== 1. listener + 上一条以问号收尾 ==")
print("role:", res.get("role"), "level:", res.get("level"))
for key in ("[这一轮：倾听者]", "非必要不反问", "不要用问句收尾", style.LISTENER_REPEAT):
    print(f"contains {key!r}:", key in prompt)
print("prompt chars:", len(prompt))
print("--- prompt tail ---")
print(prompt[-460:])

guide_res, guide_prompt = _run(
    "我该怎么办", "p16-guide", [{"role": "user", "content": "我该怎么办"}]
)
print("\n== 2. guide 不应出现 listener 段 ==")
print("role:", guide_res.get("role"))
print("contains listener head:", style.LISTENER_HEAD in guide_prompt)
print("prompt chars:", len(guide_prompt))

plain_res, plain_prompt = _run(
    "嗯", "p16-norepeat",
    [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "我在。"}],
)
print("\n== 3. listener 但上一条是陈述句 ==")
print("role:", plain_res.get("role"))
print("contains listener head:", style.LISTENER_HEAD in plain_prompt)
print("contains repeat hint:", style.LISTENER_REPEAT in plain_prompt)
print("prompt chars:", len(plain_prompt))
