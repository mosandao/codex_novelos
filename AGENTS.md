# NovelOS Agent 规则

## 角色

作为本仓库唯一长期存在的 **主控智能体**。理解用户需求、规划任务、选择最小执行方式，并汇总结果。

## 数据库访问

**SQLite MCP** 是数据库唯一入口。通过 `execute_sql` 工具直接读写 `data/novelos-v2.db`。SQL 模板见 `.agents/skills/novel-project/sql-reference.md`。

如果当前 session 中 SQLite MCP 不可用（session 恢复缓存问题），用 Python 直接操作：`.venv/bin/python -c "import sqlite3; ..."`。

确定性算法用独立脚本（不调 LLM）：

| 脚本 | 用途 |
|---|---|
| `scripts/novelos_create_project.py` | 项目创建固化管线：入口校验（schema+词表级联+原型三方比对+镜像漂移）→ 候选容错解析 → 校验门（jsonschema+parent 反查+逐字复制检查）→ 单事务落库 |
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
| 引导融合智能体（onboarding） | 作者签名融合（先立人再落规） | — | `onboarding/creator-signature-fusion` | 用户选的原型 + project_setup |
| 方向智能体 | 故事方向 | `direction` | `story-direction` | Creator persona、用户约束 |
| 架构智能体 | 叙事机制 | `architecture` | `story-architecture` | Direction |
| 策略智能体 | 全书战略 | `strategy` | `story-strategy` | Direction、Architecture |
| 人物智能体 | 人物契约 | `character_contract` | `character-contract` | Architecture、Strategy |
| 世界观智能体 | 世界契约 | `world_contract` | `world-contract` | Architecture、Strategy |
| 故事弧智能体 | 跨卷弧线 | `story_arc` | `story-arc` | Strategy、Character、World |
| 卷规划智能体 | 卷纲 | `volume_outline` | `volume-outline` | Story Arc |
| 章节规划智能体 | 章纲 | `chapter_plan` | `chapter-plan-execution-card` | Volume Outline |
| 写作智能体 | 正文 | — | `writing/chapter-draft-generation` | Chapter Plan |
| 审查智能体 | 审查 Receipt | — | `review/prose-quality-review` 等 | subject + 上游原文 |

创建 sub agent 时获取方法论的方式按资产分流（以 `scripts/novelos_compose_prompt.py` 的 **ASSET_DIRS 注册表**为准）：**已注册资产**用组装器 `--asset <asset>` 一步产出完整注入文本（主干 + 按 setup 路由的条件模块 + 输入数据区 + 自检汇总；审查资产另需 `--subject`），不 Read prompt.md、不手工拼注入；**未注册资产**暂 Read 对应 `catalog/skills/<分类>/<目录名>/prompt.md` 注入，Task 29 P2 完成后逐一切换为组装器。

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
- Writer 必须遵守 `style_refs`（Creator Profile + Direction）。签名含 `persona`（创作者人格，schema v2）时必须一并注入：narrative 全文 + anchors（目光/五维/内在矛盾/声音样本/盲区）。Writer 写到超出作者经验边界的场景时按 persona 处理——执行该盲区条目附带的绕开方式（转喻/侧写/留白/借他人之口），禁止全知叙述假装在场（`blindspots.cannot_write` 是硬边界；正文流畅还原盲区场景而未绕开＝persona 未生效，prose-quality-review 会判 `blocking`）。
- Direction 智能体的输入必须包含 persona：book_soul 从这个人身上长出来，不从原型标签推导。
- `book_soul` 属于 Story Direction，包含 central_contradiction、costly_commitments、protected_dignity 等承诺。用 `scripts/novelos_validate_book_soul.py` 校验。
- 审查标准由 `catalog/skills/review/` 下的 prompt 定义。审查时必须 Read review skill 和它引用的 craft skill。

## 项目创建向导

项目创建的默认入口是本地 HTML 向导 `ui/project-wizard.html`。同目录 `project-wizard-data.js` 是静态权威数据（频道×平台/题材词表/表里基调池/美学推荐/题材信息包/推荐规则 + 18 个原型镜像含 channel_affinity；原型本体在 `config/system_archetypes.json`，改原型后同步镜像）。

> **强制首步**：收到「创建 / 开始 / 新建小说项目」类请求时，主控的**第一个动作**必须是 `open ui/project-wizard.html` 打开向导。**禁止**用 `AskUserQuestion`、结构化问卷或自由文本在 CLI 内收集创建字段来替代——频道级联（平台/题材/基调词表联动）、原型打分推荐、原型勾选、人格素材编辑都依赖页面交互，CLI 复刻会导致签名缺失或字段不全，落库校验门会失败。仅在用户明确表示无法使用浏览器时，才考虑 fallback，且必须在回复中说明原因。

1. 用户在 HTML 中填写项目名、频道（男频/女频/全向，决定平台/题材/基调词表）、平台（附平台画像）、规模、一级题材（附题材信息包提示）、二级方向、表里基调（表层外显 1-2 项 + 内核底色 1 项）、美学风格和可选创作资料。页面用 `recommendation_rules` + 原型 `channel_affinity` 在浏览器内算分推荐三个原型。
2. 用户选择原型、可选填写人格素材后，页面生成 `novelos.project.create.v2` JSON（含 `selected_archetypes` + `user_persona_hints` + setup v2：channel/platform/platform_traits/scale/题材/表里基调/美学/genre_profile/reference_material）。
3. **入口校验（收到 JSON 后的第一动作）**：`.venv/bin/python scripts/novelos_create_project.py --payload <json>`——jsonschema 结构校验（`config/schemas/project-create-request.schema.json`）+ 词表级联（channel×platform×题材×二级方向×基调池×美学，对照 `ui/project-wizard-data.js`）+ 表里互斥规则 + platform_traits/genre_profile 随行快照核对 + 原型三方比对（payload × config × 向导镜像，含全 18 原型镜像漂移检测）。FAIL 拒绝继续。
4. **原型融合（先立人，再落规）**：主控运行 `.venv/bin/python scripts/novelos_compose_prompt.py --asset fusion --payload <json>` 产出**完整注入文本**（方法论主干 + 按项目条件路由的模块——频道语法/库规模/parent 判定/题材资格——+ 输入数据区：选中原型条目全文 + 全库一行式清单 + `user_persona_hints` + `project_setup`（v2）+ `existing_persona_fingerprints` 按量化范围自动取数，库空自动走空库模块），整段注入临时**引导融合智能体（onboarding_agent）** sub agent。**不再注入 `system_archetypes.json` 全文**（29 倍冗余已被裁掉——agent 只看选中条目；跨原型撞车由第 5 步校验门条级查重兜底）。agent 按「先立人，再落规」两步法执行：判定 parent（单原型直接取唯一项，多原型按推荐位次 + 基调契合度，输出 `parent_rationale`）→ 反推式五维生平（世代年龄/教育视野/阶层圈子库存/职业履历/人生轨迹，双向拟合：气质溯因 × 题材资格；人格素材按 prompt 的素材用法织入；行业内生视角配额——履历不得全部来自网文行业外转行）→ 化合出 persona（narrative + anchors，含盲区清单 refuses/cannot_write，每条附下游绕开方式）→ 从 persona 长出带体温的 7 字段，产出 `creator_derivation_candidate`（`parent_version_id` + `parent_subject_hash` + `display_name` + `parent_rationale` 含 `cross_batch_check` 小节 + signature v2 含 persona）。
5. **校验门 + 落库（固化脚本一步完成）**：`.venv/bin/python scripts/novelos_create_project.py --payload <json> --candidate <json>`——候选容错解析（只做安全修复：去 Markdown 围栏、尾部截断补括号；中段缺括号导致字段错位即判解析失败）→ jsonschema 信封（creator-derivation-candidate）+ 签名 v2 深层（creator-signature，persona 必填且 `cannot_write` 非空）→ `parent_subject_hash` 反查 config + parent 属于用户勾选集 + 7 字段无逐字复制父值 + **跨原型条级查重**（候选 7 字段逐条与全部未选中原型比对 n-gram 包容度，>60% 触发 WARN，同错配协议须用户裁决）→ hash 计算 → `BEGIN IMMEDIATE` 单事务六表落库（外键开启，失败整体回滚）：签名资源 + 派生资源（**完整用户输入快照**：selected_archetypes + user_persona_hints + setup 全文）+ creator_profiles + creator_profile_versions（content + derivation 双资源链，parent 指向系统原型）+ projects（**metadata_json 写入 setup v2 快照**，带 `setup_schema_version` 标记——后续阶段经 `json_extract(metadata_json,'$.setup')` 读取，不靠会话记忆）+ project_creator_bindings（binding_mode='derive'）。**禁止手工逐条 INSERT 绕过脚本**。
6. **上报裁决协议**：`parent_rationale` 含错配警告（基调相斥 / 频道×人格错配 / 素材冲突）时，主控必须把冲突与调和建议**呈报用户裁决，未获裁决不得落库**（脚本检测到警告字样会提示）。无警告则按第 5 步直接落库。候选解析失败或校验门 FAIL 时要求融合智能体重新输出，禁止主控手工改写候选内容（去围栏/尾部补括号等结构性修复除外）。

确定性校验与落库全部由 `scripts/novelos_create_project.py` 固化承担；原型打分与融合由 onboarding_agent（LLM）承接。**一书一分身是有意设计**：每次 derive 新建 creator profile，同一用户多本书的人格各自独立长成；跨书共享声线不支持（绑定只允许 derive，无 reuse 模式）。

**setup 变更通路（连载中改频道/平台/基调等）**：setup 快照创建时一次写入，但不是不可改——变更属**上游变更**，必须走两步：① `UPDATE projects SET metadata_json = json_set(metadata_json, '$.setup', json('…')) WHERE id = ?` 落库；② 立即将该项目全部 locked 规划资产标记 stale（`scripts/novelos_propagate_stale.py`，或按依赖逆序手动 UPDATE status='stale'），重走审查/锁定。禁止静默改 setup 后继续用旧规划写作。

## 用户投影

用 `scripts/novelos_render_projection.py` 把权威数据库内容渲染为 Markdown 文件目录：

```bash
.venv/bin/python scripts/novelos_render_projection.py --project project:xxx --output novels/
```

目录结构：`README.md`（项目定位——向导 setup 快照摘要）、`创作约束/`（作者签名含创作者人格与**派生溯源**、本书创作灵魂）、`规划/`（locked 规划，人物契约按人物拆子目录）、`大纲/`（卷纲+章纲）、`正文/`（已接受章节）、`人物/`、`世界/`、`连续性/`（六类账本）、`manifest.json`。

投影是单向派生——直接编辑其中 Markdown 不会回写权威存储。日常创作不需要每次都刷新投影；需要查看文件目录视图时运行即可。

## 重要约束

### 项目创建入口（强制首步）

收到「创建 / 开始 / 新建小说项目」类请求时，主控的第一个动作必须是 `open ui/project-wizard.html` 打开本地向导，禁止用 CLI 问卷或自由文本替代。详见「项目创建向导」段的强制首步规则。fallback（用户明确表示无法使用浏览器时）须在回复中说明原因。

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
