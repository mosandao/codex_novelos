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

## 作者签名链（项目创建落库）

onboarding_agent 产出 `creator_derivation_candidate` 后，主控按以下顺序落库。签名 JSON（schema v2，含 persona）存 resources，派生记录（parent 指向 + rationale）存 derivation_resource_id 指向的第二个 resource。

```sql
-- 1. 签名内容（含 persona 的完整签名 JSON）
INSERT INTO resources (id, media_type, content, content_hash)
VALUES ('resource:sig', 'application/json', CAST(? AS BLOB), ?);  -- hash 用 novelos_hash.py

-- 2. 派生记录（parent 指向 + 判定理由 + 用户输入快照）
INSERT INTO resources (id, media_type, content, content_hash)
VALUES ('resource:deriv', 'application/json', CAST(? AS BLOB), ?);

-- 3. creator profile（每次派生新建）
INSERT INTO creator_profiles (id, display_name, ownership)
VALUES ('creator-profile:xxx', '一句话人格名', 'user');

-- 4. profile version（parent 指向系统原型版本，双资源链）
INSERT INTO creator_profile_versions (id, profile_id, revision, content_resource_id,
    subject_hash, parent_version_id, derivation_resource_id)
VALUES ('creator-profile-version:xxx', 'creator-profile:xxx', 1,
    'resource:sig', 'sha256:...',          -- 签名 JSON 的 content_hash
    'creator-profile-version:system-xxx:1', -- parent = 选定系统原型（单/多原型均为判定出的 parent）
    'resource:deriv');

-- 5. 项目 + 绑定
INSERT INTO projects (id, name, description, version, metadata_json)
VALUES ('project:xxx', '书名', '描述', 1, '{}');
INSERT INTO project_creator_bindings (project_id, profile_id, profile_version_id,
    profile_revision, subject_hash, binding_mode)
VALUES ('project:xxx', 'creator-profile:xxx', 'creator-profile-version:xxx', 1,
    'sha256:...', 'derive');  -- subject_hash 与 profile version 一致

-- 查询项目绑定的完整签名（含 persona）
SELECT v.id, v.revision, v.subject_hash, CAST(r.content AS TEXT) AS signature_json
FROM project_creator_bindings b
JOIN creator_profile_versions v ON v.id = b.profile_version_id
JOIN resources r ON r.id = v.content_resource_id
WHERE b.project_id = 'project:xxx';
```

落库校验门（INSERT 前必须全部通过）：
- `config/schemas/creator-signature.schema.json` 校验签名（v2 必须含 persona，`blindspots.cannot_write` 非空）
- overrides 字段在 7 个签名字段内且无逐字复制父值（语义继承允许，须从 persona 重新长出）
- `parent_version_id` / `parent_subject_hash` 与 `config/system_archetypes.json` 中的原型一致

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

连续性账本统一模式：描述文本先存 resources，再引用 resource id；必须带来源章节与正文 hash 溯源。

```sql
-- 章节事实（先存描述到 resources，再引用）
INSERT INTO resources (id, media_type, content, content_hash) VALUES ('resource:desc', 'text/markdown', CAST(? AS BLOB), ?);
INSERT INTO chapter_facts (id, project_id, source_chapter_id, source_content_hash, fact_type, subject, description_resource_id, status, metadata_json)
VALUES ('fact:xxx', 'project:xxx', 'chapter:xxx', 'sha256:...', 'character_state', '人物名', 'resource:desc', 'accepted', '{}');
-- status 只接受: accepted/superseded/rejected/quarantined

-- 叙事承诺（promise_key 项目内唯一；描述存 resource）
INSERT INTO resources (id, media_type, content, content_hash) VALUES ('resource:pd', 'text/markdown', CAST(? AS BLOB), ?);
INSERT INTO narrative_promises (id, project_id, promise_key, description_resource_id, status, source_chapter_id, source_content_hash)
VALUES ('promise:xxx', 'project:xxx', '伏笔键名', 'resource:pd', 'open', 'chapter:xxx', 'sha256:...');
-- status 只接受: open/resolved/broken

-- 读者期待
INSERT INTO resources (id, media_type, content, content_hash) VALUES ('resource:ed', 'text/markdown', CAST(? AS BLOB), ?);
INSERT INTO expectation_ledgers (id, project_id, expectation_key, description_resource_id, status, source_chapter_id, source_content_hash)
VALUES ('expectation:xxx', 'project:xxx', '期待键名', 'resource:ed', 'open', 'chapter:xxx', 'sha256:...');
-- status 只接受: open/met/abandoned

-- 人物关系（subject_ref/object_ref + 状态存 resource）
INSERT INTO resources (id, media_type, content, content_hash) VALUES ('resource:rd', 'text/markdown', CAST(? AS BLOB), ?);
INSERT INTO relationship_states (id, project_id, subject_ref, object_ref, state_resource_id, source_chapter_id, source_content_hash)
VALUES ('rel:xxx', 'project:xxx', '人物A的ref', '人物B的ref', 'resource:rd', 'chapter:xxx', 'sha256:...');

-- 故事弧状态（arc_ref 指向 story_arc 资产中的弧线标识）
INSERT INTO resources (id, media_type, content, content_hash) VALUES ('resource:ad', 'text/markdown', CAST(? AS BLOB), ?);
INSERT INTO arc_states (id, project_id, arc_ref, state_resource_id, source_chapter_id, source_content_hash)
VALUES ('arcstate:xxx', 'project:xxx', '弧线ref', 'resource:ad', 'chapter:xxx', 'sha256:...');

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
