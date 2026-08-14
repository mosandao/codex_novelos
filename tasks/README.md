# NovelOS Tasks

本目录只记录可执行工作和交付证据。稳定设计以 `documentation/` 为准。

## 当前架构：NovelOS 轻量化（SQLite MCP 完全替代 NovelOS MCP）

源自外部商业网文评估暴露的审查标准盲区 → 全链路追踪发现 130+ 次 MCP 调用中 55% 是治理开销 → 架构评估确认 89 个工具 90% 可被 SQLite MCP 替代。

| Task | 状态 | 说明 |
|---|---|---|
| [Task 28](./28_agent_prompt_enhancement_queue.md) | `IN PROGRESS` | 各级 Agent Prompt 增强队列，按创作阶段拆分（阶段 0-2 已提交；待执行：阶段 1 补丁=频道×题材语法/力量货币/代价形态学/道德债权，阶段 3-10=各下游 agent 方法论补全，横切收尾=metadata/串测/文档复核）。 |
| [Task 25](./25_sqlite_mcp_poc.md) | `DONE` | SQLite MCP server + POC 验证 + 5 个桥接脚本（stale 传播/hash/book_soul/reconcile/projection）。纯增量，不停 NovelOS MCP。 |
| [Task 26](./26_creation_flow_sql_migration.md) | `DONE` | migration 016 在真实数据库执行（35→26 表）+ NovelOS MCP 停用 + 6 个 SKILL.md/AGENTS.md 重写 + 端到端 7/7 验证通过。 |
| [Task 27](./27_prose_webnovel_accessibility.md) | `DONE` | craft skill prose-webnovel-accessibility（通俗度/开头/钩子强度）+ writer/reviewer/章纲三端引用。 |

## 仍有用的历史 Task

以下 Task 的产出（方法论/功能/catalog skill）在当前 SQLite MCP 架构下仍然有效：

| Task | 说明 |
|---|---|
| [Task 06](./06_user_project_projection.md) | 用户项目文件夹投影（`scripts/novelos_render_projection.py` 仍用） |
| [Task 07](./07_prompt_catalog_expansion.md) | 创作 Prompt Catalog 扩展（`catalog/skills/` 仍在用） |
| [Task 08](./08_author_signature_and_book_soul.md) | 作者签名与 book_soul（概念和 schema 仍在用） |
| [Task 09](./09_narrative_archetype_derivation.md) | 叙事原型与项目化作者派生（项目创建向导仍用） |
| [Task 15](./15_volume_outline_pacing_density.md) | Volume Outline 节奏密度约束（novel-planning SKILL.md 保留） |
| [Task 16](./16_review_prompt_self_containment.md) | 审查 prompt 自包含约束（novel-review SKILL.md 保留） |
| [Task 17](./17_world_contract_prompt_enhancement.md) | World Contract Prompt 维度处理 |
| [Task 18](./18_world_contract_review_binding.md) | World Contract Review Rubric 消费绑定 |
| [Task 20](./20_scenario_atlas_genre_seeds.md) | 桥段图集 Skill |
| [Task 21](./21_creation_seed_entry_layer.md) | 创作种子非权威入口层 |

## 延期工作

| 工作 | 状态 | 恢复条件 |
|---|---|---|
| [70-case Agent 质量实验](./experiments/agent_quality/README.md) | `DEFERRED` | 按 `deferral.json` 完成剩余案例、独立盲评和可重算汇总 |

## 目录边界

- `migration/`：来源、迁移、备份、恢复、导出证据（只读参考）
- `cutover/`：切换与仓库卫生证据
- `experiments/agent_quality/`：延期质量实验的数据/恢复点/证据
- `07_prompt_catalog/`：Task 07 的执行批次明细
- 顶层 `Task NN`：一个文件 = 一个可独立验收的阶段
