---
name: novel-memory
description: 为小说规划、续写或审查构建最小且连贯的 Canon 上下文。需要检索近期章节、人物与世界状态、相关事实、伏笔、关系时使用。
---

# 小说记忆

通过 SQLite MCP 查询数据库构建上下文。SQL 模板见 `novel-project/sql-reference.md`。

> **单一来源约定**：写作/审查/连续性提取的 canon 最小集**优先消费组装器的 `canon_minimal` 槽位**（`python legacy-python/scripts/novelos_compose_prompt.py --asset <asset> --project <id>` 自动注入六类账本近端条目 + 近期已接受章节摘要，SQL 与 sql-reference.md 模板同源）。本技能用于组装未覆盖的定制检索（特定人物/时间窗口/线索深挖）——检索时沿用 sql-reference.md 模板，禁止另写一套语义重复的 SQL。

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

-- 搜索事实（描述存 resources，按 sql-reference.md 同源模板）
SELECT cf.*, CAST(r.content AS TEXT) AS description FROM chapter_facts cf
JOIN resources r ON cf.description_resource_id = r.id
WHERE cf.subject LIKE '%关键词%' OR r.content LIKE '%关键词%';

-- 当前 locked 规划资产（Canon 快照）
SELECT id, asset_type, scope_ref, revision, metadata_json FROM planning_assets
WHERE project_id = ? AND status = 'locked' ORDER BY asset_type;

-- 项目约束快照（频道/平台耐心/表里基调/美学——写作与审查的硬约束来源）
SELECT json_extract(metadata_json, '$.setup') AS setup FROM projects WHERE id = ?;

-- 叙事承诺
SELECT * FROM narrative_promises WHERE project_id = ? AND status = 'open';

-- 人物关系
SELECT * FROM relationship_states WHERE project_id = ?;
```

3. 只在任务确实需要时读 `resources.content`（正文全文）；不要预载全部正文。
4. 以较新的 Canon 和已接受章节为准。发现矛盾时列出双方来源，不要静默裁决。
5. 返回紧凑上下文包：任务目标、项目约束（setup 快照：频道/平台耐心/表里基调/美学）、近期事件、活跃实体状态、世界约束、未解决线索、连续性风险。
6. **内核陈旧检查**（构建规划/写作上下文时顺带）：项目绑定的内核版本低于库内该内核最高 revision 时，在上下文包末尾标注「内核有新版本（当前 rN / 最新 rM）」——是否跟随新内核重派生分身由用户裁决（sql-reference.md「作者签名链」有查询模板），不静默换绑。
