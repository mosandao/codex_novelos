CREATE TABLE traces (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    operation TEXT NOT NULL,
    subject_ref TEXT,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE trace_steps (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    step_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    input_refs_json TEXT NOT NULL DEFAULT '[]',
    output_refs_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (trace_id, sequence),
    FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE CASCADE
);

CREATE INDEX idx_trace_steps_trace ON trace_steps(trace_id, sequence);
