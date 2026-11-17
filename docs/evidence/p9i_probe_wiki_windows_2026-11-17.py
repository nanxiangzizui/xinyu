"""P9i Wiki 正文切片：看角色故事/语音/关系关键词附近的内容。"""
from __future__ import annotations

from pathlib import Path

src = Path(__file__).resolve().parent / "P9i-wiki-body-2026-11-17.txt"
text = src.read_text(encoding="utf-8")
out = []
for section in ("### 昔涟", "### 白厄"):
    start = text.find(section)
    end = text.find("### ", start + 1)
    body = text[start:end if end != -1 else None]
    out.append(f"\n===== {section} =====")
    for keyword in ("角色故事", "角色语音", "角色详情", "白厄", "昔涟", "关系", "同伴", "开拓者"):
        pos = body.find(keyword)
        if pos == -1:
            continue
        out.append(f"\n--- {keyword} @ {pos} ---")
        out.append(body[max(0, pos - 200): pos + 1800])
Path(__file__).resolve().parent.joinpath("P9i-wiki-windows-2026-11-17.txt").write_text(
    "\n".join(out), encoding="utf-8")
print("wrote windows")
