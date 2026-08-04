# NovelOS Agent 规则

## 角色

作为本仓库唯一长期存在的 主控智能体。理解用户需求、规划任务、选择最小执行方式，并汇总结果。

## 路由顺序

按以下顺序选择执行方式：

1. 简单读取、写入、搜索、Git、浏览器或 API 操作，直接调用一个 MCP 工具。
2. 有明确业务流程、但不需要隔离上下文的任务，加载一个项目 Skill。
3. 当任务需要独立资产所有者、隔离上下文、独立审查或大范围推理时，创建对应的临时业务 Agent。

不要为数据库访问、文件访问或单次工具调用创建 Agent。收集结果后立即销毁临时 Agent。

对于可锁定、可版本化的规划资产，必须创建负责该资产的规划 Agent。探索性讨论、解释和不保存的局部建议可以由 主控智能体 加载 Skill 直接完成。

## Agent 规划

只有 主控智能体 长期存在。下表定义的是可按需实例化的职责模板，不是每次任务都要启动的固定团队。其余 Agent 只在目标产物需要独立上下文、明确资产所有权或独立审查时创建，返回候选结果后销毁。

Agent 的机器可校验业务契约以 `config/agents.yaml` 为唯一来源。该文件定义角色标识、生命周期、最小输入、工具白名单、唯一资产所有权、精确上游、Catalog 包、Review Profile 和销毁要求；`AGENTS.md` 只解释路由原则，不复制完整配置。当前 Codex 未提供经本项目验证的项目级自定义 Agent 声明格式，因此不得创建或宣称 `.codex/agents/*.toml` 是官方配置。临时 Agent 由 主控智能体 使用当前 Codex 的协作能力按需创建，项目配置只负责业务校验。

### 规划资产 Agent

当前角色清单共 13 类：1 个常驻 主控智能体、8 个临时规划资产 Agent，以及 Writer、Review、上下文构建智能体 3 个临时执行角色，加上项目创建阶段做多原型 LLM 融合的 引导融合智能体。这个数字表示可用职责模板，不表示一次请求会同时创建 13 个 Agent。

| Agent | 负责的资产或结果 | 主要上游 |
|---|---|---|
| 方向智能体 | 故事方向、核心冲突、主角驱动力和读者承诺 | Project Profile、用户约束；无规划资产上游 |
| 架构智能体 | 叙事机制、冲突引擎、结构形态和规则边界 | 已锁定 Story Direction |
| 策略智能体 | 全书阶段目标、不可逆状态变化和推进策略 | 已锁定 Story Direction、Architecture |
| 人物智能体 | 核心人物、人物弧和关系契约 | 已锁定 Architecture、Story Strategy |
| 世界观智能体 | 势力、制度、资源、地点和世界规则实现契约 | 已锁定 Architecture、Story Strategy |
| 故事弧智能体 | 跨卷故事弧、卷级职责、成长与伏笔分配 | 已锁定 Strategy、Character、World；已批准交叉审查 |
| 卷规划智能体 | 单卷目标、转折、章节序列和卷末状态 | 已锁定 Story Arc；当前 Canon |
| 章节规划智能体 | 章节执行卡、场景目标、进入与退出状态 | 已锁定 Volume Outline；近期 Canon |

规划 Agent 的粒度按“可独立确认、版本化和失效的权威资产”确定，而不是按一次对话或一个 Prompt 确定。满足以下全部条件时才新增规划 Agent：

1. 输出具有独立生命周期和唯一资产类型。
2. 输入边界可以由已确认上游版本明确表达。
3. 上游变更后可以独立标记该资产及其后代为 `stale`。
4. 它需要不同于相邻阶段的质量 Profile 或审查标准。

不满足这些条件的细分能力放入 `novel-planning` Skill 或 Skill Catalog，不新增 Agent。例如题材分析、节奏方法、冲突模板和场景技巧是方法，不是独立资产所有者。

Architecture、Strategy 和 Story Arc 必须保持为三个资产层级：Architecture 回答“故事按什么机制运转”，Strategy 回答“全书通过哪些阶段完成状态变化”，Story Arc 回答“这些变化如何分配到跨卷人物线、事件线和伏笔线”。三者分别确认、分别失效，并使用不同 Review Profile；不得重新合并成泛化 Planning Agent。人物和世界同理是可独立修订的契约资产，不下沉为 Architecture 的内部步骤。

### 执行与校验 Agent

| Agent | 创建条件 | 输出 |
|---|---|---|
| 写作智能体 | 完整章节、长场景或需要隔离创作上下文 | 正文候选 |
| 审查智能体 | 权威资产锁定、正文接受或连续性晋升前需要独立复核 | 绑定 `subject_hash` 的 Review Receipt |
| 上下文构建智能体 | 跨卷、多线、事实冲突或上下文超出单次 Memory Skill 可控范围 | 精选上下文包和遗漏风险 |
| 引导融合智能体 | 项目创建阶段用户选了 ≥2 个系统原型，确定性融合不足以承载跨原型约束 | `creator_derivation_candidate`（判定的 parent + 深度融合 signature + 融合理由） |

Writer、Review、上下文构建和 引导融合智能体 不拥有规划资产。审查智能体 通过不同 Review Profile 复用同一隔离审查角色，不按资产类型继续拆成多个 Reviewer。引导融合智能体 只在项目创建 Trace 内运行，输出经 `reconcile_archetypes` 确定性校验后由 `project.wizard.submit` 落库，自身不持有提交权限。

完整 70-case 质量实验当前按用户决定延期。实验完成前采用保守路由：写作智能体 只用于完整章节、长场景或明确需要隔离创作上下文的任务；上下文构建智能体 只用于跨卷、多线、事实冲突或上下文溢出。现有部分实验结果不构成质量结论，也不得据此扩大触发范围。

规划资产依赖顺序为：

```text
Story Direction
  -> Architecture
  -> Story Strategy
  -> Character / World
  -> Story Arc
  -> Volume Outline
  -> Chapter Plan
```

Character 与 World 可以并行生成，但进入 Story Arc 前必须完成交叉一致性审查。主控智能体 只创建完成当前目标所需的最短 Agent 链；已有有效且非 `stale` 的上游资产时直接复用，不重新运行前序 Agent。

每个规划 Agent 只能创建或修订自己负责的候选资产。发现上游问题时，返回变更提案和影响范围，由 主控智能体 路由给上游资产所有者；不得在下游输出中隐式重写上游。上游新版本确认后，MCP 必须将受影响的下游资产标记为 `stale`，不得自动重生成。

临时 Agent 必须按 `config/schemas/agent-result.schema.json` 返回 typed result，并让实际输出符合对应 `output_type` Schema。跨层问题必须放入符合 `config/schemas/change-proposal.schema.json` 的 `change_proposals`，不得混入本层候选正文。只有 主控智能体 可以通过 `planning.create_candidate_from_run`、`review.record_from_run` 等 MCP 工具登记候选、记录 Review Receipt 或执行锁定、接受、晋升和权威提交；不得读取 Agent Resource 后重组权威候选或 Receipt。

锁定规划、批准交叉审查、接受章节、提交 Entity 和晋升连续性时，主控智能体 必须提供当前项目仍在运行的 `trace_id`。生产 run、Reviewer run 和权威提交必须属于同一 Trace；MCP 在提交事务内写入 `authority_commits` 和 Trace step，禁止事后手工补记冒充追溯证据。

`config/agents.yaml` 的 `review_profile_routes` 是合法 Review Profile 名的唯一注册表；roles、cross-consistency 和业务用途只能引用其中已注册的 key。`isolation_evidence` 与 Story Arc 的 Character/World cross-check 受 `runtime.enforcement` 控制，默认 lenient：缺失时在权威提交事务中记录 `status=completed`、`details.severity=warning` 的 Trace step 后放行；strict 模式才阻断。无论模式，Trace 串联、不可变 subject/hash、独立 `review_agent` run、Review 输出绑定、上游 locked 和 stale 检查仍强制。`context_id` 只标识 run context，不构成真实模型上下文隔离证明。

## 分层边界

- 主控智能体：负责任务规划、Agent 路由、最终决策和结果汇总，不拥有业务规划资产。
- 业务 Agent：只负责临时的领域推理和候选产物，不拥有提交权限。
- Skill：封装可复用工作流和领域方法，不负责持久化或生命周期管理。
- MCP：访问数据库、文件、Git、浏览器和外部 API 的唯一入口。
- Storage：只负责持久化，不包含 Prompt、路由或推理。

## 用户投影

项目创建或产生任意候选、草稿、审查、规划、正文 Agent 输出后，Main Agent 必须调用
`projection.render_project_folder` 刷新 `novels/<项目目录>/`。`规划/` 与 `正文/` 保持
当前权威版本视图；`候选/` 保留兼容的候选诊断视图；`产出/` 必须保留全部状态的
规划与正文产出，以及完成的 Agent 原始输出；`档案/` 展示已锁定规划资产的生产、
独立审查和 authority commit 溯源。投影是单向派生内容，直接编辑其中 Markdown 不会回写
权威存储。`创作约束/作者签名.md` 展示项目绑定的精确 Creator Profile revision/Hash；
`创作约束/本书创作灵魂.md` 只展示 locked Direction 中的 `book_soul`，缺失时明确标注，
不得把候选内容投影为当前权威。

### 项目创建向导

项目创建的默认入口是仓库内本地向导 `mcp/novelos/src/novelos_mcp/ui/project-wizard.html`。
同目录 `project-wizard-data.js` 提供独立模式所需的 18 个原型。MCP Apps 的
`project.wizard.render` 保留为兼容入口；使用本地入口时必须按以下顺序执行：

1. Main 向用户提供本地 HTML 的绝对路径；用户先填写项目名、频道、目标平台、作品规模、一级题材、二级方向、主情绪基调、美学风格和
   可选创作资料；页面按这些约束确定性推荐三个系统叙事原型。用户选择原型、确认只读继承项并
   编辑本书最小差异后，页面生成 `novelos.project.create.v1` JSON 并显示/复制到页面底部。
   页面产出的 `creator.selected_archetypes` 是多原型数组，Main 解析 JSON 的 `setup` 后
   按 `selected_archetypes` 数量选择签名融合路径：

   - **单原型**：直接调用 `project.wizard.reconcile_archetypes`，把选择确定性融合为单一 parent
     的 derive 结构（取打分最高的原型作 parent，生成基础 overrides，并把其余原型的读者承诺
     作为辅风格追加到 `recurring_attention`），再以 `derive` 模式调用 `project.wizard.submit`。
   - **多原型（≥2）**：`reconcile_archetypes` 的确定性融合只把辅原型压缩成 `recurring_attention`
     脚注，会丢弃大量跨原型约束。因此必须先在 Trace 内创建临时 `onboarding_agent` run，把
     `selected_archetypes`、`project_setup` 和各原型完整签名交给它，由 LLM 判定 parent 并对
     跨原型约束做深度融合，产出 `creator_derivation_candidate`（含完整 `signature` 与
     `merge_rationale`）。随后用 Agent 判定的 parent 调用 `project.wizard.reconcile_archetypes`
     做确定性合规收口（校验 parent/Hash 与配置一致、签名过 schema 校验），再以 `derive` 模式调用
     `project.wizard.submit`。无论哪条路径，落库前签名都必须通过确定性 schema 校验；LLM 只在
     `onboarding_agent` run 内推理，MCP 不调 LLM。详见 Task 12。

   新向导不得提交 `reuse` 或 `create`；历史绑定仍保持可读。
3. MCP 在同一事务中确认或创建不可变 Creator Profile 版本、创建项目并绑定精确 revision/Hash；
   任一步失败都不得留下项目或孤立绑定。
4. Main 从返回值读取 `metadata.project_setup` 和 `creator_binding.constraint_ref`，启动 Trace 后把二者
   交给方向智能体；Direction 候选 metadata 必须绑定同一 ref 并包含完整 `book_soul`。
5. `project.wizard.submit` 已在创建后刷新默认投影；后续任何候选、草稿、审查或 Agent
   输出仍必须再次刷新投影。

向导的频道、平台、规模和一级题材为固定选项；二级方向按一级题材显示 18 个静态、LLM
预生成候选，本地 `file://` 页面与 `project.wizard.submit` 落库事务本身不调用 LLM，
也不接受自定义方向。多原型签名融合由临时 `onboarding_agent` 在 MCP 外的 Codex run 内完成，
落库前仍经 `reconcile_archetypes` 确定性校验。`emotional_tones` 可多选，
`aesthetic_styles` 最多两项，`reference_material` 为可选多行资料，最多 10,000 个字符。
“知乎盐选”、所有“自定义”选项和自定义字数均不属于 V3 契约。本地 `file://` 页面只生成 JSON，
不直接写入数据库，也不声称项目已经创建。

向导只创建项目容器并记录 `project_setup` 约束；页面不得直接生成、锁定或提交规划资产，
也不得跳过 Trace、Agent、Review 或 authority commit 门禁。

`creator_signature` 是用户拥有的跨项目配置，不是规划资产。Profile 修订创建新版本，不推动既有
项目漂移。临时 `onboarding_agent` 只在项目创建时做多原型 LLM 融合推理，输出
`creator_derivation_candidate`，不拥有 Creator Profile 资产，也不持有提交权限；落库仍由
`project.wizard.submit` 在确定性校验后完成。项目切换作者版本必须在运行中的本项目 Trace 内调用 `project.creator.rebind` 并提供
当前 `expected_version`、目标 Hash 和原因；成功后当前 Direction 及全部后代标记为 `stale`，
保留旧版本与 Trace 证据，不自动重生成。`book_soul` 属于 Story Direction；修改它必须生成、
审查并锁定新的 Direction 候选。Writer `style_refs` 至少包含当前作者签名精确 ref 与 locked
Direction 精确 ref，不能自行发明或改写作者思想。

### 删除项目

项目尚无权威提交且不存在运行中的 Trace 时，Main 才可调用
`project.delete(project_id, expected_version, output_root)`。`expected_version` 必须与当前
项目版本一致；服务端会再次检查活动 Trace 和 `authority_commits`。删除前只会移除同名、
非符号链接且 `manifest.json` 中 `project_id` 匹配的派生投影，随后级联删除项目容器
及其业务数据。已完成的 Trace 和 Agent 审计记录保留，但解除项目关联。任一检查失败时不得
删除投影或权威数据。

V1 只注册一个名为 `novelos` 的 stdio MCP Server。Memory、Planning、Catalog、Review 和 Trace 是同一 Server 内的工具命名空间，不拆成多个 MCP 进程。

`NovelOSService` 的稳定导入入口仍是 `novelos_mcp.service`，实现位于
`mcp/novelos/src/novelos_mcp/service/`：`service/__init__.py` 聚合 8 个领域 Mixin，
`_ServiceInternals` 保存共享事务与校验 helper。不得恢复同名 `service.py`，也不得绕过聚合服务
另建可独立写权威数据的子服务。包级兼容常量可以保留，但运行时 Review Profile 必须从当前
`AgentContractStore` 查询，不能把兼容快照当作第二权威源。

仓库已经完成纯 Codex 切换，不保留 Python Agent、Skill、LLM Provider 或旧 Memory MCP Runtime。所有权威数据访问必须经过统一 `novelos` MCP，并通过 `authority_commits` 追溯到 Trace、subject Hash 和 Review Receipt。

## 小说工作流

续写章节时：

1. 使用 `$novel-memory` 选择并组织相关上下文。
2. 使用 `$novel-writing` 起草章节。
3. 保存前使用 `$novel-review` 审查草稿。
4. 通过 NovelOS MCP 的 `chapter.*` 和 `memory.*` 工具保存审查通过的内容与记忆。

生成正式章节前，使用 章节规划智能体 根据已确认卷纲生成章节执行卡。若目标只是局部改句且不改变章节状态，可以由 主控智能体 直接使用 `$novel-writing`，不创建 章节规划智能体 或 写作智能体。

## 验证

运行：

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python scripts/build_migration_manifest.py --output-dir tasks/migration --check
.venv/bin/python scripts/build_catalog_manifest.py --check
.venv/bin/python scripts/build_agent_quality_dataset.py --check
.venv/bin/python scripts/build_seed_inventory.py --check
.venv/bin/python scripts/build_seed_inventory.py --production --check
.venv/bin/python scripts/backup_novelos_database.py --check
.venv/bin/python scripts/export_novelos_data.py --check
.venv/bin/python scripts/build_migration_summary.py --check
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/check_cutover_readiness.py --check
.venv/bin/python scripts/check_cutover_plan.py --check
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 任务连续性

执行迁移或其他多阶段工作前，先读取 `tasks/README.md` 及其中链接的当前任务文件。

- 任务状态只使用 `TODO`、`IN PROGRESS`、`DONE` 和 `BLOCKED`。
- 从依赖已满足的第一个未完成验收项继续。
- 只有生产路径接通且所需验证通过后，才能标记为 `DONE`。
- 迁移内容必须记录源 commit、源路径、目标路径和来源信息。
- 除非用户明确要求修改，否则将 `/Users/yiyi/github/novelos` 视为只读。
- 选择并记录明确的来源快照前，不得从该工程的 dirty worktree 复制内容。

## 书写语言

- `AGENTS.md`、`tasks/`、项目 `SKILL.md` 和维护文档默认使用中文。
- 代码标识符、命令、路径、MCP 工具名、协议字段和状态字面量保持原始英文。
- 只有外部规范、兼容性或用户明确要求时才编写英文说明。
