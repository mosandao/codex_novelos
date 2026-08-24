# NovelOS × DeepSeek Harness（DSH）兼容适配

本文记录 NovelOS 在 DeepSeek Harness（DSH）下运行的适配层。

## 结论

NovelOS 的核心资产（SQLite schema、`scripts/novelos_*.py`、`catalog/skills/` 方法论、`ui/project-wizard.html`、projection 渲染）与模型/harness 无关，可运行在 DSH 上。需要适配的是三层胶水：

1. SQLite MCP 注册（DSH 用 `@deepseek-ai/dsh-mcp-client`，不读 `.codex/config.toml`）。
2. Python 运行环境（纯标准库 MCP server + Windows 启动方式，无第三方依赖）。
3. AGENTS.md 中的 Codex 工具名措辞（`Agent`/`open`/`AskUserQuestion`/`Read` → DSH 等价工具）。

## DSH 已原生支持的 NovelOS 资产

- `@deepseek-ai/dsh-skill-filesystem` 自动发现项目根 `.agents/skills`（rank 200）与 `~/.agents/skills`、`.dsh/skills` 等；`SKILL.md` 需含 `name`/`description` frontmatter（NovelOS 已满足）。
- `@deepseek-ai/dsh-agent-instructions` 自动加载 `AGENTS.md` / `CLAUDE.md`（及 `.local.md` 变体）。
- `tool-subagent` / `tool-subagent-control` / `tool-subagent-report` / `tool-subagent-fork` 可承接 NovelOS 的 sub agent 工作流。

## SQLite MCP 注册（已写入 DSH profile）

已在 `~/.dsh/profiles/web/cordis.patch.yml` 增加 `mcp-novelos-sqlite` 条目：

```yaml
- insert:
    - id: mcp-novelos-sqlite
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        transport: stdio
        serverName: sqlite
        command: 'cmd.exe'
        args:
          - '/c'
          - 'scripts\run_sqlite_mcp.cmd'
        cwd: 'D:/github/codex_novelos'
        failOnStartupError: false
        toolCallTimeoutMs: 60000
```

注册后模型侧工具名为 `mcp__sqlite__execute_sql`。

## Windows 启动器

`scripts/run_sqlite_mcp.cmd`：

- 若存在 `.venv\Scripts\python.exe` 则优先使用；
- 否则回退到 PATH 上的 `python`；
- 固定以仓库根为 cwd，启动 `mcp/sqlite-mcp/server.py --db-path data/novelos-v2.db`。

`scripts/run_sqlite_mcp.sh` 保留给 Codex/WSL 使用。

## Python 依赖

`mcp/sqlite-mcp/server.py` 已改为**纯标准库实现**（JSON-RPC 2.0 over stdio），无第三方运行时依赖，不需要 pip 安装 `mcp` / `pydantic`。只需系统有 Python 3.10+ 即可。

- Windows/DSH：`scripts/run_sqlite_mcp.cmd` 自动优先使用 `.venv\Scripts\python.exe`，否则回退到 PATH 上的 `python`。
- Codex/WSL：`scripts/run_sqlite_mcp.sh` 仍用 `.venv/bin/python`（可把 `.venv` 换成任意可用 Python 3.10+）。

重启 DSH（或热重载 mcp-client 插件）后即可加载 `mcp__sqlite__execute_sql`。

## AGENTS.md 工具名映射

| Codex 措辞 | DSH 等价 | 已适配位置 |
|---|---|---|
| `Agent` 工具（创建 sub agent） | `tool-subagent`（配套 `tool-subagent-*`） | `AGENTS.md` 路由顺序 |
| `open ui/project-wizard.html` | 文件/浏览器打开工具 | `AGENTS.md` 项目创建向导 |
| `AskUserQuestion` | `ask-user` | `AGENTS.md` 项目创建向导 |
| `Read` | 文件读取工具（`read`/`fs` 系） | `AGENTS.md` 方法论/创建流程 |

Skill 调用约定：NovelOS 提示词里的 `$novel-memory`、`$novel-writing` 等符号在 DSH 中对应 `tool-skill` 或 `@skill-name` 调用方式；如 DSH 侧解析不到，可改成直接加载对应 `catalog/skills/<分类>/<目录名>/prompt.md`。

## 验证

1. 确认 server 可启动（纯标准库，无需安装依赖）：
   ```bash
   python -c "import ast; ast.parse(open('mcp/sqlite-mcp/server.py', encoding='utf-8').read()); print('syntax ok')"
   ```
2. 重启 DSH（或重载 mcp-client），在工具列表看到 `mcp__sqlite__execute_sql`。
3. 手工调用：
   ```sql
   SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;
   ```
4. 跑一次 `novel-project` skill 冒烟。

## 回滚

- 从 `~/.dsh/profiles/web/cordis.patch.yml` 删除 `mcp-novelos-sqlite` insert 条目（或把 `name` 改为不存在的包名并重启）即可关闭 DSH 侧 SQLite MCP；Codex 侧不受影响。
- 仓库侧变更：`mcp/sqlite-mcp/server.py`（FastMCP → 纯标准库 MCP）、新增 `scripts/run_sqlite_mcp.cmd`、`requirements-mcp.txt`、`docs/dsh-compatibility.md`；AGENTS.md 的 DSH 措辞为纯文档适配，可安全保留。
