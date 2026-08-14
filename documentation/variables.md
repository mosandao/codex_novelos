# 变量与配置

## SQLite MCP 配置

数据库操作唯一入口是 SQLite MCP（`mcp/sqlite-mcp/server.py`），仅暴露 `execute_sql` 工具。它由 `.codex/config.toml` 注册、`scripts/run_sqlite_mcp.sh` 启动。

| 配置项 | 位置 | 值 / 说明 |
|---|---|---|
| MCP server 注册 | `.codex/config.toml` → `[mcp_servers.sqlite]` | `command = "bash"`，`args = ["scripts/run_sqlite_mcp.sh"]` |
| 沙箱模式 | `.codex/config.toml` | `sandbox_mode = "danger-full-access"`（本地单用户，脚本需读写数据库与文件） |
| startup 超时 | `.codex/config.toml` | `startup_timeout_sec = 10` |
| tool 超时 | `.codex/config.toml` | `tool_timeout_sec = 30` |
| 数据库路径 | `scripts/run_sqlite_mcp.sh` 显式传入 | `--db-path data/novelos-v2.db`（必须是受备份保护的本地路径） |

启动脚本内容固定为 `.venv/bin/python mcp/sqlite-mcp/server.py --db-path data/novelos-v2.db`，不读取 `NOVELOS_*` 类环境变量（那是已退役的 NovelOS MCP 时代的变量，当前架构不存在）。

## Codex 项目配置

| 配置 | 文件 | 风险与要求 |
|---|---|---|
| MCP command/args | `.codex/config.toml` | 只注册一个 `sqlite` Server，调用 `scripts/run_sqlite_mcp.sh`；不得重新注册已退役的 NovelOS MCP（门禁表已 DROP，重启会崩溃） |
| startup/tool timeout | `.codex/config.toml` | 超时必须允许数据库初始化，但不能掩盖挂起进程 |
| 创作方法论 | `catalog/skills/` | 只读；Catalog manifest 校验必须通过（`scripts/build_catalog_manifest.py --check`） |
| 系统叙事原型 | `config/system_archetypes.json` | 18 个原型，项目创建向导与 onboarding_agent 读取 |
| 签名/灵魂 schema | `config/schemas/` | `creator-signature.schema.json`、`book-soul.schema.json`；落库前 jsonschema 校验 |
| `config/agents.yaml` | 历史留档 | NovelOS MCP 时代的 Agent 角色定义，**无脚本依赖**；不再作为运行时配置 |

## Secret

纯本地 SQLite V1 不需要 OpenAI API Key、数据库密码或第三方 Provider Secret。Codex 的模型认证由 Codex 产品自身管理，不进入仓库、MCP 参数或环境变量。

仓库不包含应用级 `OPENAI_API_KEY`、`OPENAI_MODEL` 或 `[model]` 配置。仓库没有客户端构建，因此不存在把服务端 Secret 打包到浏览器的问题。

## 切换检查

- `.codex/config.toml` 只引用 `scripts/run_sqlite_mcp.sh`，只注册 `sqlite` Server。
- 启动脚本显式传入正式 DB 路径 `data/novelos-v2.db`。
- 环境中不存在已退役的 `NOVELOS_DB_PATH`/`NOVELOS_AGENT_CONTRACT_PATH`/`NOVELOS_SEED_*` 变量（当前架构不读取它们）。
- 不设置或读取应用级 OpenAI 变量。
- 正式数据库备份、恢复演练和 `quick_check` 通过。
