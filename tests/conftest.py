"""conftest.py — 让 tests/ 能 import 项目根模块，并强制所有用例离线 + 独立磁盘。

为什么除了环境变量还要 monkeypatch.setattr：`memory.DATA_DIR` 与 `logger.LOG_DIR`
是模块级常量（import 时定死），光设环境变量对已经 import 的模块无效（S12 踩过）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import logger as logmod
import memory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    """S23：强制 MOCK + 每个用例独立目录，不联网、不碰仓库里的 data/。"""
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(memory, "DATA_DIR", tmp_path / "memory")
    monkeypatch.setattr(logmod, "LOG_DIR", str(tmp_path / "logs"))
    yield
