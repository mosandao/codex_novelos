# NovelOS SQL 操作速查

用 node:sqlite 操作数据库（读=只读查询；写=受控事务直写——本文件即写库模板唯一来源，纪律见 AGENTS.md「数据库访问」）。`?` 是参数占位符。

## 内容存储（resources）

所有正文、规划内容都存在 resources 表。写内容时用 `CAST(? AS BLOB)` 确保 BLOB 存储。

```sql
-- 存内容（正文/规划/JSON）
INSERT INTO resources (id, media_type, content, content_hash)
VALUES ('resource:xxx', 'text/markdown', CAST(? AS BLOB), ?);
-- media_type: 'text/markdown'(正文/规划) 或 'application/json'(结构化)
-- content_hash: 格式 'sha256:'+sha256(内容 UTF-8 字节的 hex)，node:crypto 计算

-- 读内容（自动解码为 UTF-8 文本）
SELECT content FROM resources WHERE id = 'resource:xxx';
```

## 项目 / 书 / 卷 / 章节（CRUD）

```sql
-- 项目（新建项目由主控按「作者签名链」模板单事务落库，禁止零散逐条 INSERT；
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
-- 标 stale（受控 SQL 沿依赖边 UPDATE status='stale'）并重走审查/锁定，
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

-- 章节（创建草稿——仅允许 status='draft'；状态升级按下方接受/重开纪律执行）
INSERT INTO chapters (id, volume_id, number, title, status, content_resource_id, summary, metadata_json, version)
VALUES ('chapter:xxx', 'volume:xxx', 1, '章标题', 'draft', 'resource:xxx', '', '{}', 1);

-- 接受章节（审查通过后；单事务：先核对回执 verdict='approved' 且 subject_ref=该章节，
-- 再执行本 UPDATE 并写 chapters.review_id 机器痕迹；跳审接受禁止）
UPDATE chapters SET status = 'accepted', review_id = 'review:xxx',
    version = version + 1, updated_at = CURRENT_TIMESTAMP
WHERE id = 'chapter:xxx';

-- 重开为 draft（降级操作；重开后改稿必须重审再按上方 SQL 重新接受）
UPDATE chapters SET status = 'draft', version = version + 1, updated_at = CURRENT_TIMESTAMP
WHERE id = 'chapter:xxx';

-- 查询已接受章节
SELECT c.*, r.content FROM chapters c
JOIN resources r ON c.content_resource_id = r.id
WHERE c.status = 'accepted' AND c.volume_id = 'volume:xxx'
ORDER BY c.number;
```

## 作者签名链（项目创建落库——受控事务直写）

onboarding_agent 产出 `creator_derivation_candidate` 后，主控对照 `config/schemas/creator-signature.schema.json` 自查，随后**在单事务内逐条执行以下 SQL**（`BEGIN IMMEDIATE` + `PRAGMA foreign_keys=ON`，任一步失败整体回滚——六表写入没有孤儿）。签名 JSON（schema v2，含 persona，v3 内核派生另带 `kernel_origin`）存 resources；派生记录存第二个 resource，内容固定为：`parent_version_id` + `parent_display_name` + `parent_subject_hash` + `auxiliary_archetypes` + `rationale` + `user_input_snapshot`（**完整用户输入快照** = author_kernel + setup 全文，不得缩略——它是用户原始意图的唯一持久化副本）。

```sql
-- 1. 签名内容（含 persona 的完整签名 JSON）
INSERT INTO resources (id, media_type, content, content_hash)
VALUES ('resource:sig', 'application/json', CAST(? AS BLOB), ?);  -- hash = 'sha256:'+sha256(utf8 hex)，node:crypto 计算

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

落库前自查（INSERT 前必须全部通过）：
- `config/schemas/creator-signature.schema.json` 校验签名（v2 必须含 persona，`blindspots.cannot_write` 非空）
- overrides 字段在 7 个签名字段内且无逐字复制内核 identity 条目（语义继承允许，须从 persona 重新长出）
- `parent_version_id` / `parent_subject_hash` 与库内绑定内核版本一致；`kernel_origin`（如有）与绑定内核一致

## 作者内核链（建核/修订——受控事务直写）

内核（`ownership='author_kernel'`）是跨书持久的根：建核/修订由主控对照 `config/schemas/author-kernel.schema.json` 自查后，按 AGENTS.md「项目创建向导」流程以受控事务直写落库（SQL 结构与作者签名链同型：resources → creator_profiles → creator_profile_versions）。修订在同一 profile 上出新 revision（`parent_version_id` 指向基底版本），growth_log 只追加不删改。内核名册随时经下方「查询内核名册」SQL 实时直查，无任何镜像缓存。

## 人格库指纹（融合前跨批次去重注入）

> **日常路径已固化**：`node scripts/novelos-compose-prompt.mjs --asset fusion` 会自动按量化范围（库 ≤10 全量；>10 最近 10 份 + 全部同 parent）执行本查询并拼进注入文本，主控不再手工跑。本模板留作排查参照。

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
-- 创建候选（仅允许 status='candidate'；锁定/标 stale 模板见下方）
INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status,
    content_resource_id, producer_role, metadata_json, version)
VALUES ('planning:xxx', 'project:xxx', 'direction', 'book', 1, 'candidate',
    'resource:xxx', '方向智能体', '{}', 1);

-- 锁定（审查通过后；单事务：先核对回执 verdict='approved' 且 subject_ref=本资产、直接上游全部 locked——跳审/越序锁定禁止）
UPDATE planning_assets SET status='superseded', updated_at=CURRENT_TIMESTAMP WHERE scope_ref=? AND asset_type=? AND status='locked';  -- 先翻同 scope 旧 locked
UPDATE planning_assets SET status='locked', locked_review_id='review:xxx', updated_at=CURRENT_TIMESTAMP WHERE id='planning:xxx';   -- 再置本行 locked
-- 上述三纪律（核对回执 → 翻旧 → 置新）必须在同一 BEGIN IMMEDIATE 事务内完成
-- 部分唯一索引 idx_planning_assets_current 保证同 scope 同时只有一个 locked

-- 标记 stale（上游变更后；沿 planning_asset_dependencies 依赖边，直接+间接下游全量标）
UPDATE planning_assets SET status='stale', updated_at=CURRENT_TIMESTAMP WHERE id IN (SELECT asset_id FROM planning_asset_dependencies WHERE upstream_asset_id='planning:xxx');

-- 查询当前 locked 资产
SELECT * FROM planning_assets
WHERE project_id = 'project:xxx' AND status = 'locked'
ORDER BY asset_type;

-- 记录上游依赖
INSERT INTO planning_asset_dependencies (asset_id, upstream_asset_id, upstream_version)
VALUES ('planning:downstream', 'planning:upstream', 2);
```

## 审查（reviews）

> 审查回执由主控按下方 INSERT 模板落库；`subject_hash` 取被审对象正文 resource 的 content_hash。
> `reviewer_profile` 必须带身份前缀——`model:<provider:model>`（异构厂商直审）或 `agent:<name>@<model>`（具名审查 agent），匿名裸字符串拒绝落库。

```sql
-- 落回执（审查完成后由主控执行）
INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict,
    findings_json, reviewer_profile, evidence_refs_json)
VALUES ('review:xxx', 'chapter', 'chapter:xxx',
    'sha256:...',  -- 正文 resource 的 content_hash
    'approved',
    '[{"severity":"note","message":"...","evidence_refs":["chapter:xxx"]}]',
    'model:<provider:model>',
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

-- 伏笔流水（021 起，R7-T4：余额之外必留分录——每章收口时为状态发生变化的承诺追加事件行；
-- resolve/break 时同步 UPDATE narrative_promises.status 与 resolved_chapter_id）
INSERT INTO promise_events (id, project_id, promise_key, chapter_id, event_type, note, source_content_hash)
VALUES ('pe:xxx', 'project:xxx', '伏笔键名', 'chapter:xxx', 'progress', '本章推进要点', 'sha256:...');
-- event_type 只接受: plant/progress/twist/resolve/break
-- 收付平衡查询：每章至少兑现一条（close/partial 口径见 story_arc 台账）+ Claremont 系数
SELECT COUNT(*) AS open_count FROM narrative_promises WHERE project_id = ? AND status = 'open';
SELECT promise_key, status, source_chapter_id, resolved_chapter_id FROM narrative_promises WHERE project_id = ?;
SELECT promise_key, event_type, chapter_id, created_at FROM promise_events
WHERE project_id = ? AND promise_key = ? ORDER BY created_at, rowid;

-- 读者期待
INSERT INTO resources (id, media_type, content, content_hash) VALUES ('resource:ed', 'text/markdown', CAST(? AS BLOB), ?);
INSERT INTO expectation_ledgers (id, project_id, expectation_key, description_resource_id, status, source_chapter_id, source_content_hash)
VALUES ('expectation:xxx', 'project:xxx', '期待键名', 'resource:ed', 'open', 'chapter:xxx', 'sha256:...');
-- status 只接受: open/met/abandoned

-- 人物关系（subject_ref/object_ref + 状态存 resource）
-- UNIQUE(project_id, subject_ref, object_ref)：同一人物对再次更新状态必须 UPSERT，纯 INSERT 必撞唯一约束
INSERT INTO resources (id, media_type, content, content_hash) VALUES ('resource:rd', 'text/markdown', CAST(? AS BLOB), ?);
INSERT INTO relationship_states (id, project_id, subject_ref, object_ref, state_resource_id, source_chapter_id, source_content_hash)
VALUES ('rel:xxx', 'project:xxx', '人物A的ref', '人物B的ref', 'resource:rd', 'chapter:xxx', 'sha256:...')
ON CONFLICT (project_id, subject_ref, object_ref) DO UPDATE SET
  state_resource_id = excluded.state_resource_id,
  source_chapter_id = excluded.source_chapter_id,
  source_content_hash = excluded.source_content_hash;

-- 故事弧状态（arc_ref 指向 story_arc 资产中的弧线标识）
-- UNIQUE(project_id, arc_ref)：同一弧线再次更新状态必须 UPSERT，纯 INSERT 必撞唯一约束
INSERT INTO resources (id, media_type, content, content_hash) VALUES ('resource:ad', 'text/markdown', CAST(? AS BLOB), ?);
INSERT INTO arc_states (id, project_id, arc_ref, state_resource_id, source_chapter_id, source_content_hash)
VALUES ('arcstate:xxx', 'project:xxx', '弧线ref', 'resource:ad', 'chapter:xxx', 'sha256:...')
ON CONFLICT (project_id, arc_ref) DO UPDATE SET
  state_resource_id = excluded.state_resource_id,
  source_chapter_id = excluded.source_chapter_id,
  source_content_hash = excluded.source_content_hash;

-- 搜索事实
SELECT cf.*, r.content FROM chapter_facts cf
JOIN resources r ON cf.description_resource_id = r.id
WHERE cf.subject LIKE '%关键词%' OR r.content LIKE '%关键词%';
```

## ID 生成

ID 格式为 `类型:uuid`。用 Node 生成：

```js
import { randomUUID } from 'node:crypto';
console.log(`chapter:${randomUUID()}`);   // chapter:b74aa654-...
console.log(`planning:${randomUUID()}`);  // planning:184b6f38-...
console.log(`review:${randomUUID()}`);    // review:3756c94c-...
console.log(`resource:${randomUUID()}`);  // resource:3bb695f0-...
```

## 写路径纪律（原插件门工具已退役）

| 原门工具 | 退役后纪律 |
|---|---|
| `novelos_gate_entry` | 项目创建 payload 落库前对照 `config/schemas/project-create-request.schema.json`（v3）自查：结构+词表级联+表里互斥+select 模式内核反查 |
| `novelos_kernel_commit` | 建核/修订对照 `config/schemas/author-kernel.schema.json` 自查后，按「作者内核链」受控事务落库 |
| `novelos_project_commit` | 按「作者签名链」六表单事务落库；mismatch 必须用户裁决后才放行 |
| `novelos_register_characters` | 人物注册/状态迁移用受控 SQL 写 characters 表（席位对账 + 近重名 WARN 自查执行） |
| `novelos_propagate_stale` | 沿 planning_asset_dependencies 依赖边 UPDATE status='stale'（模板见「规划资产」） |
| `novelos_delete_project` | 先备份库文件，再显式事务按依赖逆序逐表删（foreign_keys=OFF 执行后恢复） |
| `novelos_review_commit` | 按「审查」INSERT 模板落回执；reviewer_profile 带 model:/agent: 前缀 |
| `novelos_lock_asset` | 按「规划资产」锁定模板：先核对 approved 回执 → 翻旧 locked → 置新 locked |
| `novelos_accept_chapter` | 按「项目 / 书 / 卷 / 章节」接受模板：核对回执 → UPDATE status='accepted' + review_id 留痕 |

原 `dsh-novelos-viewer` 插件 defineTool 门工具已随 `plugin/` 移除退役，机器校验不再存在；上表为「原门工具 → 退役后纪律」映射（主控自查执行，SQL 模板见上文各节）。content_hash 格式 `'sha256:'+sha256(utf8 hex)`，node:crypto 计算。资产语义校验（book_soul 等 validate_* 机器门）已随插件退役，当前对照各 skill 速查表与 `config/schemas/*.json` 自查。

## R7 机器门通道（novelos-gate.mjs——2026-08-29 起关键状态写入优先走门）

上表「自查纪律」中的关键状态写入自 R7 起有机器门通道 `scripts/novelos-gate.mjs`（dry-run 默认，写库须 `--commit`，生产库路径另须 `--allow-production`；GateFail=阻断+零写入，exit 1）：

| 关键状态写入 | 门子命令 | 门强制点（SQL 模板仍是语义权威） |
|---|---|---|
| 回执落库 | `commit-review --receipt <file>` | reviewer_profile 强制 `model:/agent:` 前缀；G2 引文验证 in-process（no_hit/missing/空查回执 FATAL，`--allow-empty` 留痕豁免） |
| 规划资产锁定 | `lock-asset --asset <id> --review <id>` | 封跳审/错绑/错版；同 key 旧 locked 自动翻 superseded；幂等重放仅限同回执 |
| 章节接受 | `accept-chapter --chapter <id> --review <id>` | 同上三封 + 必写 `chapters.review_id`；Claremont 收口 WARN（open 伏笔 >2） |
| stale 传播 | `propagate-stale --asset <id> [--fine]` | coarse 全量 / fine 内容未变不误伤（依赖边版本+content_hash 双比对） |
| 人物登记/状态迁移 | `register-characters --project <id> --roster/--entry/--status-update` | 四规则校验 + 幂等合并不覆盖状态史 + 批内失败整体回滚 |
| 资产语义校验 | `validate-asset --asset <id>` | 七件校验器（book_soul 档位门/世界代价两轴/roster 规模/弧数/卷纲高潮密度等常量逐字），只读自查 |
| 升级用户裁决（开单） | `open-adjudication --project <id> --subject-type <planning\|chapter> --subject-ref <id> --reason <文本> [--rounds <json>]` | subject 存在性+归属反查；同 subject 已 open 拒绝（022 部分唯一索引兜底）；open 期间 lock/accept 门互锁阻断（R8-T2，A5） |
| 用户裁决落定 | `resolve-adjudication --adjudication <id> --resolution <文本>` | open→resolved 终态；resolution 必填；解除互锁 |

项目创建签名链（六表事务）与项目删除仍走上文受控事务模板（主控执行，未见 R7 门覆盖范围）。「连续性」流水查询见该节 promise_events 部分（migration 021）。

## 升级裁决物化（adjudications——R8-T2，A5 TBD 物化）

审查 3 轮未收敛/同因复发/mismatch 升级用户裁决时，**必须过门落一条裁决单**（不可只口头挂起）：

```sql
-- 开单（gate open-adjudication 落库语义；id 格式 adjudication:uuid）
INSERT INTO adjudications (id, project_id, subject_type, subject_ref, reason, rounds_json)
VALUES ('adjudication:uuid', 'project:xxx', 'planning', 'planning:xxx', '3 轮未收敛：<摘要>', '[{"round":1,"blocking":"…"},{"round":2,"blocking":"…"}]');
-- 裁决落定（gate resolve-adjudication 语义；status open→resolved 终态）
UPDATE adjudications SET status='resolved', resolution='<用户裁决结论>', resolved_at=CURRENT_TIMESTAMP WHERE id='adjudication:uuid';
-- 下游可见性查询（composer open_adjudications 槽同口径）
SELECT id, subject_type, subject_ref, reason, rounds_json, created_at
FROM adjudications WHERE project_id = 'project:xxx' AND status = 'open' ORDER BY created_at;
```

互锁语义：subject 存在 open 行时 `lock-asset`/`accept-chapter` GateFail（先裁决后推进）；`commit-review`/`propagate-stale` 不拦。库未应用 022 时互锁静默放行（随迁移生效），open 显式报错。

## M7 对账查询（A8 · R8——per-model 依从性记账，一次性只读）

三指标定义与判读纪律见 `docs/knowledge/metrics.md` M7 节（低于阈值只呈报用户裁决，不自动除名）。模型身份权威=`reviewer_profile` 的 `model:`/`agent:` 前缀（P4-2 机器强制）；无前缀行进「未标记」桶并视为口径违规呈报。

**M7a · per-model FATAL 率（落库成功侧；被门拦未落库者自门输出/组装日志人工归集）**：

```sql
-- 回执落库尝试的成功侧聚合：各模型 verdict 分布与被 G2 复核作废数（findings_json 含 fatal 痕迹时人工复核）
SELECT reviewer_profile,
       COUNT(*)                                        AS receipt_total,
       SUM(CASE WHEN verdict='approved' THEN 1 ELSE 0 END) AS approved_n,
       SUM(CASE WHEN verdict='rejected' THEN 1 ELSE 0 END) AS rejected_n
FROM reviews
WHERE reviewer_profile LIKE 'model:%' OR reviewer_profile LIKE 'agent:%'
GROUP BY reviewer_profile ORDER BY receipt_total DESC;
-- 无前缀行（口径违规桶）：SELECT COUNT(*) FROM reviews WHERE reviewer_profile NOT LIKE 'model:%' AND reviewer_profile NOT LIKE 'agent:%';
```

**M7b · per-model 平均审查轮次（同 subject 收敛所需 review 数）**：

```sql
-- subject 级轮次：approved 前的 review 计数即该轮收敛成本；按模型前缀分列
WITH rounds AS (
  SELECT subject_ref,
         (SELECT COUNT(*) FROM reviews r2
           WHERE r2.subject_ref = r1.subject_ref
             AND (r2.created_at < r1.created_at
                  OR (r2.created_at = r1.created_at AND r2.id <= r1.id))) AS rounds_to_approve,
         r1.reviewer_profile AS approving_model
  FROM reviews r1 WHERE r1.verdict='approved'
)
SELECT approving_model, AVG(rounds_to_approve) AS avg_rounds, COUNT(*) AS subjects
FROM rounds
WHERE approving_model LIKE 'model:%' OR approving_model LIKE 'agent:%'
GROUP BY approving_model;
```

**M7c · per-model deny 率（prescreen 候选证伪，分母口径=M3：候选数不是 finding 数）**：

```sql
-- 逐章 prescreen 候选聚合（json_each 条数级）；deny 以 code 前缀 fpr-deny: 判定（裁-2 过滤 note 二义性）
SELECT c.id AS chapter_id,
       json_extract(je.value, '$.code')          AS code,
       COUNT(*) OVER (PARTITION BY c.id)         AS candidates_per_chapter
FROM chapters c, json_each(COALESCE(json_extract(c.metadata_json, '$.prescreen'), '[]')) je
WHERE json_valid(COALESCE(c.metadata_json, '{}'))
  AND json_extract(je.value, '$.code') IS NOT NULL;
-- 汇总口径：deny 率 = COUNT(code LIKE 'fpr-deny:%') / COUNT(*)（同上结果集二次聚合；confirm=fpr:<ID>）。
-- 写作模型归属：chapters 无模型列时以 metadata_json.model（如有）或组装日志回查，未标记进「未标记」桶。
```
