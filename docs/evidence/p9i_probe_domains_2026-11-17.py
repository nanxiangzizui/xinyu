"""P9i 检索域名探测：看哪些查询能召回官方/Wiki/米游社。"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

import web  # noqa: E402

QUERIES = [
    "site:wiki.hoyolab.com 昔涟",
    "site:wiki.biligame.com 昔涟",
    "site:miyoushe.com 昔涟 角色",
    "崩坏：星穹铁道 昔涟 官方 角色介绍",
    "崩坏：星穹铁道 昔涟 米游社 剧情 经历",
    "Cyrene Honkai Star Rail wiki",
    "Honkai Star Rail Cyrene character story",
]

for query in QUERIES:
    data, err = web.search(query)
    print(f"\n### {query} -> {err or 'ok'}")
    for item in (data or {}).get("items") or []:
        print(" -", item.get("title"), item.get("url"))
