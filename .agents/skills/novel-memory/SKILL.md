---
name: novel-memory
description: 为小说规划、续写或审查构建最小且连贯的 Canon 上下文。需要检索近期章节、人物与世界状态、相关事实、伏笔、关系时使用。
---

# 小说记忆

通过 SQLite MCP 查询数据库构建上下文。SQL 模板见 `novel-project/sql-reference.md`。

## 工作流

1. 明确目标资产或章节、人物、地点、剧情线和时间窗口。
2. 用 SQL 查询获取轻量结果：

```sql
-- 近期已接受章节
SELECT c.id, c.number, c.title, c.summary, c.metadata_json, r.content
FROM chapters c JOIN resources r ON c.content_resource_id = r.id
WHERE c.volume_id = (SELECT id FROM volumes WHERE book_id = (SELECT id FROM books WHERE project_id = ?))
  AND c.status = 'accepted'
ORDER BY c.number DESC LIMIT 5;

-- 搜索事实
SELECT * FROM chapter_facts WHERE fact_json LIKE '%关键词%';

-- 当前 locked 规划资产（Canon 快照）
SELECT id, asset_type, scope_ref, revision, metadata_json FROM planning_assets
WHERE project_id = ? AND status = 'locked' ORDER BY asset_type;

-- 叙事承诺
SELECT * FROM narrative_promises WHERE project_id = ? AND status = 'open';

-- 人物关系
SELECT * FROM relationship_states WHERE project_id = ?;
```

3. 只在任务确实需要时读 `resources.content`（正文全文）；不要预载全部正文。
4. 以较新的 Canon 和已接受章节为准。发现矛盾时列出双方来源，不要静默裁决。
5. 返回紧凑上下文包：任务目标、近期事件、活跃实体状态、世界约束、未解决线索、连续性风险。
