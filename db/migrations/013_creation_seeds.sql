-- Task 21: 创作种子非权威入口层
-- 种子层不进 planning_assets（权威资产容器），不进依赖图，不触发 stale 传播。
-- 但有版本与变更留痕（is_active 机制：同一 project 同时只有一个 active 种子）。
-- 注：schema.sql 已含 CREATE TABLE IF NOT EXISTS creation_seeds；本 migration 用 IF NOT EXISTS
-- 保持幂等，使旧库升级时建表、新库（已由 schema.sql 建好）执行时跳过。
CREATE TABLE IF NOT EXISTS creation_seeds (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    protagonist_seed TEXT NOT NULL DEFAULT '',
    world_seed TEXT NOT NULL DEFAULT '',
    hook_seed TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, version),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_creation_seeds_project_active
ON creation_seeds(project_id, is_active);
