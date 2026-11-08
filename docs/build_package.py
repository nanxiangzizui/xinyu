# -*- coding: utf-8 -*-
"""S26 提交包构建：把要交给评委的文件复制成 心屿-v1.0/ 再打成一个 zip。

用法（bundled python）：
    python docs/build_package.py [输出 zip 路径]

规则来自 step/S26-ppt-demo.md §6：
- 四份材料放根目录（01_/02_/03_/04_）
- 源码 + tests + docs/evidence/ 一起进去
- 不含 .env / data/ / __pycache__ / .venv / 录屏原片 / 内部计划材料
"""
import hashlib
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_NAME = "心屿-v1.0"

# 四份材料在仓库 docs/ 下，进包时放根目录（step/S26 §6）
MATERIALS = [
    "01_项目文档.docx",
    "02_项目方案.pptx",
    "03_演示视频.mp4",
    "04_原型说明.md",
]

ROOT_FILES = [
    "app.py", "agent.py", "coordinator.py", "guardian.py", "memory.py",
    "panel.py", "resources.py", "roles.py", "logger.py", "theme.py",
    "contract_check.py", "metrics.py",
    "requirements.txt", "README.md", ".env.example", ".streamlit/config.toml",
]

# 整个目录一起拷，但跳过缓存与本地数据
DIR_TREES = ["tests", "docs/evidence"]
EXTRA_FILES = ["docs/demo-script.md", "docs/demo_timeline.json"]

SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_SUFFIX = {".pyc", ".pyo"}


def copy_tree(src: Path, dst: Path) -> int:
    n = 0
    for path in sorted(src.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in SKIP_SUFFIX or not path.is_file():
            continue
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        n += 1
    return n


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "心屿MindIsle_提交包_v1.0.zip"
    stage_root = Path(tempfile.mkdtemp(prefix="xy_pkg_"))
    pkg = stage_root / PKG_NAME
    pkg.mkdir(parents=True, exist_ok=True)

    for name in MATERIALS:
        src = ROOT / "docs" / name
        if not src.is_file():
            print("MISSING", name)
            return 1
        shutil.copy2(src, pkg / name)

    for name in ROOT_FILES:
        src = ROOT / name
        if not src.is_file():
            print("MISSING", name)
            return 1
        dst = pkg / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    count = 0
    for tree in DIR_TREES:
        count += copy_tree(ROOT / tree, pkg / tree)
    for name in EXTRA_FILES:
        src = ROOT / name
        if not src.is_file():
            print("MISSING", name)
            return 1
        shutil.copy2(src, pkg / name)

    files = [p for p in sorted(pkg.rglob("*")) if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print("materials", len(MATERIALS), "root files", len(ROOT_FILES), "tree files", count, "total files", len(files))
    for p in files:
        rel = p.relative_to(pkg).as_posix()
        print(f"{p.stat().st_size:>10}  {rel}")

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in files:
            zf.write(p, f"{PKG_NAME}/{p.relative_to(pkg).as_posix()}")

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print("ZIP", out)
    print("ZIP_BYTES", out.stat().st_size)
    print("TOTAL_BYTES", total)
    print("SHA256", digest.upper())
    shutil.rmtree(stage_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
