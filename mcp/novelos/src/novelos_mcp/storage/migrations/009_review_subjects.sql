CREATE TABLE review_subjects (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    subject_kind TEXT NOT NULL CHECK (subject_kind IN ('agent_quality_evaluation')),
    reviewer_profile TEXT NOT NULL,
    content_resource_id TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    producer_run_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE RESTRICT,
    FOREIGN KEY (content_resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    )
);

CREATE INDEX idx_review_subjects_trace
ON review_subjects(trace_id, created_at, id);

ALTER TABLE reviews ADD COLUMN assessment_resource_id TEXT
REFERENCES resources(id) ON DELETE RESTRICT;
