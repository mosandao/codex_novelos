# NovelOS SQL 操作速查

通过 SQLite MCP 的 `execute_sql` 工具直接操作数据库。`?` 是参数占位符。

## 内容存储（resources）

所有正文、规划内容都存在 resources 表。写内容时用 `CAST(? AS BLOB)` 确保 BLOB 存储。

```sql
-- 存内容（正文/规划/JSON）
INSERT INTO resources (id, media_type, content, content_hash)
VALUES ('resource:xxx', 'text/markdown', CAST(? AS BLOB), ?);
-- media_type: 'text/markdown'(正文/规划) 或 'application/json'(结构化)
-- content_hash: 用 scripts/novelos_hash.py 计算

-- 读内容（自动解码为 UTF-8 文本）
SELECT content FROM resources WHERE id = 'resource:xxx';
```

## 项目 / 书 / 卷 / 章节（CRUD）

```sql
-- 项目
INSERT INTO projects (id, name, description, version, metadata_json)
VALUES ('project:xxx', '书名', '描述', 1, '{}');
SELECT * FROM projects;
UPDATE projects SET description = ? WHERE id = 'project:xxx';

-- 书
INSERT INTO books (id, project_id, title, version, metadata_json)
VALUES ('book:xxx', 'project:xxx', '第一卷集', 1, '{}');

-- 卷
INSERT INTO volumes (id, book_id, number, title, summary)
VALUES ('volume:xxx', 'book:xxx', 1, '卷标题', '');

-- 章节（创建草稿）
INSERT INTO chapters (id, volume_id, number, title, status, content_resource_id, summary, metadata_json, version)
VALUES ('chapter:xxx', 'volume:xxx', 1, '章标题', 'draft', 'resource:xxx', '', '{}', 1);

-- 接受章节
UPDATE chapters SET status = 'accepted', version = version + 1, updated_at = CURRENT_TIMESTAMP
WHERE id = 'chapter:xxx';

-- 重开为 draft（修改）
UPDATE chapters SET status = 'draft', version = version + 1, updated_at = CURRENT_TIMESTAMP
WHERE id = 'chapter:xxx';

-- 查询已接受章节
SELECT c.*, r.content FROM chapters c
JOIN resources r ON c.content_resource_id = r.id
WHERE c.status = 'accepted' AND c.volume_id = 'volume:xxx'
ORDER BY c.number;
```

## 规划资产（planning_assets）

```sql
-- 创建候选
INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status,
    content_resource_id, producer_role, metadata_json, version)
VALUES ('planning:xxx', 'project:xxx', 'direction', 'book', 1, 'candidate',
    'resource:xxx', '方向智能体', '{}', 1);

-- 锁定（审查通过后）
UPDATE planning_assets SET status = 'locked', locked_review_id = 'review:xxx',
    updated_at = CURRENT_TIMESTAMP WHERE id = 'planning:xxx';

-- 标记 stale（上游变更后）
-- 用脚本：python scripts/novelos_propagate_stale.py --asset planning:xxx

-- 查询当前 locked 资产
SELECT * FROM planning_assets
WHERE project_id = 'project:xxx' AND status = 'locked'
ORDER BY asset_type;

-- 记录上游依赖
INSERT INTO planning_asset_dependencies (asset_id, upstream_asset_id, upstream_version)
VALUES ('planning:downstream', 'planning:upstream', 2);
```

## 审查（reviews）

```sql
-- 记录审查结果
INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict,
    findings_json, reviewer_profile, evidence_refs_json)
VALUES ('review:xxx', 'chapter', 'chapter:xxx',
    'sha256:...',  -- 正文 resource 的 content_hash
    'approved',
    '[{"severity":"note","message":"...","evidence_refs":["chapter:xxx"]}]',
    'prose-v1',
    '["resource:xxx"]');

-- 查未解决 warning
SELECT * FROM reviews
WHERE subject_ref = 'chapter:xxx'
  AND verdict = 'approved'
  AND findings_json LIKE '%warning%';
```

## 记忆 / 连续性

```sql
-- 章节事实（先存描述到 resources，再引用）
INSERT INTO resources (id, media_type, content, content_hash) VALUES ('resource:desc', 'text/markdown', CAST(? AS BLOB), ?);
INSERT INTO chapter_facts (id, project_id, source_chapter_id, source_content_hash, fact_type, subject, description_resource_id, status, metadata_json)
VALUES ('fact:xxx', 'project:xxx', 'chapter:xxx', 'sha256:...', 'character_state', '人物名', 'resource:desc', 'accepted', '{}');
-- status 只接受: accepted/superseded/rejected/quarantined

-- 叙事承诺
INSERT INTO narrative_promises (id, project_id, promise_type, description, status)
VALUES ('promise:xxx', 'project:xxx', 'mystery', '描述', 'open');

-- 人物关系
INSERT INTO relationship_states (id, project_id, character_a, character_b, relationship_type, description)
VALUES ('rel:xxx', 'project:xxx', 'char:a', 'char:b', 'ally', '描述');

-- 搜索事实
SELECT cf.*, r.content FROM chapter_facts cf
JOIN resources r ON cf.description_resource_id = r.id
WHERE cf.subject LIKE '%关键词%' OR r.content LIKE '%关键词%';
```

## ID 生成

ID 格式为 `类型:uuid`。用 Python 生成：

```python
import uuid
print(f"chapter:{uuid.uuid4()}")      # chapter:b74aa654-...
print(f"planning:{uuid.uuid4()}")     # planning:184b6f38-...
print(f"review:{uuid.uuid4()}")       # review:3756c94c-...
print(f"resource:{uuid.uuid4()}")     # resource:3bb695f0-...
```

## 确定性脚本

| 脚本 | 用途 |
|---|---|
| `scripts/novelos_hash.py` | 计算 content_hash |
| `scripts/novelos_validate_book_soul.py` | 校验 book_soul JSON |
| `scripts/novelos_render_projection.py` | 渲染项目文件目录 |
| `scripts/novelos_propagate_stale.py` | 上游变更后标记下游 stale |
