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

## 验证

```bash
PYTHONWARNINGS='error::ResourceWarning' .venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python scripts/build_migration_manifest.py --output-dir tasks/migration --check
.venv/bin/python scripts/build_catalog_manifest.py --check
.venv/bin/python scripts/build_agent_quality_dataset.py --check
.venv/bin/python scripts/build_seed_inventory.py --check
.venv/bin/python scripts/build_seed_inventory.py --production --check
.venv/bin/python scripts/backup_novelos_database.py --check
.venv/bin/python scripts/export_novelos_data.py --check
.venv/bin/python scripts/build_migration_summary.py --check
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/check_cutover_readiness.py --check
.venv/bin/python scripts/check_cutover_plan.py --check
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 用户展示

用户展示采用按小说项目生成的 Markdown 文件夹，SQLite 仍是唯一权威数据源。`规划/` 与 `正文/` 展示当前权威版本；`创作约束/` 展示项目绑定的精确作者签名和 locked Direction 的本书创作灵魂；`候选/` 提供候选诊断视图；`产出/` 保留候选、草稿、失效/替代版本和已完成 Agent 原始产出；`档案/` 展示已锁定规划的生产、独立审查和锁定凭据。投影目录可以删除和重建，直接修改其中的文件不会回写数据库。该能力的实施与验收记录在 [Task 06](./tasks/06_user_project_projection.md) 和 [Task 08](./tasks/08_author_signature_and_book_soul.md)，不提供独立 HTTP Web 应用。

## 项目创建向导

`project.wizard.render` 提供一个 MCP Apps HTML 向导资源 `ui://novelos/project-wizard-v3.html`。在支持 MCP Apps 的 Codex 宿主中调用该工具后，用户填写表单，页面通过 `project.wizard.submit` 校验并原子创建项目与作者签名精确版本绑定，随后自动刷新默认 `novels/<项目目录>/` 投影。

向导先要求在 `reuse`、`derive`、`create` 中选择作者签名：复用绑定已有精确 revision/Hash；派生从已有精确版本创建新 Profile 并只保存显式差异；新建创建首个版本。随后使用固定的频道（男频、女频、全向、出版、剧本）、目标平台（起点、番茄、晋江、七猫）、四档作品规模和 14 个一级题材。二级方向随一级题材切换，每个题材提供 18 个静态、LLM 预生成候选；不会在表单提交时调用 LLM，也不提供自定义选项、知乎盐选或自定义字数。主情绪基调可以多选，美学风格最多选择两项，用户创作资料为最多 10,000 字的可选多行文本。

表单结果保存为项目 `metadata.project_setup`：`creation_context` 包含频道、平台、规模、题材、二级方向和资料，`taxonomy` 包含情绪与美学偏好，`creator_selection` 记录绑定模式。主控智能体必须读取这些约束和返回的 `creator_binding.constraint_ref`，再启动正式 Trace 并将其交给方向智能体；方向候选形成该项目独有的 `book_soul`，向导本身不生成、锁定或提交任何规划资产。直接用 `file://.../project-wizard.html` 打开只能预览页面和静态题材联动，因没有 MCP Apps 通信桥，提交会被禁用。

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
