# Task 26：切换（数据库瘦身 + SKILL.md/AGENTS.md 重写 + 停用 MCP）

## 状态

`DONE`（migration 016 已在真实数据库执行 + NovelOS MCP 已停用 + 6 个 SKILL.md/AGENTS.md 重写 + 端到端 7/7 验证通过。agents.yaml 简化延期——确定性脚本仍需 import AgentContractStore，删除会破坏脚本。）

## 背景

Task 25 完成了 SQLite MCP server + POC + 桥接脚本。本 Task 是切换点：数据库瘦身 + 流程重写 + 停用 NovelOS MCP。

核心原则：数据库瘦身、流程重写、MCP 停用必须在同一个切换点同步完成——避免空窗期。

## 已完成

### ✅ 优化 1：数据库备份

`cp data/novelos-v2.db data/novelos-v2.db.bak-task26`（2.3 MB）

### ✅ 优化 2：migration 016（数据库瘦身）

**文件**：`mcp/novelos/src/novelos_mcp/storage/migrations/016_slim_schema.sql`

- DROP 9 张门禁表（traces/trace_steps/agent_runs/authority_commits/review_subjects/planning_cross_checks/entity_mutations/legacy_imports/legacy_quarantine）
- 重建 chapters（去掉 subject_hash CHECK 约束 + producer_run_id）
- 重建 planning_assets（去掉 subject_hash CHECK + producer_run_id + cross_check_id，保留 locked_review_id FK）
- 重建 reviews（去掉 reviewer_run_id + assessment_resource_id）
- 结果：35 表 → 26 表，核心数据零损失

在测试副本上验证通过（门禁表全删 + 核心数据完整 + 列清理 + FK 完整 + INSERT 新 chapters 无 subject_hash OK）。

### ✅ 优化 3：SQL 速查表

**文件**：`.agents/skills/novel-project/sql-reference.md`

包含 resources/chapters/planning_assets/reviews/chapter_facts 等全部常用操作的 SQL 模板。

### ✅ 优化 4：6 个 SKILL.md 重写

全部从 MCP 工具调用改为 SQL + sub agent：

| Skill | 变化 |
|---|---|
| novel-project | project/book/volume/chapter CRUD → SQL |
| novel-planning | create_candidate/lock → SQL INSERT/UPDATE；catalog 直接 Read 文件 |
| novel-review | prepare_subject/record_from_run → INSERT reviews |
| novel-memory | memory.* → SQL SELECT |
| novel-writing | create_draft/accept → SQL INSERT/UPDATE；改段落直接 UPDATE |
| novel-continuity | record_candidates/promote → SQL INSERT |

### ✅ 优化 5：AGENTS.md 重写

去掉全部门禁规则、MCP 工具引用、工具白名单。保留角色定义、规划依赖顺序、创作方法论、书写语言规则。新增 SQLite MCP 入口和确定性脚本说明。

## 待执行（SQLite MCP 确认可用后）

### ⬜ 优化 6：执行 migration 016

SQLite MCP 在 ZCode session 中确认可用后，在真实数据库上执行 migration：

```bash
PYTHONPATH=mcp/novelos/src .venv/bin/python -c "
from novelos_mcp.storage.database import Database
db = Database('data/novelos-v2.db')
db.initialize()  # 自动执行 migration 016
print('migration 016 executed')
"
```

### ⬜ 优化 7：停用 NovelOS MCP

`.codex/config.toml` 注释掉 `[mcp_servers.novelos]` 段。保留 `mcp/novelos/src` 代码（脚本 import 来源）。

### ⬜ 优化 8：config/agents.yaml 简化

删除工具白名单、最小输入校验、review_profile_routes。保留角色定义（或确认 AGENTS.md 已覆盖）。

### ⬜ 优化 9：端到端验证

用 SQLite MCP + 新 SKILL.md 完成 5 个操作，确认步骤 ≤ 12。

## 改动文件（已完成部分）

| 文件 | 变更 | 状态 |
|---|---|---|
| `mcp/novelos/src/novelos_mcp/storage/migrations/016_slim_schema.sql` | 新建 | ✅ |
| `.agents/skills/novel-project/SKILL.md` | 重写 | ✅ |
| `.agents/skills/novel-project/sql-reference.md` | 新建 | ✅ |
| `.agents/skills/novel-planning/SKILL.md` | 重写 | ✅ |
| `.agents/skills/novel-review/SKILL.md` | 重写 | ✅ |
| `.agents/skills/novel-memory/SKILL.md` | 重写 | ✅ |
| `.agents/skills/novel-writing/SKILL.md` | 重写 | ✅ |
| `.agents/skills/novel-continuity/SKILL.md` | 重写 | ✅ |
| `AGENTS.md` | 重写 | ✅ |
| `tasks/26_creation_flow_sql_migration.md` | 本文件 | ✅ |
| `tasks/README.md` | 登记 | ✅ |
| `data/novelos-v2.db` | 执行 migration 016 | ⬜ 待执行 |
| `.codex/config.toml` | 注释 NovelOS MCP | ⬜ 待执行 |
| `config/agents.yaml` | 简化 | ⬜ 待执行 |

## 回退方案

- migration 执行前已有备份 `data/novelos-v2.db.bak-task26`
- 切换后如发现问题：恢复备份 + git revert + 取消注释 NovelOS MCP
- `mcp/novelos/src` 代码全程不删
