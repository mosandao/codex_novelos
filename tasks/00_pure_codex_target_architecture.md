# Task 00: 纯 Codex 目标架构

状态：`DONE`

## 目标

冻结无 UI、纯 Codex NovelOS 的职责边界，作为后续迁移和删除旧实现的判断依据。

## 已选方案

```text
User
  -> Codex Main Agent
       -> Project Skills
       -> Temporary Codex Agents
       -> one NovelOS stdio MCP
            -> novelos.db
            -> seed.db
            -> Skill Catalog
            -> Trace / Review Receipt
```

Codex 是唯一 Agent Runtime。Main Agent 是唯一常驻 Agent；所有业务 Agent 都是由 Main Agent 创建和回收的临时 Codex 上下文。Python 只实现确定性的 MCP、Domain、Storage、Schema 和 Validator，不运行 Main Agent、业务 Agent、LLM Gateway 或语义路由器。

## Agent 契约

### 共同权限

- 临时 Agent 只能读取 Main Agent 提供的不可变 Resource refs，以及表中明确允许的只读 MCP 命名空间。
- 临时 Agent 只返回候选 Resource、变更提案、正文或 Review Receipt，不调用 `*.confirm`、`*.lock`、`*.accept`、`*.promote` 或其他权威写工具。
- Main Agent 负责将候选交给 MCP 登记，由 MCP 计算 `subject_hash`；Agent 不自报权威 Hash。
- Main Agent 是唯一权威提交者，但不能绕过 Schema、版本、Hash、Review Receipt 和状态机门禁。

### 角色清单

| Agent | 最小输入 | 输出 | 允许的只读工具 |
|---|---|---|---|
| Main Agent | 用户请求、任务状态、MCP/Agent 结果 | 路由、最终答复、明确的权威工具调用 | 全部只读工具；通过门禁后的全部提交工具 |
| Direction Agent | Project Profile、用户约束、Catalog 候选 | Story Direction candidate set | `project.*`、`knowledge.*`、`skill_catalog.*` |
| Architecture Agent | 已确认 Direction、项目约束、Catalog 候选 | Architecture candidate | `project.*`、`knowledge.*`、`skill_catalog.*`、`memory.*` |
| Strategy Agent | 已锁定 Architecture、Direction、Catalog 候选 | Story Strategy candidate | `knowledge.*`、`skill_catalog.*`、`memory.*`、规划 Resource |
| Character Agent | Architecture、Strategy、已有 Canon 人物 | Character/relationship candidates | `character.*`、`memory.*`、`knowledge.*`、`skill_catalog.*` 只读操作 |
| World Agent | Architecture、Strategy、已有 Canon 世界资产 | World realization candidates | `world.*`、`memory.*`、`knowledge.*`、`skill_catalog.*` 只读操作 |
| Story Arc Agent | Strategy、已审查 Character/World、Canon | Story Arc candidate | `memory.*`、`timeline.*`、`knowledge.*`、`skill_catalog.*` 只读操作 |
| Volume Planner | Story Arc、目标卷状态、Canon | Volume Outline candidate | `volume.*`、`memory.*`、`timeline.*`、`skill_catalog.*` 只读操作 |
| Chapter Planner | Volume Outline、近期 Canon、章节窗口 | Chapter Plan / execution card candidate | `chapter.*`、`memory.*`、`timeline.*`、`skill_catalog.*` 只读操作 |
| Writer Agent | Chapter Plan、精选上下文、风格和 Skill refs | 正文 Resource、新增 Canon 候选摘要 | `knowledge.*`、`skill_catalog.*` 只读操作；默认不直接查询 Memory |
| Review Agent | 不可变 subject、Hash、Review Profile、权威 refs | verdict、findings、evidence refs、同一 Hash | `review.*`、`memory.*`、`knowledge.*` 只读操作 |
| Context Builder | 任务目标、检索边界、Memory/Knowledge refs | 精选上下文 refs、来源、遗漏和冲突风险 | `memory.*`、`timeline.*`、`knowledge.*`、相关实体只读操作 |

Writer 默认不直接检索 Memory，避免自行扩大或替换 Main Agent 已确认的写作上下文。确需补充材料时返回 context gap，由 Main Agent 决定是否重新运行 `novel-memory` 或 Context Builder。

## 规划资产所有权

```text
Story Direction
  -> Architecture
  -> Story Strategy
  -> Character / World
  -> Story Arc
  -> Volume Outline
  -> Chapter Plan
```

| 资产 | 唯一候选生产者 | 唯一权威提交者 |
|---|---|---|
| Story Direction | Direction Agent | Main Agent |
| Architecture | Architecture Agent | Main Agent |
| Story Strategy | Strategy Agent | Main Agent |
| Character / Relationship Contract | Character Agent | Main Agent |
| World Asset / Rule Realization | World Agent | Main Agent |
| Story Arc | Story Arc Agent | Main Agent |
| Volume Outline | Volume Planner | Main Agent |
| Chapter Plan / Execution Card | Chapter Planner | Main Agent |
| Chapter Draft | Writer Agent，局部改写时可由 Main Agent | Main Agent |
| Review Receipt | Review Agent | Main Agent 仅负责登记，不得改写结论 |
| Continuity Fact Candidate | `novel-continuity` Skill | Main Agent |

Character 与 World 可以并行生成，但进入 Story Arc 前必须完成交叉一致性审查。下游 Agent 发现上游问题时只能返回 typed change proposal；Main Agent 将其路由给上游资产的候选生产者。上游新版本确认后，MCP 按依赖图将受影响下游标记为 `stale`，不自动重生成。

不设置泛化 Planning Agent，也不设置独立 Continuity Agent。连续性由 `novel-continuity` 产生候选，Review Agent 独立复核，Main Agent 通过 MCP 晋升。

## 顶层 Skills

| Skill | 触发条件 | 负责 | 不负责 |
|---|---|---|---|
| `novel-project` | 显式创建、查看或调整项目、书、卷、章节容器 | 资源定位、生命周期和管理流程 | 小说语义规划、正文生成 |
| `novel-planning` | 探索或生产方向、架构、战略、人物/世界规划、故事弧、卷纲、章纲 | 识别资产阶段、准备输入、选择 Catalog 方法、约束输出 | 保存资产、管理 Agent 生命周期、把八类规划压成同一 Prompt |
| `novel-memory` | 写作、规划或审查前需要 Canon 上下文 | 检索计划、相关性选择、紧凑上下文包 | 写正文、晋升事实、静默解决冲突 |
| `novel-writing` | 根据已确认执行卡写作或局部改写 | 写作方法、正文生成边界、新增 Canon 摘要 | 查询 Storage、保存或接受正文 |
| `novel-review` | 候选资产、正文或连续性事实进入权威状态前 | 选择 Review Profile、问题分级、证据要求 | 重写 subject、锁定或接受资产 |
| `novel-continuity` | 已接受正文需要提取事实、状态、伏笔和时间线变化 | 产生带来源的连续性候选 | 直接修改 Canon、替代独立 Review |

六个顶层 Skill 是稳定业务入口。人物塑造、世界构建、战斗、对话、节奏和题材方法进入 Skill Catalog；Agent 负责语义选择，Catalog 提供方法，MCP 只做硬过滤和校验。

## MCP 边界

V1 只运行一个名为 `novelos` 的 stdio MCP Server。不得为 Memory、Planning、Catalog 或 Review 分别启动 Server，也不提供 FastAPI、WebSocket 或浏览器后端。

工具按命名空间划分：

```text
project.*       book.*          volume.*
chapter.*       character.*     world.*
timeline.*      memory.*        continuity.*
planning.*      knowledge.*     skill_catalog.*
review.*        trace.*         resource.*
```

MCP 可以执行：

- 确定性查询、过滤、分页和投影；
- Schema/Validator、候选 membership 和引用完整性校验；
- Hash、版本、状态机、依赖失效、权限、事务和持久化；
- 不可变 Resource、Trace 和 Review Receipt 管理。

MCP 不执行：

- LLM 调用、Prompt 编排或 Agent 生命周期管理；
- 题材语义、Skill 最终选择和上下文相关性判断；
- 规划、正文、审稿结论或 Canon 冲突的语义裁决；
- 基于关键词、项目名或默认题材的隐藏业务路由。

## 数据格式边界

| 数据 | 传输形式 | 结构要求 |
|---|---|---|
| 工具参数、分页、过滤条件 | 小型结构化对象 | 严格 MCP Schema |
| 状态转换、版本、权限、引用 | 小型结构化对象 | 严格 Schema，未知字段拒绝 |
| Review Receipt、Fact Candidate、change proposal | typed result | 严格 Schema、失败关闭 |
| 正文、长规划、人物描述、审稿解释 | Markdown Resource | 不嵌入大型 JSON |
| 长上下文、Catalog Prompt、examples | 不可变 MCP Resource | 通过 `resource_ref` 按需获取 |
| 候选搜索结果 | 轻量摘要列表 | 不返回完整 Prompt 或 examples |

`resource_ref` 必须绑定内容 Hash、版本、媒体类型和来源。所有权威变更必须引用精确的 `subject_hash` 和上游版本；长内容不得同时在控制信封与 Resource 中重复保存。普通自然语言内容不为结构化而结构化，但高风险控制边界不得为减少 JSON 而取消 Schema。

## 明确不迁移

以下内容不进入最终生产路径：

- `backend/src/application/runtime/` 和 `backend/src/application/sub_agents/`；
- `backend/src/infrastructure/llm/`、`LLMGateway`、模型路由和 Rewrite Loop；
- `backend/src/presentation/`、FastAPI、WebSocket、`frontend/` 和全部 UI；
- 固定 Planner、固定 Skill 名路由、Python Agent 生命周期和多 Actor LLM 编排器；
- 当前仓库的 Python `MainAgent`、Python 业务 Agent 和代码级 Skill Runtime。

源工程位于 `backend/src/application/` 的 Planning、Strategy、Character、Story Arc、Continuity 等 Runner/Workflow 也不得直接复制为执行 Runtime。只允许提取其中的领域契约、确定性校验、状态转换、失败语义、测试场景和有来源的 Prompt/Skill 内容，再分别落入 Domain、MCP、Catalog 或 Codex Skill。

不迁移项不存在必须保留的独占执行能力：模型推理和编排由 Codex/临时 Agent 取代，HTTP/UI 入口不属于无 UI 目标，持久化与确定性门禁由单一 NovelOS MCP 承接。实际删除旧演示 Runtime 必须等替代路径验收后在 Task 05 执行。

## 待办

- [x] 将职责边界同步到根 `AGENTS.md`。
- [x] 确认 Agent roster 与规划资产所有权边界。
- [x] 为每类 Agent 冻结输入、输出和允许工具集合。
- [x] 为六个顶层 Skill 定义触发条件和边界。
- [x] 确认 V1 只运行一个 MCP Server。
- [x] 确认长期内容和结构化控制信封的格式边界。
- [x] 评审所有“不迁移”项，确认不存在必须保留的执行能力。

## 验收标准

- [x] `AGENTS.md`、Skill 设计和 MCP 设计不存在 P0/P1 职责冲突。
- [x] 每种权威写操作都有唯一提交者，且受 MCP 门禁约束。
- [x] 每种规划资产都有唯一候选生产 Agent，跨层修改只能走变更提案。
- [x] 目标权限模型不允许临时 Agent 直接修改 Storage 或 Canon。
- [x] 目标架构不存在 Python 和 Codex 两套 Agent Runtime；旧演示实现的删除由 Task 05 跟踪。
- [x] 架构评审没有未解决的 P0/P1 边界问题。

## 验证证据

- 评审日期：2026-07-29。
- 决策：唯一 Main Agent、八类规划 Agent、Writer、Review、Context Builder、六个顶层 Skill、单一 `novelos` stdio MCP。
- 权威边界：Agent 只产出候选；MCP 登记不可变 Resource 和 Hash；Review 绑定 Hash；Main Agent 是唯一提交者。
- 迁移边界：不直接迁移任何 Python LLM/Agent/Presentation Runtime；替代路径验收前不删除当前演示代码。
- 验证：`.venv/bin/python -m unittest discover -s tests -v`，7 个测试通过。
- 验证：`.venv/bin/python -m compileall -q src tests`，通过。
- 文档检查：Task 00 的所有决策项和验收项均有本文件中的对应契约；无未解决 P0/P1 项。
