# NovelOS

NovelOS 是面向长篇小说创作的纯 Codex 系统。Codex 作为唯一长期存在的 主控智能体；项目 Skill 提供业务方法，临时 Agent 负责隔离推理，统一 `novelos` MCP 负责全部权威读写、Hash、版本、Review、事务和 Trace。

## 当前状态

默认 `.codex/config.toml` 已切换到统一 `novelos` MCP，旧 Python Agent Runtime 已删除。完整 70-case Agent 质量实验按用户决定延期；在实验完成前，Writer 仅用于完整章节或长场景，上下文构建智能体 仅用于跨卷、多线、事实冲突或上下文溢出，不宣称两者已取得质量优势。

权威进度见 [tasks/README.md](./tasks/README.md)，不得以本 README 代替任务状态。

## 目录

```text
.agents/skills/       6 个顶层 Codex 业务 Skill
catalog/skills/       细粒度 Skill Catalog
config/agents.yaml    Agent 角色与工具契约
mcp/novelos/          统一 FastMCP Server
data/novelos-v2.db    正式目标数据库（本地忽略）
novels/               用户可读项目文件夹（可重建投影，含全部产出档案，本地忽略）
documentation/        稳定架构、流程、权限、变量和测试文档
tasks/                实施计划、迁移证据和未决门禁
```

## 安装

要求 Python 3.11 或更高版本。

```bash
python3 -m venv .venv
.venv/bin/pip install -e mcp/novelos
```

统一 MCP 的生产启动入口是：

```text
scripts/run_novelos_mcp.sh
```

该脚本供 Codex stdio MCP 配置调用，不是交互式命令。它显式使用 `data/novelos-v2.db`、`catalog/skills`、`config/agents.yaml` 和已授权的只读 seed；seed 必须匹配固定 inventory，且生产 runner 拒绝环境变量替换。

`NovelOSService` 从 `novelos_mcp.service` 导入，实际由 `mcp/novelos/src/novelos_mcp/service/__init__.py` 聚合 8 个领域 Mixin 和共享 `_ServiceInternals`。原 `service.py` 已移除；外部导入、构造签名和 MCP 工具契约保持兼容。Review Profile 名以 `config/agents.yaml` 的 `review_profile_routes` 为唯一注册表，默认采用 lenient 声明性门禁，可通过同文件的 `runtime.enforcement` 切换 strict 行为。

## 验证

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q lib scripts tests catalog config
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/build_catalog_manifest.py --check
```

## 用户展示

用户展示采用按小说项目生成的 Markdown 文件夹，SQLite 仍是唯一权威数据源。`规划/` 与 `正文/` 展示当前权威版本；`创作约束/` 展示项目绑定的精确作者签名和 locked Direction 的本书创作灵魂；`大纲/` 展示卷纲与章纲；`连续性/` 展示事实、承诺、关系等账本。投影由 `scripts/novelos_render_projection.py`（裸 sqlite3）渲染，可删除和重建，直接修改其中的文件不会回写数据库。不提供独立 HTTP Web 应用。

## 项目创建向导

默认入口是可直接打开的本地页面 `ui/project-wizard.html`。本地页面不直接写数据库，只生成 `novelos.project.create.v1` JSON；用户将 JSON 发回后，主控智能体按 `selected_archetypes` 数量选择签名融合路径：单原型直接调用 `scripts/novelos_reconcile.py` 确定性融合（`parent_source:"scored"`）；多原型（≥2）先创建临时 `onboarding_agent` sub agent 做 LLM 深度融合，再把 Agent 判定的 parent 与完整融合签名传给 `novelos_reconcile.py`（`--fused-parent-version-id` + `--fused-signature`，`parent_source:"fused"`）。两条路径最后都由主控智能体用 SQL INSERT 创建 projects + creator_profiles + project_creator_bindings。

V3 新向导只允许 `derive`，不得提交 `reuse` 或 `create`；历史绑定仍可读取。页面使用固定频道（男频、女频、全向、出版、剧本）、目标平台（起点、番茄、晋江、七猫）、四档作品规模和 14 个一级题材。二级方向随一级题材切换，每个题材提供 18 个静态、LLM 预生成候选；落库事务本身不调用 LLM，LLM 只在多原型融合时由 `onboarding_agent` 在 Codex run 内运行；也不提供自定义选项、知乎盐选或自定义字数。主情绪基调可以多选，美学风格最多两项，用户创作资料为最多 10,000 字的可选多行文本。页面按约束确定性推荐三个系统叙事原型，用户确认继承项并编辑本书最小差异。

表单结果保存为项目 `metadata.project_setup`：`creation_context` 包含频道、平台、规模、题材、二级方向和资料，`taxonomy` 包含情绪与美学偏好，`creator_selection` 记录绑定模式。主控智能体必须读取这些约束和返回的 `creator_binding.constraint_ref`，再启动正式 Trace 并将其交给方向智能体；方向候选形成该项目独有的 `book_soul`，向导本身不生成、锁定或提交任何规划资产。直接用 `file://.../project-wizard.html` 打开可以完整填写并生成 JSON，但不会声称项目已经创建。

Creator Profile 是用户拥有的跨项目不可变版本配置，不是常驻 Agent。Profile 后续修订不会让旧项目漂移；显式 rebind 会把当前 Direction 及全部后代标记为 `stale`，保留旧版本与 Trace 审计，并且不会自动重生成。Writer 只读取当前精确作者签名、locked Direction、POV 和局部风格引用，不自行决定作者思想。

## 删除项目

`project.delete` 只适用于尚无 `authority_commits` 且没有运行中 Trace 的项目。调用时必须提供当前 `expected_version`；服务端会验证投影目录的 `manifest.json` 确属该项目后才删除派生目录，再级联删除项目业务数据。完成的 Trace 和 Agent 审计记录会保留但不再关联该项目；已有权威提交的项目不能物理删除。

## 文档

- [系统架构](./documentation/architecture.md)
- [关键流程](./documentation/flows.md)
- [权限矩阵](./documentation/permissions.md)
- [变量与配置](./documentation/variables.md)
- [测试覆盖](./documentation/tests.md)
- [Agent 与自动化](./documentation/automation.md)
