"""P9i 真实 smoke：昔涟建卡检索 + 白厄盲点补全（只跑一次，不写盘、不写记忆）。

用法：.venv\\Scripts\\python.exe docs/evidence/p9i_smoke_2026-11-17.py
输出：控制台 + docs/evidence/P9i-enrich-smoke-2026-11-17.txt（UTF-8）
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

import rolecard  # noqa: E402
import rolecard_enrich  # noqa: E402
import rolecard_form  # noqa: E402
import rolecard_gap  # noqa: E402

CARD = {
    "kind": "rolecard", "origin": "known", "work": "崩坏：星穹铁道", "name": "昔涟",
    "identity": "哀丽秘榭的女儿，世界反面的记录者",
    "setting": "她来自世界反面，习惯记录；对开拓者和同行的人有很深的记忆。",
    "voice": "句子轻，常用呀/呢/好吗收尾；会请求对方呼唤自己的名字；不用括号写动作。",
    "address": "你", "user_role": "用户", "stage": "none",
    "examples": [("在吗", "在呀。"), ("今天有点累", "那就先歇一会儿吧，我陪着你。")],
    "lore": [], "taboos": ["我懂你", "你应该", "你必须"],
}


def _print_facts(title: str, result: dict) -> None:
    print(f"\n=== {title} ===")
    print("ok:", result.get("ok"), "error:", result.get("error"),
          "focus:", result.get("focus"))
    print("queries:", rolecard_enrich.build_queries(CARD, result.get("focus") or ""))
    print("sources:")
    for src in result.get("sources") or []:
        print(" -", src.get("title"), src.get("url"),
              "|", rolecard_enrich.authority_for(src.get("url") or ""))
    print("facts:")
    for fact in result.get("facts") or []:
        print(f" - [{fact.get('field')}] {fact.get('text')} "
              f"(source={fact.get('source', '')}, authority={fact.get('authority', '')})")
    print("conflicts:")
    for item in result.get("conflicts") or []:
        print(" -", rolecard_form.conflict_text(item))


def _print_merge(title: str, card: dict, result: dict) -> dict:
    merged, conflicts = rolecard_enrich.merge(card, result.get("facts") or [])
    print(f"\n=== {title} ===")
    print("lore:", len(merged.get("lore") or []),
          "chars:", sum(len(item) for item in merged.get("lore") or []))
    for item in merged.get("lore") or []:
        print(" -", item)
    print("merge conflicts:")
    for item in conflicts:
        print(" -", rolecard_form.conflict_text(item))
    print("validate:", rolecard.validate(merged))
    return merged


def main() -> None:
    assert rolecard.validate(CARD) == [], rolecard.validate(CARD)
    print("prompt chars:", len(rolecard.build_prompt(CARD, {}, [])))
    creation = rolecard_enrich.enrich(CARD)
    _print_facts("建卡：昔涟（Wiki 直连 + 1 次提取）", creation)
    merged = _print_merge("建卡 merge：昔涟", CARD, creation)
    focus = rolecard_enrich.enrich(CARD, focus="白厄")
    _print_facts("盲点：白厄（Wiki 直连 + 1 次提取）", focus)
    lines = rolecard_gap.gap_lines(
        rolecard_enrich.auto_facts(focus.get("facts") or []), focus="白厄")
    print("\n=== 盲点临时资料（不写入角色卡） ===")
    print("gap lines:", len(lines))
    for item in lines:
        print(" -", item)
    prompt = rolecard.build_prompt({**merged, "_gap": lines}, {}, [])
    print("gap prompt chars:", len(prompt))
    assert "[本轮盲点资料]" in prompt and "白厄的经历" in prompt


if __name__ == "__main__":
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        main()
    finally:
        sys.stdout = old
    text = buf.getvalue()
    out = ROOT / "docs" / "evidence" / "P9i-enrich-smoke-2026-11-17.txt"
    out.write_text(text, encoding="utf-8")
    print(text.encode("gbk", errors="replace").decode("gbk"))
    print("wrote", out)
