# Task 03: Skill Catalog 迁移

状态：`DONE`

依赖：[Task 01](./01_source_migration_inventory.md)、[Task 02](./02_mcp_storage_migration.md) 的 Catalog 工具骨架

## 目标

把源工程细粒度创作能力迁入按需 Catalog，仅保留六个顶层 Codex Skill，减少固定 Skill 名、巨大候选 JSON 和 Prompt 重复加载。

## 当前进度

- 六个顶层项目 Skill 已建立并统一为纯 Codex 工作流，均包含中文 `SKILL.md` 和有效 `agents/openai.yaml`。
- 已建立 17 个生产 Catalog 包：6 个 Wave A、7 个新增 Wave B 和 4 个 Wave C；其中八类规划资产均有唯一方法候选。
- Catalog 已强制包名唯一、目录名一致、严格 metadata、三类 `output_contract`、完整 provenance、候选快照 membership 和按需 Prompt Resource。
- 固定来源 138 个 Skill 已逐项分类；8 个已授权 craft Prompt 合并适配为 6 个目标包，92 个授权未核清 active 包与 38 个 experiment 包继续失败关闭。

## 顶层 Codex Skills

| Skill | 职责 | 允许的主要工具 |
|---|---|---|
| `novel-project` | 项目、书、卷、章节显式管理 | project/book/volume/chapter |
| `novel-planning` | 识别规划阶段、准备输入包、选择 Catalog 方法并约束候选输出 | planning/catalog/knowledge |
| `novel-memory` | 选择并组织任务相关上下文 | memory/knowledge/catalog 只读 |
| `novel-writing` | 写作和局部改写方法 | catalog/knowledge 只读 |
| `novel-review` | 规划、正文、连续性审查方法 | review/memory 只读，record 由 Main 调用 |
| `novel-continuity` | 提取事实和状态候选 | continuity/memory 只读 |

顶层 Skill 不保存数据、不管理 Agent、不直接读取文件或数据库。

`novel-planning` 是所有规划 Agent 共用的方法入口，不是泛化 Planning Agent。Direction、Architecture、Strategy、Character、World、Story Arc、Volume 和 Chapter Planning Agent 通过 `stage` 与 `asset` 只加载自己所需的 Catalog 包。Agent 决定业务候选，Catalog 提供方法，MCP 校验候选集合和资产状态；三者不得互相替代。

## Catalog 包格式

源工程 v2 KnowledgePackage 继续使用目录包思想：

```text
catalog/skills/<tier>/<skill-name>/
├── metadata.yaml
├── prompt.md
├── input_schema.json  # 仅高风险 typed_result
├── schema.json        # 仅高风险 typed_result
├── examples/          # 按需读取
└── provenance.yaml
```

`provenance.yaml` 至少记录源项目、源路径、源 commit/hash、许可证和迁移说明。

## 输出等级

每个 Catalog Skill 只选择一种主要输出级别：

1. `free_text`：正文、描述、分析；不强制 JSON。
2. `document`：Markdown + 少量元数据或稳定章节结构。
3. `typed_result`：Fact、Review、状态更新、拓扑和权威决策候选；使用严格 Schema。

目标是将严格结构化 Skill 控制在确实需要机器校验的范围，不能为了减少 JSON 而取消高风险边界 Schema。

## 候选选择协议

```text
Codex 提供 stage/asset/capability/genre 等硬条件
  -> skill_catalog.search 返回轻量候选摘要
  -> Codex 根据任务语义选择
  -> skill_catalog.get 按需读取完整 Prompt/Schema/examples
  -> MCP 校验选择属于候选快照
```

禁止：

- 代码根据关键词、项目名或默认题材直接选择 Skill。
- 每次把 138 个完整 Prompt 放进上下文。
- Catalog 在 MCP 内调用 LLM 完成语义路由。
- 顶层 Skill 和 Catalog Skill 重复保存同一详细方法论。

## 迁移波次

### Wave A：章节闭环

- fact extraction
- chapter planning/detail
- writer generation
- prose/continuity review
- humanization/style
- dialogue、scene、pacing 的少量高价值能力

### Wave B：规划

- Story Direction
- Architecture generate/compose/review
- Story Strategy
- Core Character
- World realization
- Story Arc
- Volume Outline
- Chapter Plan / execution card

### Wave C：题材与高级能力

- xianxia、scifi 等题材包。
- 战斗、悬疑、情感、爽点等细粒度能力。
- 经评测后解冻的实验包。

## 待办

- [x] 完成 138 个源 Skill 的 Catalog disposition Manifest。
- [x] 合并语义重复 Skill，避免一对一机械复制。
- [x] 为六个顶层 Codex Skill 更新 `SKILL.md` 和 `agents/openai.yaml`。
- [x] 创建缺少的 `novel-project`、`novel-planning`、`novel-continuity`。
- [x] 将现有三个 Skill 调整为纯 Codex 工作流，不依赖代码级 Skill 类。
- [x] 实现 Catalog 搜索、按需读取和 membership 校验。
- [x] 为当前生产和迁移包生成并强制校验 provenance。
- [x] 将长 Prompt/examples 作为 MCP Resource 按需提供。
- [x] 为当前生产 Catalog 包分类 `free_text`、`document`、`typed_result`。
- [x] 对当前 `typed_result` 包增加标准 JSON Schema 和 MCP 失败关闭校验。
- [x] 为八类规划 Agent 建立 `stage`、`asset`、`capability` 到 Catalog 候选的映射测试。
- [x] 验证全部 8 个 `awesome-novel-skill` Prompt 的固定 commit、Hash 和授权记录。

## 测试

- [x] Catalog 扫描、重复名称和 scope 优先级测试。
- [x] metadata 未知字段和非法枚举拒绝测试。
- [x] lifecycle 非 active 包不进入生产候选。
- [x] 候选 membership 和快照 Hash 测试。
- [x] Prompt Resource 按需读取测试。
- [x] 高风险 typed 包 Schema、Validator input/pre 与 output/post 测试。
- [x] 顶层 Skill 结构校验。
- [x] Catalog 搜索不包含完整 Prompt 的上下文体积测试。
- [x] 已迁移第三方包 provenance 完整性测试。

## 验收标准

- [x] 顶层 Codex Skill 恰好覆盖六类业务入口，规划 Agent 共享 `novel-planning` 且不复制 Catalog 方法。
- [x] Catalog 内容可以从来源 Manifest 追溯。
- [x] Codex 负责最终语义选择，MCP 只做硬过滤和校验。
- [x] 普通候选搜索不返回大型 JSON 或完整 Prompt。
- [x] 高风险输出仍有严格 Schema 和失败关闭行为。
- [x] Wave A 在纯 Codex 章节流程中实际被消费。

## 验证证据

当前阶段证据：

- `skill-creator` 的 `quick_validate.py`：六个顶层 Skill 均通过；项目测试额外校验 Skill 集合、frontmatter、中文工作流、UI 描述长度和 `$skill-name` 默认提示。
- `PYTHONWARNINGS='error::ResourceWarning' .venv/bin/python -m unittest discover -s tests -v`：18 个测试通过，无连接泄漏。
- `PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v`：41 个测试通过。
- `tasks/migration/catalog_disposition.csv`：138 项唯一来源；8 项 `adapt-authorized`、92 项 `defer-license`、38 项 `defer-experiment`；生成器 `--check` 通过。
- 生产 Catalog：17 个 active 包；搜索结果不含 Prompt；完整内容只通过 `novelos://catalog/{name}/{artifact}` 获取。
- Provenance：11 个 target-native 包，6 个 adapted 包；8 个授权 Prompt Hash 恰好各出现一次，其中冲突、情绪、钩子三项合并进 Chapter Plan 包。
- 八类规划映射：每个 `asset_type` 通过 `stage=plan`、`capability=generate` 只返回一个目标方法包。
- 端到端：Catalog 选择 -> 八层规划锁定 -> 正文草稿 -> 独立 Review -> 章节接受 -> 连续性提取/Review/晋升 -> Trace 完成，通过。
