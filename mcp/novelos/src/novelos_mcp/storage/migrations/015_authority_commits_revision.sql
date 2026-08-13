-- 放宽 authority_commits 唯一约束：允许同一章节多次 accept（revise 后重新接受）。
--
-- 原 UNIQUE (action, subject_ref) 约束使每个权威动作对每个 subject 只能记录一次。
-- chapter.revise 把 accepted 章节重开为 draft 后，update_draft 改变 subject_hash，
-- 重新 accept 需要记录新的 authority_commit，但 (action='chapter.accept', subject_ref=chapter_id)
-- 会与首次 accept 冲突。
--
-- 改为 UNIQUE (action, subject_ref, subject_hash)：同一章节不同内容版本的 accept
-- 各占一条记录，审计链完整保留每次 accept 的 trace/review/hash 证据。
-- 对 planning.lock 等其他 action 无影响（它们每次 subject_hash 也不同）。
--
-- _apply_migration 已在 foreign_keys=OFF 下执行（migration 014 引入）。

CREATE TABLE authority_commits_new (
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
    UNIQUE (action, subject_ref, subject_hash),
    FOREIGN KEY (trace_id) REFERENCES traces(id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE RESTRICT,
    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE RESTRICT,
    CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    )
);

INSERT INTO authority_commits_new SELECT * FROM authority_commits;

DROP TABLE authority_commits;

ALTER TABLE authority_commits_new RENAME TO authority_commits;

CREATE INDEX IF NOT EXISTS idx_authority_commits_trace
ON authority_commits(trace_id, created_at, id);

CREATE INDEX IF NOT EXISTS idx_authority_commits_project
ON authority_commits(project_id, action, subject_ref);
