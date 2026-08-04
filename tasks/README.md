# NovelOS Tasks

本目录只记录可执行工作和交付证据。稳定设计以 `documentation/` 为准，不在已完成 Task 中重复维护架构说明。

## 当前工作

| Task | 状态 | 目标 |
|---|---|---|
| 无 | - | - |

## 延期工作

| 工作 | 状态 | 恢复条件 |
|---|---|---|
| [70-case Agent 质量实验](./experiments/agent_quality/README.md) | `DEFERRED` | 按 `deferral.json` 完成剩余案例、独立盲评和可重算汇总 |

延期不等于质量通过。在实验完成前，Writer 仅用于完整章节或长场景；上下文构建智能体 仅用于跨卷、多线、事实冲突或上下文溢出。

## 历史完成项

| Task | 结果 |
|---|---|
| [Task 00](./00_pure_codex_target_architecture.md) | 冻结纯 Codex 目标架构 |
| [Task 01](./01_source_migration_inventory.md) | 冻结并盘点来源工程 |
| [Task 02](./02_mcp_storage_migration.md) | 完成统一 MCP、SQLite Schema 和数据迁移 |
| [Task 03](./03_skill_catalog_migration.md) | 完成六个顶层 Skill 和 Catalog 迁移 |
| [Task 04](./04_agent_workflows_quality.md) | 完成 Agent 契约与工作流；质量实验单独延期 |
| [Task 05](./05_cutover_cleanup.md) | 完成纯 Codex 切换、旧 Runtime 清理和交付 |
| [Task 06](./06_user_project_projection.md) | 完成用户项目 Markdown 文件夹派生投影、原子渲染与 156 项全量自动化测试 |
| [Task 07](./07_prompt_catalog_expansion.md) | 完成 08 (F1-F6) 治理、三方 Hash 校验与 150 项全量自动化测试 |
| [Task 08](./08_author_signature_and_book_soul.md) | 完成 Creator Profile 精确版本绑定、书级创作灵魂、投影和 Schema 11；受控语义质量实验保持 `BLOCKED` |
| [Task 09](./09_narrative_archetype_derivation.md) | 完成 18 个系统叙事原型、仅派生向导、确定性 Top 3 推荐、Schema 12 数据生命周期和 190 项全量自动化测试 |
| [Task 10](./10_service_module_split.md) | 完成 `service.py` 到 8 个领域 Mixin + 共享内部 Mixin 的无契约变化拆分，并通过 53 项根测试与 154 项 MCP 测试 |
| [Task 11](./11_audit_architecture_pruning.md) | 完成 Review Profile 单一注册表、默认 lenient/可选 strict 门禁、启动期 fail-closed 校验及完整边界测试 |

## 目录边界

- `migration/`：来源、迁移、备份、恢复和导出证据，不是待办。
- `cutover/`：最终切换与仓库卫生证据，不是待办。
- `experiments/agent_quality/`：延期质量实验的数据集、恢复点和已完成证据。
- 顶层 `Task NN`：一个文件对应一个可独立验收的阶段。

## 状态规则

- `TODO`：尚未开始。
- `IN PROGRESS`：已有实现，但验收尚未全部通过。
- `DONE`：生产路径和自动化验证均已完成。
- `DEFERRED`：用户明确推后，保留恢复条件和证据。
- `BLOCKED`：存在仓库内无法解决的外部阻塞。

不得因为创建了文档、Schema 或测试桩就标记为 `DONE`。
