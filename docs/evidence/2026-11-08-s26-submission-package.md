# S26 · 提交包与解压实测

> 文件名沿用 2026-11-09（原定计划日期）；**本文件实际生成于 2026-11-08**。

## 1 产出

| 产物 | 位置 | 说明 |
|---|---|---|
| 提交包 zip | `D:\deepseek harness\心屿MindIsle_提交包_v1.0.zip`（仓库外，5 MB 二进制不入库） | 108 个文件，解压后顶层目录 `心屿-v1.0/` |
| 打包脚本 | `docs/build_package.py`（入库，可重跑） | 复制 → 打 zip → 打印清单与 SHA-256 |
| 包内四份材料 | `01_项目文档.docx` / `02_项目方案.pptx` / `03_演示视频.mp4` / `04_原型说明.md` | 从仓库 `docs/` 提到包根目录，符合 step §6 的目录图 |

实测数字：

```text
total files 108   (materials 4 + root 16 + tests 9 + docs 79)
未压缩合计 5,390,139 字节
zip          4,895,891 字节（4.9 MB）
SHA256       E6F681068335C1A799FA5059A919AD305D6B02DF5F0FF7F0740A7240A945A3BE
```

## 2 包里放了什么

- **四份材料**（step §6 的 01/02/03/04，全部在包根）：文档 26 页 / PPT 17 页 / 视频 300 秒 / 原型说明。
- **业务代码 12 个 py + 配置**：`app.py` `agent.py` `coordinator.py` `guardian.py` `memory.py` `panel.py` `resources.py` `roles.py` `logger.py` `theme.py` `contract_check.py` `metrics.py`，加 `requirements.txt` `README.md` `.env.example` `.streamlit/config.toml`。
- **`tests/` 9 个文件**：`conftest.py` `pipeline.py` `test_agent` `test_fault` `test_flow` `test_guardian` `test_log` `test_memory` `test_metrics` `test_roles` `test_theme`（含驱动真实 `app.py` 的 `Chat` 与 AppTest 夹具）。
- **`docs/evidence/` 全套 79 个文件**：E-01~E-18 对应证据、16 张端到端截图、`probes/` 全部探针脚本、`metrics.md`、证据索引 `README.md`。
- **`docs/demo-script.md` + `docs/demo_timeline.json`**：视频分镜与唯一时间轴，评委要复现视频时用得到。

## 3 怎么打的（命令）

```powershell
& "C:\Users\nanxiangzi\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" docs\build_package.py
```

脚本里写死的排除项：`__pycache__` / `.pytest_cache` / `*.pyc`；不含 `.env`、`data/`、`.venv`、`.git`、录屏原片、`step/`、执行书与五份原始计划书。

## 4 解压实测（step §7 第 6 条）

把 zip 解到临时目录，**用项目 venv 的 python 在解压目录里**跑，确认跑起来靠的是包内代码而不是仓库：

```text
EXTRACT_ROOT xy_verify_lu7dtdf9   DIRS ['心屿-v1.0']
FILES 108
CMD  -m pytest -q
     132 passed in 5.92s
     RC 0
CMD  contract_check.py
     11/11 signatures OK
     5/5 constants OK
     20/20 rules OK
     RC 0
VERDICT PASS
STRAY ['.pytest_cache', '__pycache__']
```

- `pytest` 132 条全过，说明包内 `app.py` / `guardian.py` / `memory.py` 与测试齐套，AppTest 也能在解压目录里把界面拉起来。
- `contract_check.py` 11 + 5 + 20 全绿，说明 11 个契约签名与 20 条规则在包里完好。
- `STRAY` 只出现 pytest 自己的缓存，**没有 `data/`**：打包时确实没把本地记忆与日志带进去。

## 5 与 step 原文的口径差异

1. **材料位置**：step §6 的目录图把四份材料画在包根；仓库里它们在 `docs/`，脚本复制时提到根目录，包内结构仍与图一致。
2. **测试条数**：step §6 写 `tests/ (7 个文件，97 passed)`，实际是 9 个测试相关文件、**132 passed**（S22–S24 扩过）。
3. **`docs/` 内容**：step 写 `docs/ (evidence/ / demo-script.md / slides.pptx)`；实际带 `docs/evidence/`、`demo-script.md`、`demo_timeline.json`，PPT 直接用根目录的 `02_项目方案.pptx`，不再重复一份。
4. **不带的东西**：`step/`（内部执行手册）、`心屿MindIsle_工程执行书_v1.0.md`、五份原始计划书、`docs/*.py` 构建脚本都不进包——它们是过程材料，`04_原型说明.md` 里给了仓库地址。

## 6 没做的事

- zip 本身不进仓库：4.9 MB 二进制每次改动都会膨胀历史；仓库里放 `docs/build_package.py`，一条命令重打。
- **仓库是否 public 未核实**：本机 `api.github.com` 被解析到非公网地址，取不到仓库可见性；Gate A 要求仓库 public，需人工在 GitHub 页面确认一次。
- 现场三幕彩排、答辩四问脱稿、四项人工项（人设盲读 3 人 / 危机文案盲读 1 人 / 手机流量打开 / S21 另一人复跑签字）仍未完成。