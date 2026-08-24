# Task 21：新增"创作种子"非权威入口层

## 状态

`DONE`（migration + service + MCP 工具 + direction prompt + 投影 + 测试全部落地；生成验证待实际生成流程执行）

## 背景

世界观设计重构讨论稿（`documentation/worldbuilding-redesign.md`）第 22.5 条建议在 project 创建和 direction 之间，加一个非权威的"创作种子"层。

### 种子需求真实性的证据

不依赖 `agent_runs`（该表不记录用户介入），改用两条证据链：

1. **训练数据证据**：网文圈普遍共识（作者访谈、写作教程、起点创作学院）——绝大多数网文作者开书时脑里第一个清晰的不是"全书战略阶段"，而是"一个主角 + 一个爽点钩子"。典型形态："外卖员觉醒古老血脉"（人物）+"扮猪吃虎幕后流"（爽点）+"地下古老势力"（世界感觉）。"全书分几阶段"是后整理的，很多作者写到几十万字才明确。
2. **西幻项目实证**：其 `metadata.project_setup.creation_context.reference_material` = "21世纪男穿越重生生成贵族的次子可支配资源少"——这本身就是一个种子，但被塞进 project metadata，没有独立成层、没有反哺 direction 的机制、无法独立迭代。

这证明种子层不是想象需求，是网文创作的真实起手式。当前 `reference_material` 字段承载了种子内容但缺三样：独立迭代能力、direction 反向工程机制、投影可见性。

### 决策（已确认：选项 A 正式层）

选项 B（轻量只改 prompt）和 C（暂不做）被否决。理由：种子需求真实且会迭代（用户写到第 30 章可能想改主角设定），塞进 `project.metadata` 走 `update_project` 每次都 bump project version 不合理，且没有变更留痕。正式层更符合 NovelOS"生长可追溯"的原则——即使是非权威种子，迭代也该留痕。

## 种子层设计

### 核心性质：非权威、可迭代、不触发 stale

种子层与所有现有规划资产的本质区别：
- **不进 `planning_assets` 表**（那是权威资产容器，有 locked/stale/superseded 生命周期）。
- **不进依赖图**（无 `planning_asset_dependencies` 记录）。
- **不触发 stale 传播**（种子改了，不自动标 direction stale——由主控判断是否需重生成 direction）。
- **但有版本和变更留痕**（迭代可追溯，符合"生长可追溯"原则）。

### 数据 schema（新表）

```sql
CREATE TABLE IF NOT EXISTS creation_seeds (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    -- 种子内容（用户原始想法的结构化记录）
    protagonist_seed TEXT NOT NULL DEFAULT '',   -- 主角雏形
    world_seed TEXT NOT NULL DEFAULT '',          -- 世界感觉
    hook_seed TEXT NOT NULL DEFAULT '',           -- 爽点偏好
    notes TEXT NOT NULL DEFAULT '',               -- 可选创作资料/其他
    -- 变更留痕
    is_active BOOLEAN NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, version),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

设计要点：
- 一个 project 同一时刻只有一个 `is_active=1` 的种子（当前生效版）。
- 每次迭代新增一行 `version+1`，旧版 `is_active=0` 保留（留痕不删）。
- 四个文本字段（主角/世界/爽点/备注）对应讨论稿第十四章的种子结构。
- 无 `subject_hash`、无 `locked_review_id`——种子非权威，不需审查。

### MCP 工具

新增三个工具：
- `creation_seed.get(project_id)` — 取当前 active 种子。
- `creation_seed.update(project_id, protagonist_seed, world_seed, hook_seed, notes)` — 迭代种子（新增 version，旧版置 inactive）。
- `creation_seed.list(project_id)` — 列全部历史版本（留痕查阅）。

不新增 `create`——种子在项目创建时由向导或首次 `update` 自动建立 v1。

### direction prompt 改造

`catalog/skills/planning/story-direction/prompt.md` 新增职责：
"当项目存在 active 创作种子时，优先从种子反推 `book_soul`（central_contradiction / costly_commitments 等），而非凭空构造。种子的主角雏形、世界感觉、爽点偏好是用户意图的直接表达，必须被 direction 吸收；与 creator_signature/archetype 冲突时，在候选中显式标注冲突并交主控裁决。"

### 投影

在 `novels/<项目>/创作约束/` 新增 `创作种子.md`，渲染当前 active 种子的四字段 + 版本号。投影是单向派生，编辑不回写（与现有投影规则一致）。

## 优化

### 优化 1：新建 migration `013_creation_seeds.sql`

建 `creation_seeds` 表（schema 见上）。

### 优化 2：service 层新增种子 CRUD

在 `service/` 新增 `seeds.py` Mixin 或并入 `projects.py`，实现 get/update/list 三个方法。注意：
- `update` 必须在事务内：插入新 version 行 + 旧 active 行置 `is_active=0`。
- 不触发任何 stale 传播。
- 不写 `authority_commits`（种子非权威）。

### 优化 3：MCP 工具注册

在 MCP 工具表注册 `creation_seed.get/update/list` 三个工具。工具不做 authority commit、不做 review、不进 trace 的权威步骤——但 `update` 应记一条 trace step（operation 类型）留痕。

### 优化 4：direction prompt 改造

按上述方向修改 `story-direction/prompt.md`。

### 优化 5：投影渲染

在 `projection.py` 新增 `创作种子.md` 渲染逻辑。

## 改动文件

| 文件 | 变更 |
|---|---|
| `mcp/novelos/src/novelos_mcp/storage/migrations/013_creation_seeds.sql` | 新建（建表） |
| `mcp/novelos/src/novelos_mcp/storage/schema.sql` | 新增 `creation_seeds` 表定义（与 migration 一致） |
| `mcp/novelos/src/novelos_mcp/service/seeds.py` 或 `projects.py` | 新增 get/update/list |
| `mcp/novelos/src/novelos_mcp/service/__init__.py` | 聚合新 Mixin（若独立文件） |
| MCP 工具注册处 | 注册三个 `creation_seed.*` 工具 |
| `catalog/skills/planning/story-direction/prompt.md` | 新增反向工程职责 |
| `mcp/novelos/src/novelos_mcp/service/projection.py` | 新增 `创作种子.md` 渲染 |
| `tasks/migration/catalog_disposition.csv` | 无需改（direction 是已有 skill，只改 prompt） |

## 来源信息

- 来源文档：`documentation/worldbuilding-redesign.md` 第二十二条 22.5、第十四章"种子→约束→契约三阶段"
- 证据链：训练数据（网文创作起手式共识）+ 西幻项目 `reference_material` 实证
- 决策记录：选项 A（正式层），否决 B（轻量）和 C（暂不做）

## 验收标准

- [ ] migration `013_creation_seeds.sql` 建表成功，现有数据库 upgrade 不损坏西幻项目数据。
- [ ] `creation_seeds` 表 schema 与设计一致（四文本字段 + version + is_active）。
- [ ] `creation_seed.get/update/list` 三个 MCP 工具可用，行为符合设计（update 迭代留痕、不触发 stale、不写 authority_commits）。
- [ ] `story-direction/prompt.md` 新增反向工程职责，明确"存在 active 种子时优先反推 book_soul"。
- [ ] 投影新增 `创作约束/创作种子.md`，渲染当前 active 种子。
- [ ] 新增测试覆盖：种子 CRUD、version 迭代留痕、is_active 唯一性、不触发 stale 传播。
- [ ] 现有测试全部通过（不破坏 planning_assets / authority_commit / stale 机制）。
- [ ] `compileall` 通过。

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python scripts/build_catalog_manifest.py --check
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 完成条件

五个优化全部落地、migration 成功且不损坏现有数据、测试通过且新增测试覆盖种子 CRUD 与"不触发 stale"边界、验收项全部勾选，才可标记为 `DONE`。

## 风险与回退

- **schema 变更风险**：新增表（非改现有表），风险低于改现有表。回退 = drop `creation_seeds` 表 + revert 代码，不影响 planning_assets 等权威数据。
- **过度工程风险**：若实测发现用户其实不迭代种子（写完书都不改），正式层的版本留痕是冗余。缓解：is_active 机制允许"只有一个版本"的常见情况，不强制迭代。
- **与 Task 22 耦合**：种子层（入口）和检查点（中段）是同一套"用户介入体验"。Task 21 先落地种子层，Task 22 的检查点设计应参考种子层的介入形态，保持一致。
- **direction 吸收种子的质量**：prompt 改了不代表 LLM 真会反推。需在生成验证（可并入 Task 20 的验证轮次）中确认带种子的 direction 是否更贴合用户意图。
