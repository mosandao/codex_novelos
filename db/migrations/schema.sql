PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resources (
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

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS books (
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

CREATE TABLE IF NOT EXISTS volumes (
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

CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    volume_id TEXT NOT NULL,
    number INTEGER NOT NULL CHECK (number > 0),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'accepted', 'superseded')),
    content_resource_id TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (volume_id) REFERENCES volumes(id) ON DELETE CASCADE,
    FOREIGN KEY (content_resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    )
);

-- 人物注册表（migration 018 重建）：主要人物 roster + 次要角色动态登记 + 状态七态。
CREATE TABLE IF NOT EXISTS characters (
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

CREATE TABLE IF NOT EXISTS worlds (
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

CREATE TABLE IF NOT EXISTS factions (
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

CREATE TABLE IF NOT EXISTS rules (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description_resource_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (description_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS timelines (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    label TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    description_resource_id TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, sequence, label),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (description_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    subject_type TEXT NOT NULL,
    subject_ref TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('approved', 'rejected')),
    findings_json TEXT NOT NULL DEFAULT '[]',
    reviewer_profile TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    )
);

CREATE TABLE IF NOT EXISTS chapter_facts (
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

CREATE TABLE IF NOT EXISTS continuity_candidate_sets (
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

CREATE TABLE IF NOT EXISTS continuity_update_results (
    id TEXT PRIMARY KEY,
    candidate_set_id TEXT NOT NULL UNIQUE,
    subject_hash TEXT NOT NULL,
    result_resource_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_set_id) REFERENCES continuity_candidate_sets(id) ON DELETE RESTRICT,
    FOREIGN KEY (result_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS chapter_completion_checkpoints (
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

CREATE TABLE IF NOT EXISTS narrative_promises (
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

CREATE TABLE IF NOT EXISTS expectation_ledgers (
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

CREATE TABLE IF NOT EXISTS relationship_states (
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

CREATE TABLE IF NOT EXISTS arc_states (
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

CREATE INDEX IF NOT EXISTS idx_books_project ON books(project_id);
CREATE INDEX IF NOT EXISTS idx_volumes_book ON volumes(book_id, number);
CREATE INDEX IF NOT EXISTS idx_chapters_volume ON chapters(volume_id, number);
CREATE UNIQUE INDEX IF NOT EXISTS idx_chapters_active
ON chapters(volume_id, number)
WHERE status IN ('draft', 'accepted');
CREATE INDEX IF NOT EXISTS idx_characters_project ON characters(project_id, name);
CREATE INDEX IF NOT EXISTS idx_worlds_project ON worlds(project_id, name);
CREATE INDEX IF NOT EXISTS idx_factions_project ON factions(project_id, name);
CREATE INDEX IF NOT EXISTS idx_rules_project ON rules(project_id, name);
CREATE INDEX IF NOT EXISTS idx_timelines_project ON timelines(project_id, sequence);
CREATE INDEX IF NOT EXISTS idx_reviews_subject ON reviews(subject_type, subject_ref, subject_hash);
CREATE INDEX IF NOT EXISTS idx_chapter_facts_project ON chapter_facts(project_id, status, source_chapter_id);
CREATE INDEX IF NOT EXISTS idx_continuity_sets_chapter ON continuity_candidate_sets(chapter_id, source_content_hash);
CREATE INDEX IF NOT EXISTS idx_promises_project ON narrative_promises(project_id, status);
CREATE INDEX IF NOT EXISTS idx_expectations_project ON expectation_ledgers(project_id, status);
CREATE INDEX IF NOT EXISTS idx_relationships_project ON relationship_states(project_id, subject_ref, object_ref);
CREATE INDEX IF NOT EXISTS idx_arcs_project ON arc_states(project_id, arc_ref);
