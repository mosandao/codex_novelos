CREATE TABLE agent_runs (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    context_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'timed_out')),
    input_bindings_json TEXT NOT NULL,
    input_refs_json TEXT NOT NULL,
    output_type TEXT,
    output_resource_id TEXT,
    result_resource_id TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE,
    FOREIGN KEY (output_resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    FOREIGN KEY (result_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE INDEX idx_agent_runs_trace ON agent_runs(trace_id, created_at, id);

ALTER TABLE planning_assets ADD COLUMN producer_run_id TEXT;
CREATE UNIQUE INDEX idx_planning_assets_producer_run
ON planning_assets(producer_run_id) WHERE producer_run_id IS NOT NULL;

ALTER TABLE chapters ADD COLUMN producer_run_id TEXT;

ALTER TABLE reviews ADD COLUMN reviewer_run_id TEXT;
CREATE UNIQUE INDEX idx_reviews_reviewer_run
ON reviews(reviewer_run_id) WHERE reviewer_run_id IS NOT NULL;

CREATE TABLE planning_cross_checks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    character_asset_id TEXT NOT NULL,
    character_version INTEGER NOT NULL CHECK (character_version > 0),
    character_hash TEXT NOT NULL,
    world_asset_id TEXT NOT NULL,
    world_version INTEGER NOT NULL CHECK (world_version > 0),
    world_hash TEXT NOT NULL,
    content_resource_id TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    review_id TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (character_asset_id, character_version, world_asset_id, world_version),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (character_asset_id) REFERENCES planning_assets(id) ON DELETE RESTRICT,
    FOREIGN KEY (world_asset_id) REFERENCES planning_assets(id) ON DELETE RESTRICT,
    FOREIGN KEY (content_resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE RESTRICT
);

ALTER TABLE planning_assets ADD COLUMN cross_check_id TEXT;
