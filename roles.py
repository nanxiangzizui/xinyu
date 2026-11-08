"""roles.py — 常量 / 人设卡 / 规则表 / 主题，全项目唯一来源。"""
from __future__ import annotations

TIMEOUT = 15
N_WINDOW = 5
COOLDOWN = 3
SUMMARY_MAX = 200
SUMMARY_EVERY = 5

RULES: list[dict] = []      # S08 填 20 条
PERSONAS: dict = {}         # S07 填 5 张卡
THEMES: dict = {}           # S19 填 3 套
