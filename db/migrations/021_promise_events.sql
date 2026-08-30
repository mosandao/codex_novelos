-- 021 · 六账本补流水（R7-T4，修正案 A3；对抗审查 P3-3 成立判处置）
-- 背景：narrative_promises 只有余额（status 三态 open/resolved/broken + source_chapter_id）
-- 没有分录——无 resolution 章位、无事件流，300 章后断线伏笔不可审计。
-- 变更：
--   ① narrative_promises 增加 resolved_chapter_id（收束章位；存量行不回填，照 019 先例——
--      历史已 resolved 行的章位由连续性提取按新规则写入）；
--   ② 新增 promise_events 追加表（一伏笔多事件：plant/progress/twist/resolve/break，
--      形态参照 dreampowers 伏笔场记事件流，只借思想；每行可带 source_content_hash 溯源）。
-- 幂等/回滚：单事务应用，任一步失败整体回滚零写入；应用前先复制库文件备份。

ALTER TABLE narrative_promises ADD COLUMN resolved_chapter_id TEXT REFERENCES chapters(id);

CREATE TABLE promise_events (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    promise_key TEXT NOT NULL,
    chapter_id TEXT,
    event_type TEXT NOT NULL CHECK (event_type IN ('plant', 'progress', 'twist', 'resolve', 'break')),
    note TEXT NOT NULL DEFAULT '',
    source_content_hash TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE SET NULL
);

CREATE INDEX idx_promise_events_key ON promise_events(project_id, promise_key);
