# Task 01: 源工程迁移盘点

状态：`DONE`

源工程：`/Users/yiyi/github/novelos`

## 目标

冻结可审计的来源快照，生成逐文件迁移 Manifest，并把内容分为直接迁移、适配迁移、延后和不迁移。

## 冻结来源

本次迁移只使用源仓库已提交的 Git object，不读取 dirty worktree 作为迁移内容：

| 项目 | 值 |
|---|---|
| 分支观察值 | `feat/awesome-novel-absorption` |
| 来源 commit | `902d7e62f55bc8bc2862e2b9574b5ee2f5f33403` |
| 来源 tree | `3d0d32221a9d5332dd25a82868b840469288be60` |
| 来源策略 | `committed-head-only` |
| 已提交文件 | 1,260 |
| dirty 状态项 | 108，全部排除并单独盘点 |

完整指纹记录在 [source_snapshot.toml](./migration/source_snapshot.toml)。逐项 dirty 路径及 HEAD/worktree Hash 记录在 [dirty_inventory.csv](./migration/dirty_inventory.csv)。后续若要吸收这些未提交内容，必须先形成新的明确 commit，再重新生成 Manifest；不得直接从当前工作目录复制。

## 冻结基线

以下数据从固定 commit 重新生成，替代此前基于 dirty worktree 的估算：

- Backend Python：114 个模块，33,371 行。
- Backend tests：188 个 `test_*.py` 文件。
- 主 Schema：37 张表。
- Skill：138 个 metadata 包，其中 100 个 `active`、38 个 `experiment`。
- `seed.db`：23 张 `kb_*` 表，共 8,108 条记录。

## 迁移产物

| 文件 | 用途 |
|---|---|
| [source_manifest.csv](./migration/source_manifest.csv) | 1,260 个已提交文件的来源、SHA-256、分类、目标、许可证和测试映射 |
| [table_inventory.csv](./migration/table_inventory.csv) | 37 张主表的 Wave A-D 分配 |
| [skill_inventory.csv](./migration/skill_inventory.csv) | 138 个 Skill 的 lifecycle、stage、asset、capability 和来源 |
| [seed_inventory.csv](./migration/seed_inventory.csv) | 23 张知识表逐表记录数 |
| [dirty_inventory.csv](./migration/dirty_inventory.csv) | 108 个未提交状态项及排除决定 |
| [source_snapshot.toml](./migration/source_snapshot.toml) | commit/tree、dirty 指纹和统计汇总 |

Manifest 分类统计：

| 分类 | 文件数 | 含义 |
|---|---:|---|
| `direct` | 1 | 固定 Hash 的只读 `seed.db` |
| `adapt` | 531 | 提取契约、Storage、Catalog、测试或来源说明后适配目标架构 |
| `defer` | 633 | 实验 Skill、Shadow、评测、恢复、资源或高级能力，等待消费者和质量证据 |
| `reject` | 95 | UI、Presentation、LLM、旧 Agent Runtime、缓存或旧入口 |

## 分类原则

### A. 优先迁移

- Project、Book、Volume、Chapter、Character、World、Faction、Rule、Timeline、Review 模型。
- ChapterFact、Continuity、Narrative Asset 的领域契约。
- `backend/src/infrastructure/sqlite/seed.db`。
- 核心 Repository、Schema 约束和对应数据库测试。
- lifecycle 为 `active` 的 Skill Prompt、metadata、Schema、Validator 及来源信息。

除 `seed.db` 外均标为 `adapt`，因为目标包名、权限边界和单 MCP 架构与来源工程不同，不能机械复制。

### B. 提取语义后重构

- ContextBuilder：保留阶段化读取和投影方法，查询移入 MCP，相关性判断交给 Codex。
- MemoryAgent：保留事实候选、正文 Hash、独立冲突复核和原子提交契约；删除 Agent、LLM 和直接 DB 组合。
- Plugin Kernel：保留 Catalog 扫描、metadata 硬过滤、版本、Schema 和 Validator；删除语义路由。
- Trace、Review Receipt、Authority Snapshot 和版本失效规则。
- Planning、Story Arc、Core Character 等领域 Schema；Python Runner 只作为语义参考，不作为执行 Runtime 迁移。

### C. 延后

- lifecycle 为 `experiment` 的 38 个 Skill 及其包内文件。
- Shadow Runner、自动晋级、大型评测、恢复和 Work Completion 流水线。
- 未完成许可证或实际消费者审查的 autonomous resources。
- 不属于 V1 章节生产闭环的高级测试夹具和文档参考。

### D. 不迁移

- `backend/src/application/runtime/`
- `backend/src/application/sub_agents/`
- `backend/src/infrastructure/llm/`
- `backend/src/presentation/`
- `frontend/`
- 固定意图到固定 Skill 的 Planner、旧配置和构建入口。

## 数据迁移波次

- Wave A：10 张核心创作表。
- Wave B：8 张记忆与连续性表。
- Wave C：14 张规划资产表。
- Wave D：5 张高级完成度表，延后。

逐表名称和理由见 [table_inventory.csv](./migration/table_inventory.csv)。固定 commit 中没有 dirty worktree 新增的 Story Strategy、Core Character Registry 等表；这些未提交设计不得假装属于冻结来源，后续只能在新来源 commit 或目标架构中独立实现。

## Skill 来源与授权

- `craft` 插件依据源仓库 [awesome-novel-skill 授权记录](/Users/yiyi/github/novelos/docs/third_party/awesome_novel_skill.md) 标记为 `awesome-novel-skill:GPL-3.0:user-authorized`。
- 外部写作参考资料保持 `license-unverified:research-only`，本阶段全部 `defer`，不得进入生产 Prompt。
- 固定 commit 没有仓库级 LICENSE 文件；其余内容标记为 `novelos-repository:license-unverified`。这是失败关闭状态，进入实际迁移前必须确认项目级授权或逐项来源。
- 每个 Skill 的来源字段和生命周期见 [skill_inventory.csv](./migration/skill_inventory.csv)。

## 测试映射

- Domain 文件映射到 `mcp/novelos/tests/domain`。
- SQLite 文件映射到 `mcp/novelos/tests/storage`。
- Plugin/Catalog 文件映射到 `mcp/novelos/tests/catalog`。
- Application 契约映射到 `mcp/novelos/tests/services`，不移植 LLM 编排本身。
- 可复用 `backend/tests/test_*.py` 映射到 `mcp/novelos/tests/ported/`。
- 延后和拒绝项使用明确的 deferred/not-applicable 测试标记。

每个文件的具体目标和测试范围记录在 [source_manifest.csv](./migration/source_manifest.csv)。

## 待办

- [x] 冻结源工程快照，记录 commit、tree 和 dirty 指纹。
- [x] 选择已提交 HEAD 作为来源，不覆盖或吸收用户 dirty 改动。
- [x] 生成逐文件 SHA-256 和分类 Manifest。
- [x] 盘点 37 张固定快照主表并分配 Wave A-D。
- [x] 盘点 138 个 Skill 的 lifecycle、stage、asset、capability 和来源。
- [x] 标记 `awesome-novel-skill` 的 GPL-3.0 与用户授权来源。
- [x] 映射可复用测试到目标 MCP、Domain、Catalog 测试。
- [x] 对 108 个未提交状态项单独记录并排除。

## 验收标准

- [x] 固定 commit 的 1,260 个文件均有唯一 Manifest 条目。
- [x] 所有 `direct`/`adapt` 条目都有非空 commit、SHA-256 和唯一目标路径。
- [x] 第三方或未知授权内容均有非空来源字段并执行失败关闭。
- [x] `direct`/`adapt` 条目均有测试目标或测试套件映射。
- [x] reject 规则覆盖旧 Agent Runtime、LLM、Presentation 和 Frontend 入口。
- [x] Manifest 校验测试通过，重复来源和生产目标路径冲突均为零。

## 验证证据

- 生成：`.venv/bin/python scripts/build_migration_manifest.py --source /Users/yiyi/github/novelos --commit 902d7e62f55bc8bc2862e2b9574b5ee2f5f33403 --output-dir tasks/migration`。
- 校验：`.venv/bin/python scripts/build_migration_manifest.py --output-dir tasks/migration --check`，通过。
- 测试：`.venv/bin/python -m unittest discover -s tests -v`，12 个测试通过。
- 统计：1,260 个 Manifest 条目；生产目标冲突 0；37 张主表；138 个 Skill；23 张知识表、8,108 条记录。
