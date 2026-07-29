# 变量与配置

## 生产 MCP

| 名称 | 使用者 | 来源/默认值 | 风险与要求 |
|---|---|---|---|
| `NOVELOS_DB_PATH` | `novelos_mcp.server` | `data/novelos.db`；生产脚本显式改为 `data/novelos-v2.db` | 必须是受备份保护的本地路径；不得指向 legacy 来源 |
| `NOVELOS_CATALOG_PATH` | `novelos_mcp.server` | 无；生产脚本显式使用 `catalog/skills` | 只读内容；Catalog Hash 和来源测试必须通过 |
| `NOVELOS_AGENT_CONTRACT_PATH` | `novelos_mcp.server` | 自动发现；生产脚本显式使用 `config/agents.yaml` | 角色和工具白名单的权威配置，修改必须通过契约测试 |
| `NOVELOS_SEED_DB_PATH` | `novelos_mcp.server` | 生产 runner 固定为 `mcp/novelos/resources/seed.db` | runner 禁止环境变量覆盖；测试可直接向 server 传入合成路径 |
| `NOVELOS_SEED_INVENTORY_PATH` | `novelos_mcp.server` | 生产 runner 固定为 `mcp/novelos/resources/seed-inventory.json` | 与 seed 成对校验；runner 禁止环境变量覆盖 |
| `PYTHONPATH` | MCP 启动脚本 | `mcp/novelos/src` | 只能指向新 MCP 包，不能混入旧 `src/novelos` Runtime |

## Codex 项目配置

| 配置 | 文件 | 风险与要求 |
|---|---|---|
| MCP command/args | `.codex/config.toml` | 只注册一个 `novelos` Server，并调用 `scripts/run_novelos_mcp.sh` |
| startup/tool timeout | `.codex/config.toml` | 超时必须允许数据库初始化，但不能掩盖挂起进程 |
| Agent role contract | `config/agents.yaml` | 不属于 Codex 官方 Agent 声明；由 NovelOS MCP 读取和验证 |

## Secret

纯本地 SQLite V1 不需要 OpenAI API Key、数据库密码或第三方 Provider Secret。Codex 的模型认证由 Codex 产品自身管理，不进入仓库、MCP 参数或 NovelOS 环境变量。

仓库不包含应用级 `OPENAI_API_KEY`、`OPENAI_MODEL` 或 `[model]` 配置。仓库没有客户端构建，因此不存在把服务端 Secret 打包到浏览器的问题。

## 切换检查

- `.codex/config.toml` 只引用 `scripts/run_novelos_mcp.sh`。
- 启动脚本显式传入正式 DB、Catalog 和 Agent contract。
- 环境中不存在 `NOVELOS_SEED_DB_PATH` 和 `NOVELOS_SEED_INVENTORY_PATH` 覆盖；生产 runner 使用固定授权资源。
- 不设置或读取应用级 OpenAI 变量。
- 正式数据库备份、恢复演练和 `quick_check` 通过。
