# Agent 与自动化

## 所有权

Codex 主控智能体 是唯一自动化编排者。NovelOS 不运行后台 worker、cron、Webhook 或自主循环；业务 Agent 只能在用户任务期间由 Main 按需创建，完成一次结果后销毁。

项目创建向导由 Main 编排：Main 提供本地 HTML 路径，页面生成结构化
`novelos.project.create.v1` JSON；用户将其发回后，Main 按 `selected_archetypes` 数量选择签名融合
路径。单原型直接调用 `project.wizard.reconcile_archetypes` 确定性融合（`parent_source:"scored"`）；多原型（≥2）先在 Trace 内
创建临时 `onboarding_agent` run，由 LLM 判定 parent 并深度融合跨原型约束，产出
`creator_derivation_candidate`，再把 Agent 判定的 parent 与完整融合签名作为 `fused_parent_version_id` /
`fused_signature` 传给 `project.wizard.reconcile_archetypes` 做确定性合规收口（`parent_source:"fused"`，
由 MCP 自动折算 overrides diff）。两条路径
最终都调用 `project.wizard.submit` 原子创建或确认 Creator Profile 版本、创建项目、建立精确绑定并
刷新投影。新向导不得提交 `reuse` 或 `create`。落库事务本身不调用 LLM，LLM 只在 `onboarding_agent`
的 Codex run 内运行；该步骤不产生规划资产；Main 必须随后读取 `metadata.project_setup` 与
`creator_binding.constraint_ref`、启动 Trace，并按正常流程创建方向智能体。本地页面不直接写数据库，
只负责原型选择、表单校验和 JSON 生成。

## Agent 清单

| 类别 | 触发 | 输出 | 副作用 |
|---|---|---|---|
| 8 个规划资产 Agent | 需要创建或修订对应权威资产 | `planning_candidate`、change proposal | 无；Main 登记候选 |
| 写作智能体 | 完整章节、长场景或需隔离创作上下文 | `chapter_draft_candidate` | 无；Main 创建草稿 |
| 审查智能体 | 规划锁定、章节接受、Entity 提交、连续性晋升前 | `review_receipt_candidate` | 无；Main 记录 Review |
| 上下文构建智能体 | 跨卷、多线、事实冲突或上下文溢出 | `context_package` | 无 |
| 引导融合智能体 | 项目创建阶段用户选了 ≥2 个系统原型 | `creator_derivation_candidate` | 无；Main 用其输出经 reconcile 收口后 submit |

精确角色、最小输入、输出类型、Catalog 包、Review Profile、spawn gate、运行时 enforcement 和工具白名单位于 `config/agents.yaml`。`review_profile_routes` 的 key 是合法 Profile 名唯一注册表；roles、交叉一致性检查和章节、连续性、Entity 等业务用途都只保存引用。MCP 启动时验证引用结构、非空值和注册关系，缺失、拼错、未知字段或未注册 Profile 均失败关闭。

作者签名不是规划资产，也不新增常驻角色或第九种规划资产 owner。它是用户拥有的不可变版本配置；
多原型签名融合由临时 `onboarding_agent` 在项目创建 Trace 内完成，run 结束即销毁，不持有提交权限。
本书 `book_soul` 由既有方向智能体生成，Writer 仍按完整章节/长场景的保守条件临时创建。

## Steering 与硬门禁

- Steering：项目 Skill 的 `SKILL.md` 和选择后的 Catalog `prompt.md`。
- 硬门禁：MCP Tool Schema、JSON Schema、Agent contract、SQLite 状态机、Hash、版本、Review Receipt、事务和 Trace。
- Prompt 不能授权写入；Agent 的文本声明不能替代 MCP 校验。

## 生命周期

1. `trace.start` 建立操作 Trace。
2. `agent.start` 校验角色与输入，生成唯一 `agent-run` 和 `agent-context`，自动记录 `agent.spawn`。
3. Main 在新 Codex 上下文执行临时 Agent，只提供白名单工具。
4. `agent.finish` 同时校验 typed result 外壳和已注册 `output_type` 的 payload Schema；完成、失败或超时均自动记录 `agent.destroy`。
5. 权威提交在同一事务内写入 `authority_commits` 和 Trace step，并校验 Producer/Reviewer run 属于同一 Trace。
6. `trace.audit_authority` 检查项目内每个已提交状态是否具有精确 subject Hash、Review Receipt 和 Trace step；有活动 run 时 `trace.finish` 失败。

失败或超时 run 不允许返回部分结果。系统没有语义 fallback、自动重试或自动权威提交；是否重试由 Main 基于用户目标重新路由，并创建新的 run。

## 审查隔离

Reviewer run 必须读取不可变 subject ref、精确 `subject_hash`、Review Profile 和权威上下文。Main 调用 `review.record_from_run`，MCP 直接读取不可变结构化输出并与 Reviewer 输入比较，拒绝生产 run 冒充 Reviewer或由 Main 重组 Receipt。

Agent 质量实验使用 `review.prepare_subject` 构造不含执行模式的不可变盲评包。MCP 绑定已完成 Producer runs 和输出 refs，Review Receipt 额外绑定结构化 assessment Resource；该 Receipt 只用于评测证据，不具备小说权威提交权限。

完整 70-case 实验当前延期。延期期间 Writer 只处理完整章节、长场景或明确需要隔离上下文的写作；上下文构建智能体 只在 `complexity_reasons` 命中跨卷、多线、事实冲突或上下文溢出时创建。已完成的部分 case 仅作为恢复证据，不用于宣称胜率或改变路由。

Character/World 交叉审查将两个 locked 资产的 ID、版本和 Hash 组成独立 subject。调用方提供检查时，无论 enforcement 模式如何，都必须是当前项目已批准、来源未失效且与 Story Arc 上游精确匹配的检查；候选创建后还会在 lock 时重新验证。默认 lenient 允许不提供检查，并在 lock 事务中写入 `status=completed`、`details.severity=warning`、`details.enforcement_mode=lenient` 的 Trace step；`runtime.enforcement.strict_cross_consistency=true` 时缺失检查会阻断。

`isolation_evidence` 同样受 `runtime.enforcement.strict_isolation_evidence` 控制：默认 lenient 对缺失的 Producer 或 Reviewer 凭据分别记录上述 warning Trace step 后放行，strict 才维持拒绝。该字段和 `context_id` 都是审计记录，不构成真实模型上下文隔离证明；独立 `review_agent` run、不可变 subject/hash、同 Trace 和输出绑定在两种模式下始终强制。

## 操作控制

- 审批：只有 Main 可调用锁定、接受、提交和晋升工具。
- 审计：Agent run、Spawn/Destroy、Catalog 选择和 Review 进入 Trace/Receipt；权威提交不能手工补记，必须由 MCP 原子写入 `authority_commits`。
- Rate limit：本地 V1 没有独立请求限流；Agent 只在当前用户任务内创建。
- Kill switch：停止当前 Codex 任务或终止 stdio MCP 进程；未提交候选不进入权威状态。
- 外部模型/API：NovelOS MCP 不调用，模型由 Codex 产品负责。
