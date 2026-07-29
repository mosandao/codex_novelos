# Task 05：切换、清理与交付

状态：`DONE`

## 完成结论

- 默认 `.codex/config.toml` 只注册统一 `novelos` MCP。
- 旧 Python Agent、Skill、LLM Runtime、Memory MCP、旧配置和相关测试已经删除。
- 正式运行入口为 `scripts/run_novelos_mcp.sh`，固定使用 Schema 9 数据库、Catalog、Agent 契约和授权 seed。
- Legacy 迁移、数据库备份、恢复、JSONL 灾备导出和仓库卫生均完成验证。
- 完整 70-case 质量实验作为切换后延期项保留，保守路由已固化。

## 验收结果

- [x] 生产入口只有 Codex 与 `novelos` MCP。
- [x] 仓库不存在第二套 Agent Runtime。
- [x] 权威写入可追溯到 subject Hash、Review Receipt 和同一 Trace。
- [x] 数据迁移、备份恢复和降级导出经过实际演练。
- [x] 稳定架构、流程、权限、变量、测试和自动化文档齐全。
- [x] 仓库 Git 基线和产物卫生检查通过。

## 证据

- 切换就绪：[`cutover/readiness.json`](./cutover/readiness.json)，状态 `ready`、blocker 为 0。
- 删除清单：[`cutover/removal_manifest.json`](./cutover/removal_manifest.json)，阶段 `cutover`。
- 仓库卫生：[`cutover/hygiene.json`](./cutover/hygiene.json)，状态 `passed`。
- 迁移汇总：[`migration/migration_summary.json`](./migration/migration_summary.json)，状态 `completed`。
- Schema 9 恢复和导出：`tasks/migration/schema9_restore_drill.json`、`schema9_export_drill.json`。
- Git 基线：`c5a6e92`；纯 Codex 切换：`20f9376`；最终证据：`32a5f7b`。
- 当前验证基线：根测试 33 个、MCP 测试 81 个。
