# NovelOS Tasks

本目录是纯 Codex NovelOS 改造的唯一实施状态来源。架构文档描述稳定结果；本目录记录计划、依赖、进度、验收证据和阻塞项。

## 状态

- `TODO`：尚未开始。
- `IN PROGRESS`：正在实施，但尚未满足验收标准。
- `DONE`：生产路径已接通，自动化验证通过，并记录了证据。
- `BLOCKED`：存在无法由当前仓库内工作解决的外部阻塞。

不得因为创建了文件、Schema、测试桩或 Prompt 就标记为 `DONE`。

## 执行顺序

| 阶段 | 文件 | 状态 | 依赖 |
|---|---|---|---|
| 0 | [纯 Codex 目标架构](./00_pure_codex_target_architecture.md) | DONE | 无 |
| 1 | [源工程迁移盘点](./01_source_migration_inventory.md) | DONE | 阶段 0 |
| 2 | [MCP 与 Storage 迁移](./02_mcp_storage_migration.md) | DONE | 阶段 1 |
| 3 | [Skill Catalog 迁移](./03_skill_catalog_migration.md) | DONE | 阶段 1、阶段 2 的 Catalog 工具骨架 |
| 4 | [Agent 工作流与质量门禁](./04_agent_workflows_quality.md) | DONE | 阶段 2、阶段 3；完整质量实验作为明确延期项保留 |
| 5 | [切换、清理与交付](./05_cutover_cleanup.md) | DONE | 阶段 2–4；完整质量实验作为切换后延期项保留 |

Task 05 正在执行最终纯 Codex 切换；完整质量实验已按用户决定移至切换后延期项。

## 工作规则

1. 开始任务前读取本文件和目标阶段文件。
2. 从第一个未完成且依赖已满足的验收项继续。
3. 只在当前阶段文件中记录实施事实，避免在多个文件重复维护同一状态。
4. 任何从 `/Users/yiyi/github/novelos` 迁移的内容必须记录源 commit、源路径、目标路径和处理方式。
5. 源工程当前存在未提交改动；没有冻结来源快照前，不复制来源不明确的文件。
6. 每个阶段结束时记录执行过的命令和结果。未运行的验证必须明确写出原因。

## 总体完成条件

- Codex 是唯一长期存在的 Main Agent。
- 规划职责按权威资产拆分为临时 Agent，不存在覆盖整条规划链路的泛化 Planning Agent。
- Python 中不存在 Main Agent、Planner、Writer Agent、Review Agent 或 LLM 调度运行时。
- 所有外部读写只能通过 NovelOS MCP。
- 顶层 Codex Skill 数量保持精简，细粒度能力由 Skill Catalog 按需提供。
- 草稿、审查与接受通过不可变正文 Hash 和 Review Receipt 绑定。
- 迁移内容具备来源、许可证和完整性记录。
- 单元测试、MCP 协议测试和纯 Codex 端到端场景通过。
