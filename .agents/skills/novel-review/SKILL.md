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
4. 每个 finding 只使用 `blocking`、`warning` 或 `note`，并给出最小直接证据和来源 ref。
5. 只要存在 `blocking` finding，verdict 必须是 `rejected`。
6. 返回同一 `subject_hash`、verdict、findings、evidence refs 和 reviewer profile；由 Main Agent 调用 `review.record` 登记。

正文使用 `prose-*` Profile，连续性使用 `continuity-*` Profile，规划资产使用 `$novel-planning` 表中与 `asset_type` 精确对应的 Profile。
