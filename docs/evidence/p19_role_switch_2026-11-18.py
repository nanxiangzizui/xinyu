"""P19 探针：A 模式侧栏「当前角色」选择器的真实渲染与行为（2026-11-18）。

只读探针：MOCK_LLM=1，DATA_DIR / LOG_DIR 指向临时目录，不碰仓库里的 data/。
跑法（仓库根目录）：.\.venv\Scripts\python.exe docs\evidence\p19_role_switch_2026-11-18.py
输出同时写进同目录的 p19_role_switch_2026-11-18.txt（UTF-8，避免控制台代码页干扰）。
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).with_suffix(".txt")
_TMP = pathlib.Path(tempfile.mkdtemp(prefix="p19_"))

os.environ["MOCK_LLM"] = "1"
os.environ["DATA_DIR"] = str(_TMP / "memory")
os.environ["LOG_DIR"] = str(_TMP / "logs")
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

LINES: list[str] = []


def emit(text: str = "") -> None:
    """记一行到报告文件，同时打一份到控制台。"""
    LINES.append(text)
    print(text)


def enter_chat() -> AppTest:
    """从列表首页点进聊天页；返回 AppTest 实例。"""
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at.run()
    [b for b in at.button if b.key == "home_chat"][0].click().run()
    assert not list(at.exception), list(at.exception)
    return at


def box_of(at: AppTest):
    return [b for b in at.selectbox if b.key == "role_pick"][0]


def role_captions(at: AppTest) -> list[str]:
    """只看选择器自己写的两句，别把记忆面板的 caption 混进来。"""
    try:
        return [c.value for c in at.sidebar.caption
                if c.value.startswith(("这一轮：", "手动选择"))]
    except AttributeError:                     # 老版本 AppTest 没有 caption 收集器
        return []


def say(at: AppTest, text: str) -> None:
    at.chat_input[0].set_value(text).run()
    assert not list(at.exception), list(at.exception)


def state(at: AppTest) -> str:
    return (f"last_role={at.session_state['last_role']} "
            f"last_reason={at.session_state['last_reason']}")


def main() -> None:
    at = enter_chat()
    box = box_of(at)
    emit(f"label    : {box.label}")
    emit(f"options  : {box.options}")
    emit(f"current  : {box.value} / index {box.index}")
    emit(f"caption  : {role_captions(at)}")
    emit(f"侧栏 metric 只剩: {[m.label for m in at.sidebar.metric]}")

    emit("\n--- 选「引导者」后说一句普通的话 ---")
    box_of(at).select("guide").run()
    emit(f"caption  : {role_captions(at)}")
    say(at, "今天有点累")
    emit(state(at))

    emit("\n--- 选「倾听者」后说危机句 ---")
    box_of(at).select("listener").run()
    say(at, "我不想活了")
    emit(state(at))

    emit("\n--- 危机后改选「引导者」，再说一句求助 ---")
    box_of(at).select("guide").run()
    say(at, "我该怎么办")
    emit(state(at))
    emit(f"caption  : {role_captions(at)}")

    emit("\n--- 选回「自动判断」 ---")
    box_of(at).select("auto").run()
    say(at, "今天天气不错")
    emit(state(at))
    emit(f"caption  : {role_captions(at)}")

    OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
