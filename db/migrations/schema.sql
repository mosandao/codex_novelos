-- NovelOS 权威库合并基线（schema v18 终态）。
-- 由 data/novelos-v2.db 的 sqlite_master DDL 只读导出重生成（R2 准备，2026-08-24）：
-- 旧版是迁移链中段快照且缺 004/011/015/018 末端表，无法独立建库。
-- 用法：node:sqlite / sqlite3 直接执行本文件即得与生产结构一致的空库（测试夹具基线）。
-- 增量演进仍走 migrations/002..018；下次 schema 变更后须重新导出本文件。

CREATE TABLE arc_states (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    arc_ref TEXT NOT NULL,
    state_resource_id TEXT NOT NULL,
    source_chapter_id TEXT NOT NULL,
    source_content_hash TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, arc_ref),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (source_chapter_id) REFERENCES chapters(id) ON DELETE RESTRICT,
    FOREIGN KEY (state_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE books (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'archived')),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE chapter_completion_checkpoints (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL UNIQUE,
    source_content_hash TEXT NOT NULL,
    candidate_set_id TEXT NOT NULL,
    review_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status = 'continuity_promoted'),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE RESTRICT,
    FOREIGN KEY (candidate_set_id) REFERENCES continuity_candidate_sets(id) ON DELETE RESTRICT,
    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE RESTRICT
);

CREATE TABLE chapter_facts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_chapter_id TEXT NOT NULL,
    source_content_hash TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    description_resource_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'accepted' CHECK (status IN ('accepted', 'superseded', 'rejected', 'quarantined')),
    superseded_by TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (source_chapter_id) REFERENCES chapters(id) ON DELETE RESTRICT,
    FOREIGN KEY (description_resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    FOREIGN KEY (superseded_by) REFERENCES chapter_facts(id) ON DELETE RESTRICT
);

CREATE TABLE "chapters" (
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

CREATE TABLE "characters" (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role_class TEXT NOT NULL DEFAULT 'secondary'
        CHECK (role_class IN ('main', 'secondary', 'minor')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'peripheral', 'dormant', 'departed', 'transformed', 'dead')),
    description_resource_id TEXT,
    state_json TEXT NOT NULL DEFAULT '{}',
    first_chapter_id TEXT,
    exit_chapter_id TEXT,
    exit_type TEXT
        CHECK (exit_type IS NULL OR exit_type IN
               ('完成型', '迁移型', '转化型', '关系型', '功能转移型', '休眠型', '死亡型')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (description_resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    FOREIGN KEY (first_chapter_id) REFERENCES chapters(id) ON DELETE SET NULL,
    FOREIGN KEY (exit_chapter_id) REFERENCES chapters(id) ON DELETE SET NULL
);

CREATE TABLE continuity_candidate_sets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL,
    source_content_hash TEXT NOT NULL,
    authority_snapshot_json TEXT NOT NULL,
    candidate_resource_id TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    owners_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'working' CHECK (status IN ('working', 'promoted', 'rejected', 'superseded')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (chapter_id, source_content_hash),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE RESTRICT,
    FOREIGN KEY (candidate_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE continuity_update_results (
    id TEXT PRIMARY KEY,
    candidate_set_id TEXT NOT NULL UNIQUE,
    subject_hash TEXT NOT NULL,
    result_resource_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_set_id) REFERENCES continuity_candidate_sets(id) ON DELETE RESTRICT,
    FOREIGN KEY (result_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE creator_profile_versions (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    content_resource_id TEXT NOT NULL,
    subject_hash TEXT NOT NULL CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    ),
    parent_version_id TEXT,
    derivation_resource_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (profile_id, revision),
    FOREIGN KEY (profile_id) REFERENCES creator_profiles(id) ON DELETE RESTRICT,
    FOREIGN KEY (content_resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    FOREIGN KEY (parent_version_id) REFERENCES creator_profile_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (derivation_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE "creator_profiles" (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ownership TEXT NOT NULL DEFAULT 'user'
        CHECK (ownership IN ('system_archetype', 'user', 'author_kernel'))
);

CREATE TABLE expectation_ledgers (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    expectation_key TEXT NOT NULL,
    description_resource_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'met', 'abandoned')),
    source_chapter_id TEXT NOT NULL,
    source_content_hash TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, expectation_key),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (source_chapter_id) REFERENCES chapters(id) ON DELETE RESTRICT,
    FOREIGN KEY (description_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE factions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description_resource_id TEXT,
    state_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (description_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE narrative_promises (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    promise_key TEXT NOT NULL,
    description_resource_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'resolved', 'broken')),
    source_chapter_id TEXT NOT NULL,
    source_content_hash TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, promise_key),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (source_chapter_id) REFERENCES chapters(id) ON DELETE RESTRICT,
    FOREIGN KEY (description_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE planning_asset_dependencies (
    asset_id TEXT NOT NULL,
    upstream_asset_id TEXT NOT NULL,
    upstream_version INTEGER NOT NULL CHECK (upstream_version > 0),
    PRIMARY KEY (asset_id, upstream_asset_id),
    CHECK (asset_id <> upstream_asset_id),
    FOREIGN KEY (asset_id) REFERENCES planning_assets(id) ON DELETE CASCADE,
    FOREIGN KEY (upstream_asset_id) REFERENCES planning_assets(id) ON DELETE RESTRICT
);

CREATE TABLE "planning_assets" (
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

CREATE TABLE "project_creator_bindings" (
    project_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    profile_version_id TEXT NOT NULL,
    profile_revision INTEGER NOT NULL CHECK (profile_revision > 0),
    subject_hash TEXT NOT NULL CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    ),
    binding_mode TEXT NOT NULL
        CHECK (binding_mode IN ('reuse', 'derive', 'create', 'kernel_derive')),
    kernel_version_id TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES creator_profiles(id) ON DELETE RESTRICT,
    FOREIGN KEY (profile_version_id) REFERENCES creator_profile_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (kernel_version_id) REFERENCES creator_profile_versions(id) ON DELETE RESTRICT
);

CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE relationship_states (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    subject_ref TEXT NOT NULL,
    object_ref TEXT NOT NULL,
    state_resource_id TEXT NOT NULL,
    source_chapter_id TEXT NOT NULL,
    source_content_hash TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, subject_ref, object_ref),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (source_chapter_id) REFERENCES chapters(id) ON DELETE RESTRICT,
    FOREIGN KEY (state_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE resources (
    id TEXT PRIMARY KEY,
    media_type TEXT NOT NULL,
    content BLOB NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (content_hash, media_type),
    CHECK (
        substr(content_hash, 1, 7) = 'sha256:'
        AND length(content_hash) = 71
        AND substr(content_hash, 8) NOT GLOB '*[^0-9a-f]*'
    )
);

CREATE TABLE "reviews" (
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

CREATE TABLE rules (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description_resource_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (description_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE timelines (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    label TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    description_resource_id TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (project_id, sequence, label),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (description_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE volumes (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    number INTEGER NOT NULL CHECK (number > 0),
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'active', 'completed', 'archived')),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (book_id, number),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE worlds (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description_resource_id TEXT,
    state_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (description_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE INDEX idx_arcs_project ON arc_states(project_id, arc_ref);

CREATE INDEX idx_books_project ON books(project_id);

CREATE INDEX idx_chapter_facts_project ON chapter_facts(project_id, status, source_chapter_id);

CREATE UNIQUE INDEX idx_chapters_active ON chapters(volume_id, number) WHERE status IN ('draft', 'accepted');

CREATE INDEX idx_chapters_volume ON chapters(volume_id, number);

CREATE INDEX idx_characters_project ON characters(project_id, status);

CREATE INDEX idx_continuity_sets_chapter ON continuity_candidate_sets(chapter_id, source_content_hash);

CREATE INDEX idx_creator_profile_versions_profile
ON creator_profile_versions(profile_id, revision DESC);

CREATE INDEX idx_creator_profiles_ownership ON creator_profiles(ownership);

CREATE INDEX idx_expectations_project ON expectation_ledgers(project_id, status);

CREATE INDEX idx_factions_project ON factions(project_id, name);

CREATE INDEX idx_planning_asset_dependencies_upstream
ON planning_asset_dependencies(upstream_asset_id, asset_id);

CREATE UNIQUE INDEX idx_planning_assets_current ON planning_assets(project_id, asset_type, scope_ref) WHERE status = 'locked';

CREATE INDEX idx_planning_assets_lookup ON planning_assets(project_id, asset_type, scope_ref, revision DESC);

CREATE INDEX idx_project_creator_bindings_kernel
ON project_creator_bindings(kernel_version_id) WHERE kernel_version_id IS NOT NULL;

CREATE INDEX idx_project_creator_bindings_profile
ON project_creator_bindings(profile_id, profile_version_id);

CREATE INDEX idx_promises_project ON narrative_promises(project_id, status);

CREATE INDEX idx_relationships_project ON relationship_states(project_id, subject_ref, object_ref);

CREATE INDEX idx_reviews_subject ON reviews(subject_type, subject_ref);

CREATE INDEX idx_rules_project ON rules(project_id, name);

CREATE INDEX idx_timelines_project ON timelines(project_id, sequence);

CREATE INDEX idx_volumes_book ON volumes(book_id, number);

CREATE INDEX idx_worlds_project ON worlds(project_id, name);
