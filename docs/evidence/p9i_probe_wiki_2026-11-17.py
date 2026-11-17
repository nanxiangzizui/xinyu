"""P9i 直连 Wiki 探测：Biligame 的角色页能否直接抓到正文。"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request

URLS = [
    "https://wiki.biligame.com/sr/昔涟",
    "https://wiki.biligame.com/sr/白厄",
    "https://wiki.biligame.com/sr/首页",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

for raw in URLS:
    url = urllib.parse.quote(raw, safe=":/")
    print("\n###", url)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read(2_000_001)
            text = body.decode("utf-8", errors="replace")
            title = re.search(r"<title>(.*?)</title>", text, re.S)
            clean = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S)
            clean = re.sub(r"<[^>]+>", " ", clean)
            clean = re.sub(r"\s+", " ", clean).strip()
            print("status", resp.status, "bytes", len(body), "final", resp.geturl())
            print("title", (title.group(1).strip() if title else "")[:120])
            print("text", clean[:400])
    except Exception as exc:  # noqa: BLE001 - 探测脚本
        print("error", type(exc).__name__, str(exc)[:200])
