# NovelOS

NovelOS 是面向长篇小说创作的纯 Codex 系统。Codex 作为唯一长期存在的 **主控智能体**；项目 Skill 提供业务方法，临时 sub agent 负责隔离推理，SQLite MCP（`execute_sql`）是数据库唯一入口，确定性算法由 `scripts/novelos_*.py` 承担，项目创建的原型融合由引导融合智能体（onboarding_agent）承接。

## 当前状态

NovelOS MCP（89 工具 + 门禁基础设施）已彻底删除。数据库操作通过 SQLite MCP 的 `execute_sql` 工具完成，确定性算法由 `scripts/novelos_*.py` 承担，项目创建的原型融合由引导融合智能体（onboarding_agent）承接。续写流程：`$novel-memory` 取上下文 → `$novel-writing` 起草 → `$novel-review` 审查 → SQL 接受 → `$novel-continuity` 提取连续性。

权威进度见 [tasks/README.md](./tasks/README.md)，不得以本 README 代替任务状态。

## 目录

```text
.agents/skills/       6 个顶层 Codex 业务 Skill（novel-project/planning/memory/writing/review/continuity）
catalog/skills/       细粒度创作方法论 Catalog（planning/writing/review/continuity/craft/expansions）
config/agents.yaml    【历史留档】NovelOS MCP 时代的 Agent 角色定义，无脚本依赖
config/system_archetypes.json   18 个系统叙事原型
mcp/sqlite-mcp/       极薄 SQLite MCP Server（仅暴露 execute_sql）
scripts/              确定性脚本（novelos_*.py）+ MCP 启动脚本
data/novelos-v2.db    正式目标数据库（本地忽略）
db/migrations/        数据库 schema 迁移留档
novels/               用户可读项目文件夹投影（可重建，本地忽略）
ui/                   项目创建向导（project-wizard.html）
documentation/        稳定架构、流程、权限、变量和测试文档
tasks/                实施计划、迁移证据和未决工作
```

## 安装

要求 Python 3.11 或更高版本。

```bash
python3 -m venv .venv
.venv/bin/pip install mcp   # MCP SDK，供 mcp/sqlite-mcp/server.py（FastMCP）
```

SQLite MCP 由 `.codex/config.toml` 注册，启动入口：

```text
scripts/run_sqlite_mcp.sh   # 执行 .venv/bin/python mcp/sqlite-mcp/server.py --db-path data/novelos-v2.db
```

该脚本供 Codex stdio MCP 配置调用，不是交互式命令。它只暴露一个 `execute_sql` 工具，直接对 `data/novelos-v2.db` 执行 SQL——主控与 sub agent 用 SQL 直接读写核心业务表，不再有领域工具层或门禁层。

## 验证

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q scripts tests catalog config
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/build_catalog_manifest.py --check
```

## 用户展示

用户展示采用按小说项目生成的 Markdown 文件夹，SQLite 仍是唯一权威数据源。`规划/` 展示当前 locked 规划资产（人物契约按「## 人物档案」结构拆成 `人物契约/` 目录：总览 + 每人物一份），`正文/` 展示 accepted 章节，`创作约束/` 展示作者签名与本书创作灵魂，`大纲/` 展示卷纲与章纲，`连续性/` 展示事实、承诺、关系等账本。投影由 `scripts/novelos_render_projection.py`（裸 sqlite3、零 MCP 依赖）渲染，可删除和重建，直接修改其中的文件不会回写数据库。不提供独立 HTTP Web 应用。

## 项目创建向导

默认入口是可直接打开的本地页面 `ui/project-wizard.html`。本地页面不直接写数据库，只生成 `novelos.project.create.v2` JSON（频道级联定位 + 表里基调 + platform_traits/genre_profile 快照）；用户将 JSON 发回后，主控创建临时 **引导融合智能体（onboarding_agent）** sub agent，注入 `selected_archetypes` + `user_persona_hints` + `project_setup`（v2）+ `config/system_archetypes.json`，由 agent 按先立人再落规做融合，产出 `creator_derivation_candidate`。主控用 jsonschema（`config/schemas/creator-signature.schema.json`）校验签名合规 + `scripts/novelos_hash.py` 算 hash 后，用 SQL INSERT 创建 projects（metadata_json 写入 setup v2 快照）+ creator_profiles + creator_profile_versions + project_creator_bindings。

V3 新向导只允许 `derive`，不得提交 `reuse` 或 `create`；历史绑定仍可读取。页面使用固定频道（男频、女频、全向、出版、剧本）、目标平台（起点、番茄、晋江、七猫）、四档作品规模和一级题材。二级方向随一级题材切换，每个题材提供静态预生成候选；落库事务本身不调用 LLM，LLM 只在多原型融合时由 `onboarding_agent` 在 Codex run 内运行；也不提供自定义选项、知乎盐选或自定义字数。主情绪基调可以多选，美学风格最多两项，用户创作资料为最多 10,000 字的可选多行文本。页面按约束确定性推荐三个系统叙事原型，用户确认继承项并编辑本书最小差异。

表单结果保存为项目 `metadata.project_setup`。主控智能体读取这些约束和 `creator_binding.constraint_ref`，启动方向智能体生成该项目独有的 `book_soul`；向导本身不生成、锁定或提交任何规划资产。直接用 `file://.../project-wizard.html` 打开可以完整填写并生成 JSON，但不会声称项目已经创建。

Creator Profile 是用户拥有的跨项目不可变版本配置，不是常驻 Agent。Profile 后续修订不会让旧项目漂移；显式 rebind 会把当前 Direction 及全部后代标记为 `stale`，不自动重生成。Writer 只读取当前精确作者签名、locked Direction、POV 和局部风格引用，不自行决定作者思想。

## 删除项目

由确定性脚本 `scripts/novelos_delete_project.py` 完成（不调用 LLM）。建议先 `--dry-run` 调查范围，可选 `--backup` 备份数据库；脚本在 `foreign_keys=OFF` 下按依赖逆序删除项目全部业务数据（projects/books/volumes/chapters/planning_assets/实体/连续性/reviews/项目专属 resources），保护共享的 creator_profile 系统原型资源，用 `foreign_keys=ON` 复验完整性，并按 `manifest.json` 的 `project_id` 删除对应投影目录。详见 [关键流程·删除项目](./documentation/flows.md)。

## 文档

- [系统架构](./documentation/architecture.md)
- [关键流程](./documentation/flows.md)
- [权限矩阵](./documentation/permissions.md)
- [变量与配置](./documentation/variables.md)
- [测试覆盖](./documentation/tests.md)
- [Agent 与自动化](./documentation/automation.md)
