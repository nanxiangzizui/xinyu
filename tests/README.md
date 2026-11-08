# 测试目录

共 97 条：考核 48 条（28 规则 D / 12 对话 C / 8 故障 F）+ 自测 49 条。

| 文件 | 条数 | 覆盖 |
|---|---|---|
| test_memory.py | 17 | 白名单读写 / 摘要节流 / 损坏恢复 / 清空 |
| test_agent.py | 6 | prompt 装配 / MOCK / 超时兜底 |
| test_roles.py | 5 | 人设卡字段 / 主题 / 规则表结构 |
| test_log.py | 2 | 字段白名单 / 不写原文 |
| test_guardian.py | 39 | 28 条规则 + 豁免 + 复核 + 重写 |
| test_flow.py | 20 | 状态机 + 聚合 + 12 条对话 |
| test_fault.py | 8 | 8 类故障注入 |
