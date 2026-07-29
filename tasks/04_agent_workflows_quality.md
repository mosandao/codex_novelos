# Task 04: Agent 工作流与质量门禁

状态：`IN PROGRESS`

依赖：[Task 02](./02_mcp_storage_migration.md)、[Task 03](./03_skill_catalog_migration.md)

## 目标

让 Codex 成为唯一 Agent Runtime，按权威资产边界拆分规划 Agent，并以不可绕过的 MCP 契约保证规划、写作、审查和连续性质量。

## 共同契约

- Main Agent 是唯一常驻 Agent，也是唯一可以调用权威提交、锁定、接受和晋升工具的角色。
- 业务 Agent 均为临时上下文，只能读取 Main Agent 提供的 Resource refs 和允许的只读 MCP 工具。
- 每个规划 Agent 只生产或修订自己拥有的资产候选，不得直接修改上游或下游资产。
- Agent 发现上游问题时返回 typed change proposal，包含目标资产、理由、证据和影响范围。
- MCP 负责 Schema、Hash、版本、状态机、依赖图、`stale` 传播、事务和权限校验，不作语义决策。
- Agent 返回结果后由 Main Agent 校验、送审并回收；失败时不得写入部分权威状态。

机器可校验契约位于 `config/agents.yaml`。这是 NovelOS 的业务角色配置，不是 Codex 官方 Agent 声明；本机 `codex-cli 0.144.6` 只确认 `multi_agent` 功能可用，尚未从官方 manual 或本机配置 Schema 证实 `.codex/agents/*.toml`。在获得可靠官方格式前，禁止猜测该配置面。

## 最终 Agent 清单与增减结论

当前清单共 12 类职责模板：1 个常驻 Main Agent、8 个临时规划资产 Agent、Writer、Review 和 Context Builder。它不是 12 个常驻进程，也不是每次请求必须执行的固定流水线；Main Agent 只实例化目标资产所需的最短链路。

本轮评审结论是保留 8 个规划资产 Agent，不再合并，也暂不新增第 9 个规划 Agent：

- Direction、Architecture、Strategy 和 Story Arc 分别回答“写什么故事”“故事按什么机制运转”“全书怎样发生阶段性状态变化”“变化怎样分配到跨卷故事线”，拥有不同生命周期和 Review Profile。
- Character 与 World 是可独立确认、并行生成和失效的契约资产；两者在 Story Arc 前由独立 Reviewer 做交叉一致性审查。
- Volume Outline 和 Chapter Plan 的作用域、Canon 窗口和失效频率不同，必须由 Volume Planner 与 Chapter Planner 分开负责。
- 题材研究、冲突设计、节奏、伏笔、场景和对话是 Catalog 方法，不创建独立 Agent。
- 连续性提取由 `novel-continuity` Skill 产生候选，独立 Review 后由 Main Agent 晋升，不创建 Continuity Agent。
- Writer 与 Review 必须保持上下文隔离；Context Builder 仅在复杂度门禁命中时创建，是否扩大使用范围由真实质量实验决定。

## Agent 契约

### Main Agent

- 输入：用户请求、任务状态、MCP 返回和 Agent 候选。
- 输出：路由决策、最终答复和明确的权威工具调用。
- 允许：全部只读工具和权威提交工具。
- 禁止：直接访问 SQLite、文件系统或外部 API；不得绕过 Review Receipt 锁定高风险资产。

### 规划资产 Agent

八类规划 Agent 是按需创建的职责模板，不是固定流水线中的八个常驻进程。拆分依据是权威资产是否具有独立确认、版本、失效传播和 Review Profile；题材分析、节奏方法、冲突模板等没有独立生命周期的能力属于 `novel-planning` 或 Catalog，不新增 Agent。

| Agent | 最小输入 | 输出 | 禁止事项 |
|---|---|---|---|
| Direction Agent | Project Profile、用户约束、Catalog snapshot；无规划资产上游 | Story Direction candidate | 创建世界细节、卷事件或章节事件 |
| Architecture Agent | 已锁定 Direction、项目约束、Catalog snapshot | Architecture candidate | 修改 Direction、编写人物传记或卷纲 |
| Strategy Agent | 已锁定 Direction 与 Architecture、Catalog snapshot | Story Strategy candidate | 分配具体章节事件或重写 Architecture |
| Character Agent | 已锁定 Architecture 与 Strategy、已有 Canon 人物、Catalog snapshot | Character/relationship contract candidate | 改写 Strategy 或擅自生成无职责人物 |
| World Agent | 已锁定 Architecture 与 Strategy、已有 Canon 世界资产、Catalog snapshot | World realization candidate | 改写规则来源或生成无叙事用途百科设定 |
| Story Arc Agent | 已锁定 Strategy、Character 与 World、已批准交叉审查、Catalog snapshot | Story Arc candidate | 生成详细章节或修改上游契约 |
| Volume Planner | 已锁定 Story Arc、目标卷、当前 Canon、Catalog snapshot | Volume Outline candidate | 修改跨卷职责或全书战略 |
| Chapter Planner | 已锁定 Volume Outline、近期 Canon、目标章节窗口、Catalog snapshot | Chapter Plan / execution card candidate | 修改卷目标或直接生成正文 |

所有规划 Agent 允许使用 Catalog、Knowledge 和 Memory 只读工具，只能访问与当前资产及其上游依赖有关的 Resource。Agent 输出必须带上游版本 refs、证据 refs 和影响声明；Main Agent 通过 MCP 登记不可变候选 Resource 后，由 MCP 计算并返回 `subject_hash`。

Character Agent 与 World Agent 可以并行执行。进入 Story Arc 前，必须由独立 Review Agent 使用 cross-consistency Profile 检查人物能力、关系、势力、制度与世界规则是否相互支撑。

### Writer Agent

- 输入：章节执行卡、精选上下文、权威事实、风格和 Skill refs。
- 输出：正文 Resource、`subject_hash` 和新增 Canon 候选摘要。
- 默认无写工具；正文交回 Main Agent 创建草稿。
- 小范围改句、短对话和局部润色由 Main Agent + Skill 处理，不创建 Writer Agent。

### Review Agent

- 输入：不可变 subject Resource、`subject_hash`、资产类型对应的 Review Profile、权威上下文 refs。
- 输出：verdict、分级 findings、evidence refs 和同一 `subject_hash`。
- 不得看到生产 Agent 的隐藏推理、预期 Review 结果或其他 Reviewer 结论。
- 不允许接受正文、锁定资产或晋升连续性事实。
- Review Agent 是统一执行角色，但 Direction、Architecture、Strategy、Character/World、Story Arc、Volume、Chapter、Prose 和 Continuity 使用不同 Profile。

### Context Builder

- 仅在跨卷、多线、冲突事实或上下文体积明显过大时创建。
- 输出精选 Resource refs、来源、遗漏风险和连续性风险。
- 不生成规划资产或正文，不作最终 Review，不写 Storage。

### Agent 增减判据

- 新增：只有当新产物具备独立资产类型、明确上游版本、独立 `stale` 边界和独立审查标准时，才增加资产 Agent。
- 合并：若两个角色总是共享输入、一起确认、一起失效且使用同一审查标准，应合并为同一资产 Agent。
- 下沉 Skill：只提供方法、模板或分析视角，不拥有资产生命周期的能力，进入 Skill/Catalog。
- 保持专职：Writer 与 Review 需要上下文隔离；Context Builder 只在复杂上下文任务中按阈值创建。
- 禁止常驻：除 Main Agent 外，任何业务 Agent 完成一次候选或审查后都必须销毁。

## 规划资产依赖与变更

```text
Story Direction
  -> Architecture
  -> Story Strategy
  -> Character / World
  -> Story Arc
  -> Volume Outline
  -> Chapter Plan
```

- Main Agent 根据目标资产创建对应 Agent，不运行固定全链路。
- Main Agent 选择从最近一个有效且非 `stale` 的上游资产开始，只创建到目标资产为止的最短 Agent 链。
- 修订现有资产时仍路由给该资产的所有者 Agent。
- 下游 Agent 不得把上游修改混入自己的候选；必须单独返回 change proposal。
- Main Agent 接受上游新版本后，MCP 按依赖图标记下游为 `stale`。
- `stale` 资产可以作为历史证据读取，但不得继续用于生成可锁定的下游候选。
- 不自动重生成全部下游；Main Agent 根据影响范围逐项路由修订。

## 核心工作流

### 从零建立规划

```text
Main -> novel-planning + Direction Agent -> planning.create_candidate -> review.record -> planning.lock
Main -> novel-planning + Architecture Agent -> planning.create_candidate -> review.record -> planning.lock
Main -> novel-planning + Strategy Agent -> planning.create_candidate -> review.record -> planning.lock
Main -> Character Agent + World Agent -> planning.create_candidate -> review.record -> planning.lock
Main -> planning.prepare_cross_check -> Review Agent -> review.record -> planning.approve_cross_check
Main -> Story Arc Agent -> planning.create_candidate -> review.record -> planning.lock
Main -> Volume Planner -> planning.create_candidate -> review.record -> planning.lock
Main -> Chapter Planner -> planning.create_candidate -> review.record -> planning.lock
```

用户可以在任一阶段暂停、比较候选或要求修订。未确认上游时，不得继续创建依赖它的可锁定资产。

### 完整章节

```text
Main
  -> novel-memory
  -> optional Context Builder
  -> Chapter Planner（没有有效执行卡时）
  -> novel-writing + Writer Agent
  -> chapter.create_draft
  -> novel-review + independent Review Agent
  -> review.record
  -> chapter.accept
  -> novel-continuity candidate extraction
  -> Review Agent continuity profile
  -> continuity.promote_reviewed
```

### 局部规划或修订

```text
Main
  -> identify target asset and owner Agent
  -> owner Agent returns candidate or upstream change proposal
  -> MCP records immutable candidate and subject_hash
  -> Review Agent
  -> Main commits accepted version
  -> MCP marks affected descendants stale
```

### 简单任务

```text
Main -> one Skill or one MCP tool -> result
```

不得为单次查询、保存、文件读取、解释已有规划或一个确定性工具调用创建 Agent。

## 质量门禁

- 生产 Agent 与 Review Agent 必须使用隔离执行上下文。
- Review 绑定不可变 `subject_hash` 和精确上游版本 refs。
- `blocking` finding 阻止权威提交。
- 规划、正文和连续性的高风险候选先过 Schema，再过独立 Review。
- Character/World 在 Story Arc 前必须通过交叉一致性审查。
- Agent 失败不得触发硬编码语义 fallback。
- 每次 Spawn/Destroy、工具调用、候选集、Review 和最终提交写入 Trace。

## 最小质量实验

### 规划 Agent 边界

- 样本：每类规划资产至少 5 个生成或修订任务，并包含跨层变更诱因。
- 检查：资产完整性、上游忠实度、越权修改、上下文体积和返工次数。
- 通过标准：Agent 不把上游变更混入本层候选，且合法 change proposal 能被正确路由。

### Character/World 并行与交叉审查

- 样本：至少 10 组 Strategy 输入。
- 检查：人物能力与世界规则、人物关系与势力结构、成长要求与资源约束。
- 通过标准：预埋跨资产冲突被 Review 识别，修订后 Story Arc 可消费精确版本。

### Writer Agent 是否保留

- 样本：至少 10 个代表性完整章节任务。
- 对照：Main 直接写与隔离 Writer Agent。
- 评审：匿名、顺序平衡、独立 Review。
- 保留标准：Writer Agent 在关键质量维度的明确胜率至少 60%，且没有显著增加 Canon 错误。

### Context Builder 是否常用

- 样本：至少 10 个跨章或跨卷任务。
- 对照：Main + Memory Skill 与 Context Builder。
- 保留为常用角色的标准：事实遗漏或无关上下文显著下降；否则仅用于极端场景。

## 待办

- [x] 按独立资产生命周期重划规划 Agent，取消泛化 Planning Agent。
- [x] 定义 Agent 新增、合并和下沉 Skill 的判据。
- [x] 将每类 Agent 的最小输入和允许工具白名单固化为可校验配置。
- [x] 定义规划资产所有权、依赖图和 `stale` 传播规则。
- [x] 定义 typed Agent result 和 change proposal Schema。
- [x] 固化 Spawn/Destroy Trace 与 Agent run 状态机。
- [x] 将 Review Receipt 绑定到独立 Reviewer run，拒绝生产者自审。
- [x] 实现八类规划 Agent 的创建、结果校验和销毁流程。
- [x] 实现 Character/World 并行生成与交叉一致性审查。
- [x] 实现规划、章节和连续性工作流。
- [x] 实现临时 Agent 超时、失败和部分结果拒绝。
- [x] 实现生产 Agent 与 Reviewer 上下文隔离。
- [x] 准备质量实验数据集和评分 Rubric。
- [x] 验证所有临时 Agent 完成后被销毁。

## 测试

- [x] 简单任务不 Spawn Agent。
- [x] 每类正式规划资产由唯一对应 Agent 生产。
- [x] 未确认上游时拒绝创建可锁定下游候选。
- [x] 下游 Agent 的跨层修改被拒绝并转换为 change proposal。
- [x] 上游新版本使受影响下游变为 `stale`。
- [x] `stale` 资产不能用于锁定新的下游资产。
- [x] Character/World 可以并行且必须经过交叉审查。
- [x] 完整章节按需创建 Chapter Planner、Writer 和独立 Review Agent。
- [x] 短修改不创建 Chapter Planner 或 Writer Agent。
- [x] Review Agent 无权接受章节或锁定规划资产。
- [x] `blocking` finding 和 subject hash 不一致阻止提交。
- [x] Agent 失败不会写入部分权威状态。
- [x] Context Builder 只在满足复杂度判断时创建。
- [x] Agent 生命周期 Trace 完整。

## 验收标准

- [x] 只有 Main Agent 常驻。
- [x] 不存在覆盖全部规划阶段的泛化 Planning Agent。
- [x] 八类规划 Agent 均有唯一资产所有权和明确的上下游边界。
- [x] Character 与 World 的并行结果在 Story Arc 前完成交叉审查。
- [x] 不存在独立 Continuity Agent。
- [x] 规划、章节和连续性流程通过端到端测试。
- [ ] 质量实验具备原始输入、匿名输出、评分和 Review 证据。
- [x] 没有临时 Agent 可以绕过 MCP 权威门禁。

## 验证证据

当前证据：

- `config/agents.yaml`：1 个常驻 Main Agent、8 个规划资产 Agent、Writer、Review 和 Context Builder。
- `config/schemas/agent-result.schema.json`：临时 Agent 完成、失败和超时结果契约。
- `config/schemas/change-proposal.schema.json`：跨层变更提案契约。
- `mcp/novelos/tests/test_agent_contracts.py`：配置、MCP 工具白名单、Catalog、规划生产者、依赖和 Review Profile 一致性测试。
- Migration 007：`agent_runs`、Reviewer/Producer run 绑定和 `planning_cross_checks`。
- `agent.start/finish/get/list`：自动记录 Spawn/Destroy；存在运行中 Agent 时 Trace 不能结束。
- `planning.prepare_cross_check/approve_cross_check/get_cross_check`：Character/World 精确版本交叉门禁；Story Arc 缺少或错配检查时拒绝创建。
- `authority_commits`：规划、交叉审查、章节、Entity 和连续性提交强制绑定同一项目 Trace 与独立 Reviewer run；跨 Trace 提交在状态变更前失败关闭。
- Migration 009 与 `resource.create/review.prepare_subject/get_subject`：Main 基线可登记 Trace 绑定的不可变输出，匿名评测包绑定精确输出 refs/Hash、Producer runs 和 Review Profile；Reviewer 必须同 Trace 且上下文隔离，Receipt 原子绑定 assessment Resource。
- `mcp/novelos/tests/test_agent_workflows.py`：简单任务、并行 run、超时、部分结果、越权提案、Writer 触发和 Review 绑定负向测试。
- `mcp/novelos/tests/test_pure_codex_workflow.py`：八层规划、交叉审查、Writer、独立 Review、章节接受和连续性晋升共用一条 Agent run 生产路径，结束时无活动 run。
- change proposal 绑定 locked 上游的精确 ID、版本和 `subject_hash`；影响范围必须包含当前资产且只能引用该上游的真实下游，延迟处理和跨层越权均失败关闭。
- `tasks/experiments/agent_quality/`：40 个规划、10 个 Character/World、10 个 Writer A/B 和 10 个合法复杂上下文 Context Builder A/B 输入，另有绑定输入 Hash、盲标签和 Review Profile 的 70 case `execution_manifest.jsonl`；真实输出与评分尚未执行。
- `scripts/summarize_agent_quality_results.py`：失败关闭校验 70 case、完整原始输入、匿名输出文件、Review Subject、Receipt、assessment 和逐层 Hash；分数与判断必须等于 Receipt 绑定 assessment，再由 Rubric 自动解盲计算 Writer/Context Builder 决策，readiness 不信任手写 `summary.json`。
- 当前验证：根测试 40 个、MCP 测试 81 个全部通过；Migration/Catalog manifest、实验录制器/数据集、seed inventory、迁移汇总、备份/导出恢复、仓库卫生、cutover plan/readiness 和 `compileall` 检查通过。
- 正式数据库 `data/novelos-v2.db` 已前向升级至 Schema 9，`quick_check=ok`；Schema 8 升级前备份仍保留，Schema 9 恢复证据位于 `tasks/migration/schema9_restore_drill.json`。

状态为 `DONE` 前仍需执行真实质量实验，并根据结果冻结 Writer Agent 和 Context Builder 的最终触发策略。

用户已明确允许创建临时业务 Agent 并接受相应模型执行成本；当前正在执行 70-case 实验，结果仍必须保留完整匿名输出、独立 Review 和 Receipt 证据。

`scripts/record_agent_quality_experiment.py` 已通过真实 stdio MCP 单 case 集成测试，并按 `start -> prepare -> finalize` 三阶段登记独立 Trace、Producer run、Review Subject、Reviewer run、Receipt 和 assessment。正式实验已完成首个 Direction case 的全证据闭环，其余 case 继续执行；不以部分结果解除质量门禁。
