"""P30 探针：首页新组 + 三张机构页的按钮与文案（静态层，不调模型）。

跑：.\.venv\Scripts\python.exe docs\evidence\_p30_probe.py
输出：docs\evidence\P30-probe-2026-11-20.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from pipeline import Chat  # noqa: E402


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _text(at) -> str:
    kinds = ("subheader", "markdown", "info", "caption", "code",
             "success", "error", "warning")
    return " | ".join(str(el.value) for kind in kinds for el in getattr(at, kind, []))


chat = Chat(enter=False)
at = chat.at
out = ["home buttons: " + ", ".join(b.key for b in at.button), ""]
for key in ("home_teacher", "home_leave", "home_accompany"):
    _by_key(at.button, key).click().run()
    assert not list(at.exception), list(at.exception)
    out.append(f"== {key} -> mode={at.session_state['mode']} "
               f"page={at.session_state['help_page']}")
    out.append(_text(at)[:1200])
    out.append("")
    at.session_state["mode"] = "home"
    at.run()

Path("docs/evidence/P30-probe-2026-11-20.txt").write_text(
    "\n".join(out), encoding="utf-8")
print("ok", len(out))
