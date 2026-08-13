# Task 25：SQLite MCP 接线 + POC + 桥接脚本

## 状态

`DONE`（SQLite MCP server + POC 验证 + 5 个桥接脚本全部落地，验证通过）

## 背景

NovelOS MCP 的 89 个工具中，55% 是纯治理开销（trace/agent_run/authority_commit/二次落盘），在单人 LLM 创作场景下收益极低。决定完全替代——用 main agent + sub agent + SQLite MCP 直接操作数据库。

本 Task 是第一步：**纯增量**，不停用 NovelOS MCP、不碰数据库 schema。只加 SQLite MCP 作为第二条数据库访问路径，验证它能否独立完成全部创作操作。

### 决策（已确认）

| 决策点 | 选定方案 | 否决理由 |
|---|---|---|
| SQLite MCP 实现 | **自建极薄 FastMCP**（1 个 execute_sql 工具） | mcp-server-sqlite 有 MCP SDK 版本兼容问题 |
| 确定性算法 | **保留 mcp/novelos/src，脚本 import** | 提取为独立脚本需搬 500+ 行依赖链 |
| subject_hash | **废弃**（Task 26 处理） | 新架构不做门禁锚点 |
| 原 Task 25（标准补齐） | **→ Task 27，靠后** | 在重流程下补标准收益被吃掉 |
| 原 Task 26（warning 闭环） | **取消** | 新架构下 SELECT 可查 |

## 目标 / 优化

### 优化 1：自建极薄 SQLite MCP Server

**文件**：`mcp/sqlite-mcp/server.py` + `scripts/run_sqlite_mcp.sh`

一个 `execute_sql(sql, params)` 工具，直接对 NovelOS 数据库执行 SQL：
- SELECT → `{"rows": [...], "count": N}`（BLOB 列自动解码为 UTF-8）
- INSERT/UPDATE/DELETE → `{"rowcount": N}`
- 错误 → `{"error": "..."}`（不抛异常）
- 外键约束启用（`PRAGMA foreign_keys = ON`）

`.codex/config.toml` 新增 `[mcp_servers.sqlite]` 注册。NovelOS MCP 保留不动。

### 优化 2：stale 传播脚本

**文件**：`scripts/novelos_propagate_stale.py`

原来 NovelOS MCP 在上游资产修订时自动标记下游 stale。砍掉后用脚本替代：查 `planning_asset_dependencies` 依赖图，递归 UPDATE 下游 SET status='stale'。附 `--check` 干跑模式。不调 LLM。

### 优化 3：确定性脚本桥接（import 方式）

保留 mcp/novelos/src 代码原地不动。需要确定性算法时用 CLI 包装脚本 import：

| 脚本 | 功能 | 来源 |
|---|---|---|
| `scripts/novelos_hash.py` | content_hash（sha256:前缀） | `hashing.py`，3 行 |
| `scripts/novelos_validate_book_soul.py` | book_soul schema 校验 | `creative_contracts.py` 或 jsonschema |
| `scripts/novelos_reconcile.py` | 多原型确定性融合 | `creators.py` reconcile_project_wizard_archetypes |
| `scripts/novelos_render_projection.py` | 项目投影渲染 | `projection.py` ProjectionEngine |

## 改动文件

| 文件 | 变更 |
|---|---|
| `mcp/sqlite-mcp/server.py` | 新建：极薄 SQLite MCP（execute_sql 工具） |
| `scripts/run_sqlite_mcp.sh` | 新建：MCP 启动脚本 |
| `scripts/novelos_hash.py` | 新建：hash CLI |
| `scripts/novelos_validate_book_soul.py` | 新建：book_soul 校验 CLI |
| `scripts/novelos_reconcile.py` | 新建：reconcile CLI 包装 |
| `scripts/novelos_render_projection.py` | 新建：projection CLI 包装 |
| `scripts/novelos_propagate_stale.py` | 新建：stale 传播 |
| `.codex/config.toml` | 新增 `[mcp_servers.sqlite]` |
| `tasks/25_sqlite_mcp_poc.md` | 本文件 |
| `tasks/README.md` | 登记 Task 25 |

## 不改动项（显式）

- 数据库 schema 不变
- NovelOS MCP 不停用（config.toml 保留注册）
- mcp/novelos/src 代码不动
- SKILL.md 不动
- catalog/ 不动

## 来源信息

- 触发决策：外部评估暴露审查标准盲区 → 审查链路全链路追踪（130+ 次 MCP 调用，55% 治理开销）→ 架构评估（89 工具 90% 可被 SQLite MCP 替代）
- POC 验证：SQLite 3.51.0（支持 DROP COLUMN）；数据库层面 BLOB/FK/CHECK 全部验证通过
- MCP SDK：项目 .venv 已有 `mcp>=1.28.1,<2` 的 FastMCP

## 验收标准

- [x] SQLite MCP server `execute_sql` 通过 6 项 POC（SELECT/INSERT BLOB/读回 BLOB/UPDATE/FK RESTRICT/CHECK 约束）
- [x] BLOB 读取返回 UTF-8 可读文本（不是 bytes repr）
- [x] novelos_propagate_stale.py --check 正确找到 13 个下游
- [x] novelos_hash.py 输出 `sha256:<64 hex>` 格式
- [x] novelos_validate_book_soul.py 校验西幻项目 book_soul 通过
- [x] novelos_render_projection.py 渲染 133 个文件
- [x] .codex/config.toml 包含 `[mcp_servers.sqlite]`
- [x] NovelOS MCP 注册保留不动
- [x] compileall 通过

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python scripts/novelos_propagate_stale.py --check --asset planning:006c68a6-a6a8-4842-b8c8-9d03c1c2587e
.venv/bin/python scripts/novelos_hash.py --text "test"
.venv/bin/python scripts/novelos_render_projection.py --project project:b32d765e-9a32-472a-87f0-e979329d6fbc --output /tmp/test-proj
.venv/bin/python -m compileall -q scripts mcp/sqlite-mcp
```

## 完成条件

SQLite MCP 可独立完成全部数据库操作 + 5 个桥接脚本就绪 + POC 全部通过。Task 26 切换的前置条件满足。

## 后续工作（不在本任务范围）

- **Task 26**：数据库瘦身（DROP 门禁表）+ SKILL.md/AGENTS.md 重写 + 停用 NovelOS MCP
- **Task 27**：craft skill 标准补齐（通俗度/开头/钩子强度）
- SQLite MCP server 需要 Codex 重启后才能通过 MCP 协议连接（当前已通过函数级 POC 验证）
