"""一次性：把 P9k 记录写进 .claude/CLAUDE.md（4 处精确替换，锚点缺失就报错）。"""
from pathlib import Path

PATH = Path(r"D:\deepseek harness\xinyu-agent\.claude\CLAUDE.md")
text = PATH.read_text(encoding="utf-8")

ROW_ANCHOR = "| P9j | 角色卡「继承上一张」"
ROW = (
    "| P9k | B prompt 决策顺序（2026-11-17 真人测试后）：从“禁令清单”改成“先定三件事 + 单一裁决” | ✅ | "
    "自称由卡名决定、卡外别名不作数；`user_role` 非普通身份时原作关系/共同经历**肯定成立**，"
    "普通身份才出“不是共同经历”；prompt 示例 1521、最坏 3290/4000；"
    "**302 + 1 = 303 passed**；契约 11+5+20；真 key 探针 3/3 自称昔涟、3/3 认共同经历 |\n"
)

BULLET_ANCHOR = "卡只存用户填的字段，不进 `memory.json`、不进日志。\n"
BULLET = (
    "- ✅ **P9k 完成（2026-11-17，真人测试后）**：用户判断“两个『不要』是根因，改 agent 思考的底层逻辑”。"
    "`rolecard._prompt_sections` 新增 `[开口前先定三件事]`（我是谁 / 对方是谁 / 这件事卡里有没有），排在 `[角色卡]` 之前，"
    "并写明“卡外的同名作品知识不作数，冲突时以卡为准”；`user_role` 分支从“可以按原作关系回应，但不要替对方编造经历”"
    "改成条件成立就肯定（非普通身份：原作关系与共同经历成立、可当旧事讲、不加卡里没有的细节），"
    "普通身份才保留“不是你和对方的共同经历”；`[身份与真实]` 增“被问怎么称呼自己：答「{name}」，不用卡外别名”；"
    "删掉与角色认知段重复的“不要把原作主角的经历当成对方的经历”。测试改 `test_user_role_and_stage_prompt` + 新增 "
    "`test_prompt_sets_decision_order_before_card`。出口：**303 passed**；契约 11+5+20；prompt 示例 1521、最坏 3290/4000；"
    "真 key 探针连跑 3 次，3 次自称“昔涟”、3 次认共同经历（`docs/evidence/P9k-anchor-probe-2026-11-17.txt`）；"
    "`metrics` 未跑（A 管线 / guardian / RULES 均未动）。\n"
)

for anchor, payload, before in (
    (ROW_ANCHOR, ROW, "after-row"),
    (BULLET_ANCHOR, BULLET, "after-bullet"),
):
    assert text.count(anchor) == 1, f"锚点不唯一或不存: {anchor!r} -> {text.count(anchor)}"
    if before == "after-row":
        line_end = text.index("\n", text.index(anchor)) + 1
        text = text[:line_end] + payload + text[line_end:]
    else:
        idx = text.index(anchor) + len(anchor)
        text = text[:idx] + payload + text[idx:]

text = text.replace(
    "**P0–P6a + P5+ + P7 + P8 + P9 + P9g + P9h + P9i + P9j 已完成**",
    "**P0–P6a + P5+ + P7 + P8 + P9 + P9g + P9h + P9i + P9j + P9k 已完成**", 1)
text = text.replace(
    "**注意：P9j 之后全量基线是 302（§0 / §3 / §7 里还写着 298 的是 P9j 前的数字）",
    "**注意：P9k 之后全量基线是 303（§0 / §3 里写 298 / 302 的是旧数字）", 1)
text = text.replace(
    "# 期望 298 passed（v2 P9i 后）", "# 期望 303 passed（v2 P9k 后）", 1)

OLD_HEAD = text.splitlines()[3]
assert OLD_HEAD.startswith("> 最后更新"), OLD_HEAD[:20]
NEW_HEAD = (
    "> 最后更新：2026-11-17（P9k 落地：B prompt 从“禁令清单”改成“先定三件事 + 卡 > 卡外知识”；"
    "自称按卡名，非普通身份的原作关系肯定成立；303 passed；"
    "证据 `docs/evidence/P9k-anchor-probe-2026-11-17.txt`）"
)
text = text.replace(OLD_HEAD, NEW_HEAD, 1)

PATH.write_text(text, encoding="utf-8")
print("done")
