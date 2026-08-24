# 变量与配置

> ⚠️ 零 Python 过渡期版本（重组于本轮）：写路径门暂存 legacy-python/，R2 交付后本文档随 JS 门收敛。路线图见 ../tasks/README.md。

## 过渡期配置总览

零 Python 演进期**没有 MCP server 注册，也没有环境变量依赖**：`.codex/config.toml`、`mcp/sqlite-mcp/server.py` 与 `run_sqlite_mcp.*` 启动脚本已全部删除；仓库不读取任何 `NOVELOS_*` 环境变量（那是更早 NovelOS MCP 时代的遗留变量，不要再寻找）。过渡期的「配置」即以下文件约定：

| 配置项 | 位置 | 值 / 说明 |
|---|---|---|
| 权威数据库 | `data/novelos-v2.db` | 本地 SQLite 单文件；schema 由 `db/migrations/` 顺序前向迁移管理（migration 016 后 26 表）；任何 schema 变更前先复制备份 |
| 写路径校验门 | `legacy-python/scripts/novelos_create_project.py` | jsonschema 门（消费 `config/schemas/*.json`）+ `BEGIN IMMEDIATE` 单事务落库；DB 路径按仓库相对约定 `data/novelos-v2.db`，无连接串、无环境变量 |
| 读路径 | `dsh-novelos-viewer` 面板（sql.js 只读，R1 待建）或一次性 node:sqlite 查询 | 直连 db 字节/文件，零配置项 |
| 方法论组装器 | `legacy-python/scripts/novelos_compose_prompt.py` | 配方矩阵权威在 `config/agent-recipes.json`；组装产物存 `data/compositions/` |
| 系统叙事原型 | `config/system_archetypes.json` | 18 个原型；内核取代原型进入创建链后降为参考资料库 |
| 校验 schema | `config/schemas/*.json` | ×18，语言无关资产，R2 后由 ajv 原样复用 |
| 题材信息包 | `config/genre-packs.json` | 向导与组装器消费的频道×题材数据包 |
| 创作方法论 | `catalog/skills/` | 只读；manifest 校验须通过（`python legacy-python/scripts/build_catalog_manifest.py --check`） |
| Python 解释器 | 仓库根 `.venv\Scripts\python.exe` | 由 `py -3.10 -m venv .venv` 重建（装 jsonschema+pyyaml）；全局 Python 是 3.15.0a7 alpha，rpds DLL 不兼容不可用；过渡期运行 py 门专用，不得新增 .py |

## Secret

纯本地 SQLite 不需要 API Key、数据库密码或第三方 Provider Secret。模型认证由所用 harness 产品自身管理，不进入仓库、命令行参数或环境变量。

仓库不包含应用级 `OPENAI_API_KEY`、`OPENAI_MODEL` 或 `[model]` 配置。

## 切换检查

- 仓库中不存在 `.codex/config.toml`、`mcp/sqlite-mcp/`、`run_sqlite_mcp.*`；不要重建任何 MCP 注册。
- 环境中不存在、也不读取已退役的 `NOVELOS_DB_PATH`/`NOVELOS_AGENT_CONTRACT_PATH`/`NOVELOS_SEED_*` 变量。
- 不设置或读取应用级 OpenAI/模型变量。
- 正式数据库备份、恢复演练和 `quick_check` 通过。
