# NovelOS

NovelOS 是面向长篇小说创作的纯 Codex 系统。Codex 作为唯一长期存在的 Main Agent；项目 Skill 提供业务方法，临时 Agent 负责隔离推理，统一 `novelos` MCP 负责全部权威读写、Hash、版本、Review、事务和 Trace。

## 当前状态

默认 `.codex/config.toml` 已切换到统一 `novelos` MCP，旧 Python Agent Runtime 已删除。完整 70-case Agent 质量实验按用户决定延期；在实验完成前，Writer 仅用于完整章节或长场景，Context Builder 仅用于跨卷、多线、事实冲突或上下文溢出，不宣称两者已取得质量优势。

权威进度见 [tasks/README.md](./tasks/README.md)，不得以本 README 代替任务状态。

## 目录

```text
.agents/skills/       6 个顶层 Codex 业务 Skill
catalog/skills/       细粒度 Skill Catalog
config/agents.yaml    Agent 角色与工具契约
mcp/novelos/          统一 FastMCP Server
data/novelos-v2.db    正式目标数据库（本地忽略）
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

## 文档

- [系统架构](./documentation/architecture.md)
- [关键流程](./documentation/flows.md)
- [权限矩阵](./documentation/permissions.md)
- [变量与配置](./documentation/variables.md)
- [测试覆盖](./documentation/tests.md)
- [Agent 与自动化](./documentation/automation.md)
