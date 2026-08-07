# NovelOS Tasks

本目录只记录可执行工作和交付证据。稳定设计以 `documentation/` 为准，不在已完成 Task 中重复维护架构说明。

## 当前工作

源自 `documentation/worldbuilding-redesign.md` 九条改造建议，已全部转化并处理完毕：

### 已完成

| Task | 状态 | 说明 |
|---|---|---|
| [Task 17](./17_world_contract_prompt_enhancement.md) | `DONE` | World Contract prompt 维度处理与消费约束增强（22.1/22.7/22.8） |
| [Task 18](./18_world_contract_review_binding.md) | `DONE` | World Contract review rubric 消费绑定检查（22.3，依赖 Task 17） |
| [Task 20](./20_scenario_atlas_genre_seeds.md) | `DONE` | 桥段图集 skill 新建（8 题材簇约 45 桥段，lifecycle=experiment 待生成验证转 active） |
| [Task 21](./21_creation_seed_entry_layer.md) | `DONE` | 创作种子非权威入口层（migration 013 + SeedsMixin + 3 MCP 工具 + direction 反向工程 + 投影 + 7 测试） |
| [Task 22](./22_checkpoint_option_presentation.md) | `DONE` | 检查点选项呈现原子能力（extract_decision_points + create_revision_candidate + prompt + 8 测试） |
| [Task 24](./24_reconcile_fused_parent_handoff.md) | `DONE` | reconcile 接收 fused parent + 融合签名确定性收口（A–D 契约缺口修复：扩展 reconcile fused 入参、handoff 文档化、双 parent 裁决规则、agent.start 契约；推翻 Task 12「不改 reconcile」旧约束） |

### 已评估取消

| Task | 状态 | 结论 |
|---|---|---|
| [Task 19](./19_world_expansion_output_retargeting.md) | `CANCELLED` | 经训练数据多题材对照（修仙/无限流/序列流），"强制收编"方向不成立。世界契约组织形态是题材相关的，应由 world Agent 按题材自选，四个 expansion 维持独立输出。 |
| [Task 23](./23_stale_propagation_scope.md) | `CANCELLED` | 经技术评估，asset 级依赖图无设定项粒度，scope 判定不可机械化；靠声明则判错会 silently 漏标 stale。全树 stale 保证一致性铁律，是合理代价。 |

九条建议处理完毕：5 条落地（Task 17/18/20/21/22），2 条经评估取消（Task 19/23）。全部通过 AGENTS.md 验证套件（根测试 53 + MCP 测试 173 + 14 项检查脚本）。

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
| [Task 12](./12_archetype_llm_merge_agent.md) | 新增临时 `onboarding_agent` 角色固化多原型 LLM 深度融合，`creator_derivation_candidate` schema + 确定性收口双路径，13 角色契约就绪 |
| [Task 13](./13_planning_skill_schema_checklists.md) | 完成规划/审查 Skill 操作前置检查、book_soul 速查表与 `creative_contracts._validate` 错误信息改进，通过 53 项根测试与 158 项 MCP 测试 |
| [Task 14](./14_planning_catalog_and_id_checklists.md) | 新增 Catalog 搜索参数值、snapshot hash 校验、项目 ID 前缀与 upstream_refs 格式操作前置检查 |
| [Task 15](./15_volume_outline_pacing_density.md) | 新增 Volume Outline 节奏密度约束（战略骨架不可碎 + 并行冲突线/副高潮/POV 多样性 + 节奏阀门） |
| [Task 16](./16_review_prompt_self_containment.md) | 修复审查 sub-agent token 暴涨：审查 prompt 必须自包含全部上游原文，禁止依赖 sub-agent 自行读文件 |

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
