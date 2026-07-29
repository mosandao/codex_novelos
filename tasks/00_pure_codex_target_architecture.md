# Task 00：纯 Codex 目标架构

状态：`DONE`

## 完成结论

- Codex Main Agent 是唯一常驻 Agent，也是唯一权威提交者。
- 业务 Agent 均为临时上下文，只产出候选；Skill 只提供方法，不持久化。
- 单一 `novelos` MCP 是 SQLite、文件、Git、浏览器和外部 API 的唯一访问边界。
- SQLite 保存权威状态；长内容保存为不可变 Resource，控制数据使用严格 Schema、版本和 Hash。
- 规划按八类权威资产拆分：方向、架构、战略、人物契约、世界契约、故事弧、卷纲、章纲。
- 不迁移 Python Agent/LLM Runtime、FastAPI、WebSocket、Frontend 和旧语义路由。

稳定架构见 [`documentation/architecture.md`](../documentation/architecture.md)，权限边界见 [`documentation/permissions.md`](../documentation/permissions.md)。

## 验收结果

- [x] 唯一 Main Agent、临时业务 Agent、Skill、MCP 和 Storage 职责无冲突。
- [x] 每类规划资产有唯一候选生产者，所有权威写入有唯一提交者。
- [x] 临时 Agent 无法直接修改 Storage 或 Canon。
- [x] 最终生产路径不存在 Python 与 Codex 两套 Agent Runtime。

## 证据

- Agent 契约：`config/agents.yaml`。
- 顶层业务 Skill：`.agents/skills/`。
- 统一 MCP：`mcp/novelos/`。
- 最终切换与删除证据：Task 05、`tasks/cutover/`。
