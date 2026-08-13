CREATE TABLE authority_commits (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN (
        'planning.lock',
        'planning.cross_check.approve',
        'chapter.accept',
        'entity.commit',
        'continuity.promote'
    )),
    subject_type TEXT NOT NULL CHECK (subject_type IN (
        'planning_asset',
        'planning_cross_check',
        'chapter',
        'entity_mutation',
        'continuity_candidate_set'
    )),
    subject_ref TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    review_id TEXT NOT NULL,
    result_ref TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (action, subject_ref),
    FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE RESTRICT,
    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE RESTRICT,
    CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    )
);

CREATE INDEX idx_authority_commits_trace
ON authority_commits(trace_id, created_at, id);

CREATE INDEX idx_authority_commits_project
ON authority_commits(project_id, action, subject_ref);
