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
-- 项目（新建项目由 scripts/novelos_create_project.py 单事务落库，禁止手工逐条 INSERT；
-- 此模板仅示意 metadata_json 结构。setup v2 快照是频道/平台/规模/题材/表里基调/美学/
-- 题材信息包/创作资料的权威存储；setup_schema_version 标记快照契约版本，后续阶段经 SQL 读取，不靠会话记忆）
INSERT INTO projects (id, name, description, version, metadata_json)
VALUES ('project:xxx', '书名', '一句话定位', 1,
    json('{"setup_schema_version": 2, "setup": {"channel": "女频", "platform": "晋江",
        "platform_traits": {...}, "scale": "...", "primary_genre": "...",
        "secondary_directions": [...], "emotional_surface": [...], "emotional_core": "...",
        "tonal_contrast": null, "aesthetic_styles": [...], "genre_profile": {...},
        "reference_material": "..."}}'));
SELECT * FROM projects;
UPDATE projects SET description = ? WHERE id = 'project:xxx';

-- 读项目 setup 快照（方向/策略/世界观/写作等阶段的标准输入）
SELECT json_extract(metadata_json, '$.setup') AS setup FROM projects WHERE id = 'project:xxx';

-- setup 变更（连载中改频道/平台/基调等——属上游变更：改后必须把全部 locked 规划资产
-- 标 stale（scripts/novelos_propagate_stale.py 或手动 UPDATE status='stale'）并重走审查/锁定，
-- 见 AGENTS.md「setup 变更通路」。禁止静默改 setup 后继续用旧规划写作）
UPDATE projects
SET metadata_json = json_set(metadata_json, '$.setup', json('{"channel": ..., ...}')),
    updated_at = CURRENT_TIMESTAMP
WHERE id = 'project:xxx';

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

## 作者签名链（项目创建落库——固化脚本执行）

onboarding_agent 产出 `creator_derivation_candidate` 后，主控运行 `scripts/novelos_create_project.py --payload <向导JSON> --candidate <候选JSON>` 一步完成校验门与落库，**不手工逐条执行以下 SQL**（模板仅作结构说明与排查参照）。落库在单事务内执行（`BEGIN IMMEDIATE` + `PRAGMA foreign_keys=ON`，任一步失败整体回滚——六表写入没有孤儿）。签名 JSON（schema v2，含 persona，v3 内核派生另带 `kernel_origin`）存 resources；派生记录存第二个 resource，内容固定为：`parent_version_id` + `parent_display_name` + `parent_subject_hash` + `auxiliary_archetypes` + `rationale` + `user_input_snapshot`（**完整用户输入快照** = author_kernel + setup 全文，不得缩略——它是用户原始意图的唯一持久化副本）。

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

-- 4. profile version（parent 指向内核版本，双资源链）
INSERT INTO creator_profile_versions (id, profile_id, revision, content_resource_id,
    subject_hash, parent_version_id, derivation_resource_id)
VALUES ('creator-profile-version:xxx', 'creator-profile:xxx', 1,
    'resource:sig', 'sha256:...',          -- 签名 JSON 的 content_hash
    'creator-profile-version:<内核版本id>', -- parent = 绑定的作者内核版本
    'resource:deriv');

-- 5. 项目 + 绑定（metadata_json 写 setup 快照，结构见上方项目模板）
INSERT INTO projects (id, name, description, version, metadata_json)
VALUES ('project:xxx', '书名', '描述', 1, json('{"setup_schema_version": 3, "setup": {...}}'));
INSERT INTO project_creator_bindings (project_id, profile_id, profile_version_id,
    profile_revision, subject_hash, binding_mode, kernel_version_id)
VALUES ('project:xxx', 'creator-profile:xxx', 'creator-profile-version:xxx', 1,
    'sha256:...', 'kernel_derive', 'creator-profile-version:<内核版本id>');

-- 查询项目绑定的完整签名（含 persona）
SELECT v.id, v.revision, v.subject_hash, CAST(r.content AS TEXT) AS signature_json
FROM project_creator_bindings b
JOIN creator_profile_versions v ON v.id = b.profile_version_id
JOIN resources r ON r.id = v.content_resource_id
WHERE b.project_id = 'project:xxx';

-- 查询项目绑定的作者内核全文（内核层溯源；组装器 kernel_full 槽同源查询）
SELECT v.id, v.revision, v.subject_hash, cp.display_name, CAST(r.content AS TEXT) AS kernel_json
FROM project_creator_bindings b
JOIN creator_profile_versions v ON v.id = b.kernel_version_id
JOIN creator_profiles cp ON cp.id = v.profile_id
JOIN resources r ON r.id = v.content_resource_id
WHERE b.project_id = 'project:xxx';

-- 查询内核名册（active 内核每 profile 取最高 revision——roster 导出同源）
SELECT v.id AS kernel_version_id, v.subject_hash, v.revision, cp.display_name
FROM creator_profile_versions v
JOIN creator_profiles cp ON cp.id = v.profile_id
WHERE cp.ownership = 'author_kernel' AND cp.status = 'active'
  AND v.revision = (SELECT MAX(v2.revision) FROM creator_profile_versions v2
                    WHERE v2.profile_id = v.profile_id);

-- 内核陈旧检查：绑定旧版内核的项目（内核出新 revision 后待裁决是否重派生）
SELECT b.project_id, b.kernel_version_id, b.profile_version_id
FROM project_creator_bindings b
JOIN creator_profile_versions bound ON bound.id = b.kernel_version_id
WHERE b.binding_mode = 'kernel_derive'
  AND bound.revision < (SELECT MAX(v2.revision) FROM creator_profile_versions v2
                        WHERE v2.profile_id = bound.profile_id);
```

落库校验门（INSERT 前必须全部通过）：
- `config/schemas/creator-signature.schema.json` 校验签名（v2 必须含 persona，`blindspots.cannot_write` 非空）
- overrides 字段在 7 个签名字段内且无逐字复制内核 identity 条目（语义继承允许，须从 persona 重新长出）
- `parent_version_id` / `parent_subject_hash` 与库内绑定内核版本一致；`kernel_origin`（如有）与绑定内核一致

## 作者内核链（建核/修订——固化脚本执行）

内核（`ownership='author_kernel'`）是跨书持久的根：建核/修订走 `scripts/novelos_create_project.py --payload <向导JSON> --kernel-candidate <内核候选JSON> [--emit-payload <缝合路径>]`（独立修订用 `--kernel-revise <revise载荷>`），**禁止手工 INSERT**。修订在同一 profile 上出新 revision（`parent_version_id` 指向基底版本），growth_log 只追加不删改。建核/修订后重跑 `scripts/novelos_export_kernel_roster.py` 刷新向导名册镜像。

## 人格库指纹（融合前跨批次去重注入）

> **日常路径已固化**：`scripts/novelos_compose_prompt.py --asset fusion` 会自动按量化范围（库 ≤10 全量；>10 最近 10 份 + 全部同 parent）执行本查询并拼进注入文本，主控不再手工跑。本模板留作排查参照。

注入 onboarding_agent 前查询已派生人格的指纹摘要（`existing_persona_fingerprints`），供跨批次去重校验——道具结构/烙印事件/张力形态/主题×频道组合不得与库中雷同。人格库为空（查询无结果）时省略此输入。

```sql
SELECT cp.display_name,
       json_extract(cast(r.content as text), '$.persona.anchors.five_dimensions.life_trajectory') AS life_trajectory,
       json_extract(cast(r.content as text), '$.persona.anchors.five_dimensions.career_track')    AS career_track,
       json_extract(cast(r.content as text), '$.persona.anchors.trait_profile')                  AS trait_profile,
       json_extract(cast(r.content as text), '$.persona.anchors.inner_tension')                  AS inner_tension,
       json_extract(cast(r.content as text), '$.persona.anchors.theme_orientation.dominant')     AS theme_dominant
FROM creator_profile_versions v
JOIN creator_profiles cp ON cp.id = v.profile_id
JOIN resources r ON r.id = v.content_resource_id
WHERE v.parent_version_id IS NOT NULL
ORDER BY v.created_at;
```

trait_profile / inner_tension / life_trajectory 原文注入即可（agent 按结构指纹比对，不需要主控预摘要）。注入时称其为「跨批次比对基准人格」——指纹清单包含**全部历史派生人格**（含已被 rebind 换下但保留在库的），它们都是比对基准；不要说「待替换的旧人格」（会误导 agent 与下游把历史人格理解为已废弃）。

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
