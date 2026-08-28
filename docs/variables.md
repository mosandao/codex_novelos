# 变量与配置

## 配置总览

仓库**没有 MCP server 注册，也没有环境变量依赖**：`.codex/config.toml`、`mcp/sqlite-mcp/server.py` 与 `run_sqlite_mcp.*` 启动脚本已全部删除；仓库不读取任何 `NOVELOS_*` 环境变量（那是更早 NovelOS MCP 时代的遗留变量，不要再寻找）。仓库的「配置」即以下文件约定：

| 配置项 | 位置 | 值 / 说明 |
|---|---|---|
| 权威数据库 | `data/novelos-v2.db` | 本地 SQLite 单文件；schema 由 `db/migrations/` 顺序前向迁移管理（migration 016 后 26 表）；任何 schema 变更前先复制备份 |
| 写路径 | 主控 node:sqlite 受控直写 | SQL 模板唯一来源 `.agents/skills/novel-project/sql-reference.md`，落库前对照 `config/schemas/*.json` 自查；`BEGIN IMMEDIATE` + `PRAGMA foreign_keys=ON` 单事务，任一步失败整体回滚零写入；DB 路径按仓库相对约定 `data/novelos-v2.db`，无连接串、无环境变量 |
| 读路径 | 一次性 node:sqlite 只读查询（人类浏览 novels/ 投影） | 直连 db 文件，零配置项 |
| 方法论组装器 | `node scripts/novelos-compose-prompt.mjs` | 配方矩阵权威在 `config/agent-recipes.json`；组装产物存 `data/compositions/` |
| 系统叙事原型 | `config/system_archetypes.json` | 18 个原型；内核取代原型进入创建链后降为参考资料库 |
| 校验 schema | `config/schemas/*.json` | ×18，语言无关资产，落库前主控自查复用 |
| 题材信息包 | `config/genre-packs.json` | 频道×题材数据包的**唯一权威源**（原 `plugin/client/project-wizard-data.js` 双源镜像已随插件退役删除）；`node scripts/test-guardrails.mjs` 守卫每包四字段结构自洽 |
| 创作方法论 | `catalog/skills/` | 只读；manifest 机器门校验命令已随零 Python 退役（语义未 JS 化部分登记 R4 待办，以 `tasks/README.md` 账本为准） |
| 运行时 | Node.js ≥22 | 全局安装即可；脚本用 node:sqlite/crypto，无额外依赖、无虚拟环境 |

## Secret

纯本地 SQLite 不需要 API Key、数据库密码或第三方 Provider Secret。模型认证由所用 harness 产品自身管理，不进入仓库、命令行参数或环境变量。

仓库不包含应用级 `OPENAI_API_KEY`、`OPENAI_MODEL` 或 `[model]` 配置。

## 切换检查

- 仓库中不存在 `.codex/config.toml`、`mcp/sqlite-mcp/`、`run_sqlite_mcp.*`；不要重建任何 MCP 注册。
- 环境中不存在、也不读取已退役的 `NOVELOS_DB_PATH`/`NOVELOS_AGENT_CONTRACT_PATH`/`NOVELOS_SEED_*` 变量。
- 不设置或读取应用级 OpenAI/模型变量。
- 正式数据库备份、恢复演练和 `quick_check` 通过。
