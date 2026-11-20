"""P27 探针：首屏四选一分诊的两种状态（分诊 / 收起），只打印，不绑定测试。

跑：.\.venv\Scripts\python.exe -X utf8 docs\evidence\_p27_probe.py
输出：docs\evidence\P27-probe-2026-11-20.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from pipeline import Chat  # noqa: E402


def _click(at, key: str) -> None:
    [b for b in at.button if b.key == key][0].click().run()


def _dump(title: str, at) -> list[str]:
    lines = [f"== {title}", f"mode={at.session_state.get('mode')!r} "
             f"browse={at.session_state.get('home_browse_on')!r}"]
    lines.append("buttons: " + ", ".join(
        f"{b.key}={b.label}" for b in at.button))
    for kind in ("subheader", "markdown", "caption", "info"):
        for el in getattr(at, kind, [])[:6]:
            text = str(el.value).replace("\n", " ")
            lines.append(f"{kind}: {text[:90]}")
    lines.append("")
    return lines


def main() -> None:
    chat = Chat(enter=False)
    out = _dump("首屏分诊", chat.at)
    _click(chat.at, "home_browse")
    out += _dump("点「我只是逛逛」之后", chat.at)
    _click(chat.at, "home_triage_on")
    out += _dump("点「展开四个入口」之后", chat.at)
    target = Path(__file__).resolve().parent / "P27-probe-2026-11-20.txt"
    target.write_text("\n".join(out), encoding="utf-8")
    print("wrote", target.name, len(out), "lines")


if __name__ == "__main__":
    main()
