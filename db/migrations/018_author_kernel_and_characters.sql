-- NovelOS Task 30：作者内核双层架构 + 人物注册表。
--
-- 背景：用户裁决「作者内核跨题材一致，每本书从内核派生分身」。内核不建新表，
-- 复用 creator_profiles 全套机制（版本链/双资源链/subject_hash/指纹去重/绑定表），
-- 仅扩展 ownership 枚举增加 'author_kernel'。每书分身的
-- creator_profile_versions.parent_version_id 指向内核版本（自引用 FK 天然成立）。
-- characters 表自建库以来无写入路径（死表），本次重建为「人物注册表」：
-- 主要人物全量设计的 roster 锚点 + 次要角色动态登记 + 人物状态（活跃/退场/死亡）
-- 连续性账本的宿主。三表均含 CHECK 约束变更，SQLite 不能 ALTER，用表重建法
-- （参照 migration 014/016）。执行时 foreign_keys=OFF，INSERT SELECT 保持 id 不变。
-- 现网数据：creator_profiles 30 行（26 system_archetype + 4 user）、
-- bindings 1 行、characters 0 行——重建零数据损失。

-- ============================================================
-- 1. 重建 creator_profiles（ownership + 'author_kernel'）
-- ============================================================

CREATE TABLE creator_profiles_new (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ownership TEXT NOT NULL DEFAULT 'user'
        CHECK (ownership IN ('system_archetype', 'user', 'author_kernel'))
);

INSERT INTO creator_profiles_new (id, display_name, status, version, created_at, updated_at, ownership)
SELECT id, display_name, status, version, created_at, updated_at, ownership FROM creator_profiles;

DROP TABLE creator_profiles;
ALTER TABLE creator_profiles_new RENAME TO creator_profiles;

CREATE INDEX IF NOT EXISTS idx_creator_profiles_ownership ON creator_profiles(ownership);

-- ============================================================
-- 2. 重建 project_creator_bindings（+ kernel_version_id + binding_mode 'kernel_derive'）
--    kernel_version_id 指向内核版本（分身的 parent），供「项目用哪个内核」直查
--    与内核修订后的跨项目陈旧检查；旧项目（原型直连派生）保持 NULL。
-- ============================================================

CREATE TABLE project_creator_bindings_new (
    project_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    profile_version_id TEXT NOT NULL,
    profile_revision INTEGER NOT NULL CHECK (profile_revision > 0),
    subject_hash TEXT NOT NULL CHECK (
        substr(subject_hash, 1, 7) = 'sha256:'
        AND length(subject_hash) = 71
        AND substr(subject_hash, 8) NOT GLOB '*[^0-9a-f]*'
    ),
    binding_mode TEXT NOT NULL
        CHECK (binding_mode IN ('reuse', 'derive', 'create', 'kernel_derive')),
    kernel_version_id TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES creator_profiles(id) ON DELETE RESTRICT,
    FOREIGN KEY (profile_version_id) REFERENCES creator_profile_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (kernel_version_id) REFERENCES creator_profile_versions(id) ON DELETE RESTRICT
);

INSERT INTO project_creator_bindings_new
    (project_id, profile_id, profile_version_id, profile_revision, subject_hash,
     binding_mode, kernel_version_id, version, created_at, updated_at)
SELECT project_id, profile_id, profile_version_id, profile_revision, subject_hash,
       binding_mode, NULL, version, created_at, updated_at
FROM project_creator_bindings;

DROP TABLE project_creator_bindings;
ALTER TABLE project_creator_bindings_new RENAME TO project_creator_bindings;

CREATE INDEX IF NOT EXISTS idx_project_creator_bindings_profile
ON project_creator_bindings(profile_id, profile_version_id);
CREATE INDEX IF NOT EXISTS idx_project_creator_bindings_kernel
ON project_creator_bindings(kernel_version_id) WHERE kernel_version_id IS NOT NULL;

-- ============================================================
-- 3. 重建 characters（死表复活为人物注册表）
--    role_class：main（契约全量设计）/ secondary（执行卡预登记的复用配角）/ minor（一次性）。
--    status 七态对齐退场方法论：active 活跃 / peripheral 外围 / dormant 休眠 /
--    departed 离开 / transformed 转化 / dead 死亡（不可逆，同时留 chapter_facts 证据）。
--    exit_type 七型退场方式；state_json 存自由补充（债务清算、回归条件等）。
-- ============================================================

CREATE TABLE characters_new (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role_class TEXT NOT NULL DEFAULT 'secondary'
        CHECK (role_class IN ('main', 'secondary', 'minor')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'peripheral', 'dormant', 'departed', 'transformed', 'dead')),
    description_resource_id TEXT,
    state_json TEXT NOT NULL DEFAULT '{}',
    first_chapter_id TEXT,
    exit_chapter_id TEXT,
    exit_type TEXT
        CHECK (exit_type IS NULL OR exit_type IN
               ('完成型', '迁移型', '转化型', '关系型', '功能转移型', '休眠型', '死亡型')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (description_resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    FOREIGN KEY (first_chapter_id) REFERENCES chapters(id) ON DELETE SET NULL,
    FOREIGN KEY (exit_chapter_id) REFERENCES chapters(id) ON DELETE SET NULL
);

INSERT INTO characters_new
    (id, project_id, name, role_class, status, description_resource_id, state_json,
     version, created_at, updated_at)
SELECT id, project_id, name, 'secondary', 'active', description_resource_id, state_json,
       version, created_at, updated_at
FROM characters;

DROP TABLE characters;
ALTER TABLE characters_new RENAME TO characters;

CREATE INDEX IF NOT EXISTS idx_characters_project ON characters(project_id, status);
