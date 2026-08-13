-- 释放 superseded 章节的 (volume_id, number) 槽位，支持重写已接受章节。
--
-- 原 chapters 表的 UNIQUE (volume_id, number) 是状态无关的表级约束，
-- superseded 行仍占用槽位，导致 create_chapter_draft 同号报 conflict。
-- 改为部分唯一索引：仅 draft/accepted 互斥，superseded 不占位。
-- 对齐 planning_assets 的部分唯一索引模式（idx_planning_assets_current WHERE status='locked'）。
--
-- SQLite 不支持 ALTER TABLE DROP CONSTRAINT，用表重建法。
-- _apply_migration 已在 foreign_keys=OFF 下执行本脚本，INSERT SELECT * 保持 id 不变，
-- 子表（chapter_facts/continuity_candidate_sets 等）的 FK 引用不会断。

CREATE TABLE chapters_new (
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
    producer_run_id TEXT,
    FOREIGN KEY (volume_id) REFERENCES volumes(id) ON DELETE CASCADE,
    FOREIGN KEY (content_resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    )
);

INSERT INTO chapters_new SELECT * FROM chapters;

DROP TABLE chapters;

ALTER TABLE chapters_new RENAME TO chapters;

-- 重建非唯一索引（DROP TABLE 已删除原 idx_chapters_volume）
CREATE INDEX IF NOT EXISTS idx_chapters_volume ON chapters(volume_id, number);

-- 新部分唯一索引：仅 draft/accepted 互斥，superseded 释放槽位
CREATE UNIQUE INDEX IF NOT EXISTS idx_chapters_active
ON chapters(volume_id, number)
WHERE status IN ('draft', 'accepted');
