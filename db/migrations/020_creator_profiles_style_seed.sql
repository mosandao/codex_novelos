-- NovelOS R5（裁-11）：creator_profiles ownership 枚举 + 'style_seed'（风格种子库）。
--
-- 背景：kb_author_personas 试点（12-16 条，U6 裁决）以 ownership='style_seed' 落
-- creator_profiles，与 author_kernel（内核层）/user（分身层）同构复用 creator_profiles
-- 全套版本链机制（版本链/双资源链/subject_hash/绑定反查），语义由 ownership 区分——
-- 种子卡是「表达层参照」，不作任何派生的 parent。SQLite 不能 ALTER CHECK 约束，
-- 照 migration 018 模板表重建：CREATE new → INSERT SELECT（id 不变）→ DROP →
-- RENAME → 重建索引。执行时 foreign_keys=OFF（project_creator_bindings 对本表有
-- FK 引用，照 018 同法；creator_profile_versions 的 FK 指向本表 id，INSERT SELECT
-- 保持 id 不变故引用不断）。
--
-- ⚠ prepare-only 纪律（本文件在 R5 准备轮仅为草案，不随本轮执行）：
--   1. 生产库执行前置 = 先备份（口径照裁-10：wal_checkpoint(TRUNCATE) → cp，
--      命令见 tasks/r5-plans/u5-u7-signature-package.md）+ U5 用户裁决放行；
--   2. 本仓库不手工动生产库——执行由主控在用户批准后的受控会话完成；
--   3. 执行后动作 = 从生产库重新导出 db/migrations/schema.sql（红方 F4 / 裁-11，
--      导出步骤见 u5-u7-signature-package.md §schema.sql 再导出）。
-- 现网影响面（2026-08-29 只读实测）：creator_profiles 30 行
--   （26 system_archetype + 4 user）——重建零数据损失；schema_migrations 止于 v18。

-- ============================================================
-- 重建 creator_profiles（ownership CHECK + 'style_seed'）
-- ============================================================

CREATE TABLE creator_profiles_new (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ownership TEXT NOT NULL DEFAULT 'user'
        CHECK (ownership IN ('system_archetype', 'user', 'author_kernel', 'style_seed'))
);

INSERT INTO creator_profiles_new (id, display_name, status, version, created_at, updated_at, ownership)
SELECT id, display_name, status, version, created_at, updated_at, ownership FROM creator_profiles;

DROP TABLE creator_profiles;
ALTER TABLE creator_profiles_new RENAME TO creator_profiles;

CREATE INDEX IF NOT EXISTS idx_creator_profiles_ownership ON creator_profiles(ownership);
