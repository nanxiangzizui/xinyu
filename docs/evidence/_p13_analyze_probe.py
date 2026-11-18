"""_p13_analyze_probe.py — 打印“想分析结果”时真正送进 prompt 的那一块与总长度。

用法：.venv\\Scripts\\python.exe docs\\evidence\\_p13_analyze_probe.py
只读：数据目录用临时目录，不碰 data/memory。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="p13probe-")
os.environ["MOCK_LLM"] = "1"

import agent  # noqa: E402
import quiz_store  # noqa: E402
import roles  # noqa: E402

SID = "probe00000001"


def main() -> None:
    quiz_store.append(SID, {"quiz": "house", "title": "四院分院帽", "key": "ambition",
                            "name": "野心院",
                            "scores": {"勇气": 4, "思辨": 3, "野心": 5}})
    block = quiz_store.recall(SID, "帮我分析分析这个结果")
    print("---- block ----")
    print(block)
    print("---- block chars:", len(block), "----")

    mem = {"coping_preferences": "想找人说话", "emotion_tags": "累",
           "unresolved_issues": "作业", "rolling_summary": "摘要" * 100,
           "_quiz_text": block}
    sizes = {pid: len(agent.build_system_prompt(pid, mem, [])) for pid in roles.PERSONAS}
    print("---- prompt chars ----")
    for pid, size in sizes.items():
        print(f"{pid}: {size}")
    print("max:", max(sizes.values()))


if __name__ == "__main__":
    main()
