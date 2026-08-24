# NovelOS

> **当前处于「零 Python 演进路线」过渡期**：视图链已 JS 化，Python 校验门暂存 `legacy-python/` 待 JS 门替代。
> 路线图与裁决记录见 [tasks/README.md](./tasks/README.md)，agent 行为规则见 [AGENTS.md](./AGENTS.md)。

## 项目定位

NovelOS 是一套**面向长篇小说创作的多智能体创作操作系统**：

- **L0 权威存储**：`data/novelos-v2.db`（SQLite）承载全部规划资产与正文，`config/` 提供与语言无关的 JSON Schema 校验门、题材包与系统叙事原型——这是整个系统的唯一事实源。
- **L1 运行时**：目标态为插件 host JS 工具（唯一读写口）；过渡态为 `legacy-python/scripts/*.py` 校验门（只维护不新增）。
- **L2 方法论**：`catalog/skills/**` 创作方法论 Catalog（prompt.md 主干 + 条件模块 + manifest），与语言无关，原样有效。
- **L3–L5**：组装产物（`data/compositions/`）、harness 适配（`adapters/`）、会话编排（`.agents/skills/novel-*` 六个操作技能 + `AGENTS.md` 路由协议）。

主控 agent 经组装器把方法论注入各角色 agent（内核融合、分身融合、方向／架构／策略／世界／人物／故事弧／卷纲／章纲、写作、审查、连续性），产物经确定性校验门落库。

## 当前状态：现状 vs 目标态

| 能力 | 现状（过渡期） | 目标态 |
|---|---|---|
| 写路径 | 唯一守门人 = `legacy-python\scripts\novelos_create_project.py`（jsonschema 门 + BEGIN IMMEDIATE 单事务）；只维护不新增 | 插件 host `defineTool` JS 写门（node:sqlite + ajv + crypto），交付并全绿后整体删除 `legacy-python/` |
| 读路径（人类） | 浏览器打开 `plugin/client/project-wizard.html`（面板化前允许 file://）；viewer 仅有原型 | `dsh-novelos-viewer` 面板：sql.js(WASM) 内存只读，host 双只读路由 `GET /db-bytes` + `GET /manifest`（R1） |
| 读路径（agent） | 一次性 node:sqlite 只读查询 | 插件查询工具就绪后统一走插件 |
| 人类视图 | HTML(JS) 是唯一渲染器 | 不变 |

**路线图**：R1 插件实体化（读路径先行）→ R2 JS 写门（ajv 复用 `config/schemas/*.json` + node:sqlite 单事务 + crypto content_hash + vitest 等价迁移，三件套捆绑交付）→ R3 编排层适配。条目与退出条件见 [tasks/README.md](./tasks/README.md)。

**已退役清单**（不要寻找、不要重建）：`.venv`、`mcp/sqlite-mcp/`（Python MCP 通道）、`run_sqlite_mcp.cmd/.sh`、`.codex/config.toml`、`requirements-mcp.txt`、md 投影渲染器、`ui/`（三件套已迁 `plugin/client/`）、`documentation/`（已并入 `docs/`）。仓库无任何 MCP 配置需求。

## 目录结构

```text
.agents/skills/novel-*    会话编排层六个操作技能（project/planning/memory/writing/review/continuity）
adapters/                 harness 适配层，单源 adapters/source/harness.yaml
catalog/skills/           创作方法论 Catalog（onboarding/planning/writing/review/continuity/craft/expansions）
config/
  schemas/                JSON Schema 校验门（语言无关，JS 门直接复用的核心资产）
  agent-recipes.json      角色 × 方法论配方矩阵权威
  genre-packs.json        题材包
  system_archetypes.json  系统叙事原型
data/novelos-v2.db        权威 SQLite 库（变更前先备份；data/compositions/ 组装产物运行时生成）
db/migrations/            SQL 迁移留档 + schema.sql 基线（语言无关资产）
docs/                     文档（历史任务账本在 docs/archive/tasks/）
legacy-python/            过渡期暂存区：py 校验门脚本 + unittest 用例，只维护不新增，R2 后整体删除
plugin/client/            UI 资产三件套：project-wizard.html / project-wizard-data.js / kernel-roster.js
scripts/                  JS 工具脚本（现有 fix-dsh-projcache.mjs）；新增脚本一律 JS，禁止新建 .py
tasks/README.md           零 Python 路线图 + 重组裁决记录
```

## 快速上手

### 环境要求

- Node.js ≥ 22（内置 `node:sqlite`，agent 查库与未来 JS 门的基础）。
- 过渡期运行 legacy-python 校验门需系统 Python ≥ 3.11（**不建 venv**，直接用系统解释器；门依赖第三方库 `jsonschema`）。

### 创建小说项目（现状流程）

1. 浏览器打开 `plugin/client/project-wizard.html`。
2. 向导产出 `novelos.project.create.v3` JSON → 入口校验门校验（FAIL 拒绝）。
3. mode=create 先建核：内核融合 agent 产出 author_kernel → 分身派生 creator_signature → 经守门人单事务六表落库。

细节与角色分工见 [AGENTS.md](./AGENTS.md)「项目创建向导」；viewer 面板的实现规格见 [docs/novelos-viewer-design.md](./docs/novelos-viewer-design.md)。

### 查询数据库（agent 一次性只读查询）

```bash
node -e "const {DatabaseSync}=require('node:sqlite');const db=new DatabaseSync('data/novelos-v2.db');console.log(db.prepare('SELECT id FROM projects').all())"
```

读可随意，写必须走守门人（见下节）。人类浏览库内容的专用面板见路线图 R1。

### 组装方法论注入文本

已注册资产的注入文本一律由组装器产出（主干 + 条件模块 + 输入数据区 + 自检汇总），不 Read prompt.md、不手工拼装：

```bash
python legacy-python/scripts/novelos_compose_prompt.py --asset <asset> --project <id>
# 审查另加 --subject；修复重试加 --review-feedback + --round
```

配方矩阵权威在 `config/agent-recipes.json`；组装产物即主控 ↔ sub agent 的 ABI。

### 过渡期验证

```bash
python -m unittest discover -s legacy-python/tests -v
```

`legacy-python/tests` 是 JS 门重写时的**验收基准**（行为等价以这些用例的断言语义为准）。注意：仓库重组后部分证据类用例引用的归档路径尚待修复，套件暂非全绿，以 [legacy-python/README.md](./legacy-python/README.md) 与 [tasks/README.md](./tasks/README.md) 为准。

## 写库纪律（红线）

- **唯一守门人**：写库只能经 `legacy-python\scripts\novelos_create_project.py`（jsonschema 门 + BEGIN IMMEDIATE 单事务）。禁止手工 INSERT 绕过校验门直接写库。
- **写库三件事不变**：① ID 格式 `类型:uuid`；② 写 `resources.content` 必须 `CAST(? AS BLOB)`；③ 写 resource 必须同时计算 content_hash。
- **备份先行**：任何 schema 变更前先复制 `data/novelos-v2.db`。
- **FAIL 必须阻断**：任何校验门 FAIL 必须阻断退出；mismatch 仅警告放行 = 纸面化。
- **生产镜像只读**：`/Users/yiyi/github/novelos` 是生产环境，只读。
- **R2 之后**：唯一写入口收敛为插件 `defineTool`，agent 不再有任何裸 SQL 写通道；届时整体删除 `legacy-python/`，仓库达成零 Python。

## 文档索引

Agent 协作入口：

- [AGENTS.md](./AGENTS.md) — agent 行为规则、路由顺序、小说工作流（过渡期权威）
- [tasks/README.md](./tasks/README.md) — 零 Python 路线图（R1/R2/R3）与重组裁决记录

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
- [docs/novelos-viewer-design.md](./docs/novelos-viewer-design.md) — viewer 面板设计规格（R1 实现依据）
- [docs/novelos-viewer-prototype.html](./docs/novelos-viewer-prototype.html) — viewer 视觉原型
- [legacy-python/README.md](./legacy-python/README.md) — 过渡期暂存区内容、已退役清单与退出条件
- [docs/archive/tasks/](./docs/archive/tasks) — 历史任务账本（Task 06–39，py 时代考古参考，不再更新）
