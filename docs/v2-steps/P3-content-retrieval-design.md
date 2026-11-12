# P3 内容检索候选设计：本地识别 + host 路由 + MCP 取内容

| 项 | 内容 |
|---|---|
| 文档 | P3 内容检索候选设计（未决策） |
| 状态 | **候选方案**，不改变 `docs/plan-orchestrated-single-agent.md` 与 D-1~D-5 |
| 日期 | 2026-11-12 |
| 关联 | 计划书 §3 / §4、[P3-web-search.md](P3-web-search.md)、[P5-style-layer.md](P5-style-layer.md) |
| 一句话 | 聊天中由**本地规则**识别“这一轮要不要取内容”，由 **orchestrator** 决定允许哪些工具，由 **MCP/HTTP 适配层**去云端取风格、贴纸、图片；模型始终只能从白名单里选，guardian 始终有一票否决 |

## 1. 这份文档解决什么

用户原始想法：**skills + MCP + host（协调与路由）**，让 AI 对特定内容做特定检索——语言风格 prompt、表情包、图片/动图；本地写轻量识别文件，聊天中触发后从云端（MCP 等）取对应内容。

现有文档只写到“P3 做搜索 / 图片 / 风格包，provider / MCP / key 待定”（计划书 :137、:15、:236），**没有**写：谁识别、识别什么、怎么路由、MCP 怎么接、取回的内容怎么防注入。本文把这块补齐为候选设计，供 D-1 决策时直接拿去讨论。

**本文不是开工令。** P3b 仍被 D-1 卡住；在 provider / MCP host / key 未定之前，只允许做 C0（纯本地识别）。

## 2. 先把三个词说清

| 说法 | 在本项目里的准确含义 | 不是什么 |
|---|---|---|
| skill | `.claude/skills/*/SKILL.md`，给**编码 Agent**看的操作手册 | 不是运行时能力；Streamlit 进程读不到、也不该读 |
| 本地轻量识别 | 一个**纯函数** + Python 常量/JSON 白名单，输入用户文本，输出意图标签 | 不是 skill、不是模型调用、不是网络请求 |
| host（协调与路由） | 本项目的 `orchestrator` + `agent_loop`：决定这一轮允许哪些工具、跑几步 | 不是新服务、不是新框架、不是消息总线 |
| MCP | `web.py` 内部的一种 **transport**（JSON-RPC over HTTP），对外仍是一个白名单工具 | 不是模型可自由连接的通道；不是新依赖（只用 `urllib`） |
| hosts | 部署细节：MCP 服务所在域名/IP 的**允许清单** | 不是让模型拼 URL；用户原文永远不当 URL |

一句话：**识别在本地，路由在代码，取内容在适配层；模型只在“允许的工具”里做选择。**

## 3. 三层架构

```text
用户输入
  → guardian_pre_check（L3 直接短路：0 工具、0 LLM、0 检索）
  → coordinator_decide（role）
  → intent.detect(text)          # 第一层：本地轻量识别，纯函数，0 网络
  → tools.list_for_turn(role, level, allow_web, intents)
                                 # 第二层：orchestrator 决定白名单
  → agent_loop.run_agent()       # 模型只能从白名单里选工具
      → tools.execute() → guardian_tool_check() → web/content 适配层
                                 # 第三层：MCP/HTTP 取内容，超时 + 大小 + schema
  → guardian_post_check          # 最终否决不变
  → style.polish（仅通过审查的非 L3）
  → 代码渲染来源 / 贴纸 / 图片
```

三层职责不交叉：识别层不碰网络，路由层不碰内容，适配层不碰等级判断。

## 4. 第一层：本地轻量识别

### 4.1 接口

```python
# intent.py（候选新文件，预算 ≤120 行）
def detect(text: str) -> frozenset[str]:
    """返回本轮意图标签；纯规则、无网络、无 LLM、可离线单测。"""
```

候选标签（闭集，测试断言全集）：

| 标签 | 触发示例 | 允许的工具 | 明确禁止 |
|---|---|---|---|
| `factual_question` | “今天有什么新闻”“现在几点”“XX 是谁” + 问号 | `web_search` | 情绪倾诉时不触发 |
| `style_request` | “换个语气”“温柔一点”“活泼点说” | `style_pick` | 不得让远端改安全规则 |
| `sticker_moment` | “哈哈”“笑死”“晚安”“抱抱”，且 level=L1 | `sticker_pick` | L2 / L3 不给贴纸 |
| `image_request` | “来张图”“配个图”“动图”“GIF” | `image_pick` | 用户给的 URL 一律不用 |
| `emotional_venting` | “我难受”“压力好大”“想哭” | 无（先共情） | 不检索，符合计划书“情绪倾诉 → 不检索” |

### 4.2 优先级（写死，不靠模型）

1. L3：`detect()` 不被调用，`list_for_turn` 返回 `[]`。
2. L2：只允许 `web_search`（事实问题）与 `style_pick`；不给贴纸、不给图片。
3. L1：四类内容工具都可按标签放开。
4. 同时命中 `emotional_venting` 与 `factual_question`：**只保留共情**，检索让位（宁可少答，不把倾诉当查询）。
5. 标签冲突无法判定：返回空集，这一轮不检索。

### 4.3 规则形态

- 规则写成模块级常量表（正则/关键词 + 最短长度），不写进 prompt。
- 每条规则带 `test_` 用例；新增一条规则必须同时加“不该触发”的反例。
- 不引入分词库、不引入模型分类器；中文关键词 + 标点足够覆盖演示场景。
- 规则文件不做热更新；改规则 = 改代码 + 跑测试。

## 5. 第二层：host 路由

`tools.list_for_turn` 扩一个可选参数，保持向后兼容：

```python
def list_for_turn(role, level, allow_web=False, intents=None) -> list[dict]:
    """intents=None 时行为与 P2 完全一致；否则按标签收紧白名单。"""
```

orchestrator 在 `pre_check` 之后、`generate` 之前调用一次 `intent.detect`，把结果放进 trace 的 `detail`（只放标签名，不放原文）。这一步是**代码决定**，不是模型决定；模型看到的工具列表已经是裁剪后的结果。

约束：

- 路由只看 `role / level / intents`，不看模型说了什么。
- 不允许“模型要求开工具”就追加；要开新工具只能改代码白名单。
- `AGENT_LOOP=0` 时整层跳过，行为与 v1 一致。

## 6. 第三层：内容契约

四类内容共用 `ToolResult`，不新增返回类型：

```python
ToolResult(ok: bool, data: dict | list, error: str, source: str, latency_ms: int)
```

| 工具 | 入参 schema | 返回 data | 渲染方 |
|---|---|---|---|
| `web_search` | `{"query": str}`（先 `scrub`，截 80 字） | `[{"title","url","snippet"}]` | 代码渲染链接 |
| `style_pick` | `{"tone": "gentle|playful|plain"}` | `{"id": "gentle"}` | 本地表取文案 |
| `sticker_pick` | `{"mood": "hug|cheer|night"}` | `{"id","url","alt"}` | 代码 `st.image` |
| `image_pick` | `{"topic": str}`（闭集枚举，不收自由文本） | `{"url","alt","credit"}` | 代码 `st.image` |

### 6.1 语言风格：只取 id，不取 prompt 原文

这是本设计最重要的一条：

- 远端**只能返回一个闭集 id**（`gentle / playful / plain`），本地 `STYLE_PACKS` 持有经过审查的文案。
- **禁止**把远端返回的自由文本拼进 system prompt——那是典型的指令注入面，且会绕过术语红线。
- 远端返回未知 id → 丢弃，按“无风格包”处理，不报错给用户。
- 若未来必须支持云端更新文案：先过 schema（长度上限、无 URL、无祈使句、无安全词），再过人工审查，且只作为“候选”不直接生效。

### 6.2 贴纸 / 图片：白名单 + 代码渲染

- 只接受 `https://`，主机必须在 `CONTENT_HOSTS` 允许清单内；禁止 `http`、内网、`userinfo@`、重定向到私网。
- 贴纸只给 **L1**，每轮最多 1 张；L2/L3 不给。
- 图片先只做**策展包**（闭集 topic），不做“任意 query 图搜”；避免不适宜内容与版权风险。
- 版权：每个资源记录 `credit` / license；演示与报告只使用有明确授权的来源（Unsplash / Pexels / Giphy 等按其条款），不抓任意站点。
- 渲染由代码完成：`st.image(url, caption=alt)`；模型不写 URL、不写 Markdown 图片语法。

## 7. MCP 接入方式（候选）

### 7.1 两种实现

| 方案 | 做法 | 优点 | 代价 |
|---|---|---|---|
| A. 直连 provider | `web.py` 直接调搜索/图片 API | 简单、错误码清晰 | 每家一个适配器 |
| B. MCP 网关 | `web.py` 发 JSON-RPC 到自建/托管 MCP server | 内容类型可扩展、统一鉴权 | 多一层运维；仍是手写 JSON-RPC |

**建议**：先 A 后 B。C1 用 A 把 `web_search` 跑通；只有内容类型增加到 3 类以上、或需要统一 key 管理时，才上 B。两者对外都是同一个 `execute()`，切换不影响 agent loop。

### 7.2 MCP 客户端草案（B 方案，仍只用 urllib）

```python
def _rpc(fetch, method: str, params: dict) -> tuple[dict | None, str | None]:
    """一次 JSON-RPC 调用；成功 (data, None)，失败 (None, 错误码)。"""
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
    }).encode("utf-8")
    req = urllib.request.Request(
        MCP_BASE_URL, data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {MCP_TOKEN}"},
    )
    with fetch(req, timeout=TOOL_TIMEOUT_S) as resp:
        raw = resp.read(TOOL_MAX_BYTES + 1)
    if len(raw) > TOOL_MAX_BYTES:
        return None, "too_large"
    ...
```

错误映射沿用 P3 七类：`timeout / http_401 / http_429 / bad_json / too_large / empty / bad_url`；MCP 的 `error` 字段统一归到 `bad_json`，不把远端错误原文透给界面。

### 7.3 配置

```text
MCP_BASE_URL=https://<host>/rpc      # 只允许 https
MCP_TOKEN=...                        # 进 Secrets，不进仓库
MCP_ALLOWED_HOSTS=<host>             # 主机白名单；重定向后仍需命中
```

hosts 的两种理解都在这里收敛：MCP 架构里的 host = 本应用；部署里的 hosts = `MCP_ALLOWED_HOSTS` 允许清单。**任何情况下都不接受用户输入当 URL。**

## 8. 安全与红线

| 红线 | 本设计的落地 |
|---|---|
| L3 零工具、零 LLM | `pre_check` 在 `detect` 之前短路；`list_for_turn` 对 L3 返回 `[]`；测试断言 agent 未被调用 |
| 否决权唯一 | 每次工具调用前 `guardian_tool_check`；最终回复仍过 `guardian_post_check`；远端内容不能说服它 |
| 结果不可信 | 远端只提供**数据**；风格只取 id；贴纸/图片只取白名单 URL；模型不执行其中的指令 |
| 参数校验 | 工具名白名单 + schema；`tone/mood/topic` 是闭集；`query` 先 `scrub` |
| 预算硬上限 | 沿用 `TOOL_TIMEOUT_S=6`、`TOOL_MAX_BYTES=2_000_000`、总超时 20s；超限 `ok=False` |
| 日志 | 只记工具名 / 状态 / 耗时 / 条数；**不记 query、不记内容 id、不记远端原文** |
| 可关 | `AGENT_LOOP=0` 回到 v1；内容工具再单独受 `allow_web` 控制 |
| 不加依赖 | 只用 `urllib.request` + `json`；不引入 MCP SDK、不引入图片库 |
| 离线测试 | 注入假 transport / 假 MCP；测试不连真实域名 |

额外两条：

- **图片安全**：只做策展包，不做开放图搜；host 白名单 + 尺寸上限；渲染前不把远端描述当正文。
- **版权**：贴纸/图片必须可追溯授权；报告与 PPT 里标注来源；不用未授权表情包做演示素材。

## 9. 测试策略（离线）

| 层 | 用例 | 断言 |
|---|---|---|
| intent | 每标签 2 条正例 + 2 条反例 | 标签集合精确相等；L3 不调用 |
| 路由 | L1/L2/L3 × 标签组合 | `list_for_turn` 返回的名字集合 |
| 内容 | 假 transport 返回 200/401/429/坏 JSON/超限 | 错误码正确、`ok=False`、不抛异常 |
| 风格 | 远端返回未知 id | 丢弃、不拼 prompt |
| 图片 | 私网 URL / http / 重定向 | 被过滤，来源列表为空 |
| 日志 | 跑一轮含检索 | 日志无 query、无内容 id |

测试全部走 `monkeypatch` 注入，不新增网络标记；CI 离线可跑。

## 10. 与现有决策的冲突

| 现有决策 | 本设计的影响 | 转正时必须改 |
|---|---|---|
| D-1（provider / key / MCP 待定） | 仍然待定；本文只给候选 | 计划书 §3/§4、P3 文档 §2 |
| D-3（风格包静态、不走网络） | 改为“默认静态；可选远端只取 id” | P5 文档、`style.py` 契约 |
| D-4（MVP 只做 web_search） | 扩为“搜索 + 风格 + 贴纸 + 图片” | 计划书 §4 P3 行、README 节点表 |
| P5 贴纸白名单 ≤5、仅 L1 | 可保留本地兜底；远端只提供 id | P5 测试与行数预算 |
| `web.py ≤250` | 四类内容 + MCP 客户端可能超 | 拆 `content.py`（≤180）或收紧范围 |

不冲突的部分：L3 短路、guardian 门禁、`ToolResult`、七类错误码、`AGENT_LOOP` 开关、11 条契约，全部沿用。

## 11. 分期建议

| 阶段 | 做什么 | 网络 | 出口 |
|---|---|---|---|
| **C0** | `intent.py` + `list_for_turn(intents)` + 规则测试 | 无 | 标签正反例全绿；L3/倾诉不检索；可在 P3 之前做 |
| **C1** | `web.py` 接 A 方案 provider；`style_pick` 只取 id | 有 | 假 transport 七类错误码 + 一次真实 smoke |
| **C2** | 贴纸 / 图片策展包；host 白名单；代码渲染 | 有 | 私网/ http / 重定向被拦；版权清单齐 |
| **C3（可选）** | MCP 网关替代 A 方案 | 有 | 同一 `execute()` 下行为不变；运维文档 |

C0 不依赖 D-1，建议先做；C1 起必须等 provider / key / host 决策。

## 12. 待决策清单

1. provider / MCP host / key：博查、Tavily、自建 MCP，还是先 A 后 B？
2. 风格包：只允许闭集 id（推荐），还是允许云端更新文案（需审查流程）？
3. 贴纸 / 图片：先做策展包还是开放图搜？版权与内容安全谁签字？
4. `style_pick` 的 tone 闭集由谁定？是否与人设绑定？
5. 是否允许 L2 使用 `style_pick`（只改语气、不取外部内容）？
6. 新增 `intent.py` / `content.py` 的行数预算与测试配额。

## 13. 不做什么

- 不做运行时加载 skill；skill 只服务编码阶段。
- 不做自由 MCP 客户端；模型不能指定 server / method / URL。
- 不把远端返回的自由文本拼进 system prompt。
- 不做开放图搜、不做用户 URL 抓取、不做本地文件读取。
- 不让内容检索影响等级判断；L3 永远 0 工具。
- 不引入 LangChain / MCP SDK / 图片处理库。

## 14. 变更记录

- 2026-11-12：创建候选设计 v0.1；记录用户“skills + MCP + host”三层想法，明确 skill 非运行时、host=orchestrator、MCP=白名单工具后端；未改计划书与 D-1~D-5。
