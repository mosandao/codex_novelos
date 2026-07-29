# Task 02: MCP 与 Storage 迁移

状态：`DONE`

依赖：[Task 01](./01_source_migration_inventory.md)

## 目标

建立纯执行型 NovelOS MCP，将源工程领域模型、SQLite、知识库、连续性和审查契约迁入统一工具边界，不包含任何 LLM 或语义路由。

## 当前进度

- 已创建独立 `mcp/novelos` Python 包和唯一 `novelos` FastMCP Server。
- 已建立 Wave A 的 10 类核心表、不可变 Resource、Review 和 Schema 版本表。
- 统一 Server 当前包含 Core、Memory、Continuity、Planning、Knowledge、Catalog、Review、Entity Mutation、Trace、Resource 和 Agent Workflow 共 63 个工具、3 个 Resource Template；其中 Agent Workflow、交叉审查、评测 Review Subject 和权威追溯工具在 Task 04/05 实现。
- 已实现 `subject_hash`、乐观版本、事务回滚和草稿—审查—接受门禁。
- 已完成 Wave B 连续性候选、Review 和原子晋升，以及 Knowledge/Catalog 只读工具。
- 已从固定只读快照正式迁移 legacy 数据到 `data/novelos-v2.db`，报告记录于 `tasks/migration/legacy_migration_report.json`；来源 4 个项目、3 本书、3 卷、4 章、2 个人物全部迁移，隔离项为 0。
- 已用统一 `planning_assets` 和显式依赖表实现 Wave C，覆盖八类规划资产候选、唯一生产者、精确上游版本、Review 锁定和递归 `stale` 传播，避免复制八套硬编码表。
- 已增加 Catalog `typed_result` 的标准 JSON Schema 校验工具；Review finding 和 continuity owner 在最终写入边界再次严格校验。
- 已移除公开 `character/world/faction/rule/timeline.upsert`，统一改为 `entity.prepare_mutation -> review.record -> entity.commit_mutation`；候选绑定规划来源、payload Hash、目标版本和 Review Receipt。
- Migration 008 增加 append-only `authority_commits`；五类 Review 门禁提交必须把同一 Trace、subject Hash、Review Receipt 和结果引用写入同一事务，并可通过 `trace.audit_authority` 做项目级覆盖审计。
- `seed.db` 已按用户明确授权从固定 commit/Hash 复制到 `mcp/novelos/resources/seed.db`，生产 inventory、只读查询和 runner stdio 路径均已验证。
- 来源侧只读完整性已冻结：23 张 `kb_*` 表、8,108 条、逐表 Schema/内容 Hash 均记录在 `tasks/migration/seed_source_inventory.json`；用户授权审计记录于 `tasks/migration/seed_authorization_audit.md`。固定 commit、路径和 Hash 的完整 seed 已复制到 `mcp/novelos/resources/seed.db`，该授权不扩展到其他 `defer-license` Catalog 项。
- `KnowledgeStore` 仅在 seed 与 inventory 同时配置且文件 Hash、`quick_check`、精确表集合、逐表 Schema/内容 Hash 和计数全部一致时启动；连接固定为 `mode=ro&immutable=1` 与 `query_only`，活动 WAL/SHM/journal 或校验后的文件变化会失败关闭。

## 目标包结构

```text
mcp/novelos/
├── pyproject.toml
├── src/novelos_mcp/
│   ├── server.py
│   ├── domain/
│   ├── tools/
│   ├── services/
│   ├── storage/
│   ├── validators/
│   └── resources/
└── tests/
```

V1 只运行一个 stdio MCP Server。内部可按模块拆分，外部不增加进程间复杂度。

## 数据迁移波次

### Wave A：核心创作数据

- projects
- books
- volumes
- chapters
- characters
- worlds
- factions
- rules
- timelines
- reviews

### Wave B：记忆与连续性

- chapter_facts
- continuity_candidate_sets
- continuity_update_results
- chapter_completion_checkpoints
- narrative_promises
- expectation_ledgers
- relationship_states
- arc_states

### Wave C：规划资产

- story_direction_sets
- architecture_plans
- architecture_artifacts
- architecture_reviews
- prompt_recipes
- story_planning_windows
- story_arc_outlines
- core_character_sets/registries
- story_strategy_skeletons

上述 legacy 表只作为字段语义来源。目标侧不逐表复制，而是统一为 `planning_assets`、`planning_asset_dependencies` 和不可变 Markdown Resource；`asset_type` 区分八类权威资产，控制信封只保存版本、Hash、状态和引用。

### Wave D：延后资产

- Shadow、自动晋级、评测 Receipt 和高级恢复表。
- Work completion 的高级证明链。
- 未进入 V1 流程且缺少稳定消费者的表。

不得一次复制全部 Schema。每个 Wave 必须有消费者、工具、迁移测试和回滚策略。

## 工具设计

### Core

```text
project.create/get/list/update
book.create/get/list
volume.create/get/list
chapter.create_draft/get/list/update_draft
chapter.accept/supersede
character.get/list
world.get/list
faction.get/list
rule.get/list
timeline.get/list
entity.prepare_mutation
entity.commit_mutation
```

### Memory / Continuity

```text
memory.recent_chapters
memory.search_facts
memory.get_entity_states
memory.get_authority_snapshot
continuity.record_candidates
continuity.get_candidates
continuity.promote_reviewed
```

### Planning

```text
planning.create_candidate
planning.get
planning.list
planning.lock
planning.prepare_cross_check
planning.approve_cross_check
planning.get_cross_check
```

### Knowledge / Catalog

```text
knowledge.search
knowledge.get
skill_catalog.search
skill_catalog.get
skill_catalog.validate
skill_catalog.validate_input
skill_catalog.validate_output
```

### Review / Trace

```text
review.record
review.get
review.prepare_subject
review.get_subject
resource.create
trace.start
trace.record_step
trace.get
trace.finish
agent.start
agent.finish
agent.get
agent.list
```

## 权威写入协议

正文接受必须执行：

```text
chapter.create_draft
  -> draft_ref + subject_hash
review.record
  -> review_ref bound to subject_hash
chapter.accept(draft_ref, review_ref)
  -> deterministic hash/verdict/state checks
```

MCP 拒绝以下情况：

- Review 的 `subject_hash` 与草稿不一致。
- 存在 blocking finding。
- Review 不属于当前草稿版本。
- 状态转换不是合法边。
- Authority base version 已被更新。
- 写入缺少来源引用或事务中间步骤失败。

## 结构化数据边界

必须保留结构化 Schema：

- Tool 参数与返回控制信封。
- ID、版本、Hash 和 Artifact 引用。
- 状态机与权限。
- Fact Candidate、State Update 和 Review Receipt。
- Catalog metadata 和 Validator 结果。

改为 Markdown/MCP Resource：

- 小说正文。
- 世界观和人物长描述。
- 规划正文与解释。
- Skill Prompt、examples 和长审稿说明。
- 大型上下文包。

控制信封只携带 `resource_ref`、`subject_hash`、类型和版本，不重复嵌入长内容。

## 待办

- [x] 创建独立 `mcp/novelos` 包并建立统一 FastMCP 启动入口。
- [x] 定义统一错误码、分页、资源引用和版本规范。
- [x] 实现 Wave A 目标 Domain、Schema、Repository 和工具。
- [x] 实现固定来源 Schema 到目标 Wave A/B 的 legacy 数据迁移和对账。
- [x] 将 `seed.db` 作为只读资源迁入，验证 23 张表和 8,108 条记录。
- [x] 对固定来源 `seed.db` 建立不含正文的 23 表/8,108 条只读完整性清单和授权审计。
- [x] 实现复用 frozen inventory 的运行时完整性校验器，并以合成 seed 覆盖成功和失败路径。
- [x] 迁移 Wave B 连续性契约和原子提交逻辑。
- [x] 按实际 Skill/Agent 消费者迁移 Wave C。
- [x] 实现草稿—审查—接受两阶段协议。
- [x] 实现只读 MCP Resources，避免大型 JSON 返回。
- [x] 增加数据库升级版本表和前向迁移机制。
- [x] 增加精确来源 Hash、Receipt 和 append-only Trace 写入。
- [x] 禁止 MCP 包依赖 OpenAI SDK 或任何模型 Provider。

## 测试

- [x] Domain 状态、严格候选字段和参数校验单元测试。
- [x] 每个生产工具命名空间的声明操作、事务回滚和并发版本测试。
- [x] MCP `initialize`、`tools/list`、`tools/call` 协议测试。
- [x] 只读 Resource 获取和不存在资源测试。
- [x] `subject_hash` 不一致拒绝测试。
- [x] blocking Review 拒绝接受测试。
- [x] stale base version 拒绝测试。
- [x] 八类规划资产唯一生产者、精确上游类型和完整锁定链测试。
- [x] 上游新版本递归标记下游 `stale`，且失效候选不能锁定。
- [x] 规划 Review 的 subject hash 和 Profile 不匹配拒绝测试。
- [x] Review evidence、连续性 owner 和 Catalog typed output 未知字段拒绝测试。
- [x] 合成 `seed.db` 的 inventory Schema、文件 Hash、精确表集合、Schema/内容 Hash、计数、sidecar、运行后篡改、只读写拒绝和 stdio 查询测试。
- [x] 对迁入的真实 `seed.db` 执行 23 表/8,108 条完整性、只读和生产 stdio 查询测试。
- [x] Schema 迁移前后数据计数与 Hash 对账。
- [x] 失败调用不产生部分权威写入。

## 验收标准

- [x] Codex/Skill 不导入 SQLite Repository。
- [x] MCP Server 不包含 Prompt、LLM 调用或语义选择逻辑。
- [x] Wave A、B 的生产工具和测试全部通过。
- [x] 大型正文、Knowledge 和 Catalog 内容通过 Resource 提供。
- [x] 所有叙事权威写入有版本、Hash、Receipt 和事务保护。
- [x] MCP stdio 初始化、工具调用和 Resource Template 端到端测试通过。

## 验证证据

当前阶段证据：

- `PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v`：当前 81 个测试通过，无连接泄漏。
- `PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s tests -v`：当前 40 个架构、Manifest、Skill、实验录制/数据集/结果证据、迁移汇总、仓库卫生、切换清单、备份/导出恢复与真实迁移产物测试通过。
- `.venv/bin/python -m compileall -q src tests mcp/novelos/src mcp/novelos/tests scripts catalog config`：通过。
- stdio：Server 名称 `novelos`，63 个工具，3 个 Resource Template；五个 authority `*.upsert` 不再注册。
- Legacy 来源：`data/migration/backend-novelos-aaadc9bedf499e.db`，SHA-256 为 `aaadc9bedf499e9a10534422064d4d91862293529bccac160843e0ab846ae1ba`。
- Legacy 目标：`data/novelos-v2.db`；`PRAGMA quick_check` 返回 `ok`，Schema version 为 1、2、3、4、5、6、7、8、9。
- 对账：projects 4、books 3、volumes 3、chapters 4、characters 2，隔离项 0；逐表目标 Hash 记录在 `tasks/migration/legacy_migration_report.json`。
- Wave C：八类规划资产完整锁定链通过；新上游版本替换后，已锁定和候选下游均递归变为 `stale`。
- Entity Mutation：character、world、faction、rule、timeline 均通过来源失效、Review Profile、并发版本和无部分写入测试。
- Seed 接入门禁：`mcp/novelos/tests/test_seed_integrity.py` 同时验证合成数据和授权生产副本的 seed/inventory、文件与逐表 Hash、精确表集合、23 表/8,108 条、SQLite sidecar、校验后变更和只读写拒绝；`test_runner_protocol.py` 证明统一生产 runner 可直接执行真实 Knowledge 查询。
- 来源 inventory 可由 `.venv/bin/python scripts/build_seed_inventory.py --check` 重建，生产副本由同一算法通过 `.venv/bin/python scripts/build_seed_inventory.py --production --check` 验证；runner 固定目标路径并拒绝环境变量替换。
