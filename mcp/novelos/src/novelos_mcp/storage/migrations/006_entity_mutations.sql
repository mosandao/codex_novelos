CREATE TABLE entity_mutations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('character', 'world', 'faction', 'rule', 'timeline')),
    mutation_resource_id TEXT NOT NULL,
    subject_hash TEXT NOT NULL CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    ),
    authority_source_ref TEXT NOT NULL,
    authority_source_hash TEXT NOT NULL,
    authority_source_version INTEGER NOT NULL CHECK (authority_source_version > 0),
    target_id TEXT,
    target_expected_version INTEGER,
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'applied')),
    applied_review_id TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (mutation_resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    FOREIGN KEY (applied_review_id) REFERENCES reviews(id) ON DELETE RESTRICT
);

CREATE INDEX idx_entity_mutations_project
ON entity_mutations(project_id, entity_type, created_at DESC);
