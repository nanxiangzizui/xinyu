"""test_no_secrets.py — 开源 / 交作业前的泄漏护栏（P21）。

为什么单开一个文件：这条守的不是业务行为，而是"仓库与提交包里不许有真密钥"
这条交付红线——项目要开源并交给学校评分，密钥只该待在本地 `.env` 与
Streamlit Cloud 的 Secrets 里。用例不联网、不读 `.env`、没 git 时自动跳过
跟踪检查，所以把提交包解压出来跑 pytest 也不会红。
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# 真实对话、虚拟环境、运行时数据、探针临时目录：本机才有，扫了没意义还会误报
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
             ".ruff_cache", "node_modules", "data", "assets", "真人测试"}
TEMP_DIR_RE = re.compile(r"^p[0-9]{2}[-_]|^pytest-of-")
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".json", ".jsonl", ".yml", ".yaml",
                 ".example", ".cfg", ".ini", ".html", ".css", ".js"}
LOCAL_SECRET_FILES = {".env", "secrets.toml"}

# 只认"真密钥的形状"：平台前缀 + 足够长，或"配置项后面接了 24 位以上的值"。
# 占位符（sk-your-own-key-here）与文档里的 sk-... 都不会命中。
KEY_PATTERNS = (
    ("sk- 前缀", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("tvly- 前缀", re.compile(r"tvly-[A-Za-z0-9]{10,}")),
    ("配置项被填了真值", re.compile(
        r"(?:BOCHA|TAVILY|LLM|WEB)_API_KEY\s*[=:]\s*[\"']?[A-Za-z0-9_\-]{24,}")),
)


def _iter_text_files():
    """仓库里要扫的文本文件：边遍历边剪掉不该进的目录，不去翻 .venv。"""
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not TEMP_DIR_RE.match(d)]
        for name in filenames:
            if name in LOCAL_SECRET_FILES or Path(name).suffix.lower() not in TEXT_SUFFIXES:
                continue
            yield Path(dirpath) / name


def test_repo_text_has_no_key_shaped_string():
    """仓库文本里不许出现密钥形状的字符串；真 key 只在被忽略的 .env 里。"""
    hits: list[str] = []
    for path in _iter_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in KEY_PATTERNS:
            found = pattern.search(text)
            if found:
                rel = path.relative_to(ROOT).as_posix()
                hits.append(f"{rel} [{label}] {found.group(0)[:6]}…")
    assert not hits, "疑似真实密钥（应放 .env / Secrets）：" + "; ".join(hits)


def test_secret_and_runtime_files_are_not_tracked():
    """.env / secrets.toml / data 下的运行数据都不许进 git。"""
    exe = shutil.which("git")
    if not exe or not (ROOT / ".git").exists():
        pytest.skip("没有 git 仓库（提交包解压后就是这样）")
    done = subprocess.run([exe, "ls-files"], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=60)
    tracked = done.stdout.splitlines()
    bad = [p for p in tracked if p in {".env", ".streamlit/secrets.toml"}]
    bad += [p for p in tracked if p.startswith("data/") and not p.endswith(".gitkeep")]
    assert bad == [], f"这些文件不该进 git：{bad[:8]}"


def test_ignore_rules_cover_runtime_paths():
    """运行时目录的**子目录**也要被忽略：P19 发现 data/memory/quiz/ 漏网。"""
    exe = shutil.which("git")
    if not exe or not (ROOT / ".git").exists():
        pytest.skip("没有 git 仓库（提交包解压后就是这样）")
    probes = [
        ".env", ".streamlit/secrets.toml",
        "data/memory/x.json", "data/memory/quiz/1.json", "data/memory/episodes/1.json",
        "data/memory/rolecards/1.json", "data/logs/2026-01-01.jsonl",
        "p19_abcd/memory/x.json",
    ]
    missing = [p for p in probes
               if subprocess.run([exe, "check-ignore", "-q", p], cwd=ROOT).returncode != 0]
    assert missing == [], f"这些路径没被 .gitignore 覆盖：{missing}"


def _load_packager():
    """按路径加载 docs/build_package.py：它不是包内模块，只能这样 import。"""
    spec = importlib.util.spec_from_file_location("build_package", ROOT / "docs" / "build_package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packager_refuses_env_data_and_keys(tmp_path):
    """提交包自检：.env 与 data/ 一旦落进包就中止，密钥形状的字符串也不放过。"""
    module = _load_packager()
    dirty = tmp_path / "dirty"
    (dirty / "data").mkdir(parents=True)
    (dirty / ".env").write_text("LLM_API_KEY=whatever", encoding="utf-8")
    (dirty / "data" / "memory.json").write_text("{}", encoding="utf-8")
    (dirty / "app.py").write_text("print(1)", encoding="utf-8")
    assert len(module._scan_package(dirty)) == 2

    leaky = tmp_path / "leaky"
    leaky.mkdir()
    (leaky / "notes.md").write_text("LLM_API_KEY=sk-" + "a" * 32, encoding="utf-8")
    assert len(module._scan_package(leaky)) == 1

    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "app.py").write_text("print(1)", encoding="utf-8")
    assert module._scan_package(clean) == []
