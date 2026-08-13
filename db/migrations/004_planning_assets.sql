CREATE TABLE planning_assets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (asset_type IN (
        'direction',
        'architecture',
        'strategy',
        'character_contract',
        'world_contract',
        'story_arc',
        'volume_outline',
        'chapter_plan'
    )),
    scope_ref TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'locked', 'stale', 'superseded')),
    content_resource_id TEXT NOT NULL,
    subject_hash TEXT NOT NULL CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    ),
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

CREATE UNIQUE INDEX idx_planning_assets_current
ON planning_assets(project_id, asset_type, scope_ref)
WHERE status = 'locked';

CREATE INDEX idx_planning_assets_lookup
ON planning_assets(project_id, asset_type, scope_ref, revision DESC);

CREATE TABLE planning_asset_dependencies (
    asset_id TEXT NOT NULL,
    upstream_asset_id TEXT NOT NULL,
    upstream_version INTEGER NOT NULL CHECK (upstream_version > 0),
    PRIMARY KEY (asset_id, upstream_asset_id),
    CHECK (asset_id <> upstream_asset_id),
    FOREIGN KEY (asset_id) REFERENCES planning_assets(id) ON DELETE CASCADE,
    FOREIGN KEY (upstream_asset_id) REFERENCES planning_assets(id) ON DELETE RESTRICT
);

CREATE INDEX idx_planning_asset_dependencies_upstream
ON planning_asset_dependencies(upstream_asset_id, asset_id);
