"""P9i 已知作品的 Wiki 正文直连：搜索找不到中文官方页时，直接取角色页正文。

只接受按作品映射出来的固定 Wiki 主机 + 角色名，不接受用户给的任意 URL；
正文只当资料交给提取器，代码不执行其中的任何指令。
"""
from __future__ import annotations

import html
import re
import urllib.error
import urllib.parse
import urllib.request

import web

# 作品关键词 → Biligame Wiki 前缀；匹配用包含，不要求写全名。
WORK_WIKI = (
    (("星穹铁道", "Star Rail", "StarRail"), "https://wiki.biligame.com/sr/"),
    (("原神", "Genshin"), "https://wiki.biligame.com/ys/"),
    (("绝区零", "Zenless"), "https://wiki.biligame.com/zzz/"),
    (("崩坏3", "崩坏3rd", "Honkai Impact"), "https://wiki.biligame.com/bh3/"),
    (("鸣潮", "Wuthering"), "https://wiki.biligame.com/mc/"),
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
}
WIKI_TIMEOUT_S = 8
WIKI_MAX_BYTES = 2_000_000
WIKI_TEXT_MAX = 6000
WIKI_MIN_CHARS = 200
_BODY_RE = re.compile(r'<div class="mw-parser-output">(.*?)</div>\s*<div class="printfooter"', re.S)
_FALLBACK_BODY_RE = re.compile(r'<div class="mw-parser-output">(.*?)<!--', re.S)


def wiki_prefix(work: str) -> str:
    """按作品名找固定 Wiki 前缀；找不到返回空串。"""
    text = str(work or "").casefold()
    for keywords, prefix in WORK_WIKI:
        if any(keyword.casefold() in text for keyword in keywords):
            return prefix
    return ""


def _name_variants(name: str) -> list[str]:
    """带括号别名的卡名先试基名，再试全名；Biligame 角色页通常用基名。

    例如“白厄（卡厄斯兰那）”：全名页 404，基名“白厄”才是角色页。
    只剥末尾括号，避免把名字中间正当的括号当别名。
    """
    text = str(name or "").strip()
    if not text:
        return []
    base = re.sub(r"[（(【\[].*?[)）】\]]\s*$", "", text).strip()
    return [base, text] if base and base != text else [text]


def wiki_urls(card: dict, *, focus: str = "") -> list[str]:
    """按优先级返回 Wiki 地址：基名 → 全名；不做任意 URL 接受。"""
    prefix = wiki_prefix(card.get("work", ""))
    name = str(focus or card.get("name", "")).strip()
    if not prefix or not name:
        return []
    return [prefix + urllib.parse.quote(item, safe="") for item in _name_variants(name)]


def wiki_url(card: dict, *, focus: str = "") -> str:
    """兼容旧调用：返回第一个候选地址；完整候选用 wiki_urls。"""
    urls = wiki_urls(card, focus=focus)
    return urls[0] if urls else ""


def _http_text(url: str) -> tuple[str, str]:
    """取页面 HTML；网络/大小/安全错误都返回空串 + 错误码。"""
    if not web.is_safe_url(url):
        return "", "bad_url"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=WIKI_TIMEOUT_S) as resp:
            if not web.is_safe_url(resp.geturl()):
                return "", "bad_url"
            raw = resp.read(WIKI_MAX_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return "", "fetch_failed"
    if len(raw) > WIKI_MAX_BYTES:
        return "", "too_large"
    return raw.decode("utf-8", errors="replace"), ""


def _clean_body(page: str) -> str:
    """从 MediaWiki 页面里只取正文，去脚本/样式/标签；拿不到正文返回空串。"""
    match = _BODY_RE.search(page) or _FALLBACK_BODY_RE.search(page)
    if not match:
        return ""
    block = re.sub(r"<script.*?</script>|<style.*?</style>", " ", match.group(1), flags=re.S)
    block = html.unescape(re.sub(r"<[^>]+>", " ", block))
    return re.sub(r"\s+", " ", block).strip()


def fetch_text(url: str, *, fetch=None) -> tuple[str, str]:
    """取 Wiki 正文并截断；fetch 可注入，测试不联网。"""
    page, error = fetch(url) if fetch else _http_text(url)
    if error or not page:
        return "", error or "empty"
    text = _clean_body(page)[:WIKI_TEXT_MAX]
    return (text, "") if len(text) >= WIKI_MIN_CHARS else ("", "no_body")


def rows(card: dict, *, focus: str = "", fetch=None) -> list[dict]:
    """known 卡返回一条 Wiki 正文行；基名失败再试全名，仍拿不到就空。"""
    if card.get("origin") != "known":
        return []
    urls = wiki_urls(card, focus=focus)
    if not urls:
        return []
    name = str(focus or card.get("name", "")).strip()
    for url in urls:
        text, error = fetch_text(url, fetch=fetch)
        if error or not text:
            continue
        return [{"title": f"{card.get('work', '')} Wiki · {name}",
                 "url": url, "snippet": text}]
    return []
