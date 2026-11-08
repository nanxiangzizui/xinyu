"""_probe_s19.py — AppTest 验证三套主题可选、CSS 随选择变化、对话不受影响。"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ["MOCK_LLM"] = "1"

import memory  # noqa: E402
import logger  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402
from theme import THEMES, theme_css  # noqa: E402

tmp = pathlib.Path(tempfile.mkdtemp(prefix="xinyu_s19_"))
memory.DATA_DIR = tmp / "mem"
logger.LOG_DIR = tmp / "logs"
memory.DATA_DIR.mkdir()
logger.LOG_DIR.mkdir()

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
print("exceptions:", len(at.exception))
radios = at.sidebar.radio
print("radio count:", len(radios))
print("radio label/options:", radios[0].label, list(radios[0].options))
print("default value:", radios[0].value)

styles = [m.value for m in at.markdown if "<style>" in m.value]
print("style blocks:", len(styles), "| sakura css in page:", any(THEMES["sakura"]["bg"] in s for s in styles))
print("no cdn in style:", all("http" not in s for s in styles))

at.sidebar.radio[0].set_value("matcha").run()
styles = [m.value for m in at.markdown if "<style>" in m.value]
print("after matcha | green bg present:", any(THEMES["matcha"]["bg"] in s for s in styles),
      "| sakura bg gone:", all(THEMES["sakura"]["bg"] not in s for s in styles))

at.sidebar.radio[0].set_value("sunset").run()
styles = [m.value for m in at.markdown if "<style>" in m.value]
print("after sunset | orange bg present:", any(THEMES["sunset"]["bg"] in s for s in styles))

at.chat_input[0].set_value("今天有点累").run()
print("chat exceptions:", len(at.exception))
print("assistant msgs:", len(at.chat_message), "| last:", at.chat_message[-1].markdown[0].value[:40])
print("style still sunset:", any(THEMES["sunset"]["bg"] in m.value for m in at.markdown if "<style>" in m.value))
print("expected css len equal:", len(theme_css("sunset")))
print("tmp:", tmp)
