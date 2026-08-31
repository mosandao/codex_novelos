# 系统架构

> ✅ 零 Python 终态：写路径 = 主控 node:sqlite 受控直写（插件 defineTool 门已随 `plugin/` 退役）；组装器已 JS 化；`legacy-python/` 与 `.venv` 已删除。路线与验证记录见 ../tasks/README.md。

## 产品范围

NovelOS 是面向本地单用户长篇小说创作的**主控智能体编排系统**（原「纯 Codex 系统」表述已中性化）。主控智能体是唯一长期存在的常驻角色：项目 Skill 提供方法，临时 sub agent 负责隔离推理。数据库写路径 = 主控 node:sqlite 受控直写（`BEGIN IMMEDIATE` + `PRAGMA foreign_keys=ON`，SQL 模板唯一来源 `.agents/skills/novel-project/sql-reference.md`，落库前对照 `config/schemas/*.json` 自查）；读路径 = 一次性 node:sqlite 只读查询或 novels/ 投影。确定性工具 = `scripts/novelos-compose-prompt.mjs` 组装器与 `scripts/test-*.mjs` 测试脚本。

当前没有独立 HTTP/Web 前端、账号体系、网络服务、邮件、定时任务或公开 SEO 页面。人类视图遵循**单渲染器原则**：md 投影是唯一渲染器——`scripts/novelos-render-projection.mjs`（node:sqlite 只读）把权威库单向渲染为 `novels/` 项目文件夹，可删除重建、改文件不回写；viewer 面板已退役，不要重建。项目创建由主控与用户交互确认项目约束（原 `plugin/client/project-wizard.html` 本地向导已随插件退役），不建立第二套权威业务状态，因此不建立 `emails.md`、`cron.md` 或 `seo.md`。

## 运行结构

```text
用户
  -> 主控智能体
      -> 项目 Skill（.agents/skills）/ 创作方法论（catalog/skills）
      -> 临时 sub agent（规划/写作/审查/onboarding 等，只返回候选）
      -> 写路径：主控 node:sqlite 受控直写（sql-reference.md 模板 + schemas 自查）
          -> data/novelos-v2.db（BEGIN IMMEDIATE + PRAGMA foreign_keys=ON 单事务）
      -> 读路径：一次性 node:sqlite 只读查询 / novels/ 投影
      -> 确定性工具：scripts/novelos-compose-prompt.mjs 组装器 + scripts/test-*.mjs
```

## 技术栈

| 层 | 实现 | 责任 |
|---|---|---|
| 主控智能体 | 当前 harness 会话 | 理解请求、路由、创建临时 sub agent、node:sqlite 受控直写落库、调用组装器与只读查询 |
| Skill | `.agents/skills/*` | 6 个可复用业务流程（novel-project/planning/memory/writing/review/continuity），不持久化 |
| 创作方法论 | `catalog/skills/*` | 细粒度创作 Prompt（planning/writing/review/continuity/craft/expansions） |
| 数据库写入口 | 主控 node:sqlite 受控直写 + `scripts/novelos-gate.mjs` 机器门 | 关键状态写入优先走门（commit-review/lock-asset/accept-chapter/propagate-stale/register-characters/validate-asset/open-adjudication/resolve-adjudication），门未覆盖的走单事务受控直写；Python MCP 通道与插件门已删除 |
| 确定性算法 | `scripts/novelos-compose-prompt.mjs` 组装器 + `scripts/novelos-gate.mjs` 机器门 + `scripts/test-*.mjs` + 主控自查 | 方法论组装、content_hash（node:crypto）、schema 自查、stale 传播、人物注册表、裁决物化、项目删除；不调 LLM |
| Storage | SQLite | 权威业务数据（27 表，migration 022 终态） |
| 项目创建向导 | 主控与用户交互确认 | 收集项目约束（频道级联/表里基调/作者内核 select/create 双模式）产出 `novelos.project.create.v3` JSON，落库前对照 schema 自查 |
| 人类视图 | md 投影渲染器 `scripts/novelos-render-projection.mjs`（node:sqlite 只读） | 单向渲染 `novels/` 项目文件夹 + manifest 逐文件 SHA-256；可删除重建、不回写；viewer 面板已退役 |

组装器与测试脚本不依赖模型 Provider，不保存 Prompt，不作语义选择；长文本存为 `resources`（BLOB），控制信封只携带 ID、版本、Hash 和状态。组装器不依赖已退役的 `config/agents.yaml`（现为历史留档），均为 node 标准库实现、零 MCP 依赖；Markdown 投影已按用户裁决恢复为 JS 实现（`scripts/novelos-render-projection.mjs`）。

Markdown 投影层已按用户裁决恢复（记录见 `../tasks/README.md`「投影恢复裁决记录」）：`scripts/novelos-render-projection.mjs` 把权威库单向渲染为 `novels/`（只读派生、不构成第二存储、改文件不回写）；viewer 面板已退役，不要重建。

## 信任边界

- 用户到 Codex：用户决定创作意图和最终接受范围。
- 主控智能体 到临时 sub agent：主控只提供最小输入与必要只读上下文；临时 sub agent 没有数据库写入权限，只返回候选，由主控落库。
- 主控智能体 到 SQLite：所有持久化由主控完成——机器写门优先（`scripts/novelos-gate.mjs`）+ node:sqlite 受控直写（sql-reference.md 模板 + schemas 自查 + node:crypto Hash + 状态机纪律）；sub agent 没有数据库写通道。
- 用户到主控：主控与用户交互确认产出 `novelos.project.create.v3` JSON；主控解析后创建 onboarding_agent 做原型融合，再对照 schema 自查后原子落库（projects.metadata_json 写入 setup 快照供后续阶段读取）。
- 主控 到 人类视图：md 投影渲染器（node:sqlite 只读）单向派生 novels/，可删除重建、不回写；除投影外没有任何层构造人类视图（单渲染器原则）。
- 来源仓库到当前仓库：`/Users/yiyi/github/novelos` 只读；迁移必须绑定固定 commit、Hash 和授权状态。

本地 V1 没有身份认证、session、tenant claim 或行级安全。操作系统文件权限和 Codex 工作区权限是外层信任边界。

## 权威数据

- 正式数据库：`data/novelos-v2.db`，schema 由 `db/migrations/` 顺序前向迁移管理（migration 022 终态为 27 表）。
- 系统叙事原型：`config/system_archetypes.json`（18 个原型）。
- 签名校验 schema：`config/schemas/`（含 `creator-signature.schema.json`、`book-soul.schema.json`）。
- `config/agents.yaml`：NovelOS MCP 时代的 Agent 角色定义，**历史留档**，无脚本依赖。
- 顶层业务 Skill：`.agents/skills` 下固定 6 个。
- 人类视图：md 投影渲染器（node:sqlite 只读）单向渲染 novels/，派生文件可重建、不回写；灾备 = 直接复制 db 文件（schema 变更前必做，见 AGENTS.md）。

## 已知风险与假设

- Python MCP 通道与 legacy-python 校验门均已删除（`mcp/sqlite-mcp/`、`.codex/config.toml` 注册、`run_sqlite_mcp.*` 启动脚本、`legacy-python/`、`.venv`）：读路径 = 一次性 node:sqlite 查询（人类可看 novels/ 投影）；写路径 = 机器写门 `scripts/novelos-gate.mjs` 优先 + node:sqlite 受控直写（见 README.md「写库纪律」与 AGENTS.md 第四约定）。不要再寻找或重建 MCP 注册或 Python 门。
- sub agent 的运行上下文隔离由主控正确创建新的 Codex 临时 Agent 保证；`context_id` 类字段不存在于当前架构，隔离不靠进程内密码学自证。
- Writer 与上下文构建智能体的质量实验已延期；Writer 暂限完整章节或长场景，上下文构建智能体暂限跨卷、多线、事实冲突或上下文溢出，部分实验结果不构成质量结论。
- 项目创建向导：主控与用户交互确认项目约束（频道/平台/题材/表里基调/作者内核 select 或 create 双模式），产出 `novelos.project.create.v3` JSON；单原型由 onboarding_agent 确定性判定 parent，多原型（≥2）由 onboarding_agent 做 LLM 深度融合，产出 `creator_derivation_candidate`；主控对照 schema 自查后单事务落库。落库事务不执行运行时 LLM 生成，LLM 只在 onboarding_agent 的 run 内运行；也不创建规划资产。
- `creator_signature` 是用户拥有的跨项目、不可变版本配置，不是 Agent 或规划资产。`book_soul` 是 Story Direction 的组成部分，由方向智能体生成并走既有审查/锁定流程。显式 rebind 会递归标记 Direction 及后代为 `stale`，但不自动重生成。
- Markdown 投影已按用户裁决恢复（`scripts/novelos-render-projection.mjs`，记录见 ../tasks/README.md「投影恢复裁决记录」）；md 是唯一人类视图，viewer 面板与 HTML 渲染器已退役，不要重建。项目删除由主控 node:sqlite 受控直写完成（依赖逆序删），详见 [关键流程·删除项目](./flows.md)。
- 仓库当前没有 CI；测试是本地交付门禁，不应被描述为受保护分支检查。零 Python 终态验证口径：`node scripts/test-guardrails.mjs`（409 断言）；`node scripts/test-gate.mjs`（70 断言）；`node scripts/test-compose-prompt.mjs`（28 用例）；`node scripts/test-render-projection.mjs`（48 用例）；`node scripts/test-prose-fingerprint.mjs`（49 用例）；`node scripts/test-verify-review-evidence.mjs`（15 用例）；`node scripts/novelos-catalog-manifest.mjs --check`（360 文件）；`node scripts/novelos-canary.mjs --compare docs/knowledge/canary-baseline.json`。

## 相关文档

- [关键流程](./flows.md)
- [权限矩阵](./permissions.md)
- [变量与配置](./variables.md)
- [测试覆盖](./tests.md)
- [Agent 与自动化](./automation.md)
- [世界观与规划层设计重构讨论稿](./worldbuilding-redesign.md)
