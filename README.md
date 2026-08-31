> ⛔ **本仓已冻结归档(2026-08-28)**:NovelOS 的唯一生产权威已迁移至 `D:\github\dsh_novelos`(DSH 侧本体)。
> 此后不要在本仓继续写入;迁移溯源与差异清单见新仓 `PROVENANCE.md`(来源 commit = 本仓 d7abbcf7)。本 README 以下内容为迁移时点快照,仅供考古。
# NovelOS

> **零 Python 演进已完成**：全仓无任何 `.py`，`legacy-python/` 与 `.venv` 已删除；方法论组装器已 JS 化并与 py 版金样逐字节等价。
> **插件时代已结束**：`plugin/`（DSH 插件、defineTool 写门、viewer 面板、wizard 三件套）已整体移除退役，数据库读写改为 node:sqlite 直连 + 文档纪律约束。
> 路线与验证记录见 [tasks/README.md](./tasks/README.md)，agent 行为规则见 [AGENTS.md](./AGENTS.md)。

## 项目定位

NovelOS 是一套**面向长篇小说创作的多智能体创作操作系统**：

- **L0 权威存储**：`data/novelos-v2.db`（SQLite，25 表）承载全部规划资产与正文，`config/` 提供与语言无关的 JSON Schema 校验基准（schemas ×18）、题材包与系统叙事原型——这是整个系统的唯一事实源。
- **L1 运行时**：主控 agent 经 node:sqlite（Node ≥ 22）直连权威库——读为一次性只读查询，写为受控事务直写（SQL 模板唯一来源 = `.agents/skills/novel-project/sql-reference.md`）。
- **L2 方法论**：`catalog/skills/**` 创作方法论 Catalog（prompt.md 主干 + 条件模块 + manifest），与语言无关，原样有效。
- **L3–L5**：组装产物（`data/compositions/`）、harness 适配（`adapters/`，单源 `adapters/source/harness.yaml`）、会话编排（`.agents/skills/novel-*` 六个操作技能 + `AGENTS.md` 路由协议）。

主控 agent 经组装器把方法论注入各角色 agent（内核融合、分身融合、方向／架构／策略／世界／人物／故事弧／卷纲／章纲、写作、审查、连续性），产物按状态机纪律（候选→锁定→stale、审查留痕）落库。

## 系统现状（终态）

| 能力 | 终态实现 |
|---|---|
| 写路径 | node:sqlite 事务直写（主控 agent，`BEGIN IMMEDIATE` + 失败整体回滚）——SQL 模板与纪律见 `.agents/skills/novel-project/sql-reference.md`；content_hash 用 node:crypto 计算并与 BLOB 同步写入 |
| 读路径 | 一次性 node:sqlite 查询（agent）；人类浏览用任意 SQLite 工具只读打开 `data/novelos-v2.db` |
| 方法论组装 | `node scripts/novelos-compose-prompt.mjs`，配方矩阵权威在 `config/agent-recipes.json`，与 py 版金样逐字节等价 |
| 校验 | 机器校验门已随插件退役；`config/schemas/*.json`（×18）保留为落库前自查基准 |
| 渲染器 | md 投影渲染器（`scripts/novelos-render-projection.mjs`，node:sqlite 只读，单向渲染到 `novels/`，可删除重建；viewer 面板与独立 HTML/Web 渲染器仍退役，不要重建） |

**路线图**：R1 插件实体化、R2 JS 写门、R3 编排层与 R4 数字门均已交付收官；此后 `plugin/` 整体移除退役（2026-08-27 裁决），写库口径改为 node:sqlite 直写 + 文档纪律，机器校验以 `config/schemas/*.json` 落库前自查替代。其后经用户裁决恢复 md 投影渲染器（2026-08-27 之后，JS 移植自 py 版 `novelos_render_projection.py`，零 Python 纪律下重建，见 [tasks/README.md](./tasks/README.md)「投影恢复裁决记录」）。账本以 [tasks/README.md](./tasks/README.md) 为准，不要重建 py 实现或插件门。

**已退役清单**（不要寻找、不要重建）：`plugin/`（DSH 插件与 defineTool 写门、viewer 面板、wizard 三件套，2026-08-27 移除）、`legacy-python/`（py 校验门 + unittest）、`.venv`、`mcp/sqlite-mcp/`（Python MCP 通道）、`run_sqlite_mcp.cmd/.sh`、`.codex/config.toml`、`requirements-mcp.txt`、`ui/` 三件套、`documentation/`（已并入 `docs/`）、python 四命令验证纪律。仓库无任何 MCP 配置需求、无任何 Python 依赖、无任何插件依赖。（md 投影渲染器已按用户裁决恢复，见「用户展示」节。）

## 目录结构

```text
.agents/skills/novel-*     会话编排层六个操作技能（project/planning/memory/writing/review/continuity）
adapters/                  harness 适配层，单源 adapters/source/harness.yaml
catalog/skills/            创作方法论 Catalog（onboarding/planning/writing/review/continuity/craft/expansions）
config/
  schemas/                 JSON Schema ×18（落库前自查的校验基准，语言无关）
  agent-recipes.json       角色 × 方法论配方矩阵权威
  genre-packs.json         题材包（唯一词表源；scripts/test-guardrails.mjs 守卫结构自洽与配方一致）
  system_archetypes.json   系统叙事原型
data/novelos-v2.db         权威 SQLite 库（变更前先备份；data/compositions/ 组装产物运行时生成）
novels/                    用户可读项目文件夹投影（只读派生，可删除重建，本地忽略）
db/migrations/             SQL 迁移留档 + schema.sql 基线（语言无关资产）
docs/                      文档（历史任务账本在 docs/archive/tasks/；插件时代规格保留作历史档案）
scripts/                   JS 工具脚本：novelos-compose-prompt.mjs 组装器 + novelos-render-projection.mjs 投影渲染器 + test-compose-prompt.mjs（19 用例）+ test-guardrails.mjs + test-render-projection.mjs（48 用例）+ fixtures/compose-golden/ 金样
tasks/README.md            路线图 + 裁决记录
```

## 快速上手

### 环境要求

- Node.js ≥ 22（内置 `node:sqlite`）。无 Python、无 venv、无 MCP 配置、无插件依赖。

### 创建小说项目

向导 UI 已随插件退役，当前由主控 agent 编排（细节见 [AGENTS.md](./AGENTS.md)「项目创建向导」与 `.agents/skills/novel-project/SKILL.md`）：

1. 与用户确认项目约束，产出 `novelos.project.create.v3` 形态的 JSON 载荷。
2. `node scripts/novelos-compose-prompt.mjs --asset fusion --payload <json>`（建核另用 `kernel-fusion`）产出注入文本，交给 onboarding sub agent 产出 author_kernel / creator_signature 候选。
3. 落库前对照 `config/schemas/*.json` 自查，随后以 node:sqlite 单事务直写落库（六表 SQL 模板见 sql-reference.md「作者签名链」）。

### 查询数据库（agent 一次性只读查询）

```bash
node -e "const {DatabaseSync}=require('node:sqlite');const db=new DatabaseSync('data/novelos-v2.db');console.log(db.prepare('SELECT id FROM projects').all())"
```

读可随意；写库由主控按受控 SQL 直写（模板见 `.agents/skills/novel-project/sql-reference.md`，纪律见下节）。人类浏览库内容用任意 SQLite 工具只读打开 db，或直接打开「用户展示」节渲染出的 `novels/` 投影目录阅读。

### 用户展示（项目投影）

SQLite 仍是唯一权威数据源；人类视图由单向 Markdown 投影提供：

```bash
node scripts/novelos-render-projection.mjs --project project:xxx [--output novels] [--db data/novelos-v2.db] [--verify]
```

渲染结果在 `novels/<项目目录>/`：`创作约束/`（作者签名 + 本书创作灵魂）、`规划/`（locked 资产；人物契约按「## 人物档案」拆成 `人物契约/` 目录：总览 + 每人物一份）、`大纲/`（卷纲 + 章纲）、`正文/`（accepted 章节）、`人物/`、`世界/`、`连续性/`（六账本 + 人物状态注册表）与 `manifest.json`（逐文件 SHA-256 可校验，`--verify` 复核）。渲染过程只读直连权威库 + 临时目录原子替换；投影可随时删除重建，直接修改其中文件**不会回写**数据库。不提供独立 HTTP/Web 应用（viewer 面板仍退役，不要重建）。

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

# ② 护栏测试（题材词表自洽 + 配方矩阵⊆manifest）
node scripts/test-guardrails.mjs

# ③ 投影渲染器测试（人物契约拆分 + 端到端渲染/校验，48 用例）
node scripts/test-render-projection.mjs
```
（插件 vitest 与 smoke-*.mjs 已随 plugin/ 退役删除。）

## 写库纪律（文档约束）

插件门工具已退役，以下纪律由主控 agent 自查执行（不再是机器强制；SQL 模板唯一来源 = `.agents/skills/novel-project/sql-reference.md`）：

- **写库收口主控**：sub agent 不持有数据库访问；读为一次性 node:sqlite 只读查询，写由主控以 `BEGIN IMMEDIATE` + `PRAGMA foreign_keys=ON` 单事务直写，任一步失败整体回滚零写入。
- **写库三约定**：① ID 格式 `类型:uuid`；② `resources.content` 经 BLOB 写入并同步 content_hash（`'sha256:'+hex`，node:crypto 计算）；③ 状态流转留痕——`candidate→locked` 必须绑定 approved 回执，章节 `accepted` 必须写 `chapters.review_id`（`db/migrations/019_state_machine_links.sql`）。
- **裁决纪律**：项目创建遇内核/签名错配（mismatch）必须呈报用户裁决后才落库；审查有 `blocking` 不得锁定/接受。mismatch 仅警告放行 = 纸面化（红队 F2 教训）。
- **备份先行**：任何 schema 变更前先复制 `data/novelos-v2.db`。
- **生产镜像只读**：`/Users/yiyi/github/novelos` 是生产环境，只读。

## 文档索引

Agent 协作入口：

- [AGENTS.md](./AGENTS.md) — agent 行为规则、路由顺序、小说工作流（权威）
- [tasks/README.md](./tasks/README.md) — 路线图（收官记录）与裁决记录

设计与参考文档（均在 `docs/` 下）：

- [docs/architecture.md](./docs/architecture.md) — 系统架构
- [docs/flows.md](./docs/flows.md) — 关键流程
- [docs/permissions.md](./docs/permissions.md) — 权限矩阵
- [docs/variables.md](./docs/variables.md) — 变量与配置
- [docs/tests.md](./docs/tests.md) — 测试覆盖
- [docs/automation.md](./docs/automation.md) — Agent 与自动化
- [docs/agent-recipes.md](./docs/agent-recipes.md) — 配方矩阵说明
- [docs/worldbuilding-redesign.md](./docs/worldbuilding-redesign.md) — 世界观契约重设计
- [docs/model-roles.md](./docs/model-roles.md) — 多模型分工方案（角色槽默认映射与防共谋矩阵）
历史档案（仅考古参考，不再更新）：

- [scripts/COMPOSE-PORT-NOTES.md](./scripts/COMPOSE-PORT-NOTES.md) — 组装器 py → JS 移植记录（金样等价验收）
- [docs/archive/tasks/](./docs/archive/tasks) — 历史任务账本（Task 06–39，py 时代考古参考，不再更新）
