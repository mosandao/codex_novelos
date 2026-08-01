# Agent 与自动化

## 所有权

Codex 主控智能体 是唯一自动化编排者。NovelOS 不运行后台 worker、cron、Webhook 或自主循环；业务 Agent 只能在用户任务期间由 Main 按需创建，完成一次结果后销毁。

项目创建向导也由 Main 编排：Main 通过 `project.wizard.render` 将 MCP Apps 资源交给用户填写，
由 `project.wizard.submit` 原子创建或确认 Creator Profile 版本、创建项目、建立精确绑定并刷新投影。
该步骤不创建业务 Agent，也不产生规划资产；Main 必须随后读取 `metadata.project_setup` 与
`creator_binding.constraint_ref`、启动 Trace，并按正常流程创建方向智能体。直接打开
`project-wizard.html` 的本地 `file://` 预览页没有提交权限。

## Agent 清单

| 类别 | 触发 | 输出 | 副作用 |
|---|---|---|---|
| 8 个规划资产 Agent | 需要创建或修订对应权威资产 | `planning_candidate`、change proposal | 无；Main 登记候选 |
| 写作智能体 | 完整章节、长场景或需隔离创作上下文 | `chapter_draft_candidate` | 无；Main 创建草稿 |
| 审查智能体 | 规划锁定、章节接受、Entity 提交、连续性晋升前 | `review_receipt_candidate` | 无；Main 记录 Review |
| 上下文构建智能体 | 跨卷、多线、事实冲突或上下文溢出 | `context_package` | 无 |

精确角色、最小输入、输出类型、Catalog 包、Review Profile、spawn gate 和工具白名单位于 `config/agents.yaml`。

作者签名不是 Agent，也不新增常驻角色或第九种规划资产 owner。它是用户拥有的不可变版本配置；
本书 `book_soul` 由既有方向智能体生成，Writer 仍按完整章节/长场景的保守条件临时创建。

## Steering 与硬门禁

- Steering：项目 Skill 的 `SKILL.md` 和选择后的 Catalog `prompt.md`。
- 硬门禁：MCP Tool Schema、JSON Schema、Agent contract、SQLite 状态机、Hash、版本、Review Receipt、事务和 Trace。
- Prompt 不能授权写入；Agent 的文本声明不能替代 MCP 校验。

## 生命周期

1. `trace.start` 建立操作 Trace。
2. `agent.start` 校验角色与输入，生成唯一 `agent-run` 和 `agent-context`，自动记录 `agent.spawn`。
3. Main 在新 Codex 上下文执行临时 Agent，只提供白名单工具。
4. `agent.finish` 校验 typed result；完成、失败或超时均自动记录 `agent.destroy`。
5. 权威提交在同一事务内写入 `authority_commits` 和 Trace step，并校验 Producer/Reviewer run 属于同一 Trace。
6. `trace.audit_authority` 检查项目内每个已提交状态是否具有精确 subject Hash、Review Receipt 和 Trace step；有活动 run 时 `trace.finish` 失败。

失败或超时 run 不允许返回部分结果。系统没有语义 fallback、自动重试或自动权威提交；是否重试由 Main 基于用户目标重新路由，并创建新的 run。

## 审查隔离

Reviewer run 必须读取不可变 subject ref、精确 `subject_hash`、Review Profile 和权威上下文。MCP 比较 Reviewer 输入、结构化输出和 `review.record` 参数，并拒绝生产 run 冒充 Reviewer。

Agent 质量实验使用 `review.prepare_subject` 构造不含执行模式的不可变盲评包。MCP 绑定已完成 Producer runs 和输出 refs，Review Receipt 额外绑定结构化 assessment Resource；该 Receipt 只用于评测证据，不具备小说权威提交权限。

完整 70-case 实验当前延期。延期期间 Writer 只处理完整章节、长场景或明确需要隔离上下文的写作；上下文构建智能体 只在 `complexity_reasons` 命中跨卷、多线、事实冲突或上下文溢出时创建。已完成的部分 case 仅作为恢复证据，不用于宣称胜率或改变路由。

Character/World 交叉审查将两个 locked 资产的 ID、版本和 Hash 组成独立 subject；Story Arc 只能消费已批准且仍有效的检查。

## 操作控制

- 审批：只有 Main 可调用锁定、接受、提交和晋升工具。
- 审计：Agent run、Spawn/Destroy、Catalog 选择和 Review 进入 Trace/Receipt；权威提交不能手工补记，必须由 MCP 原子写入 `authority_commits`。
- Rate limit：本地 V1 没有独立请求限流；Agent 只在当前用户任务内创建。
- Kill switch：停止当前 Codex 任务或终止 stdio MCP 进程；未提交候选不进入权威状态。
- 外部模型/API：NovelOS MCP 不调用，模型由 Codex 产品负责。
