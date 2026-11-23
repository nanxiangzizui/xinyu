# -*- coding: utf-8 -*-
"""提交包构建：把要交给评委的文件复制成 心屿-v3.3/ 再打成一个 zip。

用法（bundled python）：
    python docs/build_package.py [输出 zip 路径]

规则来自 step/S26-ppt-demo.md §6，P21 另加一条开源红线：
- 四份材料放根目录（01_/02_/03_/04_）
- 源码取根目录**全部** *.py：不再维护白名单，新模块落地即进包，
  不会出现"包里少一个 rolecard_memory.py、评委那边起不来"这种事
- 绝不收 .env / .streamlit/secrets.toml / data/；落包前再自检一遍，
  命中禁忌路径或密钥形状的字符串就中止，不出 zip
"""
import hashlib
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_NAME = "心屿-v3.3"

# 四份材料在仓库 docs/ 下，进包时放根目录（step/S26 §6）
MATERIALS = [
    "01_项目文档.docx",
    "02_项目方案.pptx",
    "03_演示视频.mp4",
    "04_原型说明.md",
]

# 非 .py 的根文件；.py 由 _root_modules() 现扫
ROOT_FILES = [
    "requirements.txt", "README.md", ".env.example", ".streamlit/config.toml",
]

# 整个目录一起拷，但跳过缓存与本地数据
DIR_TREES = ["tests", "docs/evidence"]
EXTRA_FILES = ["docs/demo-script.md", "docs/demo_timeline.json"]

SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_SUFFIX = {".pyc", ".pyo"}
# [SAFE] 构建日志与解压复跑日志都描述“这个包”，打进包会自指；留在仓库即可
SKIP_FILES = {"p6_package_build_2026-11-13.txt", "p6_package_pytest_2026-11-13.txt"}

# [SAFE] P21 开源红线：这些路径出现在包里 = 打包方式错了，直接中止
FORBIDDEN_NAMES = {".env", "secrets.toml"}
FORBIDDEN_PREFIXES = ("data/",)
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".json", ".jsonl", ".example", ".cfg", ".ini"}
# 只认“真密钥的形状”：平台前缀 + 足够长；sk-your-own-key-here 这类占位符不命中
KEY_RE = re.compile(r"sk-[A-Za-z0-9]{20,}|tvly-[A-Za-z0-9]{10,}")


def _root_modules() -> list[str]:
    """根目录全部 .py 就是源码清单：加模块不用改这里，少一个也瞒不过去。"""
    return sorted(p.name for p in ROOT.glob("*.py"))


def copy_tree(src: Path, dst: Path) -> int:
    """整棵目录拷进包：跳过缓存目录、字节码与自指日志，返回拷贝的文件数。"""
    n = 0
    for path in sorted(src.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in SKIP_SUFFIX or path.name in SKIP_FILES or not path.is_file():
            continue
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        n += 1
    return n


def _copy_checked(pkg: Path, pairs: list[tuple[Path, Path]]) -> bool:
    """逐个复制；任何一个源文件缺失就报名字并返回 False，不带着缺口继续打包。"""
    for src, dst in pairs:
        if not src.is_file():
            print("MISSING", src.relative_to(ROOT).as_posix())
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return True


def _scan_package(pkg: Path) -> list[str]:
    """落包自检：禁忌路径 + 密钥形状字符串。返回问题清单，空表示干净。"""
    problems: list[str] = []
    for path in pkg.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(pkg).as_posix()
        if path.name in FORBIDDEN_NAMES or rel.startswith(FORBIDDEN_PREFIXES):
            problems.append(f"禁忌文件进包：{rel}")
        elif path.suffix.lower() in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if KEY_RE.search(text):
                problems.append(f"疑似密钥：{rel}")
    return problems


def _write_zip(pkg: Path, out: Path) -> None:
    """先打印全部清单（便于人眼过一遍），再压缩，最后报大小与 SHA256。"""
    files = [p for p in sorted(pkg.rglob("*")) if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print("root modules", len(_root_modules()), "total files", len(files))
    for p in files:
        print(f"{p.stat().st_size:>10}  {p.relative_to(pkg).as_posix()}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in files:
            zf.write(p, f"{PKG_NAME}/{p.relative_to(pkg).as_posix()}")
    print("ZIP", out)
    print("ZIP_BYTES", out.stat().st_size)
    print("TOTAL_BYTES", total)
    print("SHA256", hashlib.sha256(out.read_bytes()).hexdigest().upper())


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "心屿MindIsle_提交包_v3.3.zip"
    stage_root = Path(tempfile.mkdtemp(prefix="xy_pkg_"))
    pkg = stage_root / PKG_NAME
    pkg.mkdir(parents=True, exist_ok=True)

    pairs = [(ROOT / "docs" / n, pkg / n) for n in MATERIALS]
    pairs += [(ROOT / n, pkg / n) for n in _root_modules() + ROOT_FILES]
    ok = _copy_checked(pkg, pairs)
    if ok:
        for tree in DIR_TREES:
            copy_tree(ROOT / tree, pkg / tree)
        ok = _copy_checked(pkg, [(ROOT / n, pkg / n) for n in EXTRA_FILES])

    problems = _scan_package(pkg) if ok else []
    if problems or not ok:
        for item in problems:
            print("LEAK", item)
        print("ABORT：包不干净或缺文件，未生成 zip")
        shutil.rmtree(stage_root, ignore_errors=True)
        return 2

    _write_zip(pkg, out)
    shutil.rmtree(stage_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
