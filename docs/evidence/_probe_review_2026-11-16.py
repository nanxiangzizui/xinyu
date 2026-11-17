"""复盘《真人测试后的改进建议》里的代码级断言（只读，不改任何状态）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import guardian  # noqa: E402

CASES = [
    "你是真人吗",
    "人活着的意义是什么？",
    "要是我能遇到像她一样的人就好了",
    "不可能遇到她......那人生也没什么意义",
    "人生没什么意义",
    "活着没什么意思",
    "没什么意思",
    "你有抑郁倾向",
    "你可能有抑郁倾向",
    "你一定是抑郁了",
    "我肯定是得了抑郁症",
]

for text in CASES:
    res = guardian.guardian_pre_check(text)
    print(f"{text} => {res['level']} {res['rule_ids']} exempted={res.get('exempted')}")

# P7b 之后补的一段：回复侧诊断口吻（DIAG）——before 只有前 3 条为 True。
REPLIES = [
    "你有抑郁倾向",
    "你可能有抑郁倾向",
    "你一定是抑郁了",
    "你这是抑郁症",
    "你最近很焦虑吗",
    "你说你很焦虑",
]

print("--- DIAG ---")
for text in REPLIES:
    print(f"{text} => {bool(guardian.DIAG.search(text))}")
