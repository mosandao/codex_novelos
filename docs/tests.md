# 测试覆盖

## 现有覆盖

| 用例 | 固定规则与拒绝路径 | 证据 | 状态 |
|---|---|---|---|
| Agent 契约 | 仅 Main 常驻；8 类唯一 owner；临时工具只读；Profile 注册表与全部 binding 启动期失败关闭；自定义配置不读取兼容快照 | `mcp/novelos/tests/test_agent_contracts.py` | existing |
| Agent 生命周期 | Spawn/Destroy、活动 run 阻止 Trace 结束、失败/超时无部分结果；`isolation_evidence` 默认 lenient 告警与 strict 拒绝 | `mcp/novelos/tests/test_agent_workflows.py` | existing |
| change proposal | 只能绑定当前项目 locked 上游的精确 ID/版本/Hash和合法下游影响 | `test_agent_workflows.py` | existing |
| Character/World | run 可并行；提供的 cross-check 必须 approved、匹配且非 stale，并在 lock 时重验；缺失时覆盖 lenient 告警与 strict 拒绝 | `test_planning.py`、`test_pure_codex_workflow.py` | existing |
| 规划状态机 | 唯一生产者、精确上游、Review Profile、递归 `stale` | `test_planning.py` | existing |
| 章节门禁 | 正文 Hash 变化使 Review 失效；blocking finding 阻止接受 | `test_service.py` | existing |
| Entity 修改 | 五类 Entity 都必须经过来源绑定候选与 Review | `test_entity_mutations.py` | existing |
| 连续性晋升 | Authority Snapshot、Hash、Review 和单事务 | `test_service.py`、`test_pure_codex_workflow.py` | existing |
| 权威追溯 | 五类提交原子绑定 Trace/subject/Receipt；跨 Trace 拒绝；项目覆盖审计 | `test_pure_codex_workflow.py`、`test_agent_workflows.py` | existing |
| 作者签名与项目创建 | V3 系统叙事原型加载、standalone bundle Hash、Top 3 推荐、JSON handoff、仅派生模式 (`derive`) 原子绑定、只读系统原型保护、归档、精确 Hash、rebind 失效与 Trace | `test_system_archetypes.py`、`test_creator_profiles.py`、`test_project_wizard.py` | existing |
| 项目删除 | 项目删除的 Trace/投影/authority commit 门禁；删除项目不删除可复用 Creator Profile | `test_core_tools.py`、`test_creator_profiles.py` | existing |
| Service 结构 | `service/` 包聚合 8 个领域 Mixin，构造签名和容器方法兼容，不与旧 `service.py` 并存 | `test_service_structure.py` | existing |
| MCP 协议 | stdio 初始化、81 条直连工具 + 1 个 wizard 编排（总数 82）、项目创建向导 Resource、公开写接口和 Resource Template | `test_protocol.py`、`test_runner_protocol.py` | existing |
| 数据迁移 | 固定来源 Hash、计数、目标对账和前向 Migration | `tests/test_legacy_migration_artifacts.py`、`test_migrations.py` | existing |
| Seed 接入门禁 | 授权副本与合成数据均验证 seed/inventory、文件/表/Schema/内容 Hash、sidecar、运行后篡改、只读写拒绝和 stdio 查询 | `test_seed_integrity.py`、`test_protocol.py` | existing |
| Skill/Catalog | 6 个顶层 Skill、37 个 Catalog 包（29 个 active + 8 个 experiment）、来源和 typed Schema | `tests/test_project_skills.py`、Catalog tests | existing |
| 质量数据集 | 40+10+10+10 输入、70 case 执行清单、合法 Spawn、盲评 Rubric | `tests/test_agent_quality_dataset.py` | existing |
| 质量结果证据 | 完整覆盖、输入/evidence Hash、run/Receipt 隔离、自动解盲决策、篡改拒绝 | `tests/test_agent_quality_results.py` | existing |
| 切换删除清单 | 旧 Runtime/入口/配置/测试完整覆盖、替代证据、两阶段断言、遗漏引用扫描 | `tests/test_cutover_plan.py` | existing |
| 备份恢复演练 | source/backup/restore 逻辑 Hash、Schema 12、计数和 `quick_check` 一致 | `schema12_restore_drill.json`、`test_shipping_artifacts.py` | existing |
| 降级数据导出 | Schema/JSONL/Hash Manifest 可恢复；Creator Profile 历史/绑定、BLOB、触发器和篡改拒绝 | `schema12_export_drill.json`、`test_data_export.py` | existing |
| 创作约束投影 | 精确作者 revision/Hash、只展示 locked Direction 的 `book_soul`、旧项目缺失态和 manifest 来源 ref | `test_projection.py` | existing |
| 迁移汇总 | 来源、Legacy、Catalog、seed、质量实验和切换门禁动态重建；统计篡改失败关闭 | `migration_summary.json`、`test_migration_summary.py` | existing |
| 仓库产物卫生 | prospective Git 文件集、忽略规则、生成物和本地敏感文件失败关闭 | `hygiene.json`、`test_repository_hygiene.py` | existing |

当前基线为 53 项根测试和 154 项 MCP 测试。Profile 测试覆盖 binding 缺失、键名拼错、空值、未注册引用、自定义运行时映射，以及 enforcement 缺省值、boolean 类型、未知 key 和未知查询名；交叉审查测试覆盖 pending、错配、stale、缺失及 lock 前来源失效。完整本地门禁还包括 Migration/Catalog manifest、Agent 质量数据集、seed inventory、迁移汇总、备份/导出恢复、仓库卫生、cutover plan/readiness 和 `compileall` 检查。仓库没有 CI，这些检查目前不自动阻止合并。

## 已提出但未完成

| 用例 | 类型 | 预期证据 | 状态 |
|---|---|---|---|
| 70 个真实 Agent 质量实验 | guarded live + manual blind review | 原始输入、匿名输出、评分、Reviewer run 和 Receipt | deferred |
| 独立 Codex CLI 进程发现新 MCP/Skill | integration | `codex mcp list`、runner stdio 调用、6 个 Skill 发现 | completed |
| 最终 `.codex` 切换 | automated integration + manual | 只启动一个 `novelos`，旧 Server 不可发现 | completed |

## 缺口

| 风险 | 未验证规则 | 暴露 |
|---|---|---|
| 中 | Writer/上下文构建智能体 尚无完整真实质量结论 | 当前使用保守触发范围，不能宣称质量优势或扩大路由 |
| 中 | 没有 CI 或受保护分支门禁 | 本地检查可能被跳过 |
| 中 | Agent context 隔离依赖 Main 正确创建 Codex 临时上下文 | 协议记录不能单独证明模型上下文未复用 |
