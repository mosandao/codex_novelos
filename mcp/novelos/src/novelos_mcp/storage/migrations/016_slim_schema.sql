-- NovelOS 轻量化：删除门禁基础设施表 + 废弃 subject_hash + 清理悬空列。
--
-- 背景：Task 26 完全替代 NovelOS MCP。89 个工具中 55% 是纯治理开销。
-- 9 张门禁表对正文质量零贡献。核心业务表不反向引用门禁表，DROP 零数据损失。
--
-- subject_hash 有 CHECK 约束，不能直接 DROP COLUMN，用表重建法（参照 migration 014）。
-- _apply_migration 已在 foreign_keys=OFF 下执行本脚本，INSERT SELECT 保持 id 不变。

-- ============================================================
-- 1. DROP 门禁基础设施表（9 张）
-- ============================================================

DROP TABLE IF EXISTS trace_steps;
DROP TABLE IF EXISTS traces;
DROP TABLE IF EXISTS agent_runs;
DROP TABLE IF EXISTS authority_commits;
DROP TABLE IF EXISTS review_subjects;
DROP TABLE IF EXISTS planning_cross_checks;
DROP TABLE IF EXISTS entity_mutations;
DROP TABLE IF EXISTS legacy_imports;
DROP TABLE IF EXISTS legacy_quarantine;

-- ============================================================
-- 2. 重建 chapters（去掉 subject_hash CHECK + producer_run_id）
-- ============================================================

CREATE TABLE chapters_new (
    id TEXT PRIMARY KEY,
    volume_id TEXT NOT NULL,
    number INTEGER NOT NULL CHECK (number > 0),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'accepted', 'superseded')),
    content_resource_id TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (volume_id) REFERENCES volumes(id) ON DELETE CASCADE,
    FOREIGN KEY (content_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

INSERT INTO chapters_new (id, volume_id, number, title, status, content_resource_id, summary, metadata_json, version, created_at, updated_at)
SELECT id, volume_id, number, title, status, content_resource_id, summary, metadata_json, version, created_at, updated_at FROM chapters;

DROP TABLE chapters;
ALTER TABLE chapters_new RENAME TO chapters;

CREATE INDEX IF NOT EXISTS idx_chapters_volume ON chapters(volume_id, number);
CREATE UNIQUE INDEX IF NOT EXISTS idx_chapters_active ON chapters(volume_id, number) WHERE status IN ('draft', 'accepted');

-- ============================================================
-- 3. 重建 planning_assets（去掉 subject_hash CHECK + producer_run_id + cross_check_id）
--    保留 locked_review_id FK
-- ============================================================

CREATE TABLE planning_assets_new (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (asset_type IN (
        'direction', 'architecture', 'strategy', 'character_contract',
        'world_contract', 'story_arc', 'volume_outline', 'chapter_plan'
    )),
    scope_ref TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'locked', 'stale', 'superseded')),
    content_resource_id TEXT NOT NULL,
    producer_role TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    locked_review_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, asset_type, scope_ref, revision),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (content_resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    FOREIGN KEY (locked_review_id) REFERENCES reviews(id) ON DELETE RESTRICT
);

INSERT INTO planning_assets_new (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role, metadata_json, version, locked_review_id, created_at, updated_at)
SELECT id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role, metadata_json, version, locked_review_id, created_at, updated_at FROM planning_assets;

DROP TABLE planning_assets;
ALTER TABLE planning_assets_new RENAME TO planning_assets;

CREATE UNIQUE INDEX IF NOT EXISTS idx_planning_assets_current ON planning_assets(project_id, asset_type, scope_ref) WHERE status = 'locked';
CREATE INDEX IF NOT EXISTS idx_planning_assets_lookup ON planning_assets(project_id, asset_type, scope_ref, revision DESC);

-- ============================================================
-- 4. 重建 reviews（去掉 reviewer_run_id + assessment_resource_id + subject_hash CHECK）
-- ============================================================

CREATE TABLE reviews_new (
    id TEXT PRIMARY KEY,
    subject_type TEXT NOT NULL,
    subject_ref TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('approved', 'rejected')),
    findings_json TEXT NOT NULL DEFAULT '[]',
    reviewer_profile TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    evidence_refs_json TEXT NOT NULL DEFAULT '[]'
);

INSERT INTO reviews_new (id, subject_type, subject_ref, subject_hash, verdict, findings_json, reviewer_profile, created_at, metadata_json, evidence_refs_json)
SELECT id, subject_type, subject_ref, subject_hash, verdict, findings_json, reviewer_profile, created_at, metadata_json, evidence_refs_json FROM reviews;

DROP TABLE reviews;
ALTER TABLE reviews_new RENAME TO reviews;

CREATE INDEX IF NOT EXISTS idx_reviews_subject ON reviews(subject_type, subject_ref);
