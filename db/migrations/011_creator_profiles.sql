CREATE TABLE creator_profiles (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

CREATE INDEX idx_creator_profile_versions_profile
ON creator_profile_versions(profile_id, revision DESC);

CREATE TABLE project_creator_bindings (
    project_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    profile_version_id TEXT NOT NULL,
    profile_revision INTEGER NOT NULL CHECK (profile_revision > 0),
    subject_hash TEXT NOT NULL CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    ),
    binding_mode TEXT NOT NULL CHECK (binding_mode IN ('reuse', 'derive', 'create')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES creator_profiles(id) ON DELETE RESTRICT,
    FOREIGN KEY (profile_version_id) REFERENCES creator_profile_versions(id) ON DELETE RESTRICT
);

CREATE INDEX idx_project_creator_bindings_profile
ON project_creator_bindings(profile_id, profile_version_id);
