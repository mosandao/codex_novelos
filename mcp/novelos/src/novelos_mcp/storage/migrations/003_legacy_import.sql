ALTER TABLE rules ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE timelines ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE reviews ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';

CREATE TABLE legacy_imports (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    source_hash TEXT NOT NULL UNIQUE,
    source_schema TEXT NOT NULL,
    report_json TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE legacy_quarantine (
    id TEXT PRIMARY KEY,
    import_id TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    payload_resource_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (import_id, source_table, source_id),
    FOREIGN KEY (import_id) REFERENCES legacy_imports(id) ON DELETE CASCADE,
    FOREIGN KEY (payload_resource_id) REFERENCES resources(id) ON DELETE RESTRICT
);

CREATE INDEX idx_legacy_quarantine_import ON legacy_quarantine(import_id, source_table);
