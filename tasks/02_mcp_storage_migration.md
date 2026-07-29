# Task 02：MCP 与 Storage 迁移

状态：`DONE`

## 完成结论

- 建立唯一 `novelos` FastMCP Server，MCP 内不包含模型调用、Prompt 编排或语义路由。
- 正式数据库为 `data/novelos-v2.db`，当前 Schema 9。
- Core、Memory、Continuity、Planning、Knowledge、Catalog、Review、Entity、Trace、Resource 和 Agent Workflow 已接入统一工具面。
- 长正文和规划使用不可变 Resource；权威写入受 Schema、Hash、乐观版本、Review Receipt、Trace 和事务保护。
- 八类规划资产使用统一 `planning_assets` 与依赖图，支持唯一生产者、精确上游和递归 `stale`。
- Legacy 核心数据完成迁移并对账；授权 `seed.db` 通过固定 inventory 只读接入。

## 验收结果

- [x] Skill 和 Agent 不直接访问 SQLite。
- [x] MCP 不依赖模型 Provider 或 Prompt Runtime。
- [x] 规划、正文、Entity 和连续性权威写入均具备失败关闭门禁。
- [x] MCP stdio、Resource、迁移、恢复和只读 Knowledge 路径通过测试。

## 证据

- Schema 与实现：`mcp/novelos/src/novelos_mcp/`。
- Legacy 对账：[`migration/legacy_migration_report.json`](./migration/legacy_migration_report.json)
- Schema 9 恢复：[`migration/schema9_restore_drill.json`](./migration/schema9_restore_drill.json)
- 灾备导出恢复：[`migration/schema9_export_drill.json`](./migration/schema9_export_drill.json)
- Seed 授权：[`migration/seed_authorization_audit.md`](./migration/seed_authorization_audit.md)
- 当前验证基线：根测试 33 个、MCP 测试 81 个。
