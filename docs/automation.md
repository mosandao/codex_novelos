# Agent 与自动化

## 所有权

**主控智能体** 是唯一自动化编排者。NovelOS 不运行后台 worker、cron、Webhook 或自主循环；业务 sub agent 只能在用户任务期间由主控按需创建（用 Agent 工具），返回一次结果后销毁。

项目创建向导由主控编排（向导 UI 已随插件退役）：主控与用户交互确认项目约束（频道级联：平台/题材库/基调池随频道切换；表里基调分表层与内核；作者内核 select/create 双模式），产出结构化 `novelos.project.create.v3` JSON；落库前对照 `config/schemas/project-create-request.schema.json`（v3）自查（结构 + 词表级联 + 表里互斥 + select 模式内核库内反查）。随后主控用组装器注入（`node scripts/novelos-compose-prompt.mjs --asset fusion --payload <json>`，含 `selected_archetypes` + `user_persona_hints` + `project_setup`（v3）），创建临时 **引导融合智能体（onboarding_agent）** sub agent。agent 按「先立人，再落规」两步法：判定 parent 并输出 rationale → 反推式五维生平化合出 persona（含盲区清单 refuses/cannot_write）→ 从 persona 长出带体温的 7 字段，产出 `creator_derivation_candidate`（签名 schema v2）。mode=create 时内核候选经组装器（`--asset kernel-fusion`）注入内核融合智能体产出并对照 author-kernel schema 自查后落库；分身候选对照 creator-signature schema 自查（persona 必填、cannot_write 非空、七字段无逐字复制内核 identity）后，主控以 `BEGIN IMMEDIATE` 单事务直写（模板见 sql-reference.md「作者签名链」）：resources×2（签名 + 派生记录含完整用户输入快照）、creator_profiles/versions（content + derivation 双资源链）、projects（metadata_json 写入 setup v3 快照，带 setup_schema_version 标记，供后续阶段读取）与精确绑定，失败整体回滚零写入。`parent_rationale` 含错配标记时须呈报用户裁决后方可落库；候选解析失败（含字段错位）要求 agent 重出。落库事务本身不调用 LLM，LLM 只在 sub agent 的运行上下文内执行；该步骤不产生规划资产。

## Agent 清单

| 类别 | 触发 | 输出 | 副作用 |
|---|---|---|---|
| 8 个规划资产 Agent（方向/架构/策略/人物/世界观/故事弧/卷规划/章节规划） | 需要创建或修订对应权威资产 | 规划候选正文 | 无；主控落库 |
| 写作智能体 | 完整章节、长场景或需隔离创作上下文 | 章节草稿 | 无；主控创建草稿 |
| 审查智能体 | 规划锁定、章节接受、连续性晋升前 | 审查意见 | 无；主控登记 reviews |
| 上下文构建智能体 | 跨卷、多线、事实冲突或上下文溢出 | 上下文包 | 无 |
| 引导融合智能体（onboarding） | 项目创建阶段 | `creator_derivation_candidate` | 无；主控对照 schema 自查后受控直写落库 |

精确角色职责、最小输入与方法论由主控在创建 sub agent 时经组装器注入（见 AGENTS.md「方法论获取」节）。sub agent 没有数据库写入权限，只返回候选文本；所有持久化由主控以 node:sqlite 受控直写完成（SQL 模板唯一来源 sql-reference.md；content_hash 用 node:crypto 计算 + BLOB 写入 + 状态机纪律）。

作者签名不是规划资产，也不新增常驻角色。它是用户拥有的不可变版本配置；多原型签名融合由临时 onboarding_agent 在项目创建时完成，run 结束即销毁。本书 `book_soul` 由既有方向智能体生成，Writer 仍按完整章节/长场景的保守条件临时创建。

## Steering 与硬约束

- Steering：项目 Skill 的 `SKILL.md`（`.agents/skills/`）和选择后的创作方法论 `prompt.md`（`catalog/skills/`）。
- 硬约束：schema 自查（签名、book_soul，落库前对照 `config/schemas/*.json`）、确定性脚本（content_hash 用 node:crypto 计算）、SQLite 状态机（`planning_assets.status` 的 candidate→locked→stale 流转与 CHECK 约束）、Hash/版本、独立审查 sub agent、BLOB+content_hash 同步落库（主控自查纪律）。
- Prompt 不能授权写入；sub agent 的文本声明不替代主控受控直写的落库与自查。不再有 MCP Tool Schema、`authority_commits` 或 Trace 门禁层（已随 migration 016 删除）。

## 生命周期

1. 主控读取对应方法论 `prompt.md`，用 Agent 工具创建临时 sub agent，注入最小输入与必要的 locked 上游内容。
2. sub agent 在隔离上下文执行，只返回候选文本（规划候选 / 章节草稿 / 审查意见 / 融合候选 / 上下文包）。
3. 主控以 node:sqlite 单事务直写落库：content_hash 用 node:crypto 计算（`sha256:`+hex）→ BLOB 写入 resources → planning_assets/chapters 登记 `candidate` → 记录上游依赖 `planning_asset_dependencies`。
4. 主控创建**独立**审查 sub agent（不同上下文）审查候选 → 审查意见登记 `reviews`。
5. 审查通过后主控将状态置 `locked`（规划）或 `'accepted'`（章节）；旧版本变 `superseded`。
6. 上游资产修订（新 revision locked）后，主控以 node:sqlite UPDATE 沿依赖边递归标记下游 `stale`。
7. 章节接受后由 `$novel-continuity` 提取连续性数据 → SQL INSERT 事实/承诺/期待/关系/故事弧状态。

失败或超时的 sub agent 不返回部分结果；是否重试由主控基于用户目标重新路由，并创建新的 sub agent。

## 审查隔离

审查 sub agent 必须是与生产 sub agent 不同的 Codex 临时 Agent（独立上下文），读取不可变的候选内容与精确上游。主控把审查意见 `INSERT INTO reviews`，绑定 subject（候选 ID/Hash）与审查 Profile。审查意见是落库/锁定的前置条件，但不自动触发写入——锁定/接受由主控经 SQL 完成。

Agent 质量实验延期。延期期间 Writer 只处理完整章节、长场景或明确需要隔离上下文的写作；上下文构建智能体只在跨卷、多线、事实冲突或上下文溢出时创建。已完成的部分 case 仅作为恢复证据，不用于宣称胜率或改变路由。

## 操作控制

- 审批：只有主控执行锁定、接受、晋升和删除的 SQL。
- 审计：`reviews` 表、`planning_assets.status` 流转、`resources.content_hash`、`planning_asset_dependencies` 构成审计链；无 `authority_commits`/Trace，权威状态由 SQL 状态机直接表达。
- Rate limit：本地单用户，没有独立请求限流；sub agent 只在当前用户任务内创建。
- Kill switch：停止当前 Codex 任务；未落库的候选不进入权威状态。
- 外部模型/API：SQLite MCP 已删除、无从调用；模型认证由所用 harness 产品负责。
