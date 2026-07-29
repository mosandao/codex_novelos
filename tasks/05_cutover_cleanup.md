# Task 05: 切换、清理与交付

状态：`BLOCKED`

依赖：[Task 02](./02_mcp_storage_migration.md)、[Task 03](./03_skill_catalog_migration.md)、[Task 04](./04_agent_workflows_quality.md)

## 目标

将默认生产入口切换到纯 Codex + NovelOS MCP，删除重复 Python Agent Runtime，并形成可回滚、可验证的交付状态。

## 切换前置条件

- MCP Wave A、B 完成并通过协议测试。
- 六个顶层 Skill 已验证。
- Catalog Wave A 可被章节闭环实际调用。
- 草稿—审查—接受和连续性更新端到端通过。
- 数据迁移完成对账并保留原始数据库备份。
- 质量实验已决定 Writer Agent 和 Context Builder 的最终触发策略。

## 删除范围

最终删除与修改范围以 `tasks/cutover/removal_manifest.json` 为唯一来源。当前处于 `prepared` 阶段，清单要求旧路径继续存在且每项都有替代证据；只有所有切换前置门禁通过后，才能在单独可审查变更中将 phase 改为 `cutover` 并执行删除。

删除范围包括：

```text
src/novelos/
scripts/run_memory_mcp.sh
pyproject.toml
config.example.toml
tests/test_architecture.py
tests/test_config.py
```

不得在替代路径完成前删除旧实现。删除必须发生在单独、可审查的变更中。

## 配置切换

- `.codex/config.toml` 只注册新的 `novelos` MCP。
- 移除 Python 模型 Provider 和 `OPENAI_MODEL` 应用配置。
- Codex 模型选择由 Codex 产品配置负责，不由 NovelOS 代码负责。
- MCP 配置只包含数据库、Catalog、资源和日志位置。
- 密钥不得进入仓库；纯本地 SQLite V1 不需要应用级 API Key。

## 文档交付

在 `documentation/` 建立稳定系统文档：

- `architecture.md`
- `flows.md`
- `permissions.md`
- `variables.md`
- `tests.md`
- `automation.md`

无 UI、无邮件、无定时任务、无 SEO 时，在架构文档中明确说明，不创建空文档。

根 README 只保留用户安装、运行和最小架构说明，实施状态留在 `tasks/`。

## 回滚

- 数据迁移前生成只读备份和 Hash。
- 新 Schema 只通过前向迁移更新，不原地破坏来源数据库。
- 切换 commit 可恢复旧入口，但不得让新旧 Runtime 同时成为默认入口。
- 回滚后新写入数据必须有明确降级或导出路径。

## 待办

- [x] 建立迁移前数据库备份、Hash 和恢复演练。
- [x] 运行完整数据对账。
- [ ] 切换 `.codex/config.toml` 到新 MCP。
- [ ] 在全新 Codex 任务中验证 Skill 和 MCP 可发现。
- [ ] 运行纯 Codex 章节、规划、连续性端到端场景。
- [ ] 删除重复 Python Agent/Skill/LLM Runtime。
- [ ] 删除不再使用的依赖、CLI 和配置项。
- [x] 创建稳定 `documentation/` 文档集。
- [x] 更新 README、AGENTS 和测试命令。
- [x] 执行回滚演练。
- [x] 建立切换后新写入的确定性 JSONL 导出与恢复路径。
- [x] 冻结并校验完整的旧 Runtime 删除、目标修改和保留路径清单。
- [x] 建立可重建的迁移统计和延后项汇总，在最终切换前保持 `prepared`。
- [ ] 记录最终迁移统计和明确延后项。

## 最终测试

- [x] Python 编译和全部 MCP/Domain/Storage 测试。
- [x] Skill 结构校验。
- [x] MCP stdio 初始化、工具、资源和错误协议测试。
- [x] 全新数据库初始化测试。
- [x] 已授权 Legacy 来源数据库到目标数据库迁移对账。
- [x] 新 MCP 无 OpenAI SDK、无应用 LLM Gateway 的运行测试。
- [x] Agent 权限负向测试。
- [x] Hash/Receipt/版本/事务失败注入测试。
- [x] 无 Git 基线条件下检查 prospective 文件集、忽略规则、生成物和本地敏感文件。
- [ ] 纯 Codex 端到端验收。
- [ ] 建立 Git 基线后执行最终 diff 和仓库产物卫生复核。

## 验收标准

- [ ] 默认入口只有 Codex + `novelos` MCP。
- [ ] 仓库中不存在第二套 Agent Runtime。
- [x] 所有权威写入都能从 Trace 追溯到同一 subject 和 Review Receipt。
- [x] 迁移数据完整，回滚过程经过实际验证。
- [x] 文档明确当前能力、权限、变量和测试覆盖缺口。
- [x] 延后项保留在 Task 文件，不以空实现冒充完成。

## 验证证据

当前证据：

- `documentation/`：架构、关键流程、权限、变量、测试和 Agent 自动化 6 份稳定文档；系统无邮件、定时任务和 SEO，因此未创建空文档。
- `scripts/run_novelos_mcp.sh`：只启动统一 `novelos_mcp.server`，显式绑定 `novelos-v2.db`、Catalog 和 Agent contract；检测到未授权 seed 或 inventory 配置时拒绝启动。
- `mcp/novelos/tests/test_runner_protocol.py`：通过启动脚本在全新临时数据库完成 stdio 初始化并发现 63 个统一工具，旧写接口不可见。
- Migration 008：`authority_commits` 将五类 Review 门禁提交与运行中 Trace、subject Hash、Review Receipt 和结果引用原子绑定；`trace.audit_authority` 对项目内已提交状态做完整覆盖审计。
- `mcp/novelos/tests/test_pure_codex_workflow.py`：完整链产生 11 条权威提交并通过项目级追溯审计；`test_agent_workflows.py` 证明跨 Trace Reviewer 在状态写入前被拒绝。
- `scripts/backup_novelos_database.py`：使用 SQLite backup API 创建 Schema 9 备份并恢复到临时数据库；正式库、备份和恢复库逻辑 Hash 均为 `sha256:2ac772b894f4bf22d50964a41016f021eb681ec5981cf95f39dbab677eedfe0d`。
- 恢复证据：`tasks/migration/schema9_restore_drill.json`，`quick_check=ok`，Schema 1–9 和全部表计数一致；Schema 8 备份保留为升级前回滚点。
- `scripts/export_novelos_data.py`：为切换后新增写入提供 Schema、逐表 JSONL、BLOB 编码和 Hash Manifest 导出；目标目录存在时拒绝覆盖，恢复时先导入数据再建立索引、触发器和视图。`tasks/migration/schema9_export_drill.json` 证明 31 张表、32 行恢复后的逻辑 Hash 与备份证据一致，演练仅使用临时目录。
- `tasks/cutover/readiness.json`：当前 `not_ready`；seed 授权门禁已通过，剩余质量实验、默认配置切换、旧模型配置删除、旧 Runtime 删除和 Git 审查基线 5 个门禁。
- `tasks/cutover/removal_manifest.json`：冻结完整旧 Runtime、入口、打包、配置和测试删除范围，并记录每项替代证据、保留路径、切换前置条件及目标文件断言；`scripts/check_cutover_plan.py --check` 在 prepared/cutover 两阶段失败关闭。
- `tasks/migration/migration_summary.json`：由 `scripts/build_migration_summary.py` 从来源 Manifest、Legacy 对账、Schema 9 恢复、Catalog disposition、seed 授权、质量实验和 readiness 动态重建；当前为 `prepared`，明确记录 633 个源码延后项、5 张 Wave D 表、130 个 Catalog 延后 disposition 和 5 个切换门禁，不以手写计数冒充最终统计。
- `tasks/cutover/hygiene.json`：由 `scripts/check_repository_hygiene.py` 从 Git prospective 文件集和文件系统动态生成；当前 204 个候选文件中禁止产物与敏感文件均为 0，必需忽略规则齐全。因仓库没有 HEAD，状态保持 `prepared`，不能替代最终 `git diff`。
- 清理计划校验器扫描 `src/`、`scripts/`、`tests/`、`.codex/` 和根配置；任何未纳入删除/修改清单的旧 `novelos` 包、Memory MCP、OpenAI 应用变量或模型配置引用都会失败。
- 质量门禁只接受 `scripts/summarize_agent_quality_results.py` 从完整 70 case 证据重算且与文件逐字一致的 `summary.json`；缺 case、篡改 evidence、复用 Reviewer/Receipt 或非法评分均保持 `quality_experiment_complete=false`。
- 已授权 Legacy 来源与目标的 projects、books、volumes、chapters、characters 计数和逐表 Hash 已由 `tasks/migration/legacy_migration_report.json` 及 `tests/test_legacy_migration_artifacts.py` 对账；未授权 seed 不计作已迁移数据。
- 当前仓库 `main` 尚无 commit 且已跟踪文件数为 0，无法执行有基线的最终 `git diff`；readiness 以 `git_review_baseline_available` 失败关闭，在用户建立可审查基线前不得报告 `ready`。
- 当前验证：根测试 40 个、MCP 测试 81 个全部通过；Migration/Catalog manifest、Agent 质量录制器/数据集/结果证据、seed inventory、迁移汇总、备份/导出恢复、仓库卫生、cutover plan/readiness 和 `compileall` 检查通过。

不得因为准备项通过就提前切换。状态为 `DONE` 时继续记录最终 commit、切换后新 Codex 任务证据、数据统计和仓库卫生检查。

解阻条件：Task 04 完成；用户已经允许建立首个 Git 审查基线，并在全部 readiness 前置门禁通过后执行配置切换和旧 Runtime 删除。
