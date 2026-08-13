---
name: novel-continuity
description: 从已接受小说章节提取连续性数据。章节接受后需要更新事实、人物关系、叙事承诺、读者期待或故事弧状态时使用。
---

# 小说连续性

通过 SQLite MCP 操作数据库。SQL 模板见 `novel-project/sql-reference.md`。

## 工作流

1. 确认章节已接受：`SELECT status FROM chapters WHERE id=?` → 必须是 `accepted`。
2. 读取章节正文和当前 Canon：`SELECT content FROM resources WHERE id=(SELECT content_resource_id FROM chapters WHERE id=?)`。
3. 用 sub agent 从章节正文中提取候选：事实（fact）、叙事承诺（promise）、读者期待（expectation）、人物关系（relationship）、故事弧状态（arc）。每项必须有明确来源，不把推测写成事实。
4. 直接写入数据库：

```sql
-- 章节事实
INSERT INTO chapter_facts (id, chapter_id, fact_type, fact_json)
VALUES (?, ?, ?, ?);

-- 叙事承诺
INSERT INTO narrative_promises (id, project_id, promise_type, description, status)
VALUES (?, ?, ?, ?, 'open');

-- 人物关系
INSERT INTO relationship_states (id, project_id, character_a, character_b, relationship_type, description)
VALUES (?, ?, ?, ?, ?, ?);

-- 故事弧状态
INSERT INTO arc_states (id, project_id, arc_id, state_json)
VALUES (?, ?, ?, ?);
```

5. 如果提取的事实与既有 Canon 冲突，列出双方来源让主控决策，不静默覆盖。

连续性提取不需要独立审查流程——sub agent 直接提取，主控确认后写入。
