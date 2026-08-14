# Agent 与自动化

## 所有权

Codex **主控智能体** 是唯一自动化编排者。NovelOS 不运行后台 worker、cron、Webhook 或自主循环；业务 sub agent 只能在用户任务期间由主控按需创建（用 Agent 工具），返回一次结果后销毁。

项目创建向导由主控编排：主控提供本地 HTML 路径（`ui/project-wizard.html`），页面生成结构化 `novelos.project.create.v1` JSON；用户将其发回后，主控 Read `catalog/skills/onboarding/creator-signature-fusion/prompt.md`，连同 `selected_archetypes` + `user_signature_inputs` + `project_setup` + `config/system_archetypes.json` 一起注入临时 **引导融合智能体（onboarding_agent）** sub agent。agent 按「先立人，再落规」两步法：判定 parent 并输出 rationale → 反推式五维生平化合出 persona（含盲区清单 refuses/cannot_write）→ 从 persona 长出带体温的 7 字段，产出 `creator_derivation_candidate`（签名 schema v2）。主控用 jsonschema（`config/schemas/creator-signature.schema.json`）校验签名合规（v2 强制 persona 且 `cannot_write` 非空）、用 `scripts/novelos_hash.py` 算 hash 后，按 sql-reference.md「作者签名链」模板用 SQL 原子创建 creator_profiles/versions（content + derivation 双资源链）、projects 与精确绑定。落库事务本身不调用 LLM，LLM 只在 onboarding_agent 的 Codex run 内运行；该步骤不产生规划资产。本地页面不直接写数据库，只负责原型选择、表单校验和 JSON 生成。

## Agent 清单

| 类别 | 触发 | 输出 | 副作用 |
|---|---|---|---|
| 8 个规划资产 Agent（方向/架构/策略/人物/世界观/故事弧/卷规划/章节规划） | 需要创建或修订对应权威资产 | 规划候选正文 | 无；主控落库 |
| 写作智能体 | 完整章节、长场景或需隔离创作上下文 | 章节草稿 | 无；主控创建草稿 |
| 审查智能体 | 规划锁定、章节接受、连续性晋升前 | 审查意见 | 无；主控登记 reviews |
| 上下文构建智能体 | 跨卷、多线、事实冲突或上下文溢出 | 上下文包 | 无 |
| 引导融合智能体（onboarding） | 项目创建阶段 | `creator_derivation_candidate` | 无；主控经 jsonschema 校验后 SQL 落库 |

精确角色职责、最小输入与方法论由主控在创建 sub agent 时注入对应的 `catalog/skills/<分类>/<目录>/prompt.md`（见 AGENTS.md「Agent 角色」段）。sub agent 没有数据库写入权限，只返回候选文本；所有持久化由主控经 SQLite MCP `execute_sql` 完成。

作者签名不是规划资产，也不新增常驻角色。它是用户拥有的不可变版本配置；多原型签名融合由临时 onboarding_agent 在项目创建时完成，run 结束即销毁。本书 `book_soul` 由既有方向智能体生成，Writer 仍按完整章节/长场景的保守条件临时创建。

## Steering 与硬约束

- Steering：项目 Skill 的 `SKILL.md`（`.agents/skills/`）和选择后的创作方法论 `prompt.md`（`catalog/skills/`）。
- 硬约束：jsonschema 校验（签名、book_soul）、确定性脚本（hash、validate_book_soul）、SQLite 状态机（`planning_assets.status` 的 candidate→locked→stale 流转与 CHECK 约束）、Hash/版本、独立审查 sub agent、`CAST(? AS BLOB)` 等落库约定。
- Prompt 不能授权写入；sub agent 的文本声明不替代主控的 SQL 落库与校验。不再有 MCP Tool Schema、`authority_commits` 或 Trace 门禁层（已随 migration 016 删除）。

## 生命周期

1. 主控读取对应方法论 `prompt.md`，用 Agent 工具创建临时 sub agent，注入最小输入与必要的 locked 上游内容。
2. sub agent 在隔离上下文执行，只返回候选文本（规划候选 / 章节草稿 / 审查意见 / 融合候选 / 上下文包）。
3. 主控落库：`scripts/novelos_hash.py` 算 content_hash → `INSERT INTO resources (... CAST(? AS BLOB) ...)` → `INSERT INTO planning_assets/chapters (..., 'candidate', ...)` → 记录上游依赖 `planning_asset_dependencies`。
4. 主控创建**独立**审查 sub agent（不同上下文）审查候选 → `INSERT INTO reviews`。
5. 审查通过后主控执行 `UPDATE ... SET status='locked'`（规划）或 `'accepted'`（章节）；旧版本变 `superseded`。
6. 上游资产修订（新 revision locked）后，主控运行 `scripts/novelos_propagate_stale.py --asset <上游id>` 递归标记下游 `stale`。
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
- 外部模型/API：SQLite MCP 不调用，模型由 Codex 产品负责。
