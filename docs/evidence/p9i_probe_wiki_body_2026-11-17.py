"""P9i Wiki 正文探测：把 mw-parser-output 写到 UTF-8 文件，避免控制台 GBK。"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
out_path = Path(__file__).resolve().parent / "P9i-wiki-body-2026-11-17.txt"
parts = []
for name in ("昔涟", "白厄"):
    url = urllib.parse.quote(f"https://wiki.biligame.com/sr/{name}", safe=":/")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=8) as resp:
        text = resp.read(2_000_001).decode("utf-8", errors="replace")
    match = re.search(r'<div class="mw-parser-output">(.*?)</div>\s*<div class="printfooter"',
                      text, re.S)
    clean = ""
    if match:
        block = match.group(1)
        clean = re.sub(r"<script.*?</script>|<style.*?</style>", " ", block, flags=re.S)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
    parts.append(f"### {name} html={len(text)} clean={len(clean)}\n{clean}\n")
out_path.write_text("\n".join(parts), encoding="utf-8")
print("wrote", out_path, "bytes", out_path.stat().st_size)
