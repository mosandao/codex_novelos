# NovelOS

> **零 Python 演进已完成**：全仓无任何 `.py`，`legacy-python/` 与 `.venv` 已删除。全部读写收口为 `dsh-novelos-viewer` 插件的 JS 门工具，方法论组装器已 JS 化并与 py 版金样逐字节等价。
> 路线与验证记录见 [tasks/README.md](./tasks/README.md)，agent 行为规则见 [AGENTS.md](./AGENTS.md)。

## 项目定位

NovelOS 是一套**面向长篇小说创作的多智能体创作操作系统**：

- **L0 权威存储**：`data/novelos-v2.db`（SQLite，25 表）承载全部规划资产与正文，`config/` 提供与语言无关的 JSON Schema 校验门（schemas ×18）、题材包与系统叙事原型——这是整个系统的唯一事实源。
- **L1 运行时**：插件 host JS 工具是唯一读写口（目标态达成）——写路径 = `dsh-novelos-viewer` 六个 defineTool 门工具，读路径 = viewer 面板或一次性 node:sqlite 只读查询。
- **L2 方法论**：`catalog/skills/**` 创作方法论 Catalog（prompt.md 主干 + 条件模块 + manifest），与语言无关，原样有效。
- **L3–L5**：组装产物（`data/compositions/`）、harness 适配（`adapters/`，单源 `adapters/source/harness.yaml`）、会话编排（`.agents/skills/novel-*` 六个操作技能 + `AGENTS.md` 路由协议）。

主控 agent 经组装器把方法论注入各角色 agent（内核融合、分身融合、方向／架构／策略／世界／人物／故事弧／卷纲／章纲、写作、审查、连续性），产物经确定性校验门落库。

## 系统现状（终态）

| 能力 | 终态实现 |
|---|---|
| 写路径 | 唯一守门人 = `dsh-novelos-viewer` 插件六个 defineTool 门工具：ajv 校验复用 `config/schemas/*.json` + node:sqlite BEGIN IMMEDIATE 单事务 + crypto content_hash，FAIL 返回 ok:false 零写入 |
| 读路径（人类） | `dsh-novelos-viewer` 面板：client sql.js(WASM) 直读 db 字节，渲染总览／卷纲／章节／人物／世界／连续性六视图 |
| 读路径（agent） | 一次性 node:sqlite 只读查询（Python MCP 通道已删除） |
| 方法论组装 | `node scripts/novelos-compose-prompt.mjs`，配方矩阵权威在 `config/agent-recipes.json`，与 py 版金样逐字节等价 |
| 渲染器 | HTML(JS) 是唯一人类视图（md 投影已退役） |

**路线图**：R1 插件实体化、R2 JS 写门与组装器 JS 化均已交付收官；唯一登记待办为 R4——七个 `validate_*` 资产校验器（story_arc/volume_outline/strategy/character/world 等）的机器门语义尚未 JS 化，catalog prompt 内的机器门引用随 py 门删除失效，以 [tasks/README.md](./tasks/README.md) 账本为准，不要重建 py 实现。

**已退役清单**（不要寻找、不要重建）：`legacy-python/`（py 校验门 + unittest，JS 门等价迁移后删除）、`.venv`、`mcp/sqlite-mcp/`（Python MCP 通道）、`run_sqlite_mcp.cmd/.sh`、`.codex/config.toml`、`requirements-mcp.txt`、md 投影渲染器、`ui/` 三件套（已迁 `plugin/client/`）、`documentation/`（已并入 `docs/`）、python 四命令验证纪律。仓库无任何 MCP 配置需求、无任何 Python 依赖。

## 目录结构

```text
.agents/skills/novel-*     会话编排层六个操作技能（project/planning/memory/writing/review/continuity）
adapters/                  harness 适配层，单源 adapters/source/harness.yaml
catalog/skills/            创作方法论 Catalog（onboarding/planning/writing/review/continuity/craft/expansions）
config/
  schemas/                 JSON Schema 校验门 ×18（语言无关，JS 门直接复用的核心资产）
  agent-recipes.json       角色 × 方法论配方矩阵权威
  genre-packs.json         题材包
  system_archetypes.json   系统叙事原型
data/novelos-v2.db         权威 SQLite 库（变更前先备份；data/compositions/ 组装产物运行时生成）
db/migrations/             SQL 迁移留档 + schema.sql 基线（语言无关资产）
docs/                      文档（历史任务账本在 docs/archive/tasks/）
plugin/dsh-novelos-viewer/ L1 插件：六个 defineTool 写门（vitest 测试）+ scripts/smoke-*.mjs 冒烟脚本
plugin/client/             UI 资产三件套：project-wizard.html / project-wizard-data.js / kernel-roster.js
scripts/                   JS 工具脚本：novelos-compose-prompt.mjs 组装器 + test-compose-prompt.mjs（19 用例）+ fixtures/compose-golden/ 金样
tasks/README.md            零 Python 路线图 + 重组裁决记录
```

## 快速上手

### 环境要求

- Node.js ≥ 22（内置 `node:sqlite`；ajv 由插件依赖提供）。无 Python、无 venv、无 MCP 配置。

### 创建小说项目

1. 打开 `dsh-novelos-viewer` 面板的「项目向导」入口（host 托管 `/api/wizard`，kernel 名册由 host 经 node:sqlite 实时直查）；面板不可用时允许浏览器直接打开 `plugin/client/project-wizard.html`（file:// 离线模式）。
2. 向导产出 `novelos.project.create.v3` JSON → 入口校验门 `novelos_gate_entry` 校验（FAIL 拒绝）。
3. mode=create 先建核：内核融合 agent 产出 author_kernel（`novelos_kernel_commit` 校验落库）→ 分身派生 creator_signature → `novelos_project_commit` 单事务六表落库。

细节与角色分工见 [AGENTS.md](./AGENTS.md)「项目创建向导」；viewer 面板的实现规格见 [docs/novelos-viewer-design.md](./docs/novelos-viewer-design.md)。

### 查询数据库（agent 一次性只读查询）

```bash
node -e "const {DatabaseSync}=require('node:sqlite');const db=new DatabaseSync('data/novelos-v2.db');console.log(db.prepare('SELECT id FROM projects').all())"
```

读可随意，写必须走插件六写门（见下节）；人类浏览库内容用 viewer 面板。

### 组装方法论注入文本

已注册资产的注入文本一律由组装器产出（主干 + 条件模块 + 输入数据区 + 自检汇总），不 Read prompt.md、不手工拼装：

```bash
node scripts/novelos-compose-prompt.mjs --asset <asset> --project <id>
# 审查另加 --subject；修复重试加 --review-feedback + --round
```

配方矩阵权威在 `config/agent-recipes.json`；组装产物即主控 ↔ sub agent 的 ABI（三家 harness 零变体），存 `data/compositions/`。py → JS 移植记录见 [scripts/COMPOSE-PORT-NOTES.md](./scripts/COMPOSE-PORT-NOTES.md)（含金样对比逐字节等价的验收结论）。

### 验证口径

```bash
# ① 组装器测试（19 用例）
node scripts/test-compose-prompt.mjs

# ② 插件六写门测试（vitest，55 用例）
cd plugin/dsh-novelos-viewer && pnpm test

# ③ 冒烟脚本（只读直查 / 门工具链路回归）
node plugin/dsh-novelos-viewer/scripts/smoke-sql.mjs
node plugin/dsh-novelos-viewer/scripts/smoke-gate.mjs
node plugin/dsh-novelos-viewer/scripts/smoke-r6.mjs
node plugin/dsh-novelos-viewer/scripts/smoke-r7.mjs
```

## 写库纪律（红线）

- **唯一写入口**：写库只能经 `dsh-novelos-viewer` 插件六个 defineTool 门工具（ajv 校验 + node:sqlite BEGIN IMMEDIATE 单事务，FAIL 返回 ok:false 零写入）：`novelos_gate_entry`（入口校验，只读）、`novelos_kernel_commit`（内核候选校验落库）、`novelos_project_commit`（分身六表落库）、`novelos_register_characters`（人物重锁登记/动态配角/状态迁移）、`novelos_propagate_stale`（上游修订沿依赖图标 stale）、`novelos_delete_project`（项目整体删除）。禁止手工 INSERT/UPDATE 绕过门直接写库——agent 没有裸 SQL 写通道。
- **写库约定已在门内固化**：① ID 格式 `类型:uuid`；② `resources.content` 经 BLOB 写入并同步 content_hash。
- **裁决门红线**：`novelos_project_commit` 遇 mismatch 必须用户裁决（`userAdjudicated:true`）才放行；任何门 FAIL 必须阻断退出，mismatch 仅警告放行 = 纸面化。
- **备份先行**：任何 schema 变更前先复制 `data/novelos-v2.db`。
- **生产镜像只读**：`/Users/yiyi/github/novelos` 是生产环境，只读。

## 文档索引

Agent 协作入口：

- [AGENTS.md](./AGENTS.md) — agent 行为规则、路由顺序、小说工作流（权威）
- [tasks/README.md](./tasks/README.md) — 零 Python 路线图（收官记录 + R4 待办）与重组裁决记录

设计与参考文档（均在 `docs/` 下）：

- [docs/architecture.md](./docs/architecture.md) — 系统架构
- [docs/flows.md](./docs/flows.md) — 关键流程
- [docs/permissions.md](./docs/permissions.md) — 权限矩阵
- [docs/variables.md](./docs/variables.md) — 变量与配置
- [docs/tests.md](./docs/tests.md) — 测试覆盖
- [docs/automation.md](./docs/automation.md) — Agent 与自动化
- [docs/agent-recipes.md](./docs/agent-recipes.md) — 配方矩阵说明
- [docs/worldbuilding-redesign.md](./docs/worldbuilding-redesign.md) — 世界观契约重设计
- [docs/plugin-feasibility-adversarial-review.md](./docs/plugin-feasibility-adversarial-review.md) — 插件化可行性红队评审
- [docs/r2-js-gate-spec.md](./docs/r2-js-gate-spec.md) — R2 JS 写门规格
- [docs/novelos-viewer-design.md](./docs/novelos-viewer-design.md) — viewer 面板设计规格
- [docs/novelos-viewer-prototype.html](./docs/novelos-viewer-prototype.html) — viewer 视觉原型
- [scripts/COMPOSE-PORT-NOTES.md](./scripts/COMPOSE-PORT-NOTES.md) — 组装器 py → JS 移植记录（金样等价验收）
- [docs/archive/tasks/](./docs/archive/tasks) — 历史任务账本（Task 06–39，py 时代考古参考，不再更新）
