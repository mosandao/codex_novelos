---
name: novel-continuity
description: 从已接受小说章节提取可审查的连续性候选。章节接受后需要更新事实、人物关系、叙事承诺、读者期待、故事弧状态或时间线，并要求绑定正文 Hash 和权威快照时使用。
---

# 小说连续性

只产生带来源的候选；不要直接修改 Canon，也不要创建独立 Continuity Agent。

## 工作流

1. 用 `chapter.get` 确认章节状态为 `accepted`，记录精确 `chapter_id` 和 `subject_hash`。
2. 用 `memory.get_authority_snapshot` 获取提取时的权威版本；只读取判断候选所必需的上下文。
3. 从章节中提取严格候选：`fact`、`narrative_promise`、`expectation`、`relationship` 和 `arc`。每项必须有明确来源，不把推测写成事实。
4. 由 Main Agent 调用 `continuity.record_candidates` 登记不可变候选集和 Hash。
5. 使用 `$novel-review` 和独立 Review Agent 的 continuity Profile 审查候选集，再由 Main Agent调用 `review.record`。
6. 只有正文 Hash、Review Hash 和 Authority Snapshot 都仍有效时，Main Agent 才调用 `continuity.promote_reviewed` 原子晋升。

发现冲突或权威版本变化时停止晋升并返回冲突详情；不要用硬编码 fallback 静默选择。
