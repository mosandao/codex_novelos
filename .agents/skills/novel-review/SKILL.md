---
name: novel-review
description: 独立审查不可变小说资产并生成绑定 subject_hash 的 Review Receipt。规划资产锁定、章节接受、连续性事实晋升前，或需要检查 Canon、人物、世界规则、节奏和文本质量时使用。
---

# 小说审查

审查精确 subject；不要重写 subject、修改上游、锁定资产、接受章节或晋升 Canon。

## 工作流

1. 接收不可变 `subject_ref`、`subject_hash`、资产类型对应的 Review Profile 和精确权威上下文 refs。
2. 在隔离的 Review Agent 中审查；不要提供生产 Agent 的隐藏推理、预期结论或其他 Reviewer 结果。该 Review Agent 必须以独立 Codex Task 创建，其 agentId 作为 `isolation_evidence` 传入 `agent.start`；缺凭据的 reviewer run 无法用于 `planning.lock`/`chapter.accept`/`continuity.promote`。
3. 检查上游忠实度、Canon、人物知识和动机、世界规则、时间顺序及目标 Profile 指定的质量维度。涉及作者约束时还要核对精确 Creator Profile/Direction refs、`book_soul` 的有代价矛盾、人物独立性、叙述者说教、廉价解决、人口属性推导、具体作者模仿与跨章立场漂移。
4. 每个 finding 只使用 `blocking`、`warning` 或 `note`，并给出最小直接证据和来源 ref；可选 `code` 必须是非空稳定标识。
5. 只要存在 `blocking` finding，verdict 必须是 `rejected`。
6. `review_receipt_candidate` 只返回 `subject_type`、同一 `subject_ref`/`subject_hash`、`verdict`、`findings`、`reviewer_profile` 和 `evidence_refs`。只有 `subject_type=review_subject` 的质量评测可额外返回非空 `assessment`；不得返回 `reviewer_run_id` 或其他字段。
7. 由 Main Agent 调用 `review.record_from_run(reviewer_run_id)` 登记，MCP 直接读取并校验不可变 Agent 输出；不要由 Main 读取 Resource 后重组 Receipt。

正文使用 `prose-*` Profile，连续性使用 `continuity-*` Profile，规划资产使用 `$novel-planning` 表中与 `asset_type` 精确对应的 Profile。

## 操作前置检查

以下规则来自实际审查执行中遇到的工具调用失败，在构造数据前必须确认。

### 规划资产审查路径

规划资产审查**不走** `review.prepare_subject`——该方法只接受 `subject_kind=agent_quality_evaluation`，是 Agent 质量实验专用入口。

正确路径：

1. 创建 `review_agent` run。`input_bindings` 必须精确包含 `immutable_subject_ref`、`subject_hash`、`review_profile`、`authority_context_refs` 四个字段（从 `config/agents.yaml` 的 `review_agent.minimum_inputs` 确认），每个 value 是非空字符串或非空字符串数组。
2. 在隔离上下文中完成审查，`agent.finish` 时 `output_type=review_receipt_candidate`，`output` 传 `review_receipt_candidate` dict（不是正文文本字符串）。
3. Main 调用 `review.record_from_run(reviewer_run_id)` 登记。

### review_receipt_candidate 构造规则

派生自 `config/schemas/review-receipt-candidate.schema.json`：

- 每个 finding 必须含 `evidence_refs`（required，非空字符串数组，uniqueItems）；遗漏会导致整个 receipt 被拒。
- `subject_type` 只接受 `chapter`、`continuity_candidate_set`、`planning_asset`、`entity_mutation`、`planning_cross_check`、`review_subject`。
- `subject_type != review_subject` 时**不得**包含 `assessment` 字段（schema 用 `allOf/if-then-else` 约束）。
- findings 的 `severity` 只接受 `blocking`、`warning`、`note`。
- `verdict` 只接受 `approved`、`rejected`；存在 `blocking` finding 时必须是 `rejected`。

### 审查 prompt 自包含约束

创建审查 Codex Task sub-agent 时，prompt 必须包含**审查所需的全部上游文本原文**，不能只传摘要或"铁律速查"。

根因实例：Architecture 审查 prompt 传入了完整的 Direction 全文（含 book_soul 9 字段原文），sub-agent 0 次 tool_uses、39K tokens；Strategy 审查 prompt 只传了上游摘要，sub-agent 自己用 22 次工具调用去读文件补充信息，消耗 613K tokens（15.5 倍）。摘要不完整 → sub-agent 自行探索 → token 失控。

规则：

- **传入完整原文**：候选正文全文 + 全部已锁定上游资产的正文全文（不是摘要）。多层资产审查时（如 Strategy 的上游是 Direction + Architecture），所有上游都要传完整原文。
- **禁止依赖 sub-agent 自行读文件**：审查 sub-agent 的 prompt 自包含全部审查依据后，应在 prompt 中明确指示「依据已在 prompt 中提供，不需要读取文件或搜索」。
- **token 预算**：若候选+全部上游原文总和超过约 2 万字，优先压缩候选摘要（保留关键段落原文引用），但上游铁律（forbidden_resolutions、central_contradiction、守恒律等）必须保留原文，不可摘要化。
