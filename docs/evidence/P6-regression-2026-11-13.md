# P6 回归、材料与提交包验收（2026-11-13）

> 结论：P6a（回归 + 材料 + 包）完成。176 条测试在 `AGENT_LOOP=0` / `1` 下各跑一遍全绿；契约 11+5+20；四指标不变；三条 v2 破坏性验证按预期变红后还原；docx 26 页（正文 16）、PPT 17 页、提交包 167 文件且解压后仍 176 passed。
> 未完成的是人工项：视频重录（当前仍是 v1 合成版）、P5b 五人设盲读、真实 provider（P3b）、现场彩排、仓库 public。P6b 因此仍为 🟨。

## 1. 出口核对

| 项 | 结果 | 证据 |
|---|---|---|
| 全量测试（默认 `AGENT_LOOP=1`） | **176 passed** in 6.02s | `p6_pytest_loop1_2026-11-13.txt` |
| 全量测试（`AGENT_LOOP=0`） | **176 passed** in 6.04s | `p6_pytest_loop0_2026-11-13.txt` |
| 契约 | 11/11 signatures + 5/5 constants + 20/20 rules | `p6_contract_2026-11-13.txt` |
| 四指标 | 10/10、0/20、12/12、10/10 | `p6_metrics_2026-11-13.txt`、`metrics.md` |
| v2 破坏性验证 | 3 条均按预期红，还原后全绿 | `p6_destructive_2026-11-13.txt` |
| 16 条场景 | 16/16 PASS | `p6_scenarios_2026-11-13.txt` |
| 项目文档 | 26 页，正文 3–18（16 页），附录 19–26 | Word COM 统计，见 §6 |
| 项目方案 | 17 页，16:9，首页写赛题一 | `p6_pptx_2026-11-13.txt`、`ppt_png/` |
| 提交包 | 167 文件，解压后 176 passed | §7；`D:\deepseek harness\心屿MindIsle_提交包_v2.0.zip` |

## 2. 代码冻结与改动边界

P6 期间业务代码只改了一行 docstring，无逻辑变化：

- `orchestrator.py:195`：`"""七步固定管线…"""` → `"""九节点固定管线…"""`（P1 时是七步，P4 加 trace 后实际九个节点）。

测试侧三处修改，原因是 P6 首次双跑暴露了测试只覆盖单一生成路径：

1. `tests/test_fault.py` F-01：原来只弄坏 `agent.chat_with_tools`；`AGENT_LOOP=0` 时走 `agent.call_llm`，故障注入不生效。改为两个入口都弄坏。
2. `tests/test_tool_gate.py::test_loop_failure_becomes_template_fallback`：原断言默认 `AGENT_LOOP is True`；改为显式 `monkeypatch.setattr(orchestrator, "AGENT_LOOP", True)`，再验证 loop 失败走 L2 模板。
3. `tests/test_agent_loop.py` 新增 `test_default_step_budget_is_three`：断言默认预算就是 3 步，兼作破坏性验证 #2 的探针。

其余改动都在 `docs/`（报告 / PPT / 架构图 / 打包脚本 / 证据），不含 `guardian.py`、`coordinator.py`、`memory.py`、`roles.py`、`logger.py`、`contract_check.py`。

## 3. 双跑

```powershell
$env:AGENT_LOOP="0"; ./.venv/Scripts/python.exe -m pytest -q
$env:AGENT_LOOP="1"; ./.venv/Scripts/python.exe -m pytest -q
```

- loop=0：`176 passed in 6.04s`
- loop=1：`176 passed in 6.02s`

首轮双跑曾有 2 条红（F-01 与 loop 兜底用例），按 §2 修测试、不改业务；修完再跑两遍全绿。

## 4. 破坏性验证

脚本 `p6_destructive_2026-11-13.py` 在 `try/finally` 里改坏一处、跑指定测试、再用原字节还原；输出 `restored=True`，脚本退出 0。

| # | 改坏什么 | 预期红的用例 | 实际输出 |
|---|---|---|---|
| 1 | `orchestrator.py` 的 `if eff_level == "L3":` 改成 `if False and …` | `test_l3_short_circuits_before_agent`、`test_l3_never_calls_agent` | 2 failed in 1.10s；`AssertionError: L3 不许进 agent loop` |
| 2 | `agent_loop.py` 的 `AGENT_MAX_STEPS = 3` 改成 `99` | `test_default_step_budget_is_three` | 1 failed in 0.67s；`assert 99 == 3` |
| 3 | `agent_loop.py` 的 `if gate is not None:` 改成 `if False and …` | `test_denied_tool_is_not_executed`、`test_gate_error_fails_closed` | 2 failed in 1.59s；`tool_calls` 为 2 而非 0 |

## 5. 16 条场景

覆盖 L1 日常、L2 资源卡、L3 短路、断网 L3、豁免、危机后冷却、记忆白名单、清空、5000 字、`AGENT_LOOP=0`、错误 key、工具成功 / 超时、五人设、AppTest 首屏 / 侧栏 / 资源卡 / 来源链接、trace 与日志无原文。逐条输出见 `p6_scenarios_2026-11-13.txt`，脚本为 `p6_scenarios_2026-11-13.py`；stderr 里只有预期的 `pipeline_failed` 与 Streamlit `missing ScriptRunContext` 警告。

## 6. 项目文档（docx）

- 文件：`docs/01_项目文档.docx`，320,826 字节。
- Word COM：`PAGES=26`；目录第 2 页；正文第 3–18 页（16 页）；附录 A 第 19、B 第 22、C 第 24、D 第 25 页。
- `docs/report_toc.json` 已写入同一组页码，重新构建后复核仍为 26 页。
- 排版：正文 11.2pt、行距 1.2、左右边距 2.0cm；为把正文压进 16 页做过三轮（30→29→26 页）。
- 全文扫描（`p6_check_docx.py` → `p6_docx_2026-11-13.txt`）：`多智能体` 0、`多模态` 0、`有效缓解焦虑` 0、`AI 心理医生` 0、`心理医生` 0。`你得了` / `倾向` / `你可能是抑郁` 只出现在"不做诊断、禁止出现"的说明里。`132` 只剩版本表 v1.0 行的一处历史数字。

## 7. 项目方案与提交包

- PPT：17 页；第 8 页九节点 + `generate` 内部循环；第 11 页工具三条红线；第 15 页 176 / 11+5+20 / 七类错误码。PowerPoint COM 导出 17 张 PNG 到 `docs/evidence/ppt_png/`，逐页检查过版式。
- 包名 `心屿-v2.0`；`docs/build_package.py` 的根文件清单已补 `orchestrator.py / agent_loop.py / tools.py / web.py / style.py`。
- 最终包（在 04 / P6 证据 / README / CLAUDE 更新后重建）：`心屿MindIsle_提交包_v2.0.zip`，解压 **167 文件**，用仓库 `.venv` 在解压目录跑 `pytest -q` 得 **176 passed**。字节数与 SHA256 由构建日志 `p6_package_build_2026-11-13.txt` 记录；构建日志与解压复跑日志都留在仓库、不打进包，避免自指（每次重建会变，正文不写死）。仓库内最终全量见 `p6_pytest_final_2026-11-13.txt`（176 passed in 7.14s），解压复跑见 `p6_package_pytest_2026-11-13.txt`。

## 8. 已知限制 / 偏差

1. **视频仍是 v1 合成版**：`docs/03_演示视频.mp4` 300 秒、2,056,201 字节、5 fps，不含侧栏"本轮编排"和 v2 工具循环。提交包里的视频也在内；P6b 必须重录后再重打包。
2. **P5b 未做**：五人设盲读、真实 key 下 L1/L2/L3 与切换人设的视觉检查仍待人工。
3. **P3b 未接通**：真实搜索 provider 没有 key；当前用假 transport 覆盖七类错误码，PPT / 文档都写明"真实搜索 provider 未接通"。
4. **PPT 第 12 页仍用 v1 截图**：侧栏没有"本轮编排"；视频里必须补 v2 侧栏画面。
5. **docx 排版偏紧**：为了正文 16 页把正文压到 11.2pt；如果最终页数要求放宽，可以回到 11.5pt 重新分页。
6. **打包脚本仍收 `docs/evidence/ppt_png/`**：17 张渲染图约 1.3MB，不影响解压测试；如要减小包体可在 `build_package.py` 里排除。

## 9. 回滚

```powershell
git checkout -- orchestrator.py tests/test_agent_loop.py tests/test_fault.py tests/test_tool_gate.py
git checkout v1.0 -- docs/01_项目文档.docx docs/02_项目方案.pptx
```

代码回滚点是 `v1.0` tag；v2 全部在 `agent-v2` 分支，`main` 未动。
