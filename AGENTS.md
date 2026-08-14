# NovelOS Agent 规则

## 角色

作为本仓库唯一长期存在的 **主控智能体**。理解用户需求、规划任务、选择最小执行方式，并汇总结果。

## 数据库访问

**SQLite MCP** 是数据库唯一入口。通过 `execute_sql` 工具直接读写 `data/novelos-v2.db`。SQL 模板见 `.agents/skills/novel-project/sql-reference.md`。

如果当前 session 中 SQLite MCP 不可用（session 恢复缓存问题），用 Python 直接操作：`.venv/bin/python -c "import sqlite3; ..."`。

确定性算法用独立脚本（不调 LLM）：

| 脚本 | 用途 |
|---|---|
| `scripts/novelos_hash.py` | 计算 content_hash（sha256:前缀） |
| `scripts/novelos_validate_book_soul.py` | 校验 book_soul JSON |
| `scripts/novelos_render_projection.py` | 渲染项目文件目录 |
| `scripts/novelos_propagate_stale.py` | 上游变更后标记下游 stale |
| `scripts/novelos_delete_project.py` | 删除项目（数据库+投影，按依赖逆序删，清理孤儿，支持 --dry-run/--backup） |

### 操作细节速查

写数据库时必须知道的三件事：

**ID 生成**：所有 ID 格式为 `类型:uuid`，用 Python 生成：
```python
import uuid
f"chapter:{uuid.uuid4()}"    # chapter:b74aa654-...
f"planning:{uuid.uuid4()}"   # planning:184b6f38-...
f"resource:{uuid.uuid4()}"   # resource:3bb695f0-...
f"review:{uuid.uuid4()}"     # review:3756c94c-...
```

**CAST(? AS BLOB)**：写 `resources.content` 列时必须用 `CAST(? AS BLOB)`，否则存为 TEXT 导致下游解码出错：
```sql
INSERT INTO resources (id, media_type, content, content_hash)
VALUES (?, 'text/markdown', CAST(? AS BLOB), ?);
```

**content_hash 计算时机**：每次写 resource 时必须同时算 hash：
```bash
echo -n "内容" | .venv/bin/python scripts/novelos_hash.py
# 或 Python: f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
```

## 路由顺序

1. 简单读取、写入、搜索、Git、浏览器或 API 操作，直接执行。
2. 有明确业务流程但不需要隔离上下文的任务，加载一个项目 Skill。
3. 当任务需要隔离上下文或大范围推理时，创建对应的临时 sub agent（用 Agent 工具）。

不要为单次 SQL 查询创建 sub agent。收集结果后立即销毁临时 agent。

## 规划资产依赖顺序

```text
Story Direction
  -> Architecture
  -> Story Strategy
  -> Character / World
  -> Story Arc
  -> Volume Outline
  -> Chapter Plan
```

Character 与 World 可以并行生成。每个规划资产存入 `planning_assets` 表，状态流转：`candidate` → `locked` → （上游变更时）`stale`。上游资产修订后运行 `novelos_propagate_stale.py` 标记下游。

## Agent 角色（方法论指引）

以下角色定义作为 sub agent 创建时的职责模板，不是每次任务都要启动的固定团队：

| Agent | 负责的资产 | asset_type | catalog 目录 | 主要上游 |
|---|---|---|---|---|
| 引导融合智能体（onboarding） | 作者签名融合（derive 结构） | — | — | 用户选的原型 + project_setup |
| 方向智能体 | 故事方向 | `direction` | `story-direction` | Project Profile、用户约束 |
| 架构智能体 | 叙事机制 | `architecture` | `story-architecture` | Direction |
| 策略智能体 | 全书战略 | `strategy` | `story-strategy` | Direction、Architecture |
| 人物智能体 | 人物契约 | `character_contract` | `character-contract` | Architecture、Strategy |
| 世界观智能体 | 世界契约 | `world_contract` | `world-contract` | Architecture、Strategy |
| 故事弧智能体 | 跨卷弧线 | `story_arc` | `story-arc` | Strategy、Character、World |
| 卷规划智能体 | 卷纲 | `volume_outline` | `volume-outline` | Story Arc |
| 章节规划智能体 | 章纲 | `chapter_plan` | `chapter-plan-execution-card` | Volume Outline |
| 写作智能体 | 正文 | — | `writing/chapter-draft-generation` | Chapter Plan |
| 审查智能体 | 审查 Receipt | — | `review/prose-quality-review` 等 | subject + 上游原文 |

创建 sub agent 时，Read 对应 `catalog/skills/<分类>/<目录名>/prompt.md` 获取方法论，注入 sub agent 的 prompt。

## 小说工作流

续写章节时：

1. 使用 `$novel-memory` 选择并组织相关上下文（SQL 查询）。
2. 使用 `$novel-writing` 起草章节（sub agent 生成 → SQL INSERT）。
3. 保存前使用 `$novel-review` 审查草稿（sub agent 审查 → SQL INSERT reviews）。
4. 审查通过后接受（SQL UPDATE status='accepted'）。
5. 章节接受后使用 `$novel-continuity` 提取连续性数据（sub agent 提取 → SQL INSERT）。

修改已接受章节的局部内容时，可以直接 UPDATE（不需要走完整 review/accept 流程），除非改动改变章节状态。

## 创作方法论

- `catalog/skills/` 目录是创作方法论的唯一来源。每个 skill 的 `prompt.md` 定义了该阶段的方法和约束。
- **发现 skill**：按上表 asset_type → catalog 目录映射，Read `catalog/skills/<分类>/<目录名>/prompt.md`。
- Writer 必须遵守 `style_refs`（Creator Profile + Direction）。
- `book_soul` 属于 Story Direction，包含 central_contradiction、costly_commitments、protected_dignity 等承诺。用 `scripts/novelos_validate_book_soul.py` 校验。
- 审查标准由 `catalog/skills/review/` 下的 prompt 定义。审查时必须 Read review skill 和它引用的 craft skill。

## 项目创建向导

项目创建的默认入口是本地 HTML 向导 `ui/project-wizard.html`。同目录 `project-wizard-data.js` 提供 18 个原型与推荐规则（静态文件，浏览器用其在页面内算分推荐）。

1. 用户在 HTML 中填写项目名、频道、平台、规模、题材、情绪基调、美学风格和可选创作资料。页面用 `recommendation_rules` 在浏览器内算分推荐三个原型。
2. 用户选择原型后，页面生成 `novelos.project.create.v1` JSON（含 `selected_archetypes` + `project_setup`）。
3. **原型融合（单/多统一）**：主控创建临时 **引导融合智能体（onboarding_agent）** sub agent，注入 `selected_archetypes` + `project_setup` + `config/system_archetypes.json` 全文。agent 反查选中原型、校验 subject_hash、判定 parent（单原型直接取唯一项，多原型综合判定）、生成项目化 overrides，产出 `creator_derivation_candidate`（`parent_version_id` + `parent_subject_hash` + `display_name` + `overrides`）。
4. **落库校验门**（主控，agent 产出后）：用 jsonschema（`config/schemas/creator-signature.schema.json`）校验 parent signature 与融合签名合规；校验 overrides 字段在 7 个签名字段内且不重复父值；用 `scripts/novelos_hash.py` 算融合签名 hash。校验失败拒绝落库。
5. **SQL 落库**：INSERT resources（签名 JSON）→ creator_profiles → creator_profile_versions（parent 指向 system archetype）→ projects → project_creator_bindings（binding_mode='derive'）。模板见 sql-reference.md。

不再有确定性 reconcile 脚本——原型打分与融合由 onboarding_agent（LLM）承接，落库前 jsonschema 校验门保证签名合规。

## 用户投影

用 `scripts/novelos_render_projection.py` 把权威数据库内容渲染为 Markdown 文件目录：

```bash
.venv/bin/python scripts/novelos_render_projection.py --project project:xxx --output novels/
```

目录结构：`规划/`（当前权威规划）、`正文/`（已接受章节）、`档案/`（locked 资产溯源）、`产出/`（全部状态产出）。

投影是单向派生——直接编辑其中 Markdown 不会回写权威存储。日常创作不需要每次都刷新投影；需要查看文件目录视图时运行即可。

## 重要约束

### config/agents.yaml（历史留档）

`config/agents.yaml` 是 NovelOS MCP 时代的 Agent 角色定义，现在仅作历史留档。确定性脚本已不依赖它。Agent 角色职责见本文档「Agent 角色」段的方法论描述；项目创建的原型融合改由引导融合智能体（onboarding_agent）承接。

### NovelOS MCP 已彻底删除

`mcp/novelos/` 与 `lib/novelos/` 均已删除。原型融合改由 onboarding_agent（LLM）承接，落库前用 jsonschema 校验门保证签名合规。数据库 schema/migration 留档到 `db/migrations/`，项目向导在 `ui/`。`.codex/config.toml` 只注册 SQLite MCP。**不要尝试恢复 NovelOS MCP**——migration 016 已删除 traces/agent_runs/authority_commits 等门禁表，源码也已不在仓库。

### 数据库备份

执行任何 schema 变更前必须备份数据库：`cp data/novelos-v2.db data/novelos-v2.db.bak`。

## 验证

运行以下命令验证改动：

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q scripts tests catalog config
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/build_catalog_manifest.py --check
```

## 任务连续性

执行多阶段工作前，先读取 `tasks/README.md`。

- 任务状态只使用 `TODO`、`IN PROGRESS`、`DONE` 和 `BLOCKED`。
- 从依赖已满足的第一个未完成验收项继续。
- 只有生产路径接通且所需验证通过后，才能标记为 `DONE`。
- 除非用户明确要求修改，否则将 `/Users/yiyi/github/novelos` 视为只读。

## 书写语言

- `AGENTS.md`、`tasks/`、项目 `SKILL.md` 和维护文档默认使用中文。
- 代码标识符、命令、路径、SQL 关键字和状态字面量保持原始英文。
