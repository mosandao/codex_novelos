# 系统架构

## 产品范围

NovelOS 是面向本地单用户长篇小说创作的纯 Codex 系统。Codex 是唯一长期存在的 **主控智能体**；项目 Skill 提供方法，临时 sub agent 负责隔离推理，SQLite MCP（`execute_sql`）是数据库唯一入口，确定性算法由 `scripts/novelos_*.py` 承担。

当前没有独立 HTTP/Web 前端、账号体系、网络服务、邮件、定时任务或公开 SEO 页面。用户阅读入口采用由 SQLite 权威数据生成的 Markdown 项目文件夹；项目创建提供可直接打开的本地 HTML 向导。独立 HTML 只生成结构化 JSON，不建立第二套权威业务状态，也不替代投影，因此不建立 `emails.md`、`cron.md` 或 `seo.md`。

## 运行结构

```text
用户
  -> Codex 主控智能体
      -> 项目 Skill（.agents/skills）/ 创作方法论（catalog/skills）
      -> 临时 sub agent（规划/写作/审查/onboarding 等，只返回候选）
      -> SQLite MCP（execute_sql，数据库唯一读写入口）
          -> data/novelos-v2.db
      -> 确定性脚本 scripts/novelos_*.py（不调 LLM：hash/validate/projection/stale/delete）
      -> ui/project-wizard.html（本地向导，生成 JSON）
      -> novels/<项目目录>（可重建的用户只读投影）
```

## 技术栈

| 层 | 实现 | 责任 |
|---|---|---|
| 主控智能体 | Codex | 理解请求、路由、创建临时 sub agent、执行 SQL、调用确定性脚本 |
| Skill | `.agents/skills/*` | 6 个可复用业务流程（novel-project/planning/memory/writing/review/continuity），不持久化 |
| 创作方法论 | `catalog/skills/*` | 细粒度创作 Prompt（planning/writing/review/continuity/craft/expansions） |
| 数据库入口 | `mcp/sqlite-mcp/server.py`、FastMCP | 仅暴露 `execute_sql`，直接对 SQLite 执行 SQL |
| 确定性算法 | `scripts/novelos_*.py` | hash、book_soul 校验、投影渲染、stale 传播、项目删除；不调 LLM |
| Storage | SQLite | 权威业务数据（26 表，migration 016 后） |
| 项目创建向导 | `ui/project-wizard.html` | 收集项目约束并生成 `novelos.project.create.v1` JSON，不写数据库 |
| 用户投影 | `novels/<项目目录>`、Markdown | 从权威快照生成的可读规划、正文和连续性视图 |

SQLite MCP 不依赖模型 Provider，不保存 Prompt，不作语义选择。主控与 sub agent 用 SQL 直接读写核心业务表；长文本存为 `resources`（BLOB），工具控制信封只携带 ID、版本、Hash 和状态。

确定性脚本不依赖已退役的 `config/agents.yaml`（现为历史留档），也不依赖 NovelOS MCP——`novelos_render_projection.py` 等均为裸 sqlite3、零 MCP 依赖。

用户项目文件夹不是 Storage。它只能由 `scripts/novelos_render_projection.py` 从权威快照单向生成，可以删除并重新生成；直接修改其中的 Markdown 不会回写数据库，也不得用于绕过规划锁定、章节接受或连续性晋升。`规划/`、`正文/`、`连续性/` 与 `创作约束/` 是当前权威视图；`创作约束/作者签名.md` 来自项目精确绑定，`创作约束/本书创作灵魂.md` 只来自 locked Direction。

## 信任边界

- 用户到 Codex：用户决定创作意图和最终接受范围。
- 主控智能体 到临时 sub agent：主控只提供最小输入与必要只读上下文；临时 sub agent 没有数据库写入权限，只返回候选，由主控落库。
- 主控智能体 到 SQLite：所有持久化由主控经 `execute_sql` 完成；落库前用 jsonschema 校验签名、用确定性脚本算 Hash，SQL 状态机约束状态流转。
- 本地向导到主控：独立 HTML 只输出 `novelos.project.create.v1` JSON；主控解析后创建 onboarding_agent 做原型融合，再用 SQL 原子落库。
- 主控 到 用户投影：投影由 `novelos_render_projection.py` 确定性渲染、写 `manifest.json` 逐文件 Hash，原子替换；其他层不构造权威投影。
- 来源仓库到当前仓库：`/Users/yiyi/github/novelos` 只读；迁移必须绑定固定 commit、Hash 和授权状态。

本地 V1 没有身份认证、session、tenant claim 或行级安全。操作系统文件权限和 Codex 工作区权限是外层信任边界。

## 权威数据

- 正式数据库：`data/novelos-v2.db`，schema 由 `db/migrations/` 顺序前向迁移管理（migration 016 删除了 `traces`/`agent_runs`/`authority_commits` 等门禁表后为 26 表）。
- 系统叙事原型：`config/system_archetypes.json`（18 个原型）。
- 签名校验 schema：`config/schemas/`（含 `creator-signature.schema.json`、`book-soul.schema.json`）。
- `config/agents.yaml`：NovelOS MCP 时代的 Agent 角色定义，**历史留档**，无脚本依赖。
- 顶层业务 Skill：`.agents/skills` 下固定 6 个。
- 用户展示目录：默认 `novels/`；属于可重建派生数据，不进入权威备份，也不替代灾备 JSONL 导出。

## 已知风险与假设

- `.codex/config.toml` 只注册 SQLite MCP（`mcp_servers.sqlite`，经 `scripts/run_sqlite_mcp.sh` 启动）；NovelOS MCP 已彻底退役，重启会因门禁表已 DROP 而崩溃。
- sub agent 的运行上下文隔离由主控正确创建新的 Codex 临时 Agent 保证；`context_id` 类字段不存在于当前架构，隔离不靠进程内密码学自证。
- Writer 与上下文构建智能体的质量实验已延期；Writer 暂限完整章节或长场景，上下文构建智能体暂限跨卷、多线、事实冲突或上下文溢出，部分实验结果不构成质量结论。
- 项目创建向导：V3 要求 `derive` 作者签名模式，页面按项目约束确定性推荐 Top 3 系统原型。单原型由 onboarding_agent 确定性判定 parent；多原型（≥2）由 onboarding_agent 做 LLM 深度融合，产出 `creator_derivation_candidate`，主控用 jsonschema 校验签名合规后 SQL 落库。落库事务不执行运行时 LLM 生成，LLM 只在 onboarding_agent 的 Codex run 内运行；也不创建规划资产；本地 `file://` 页面可以生成 JSON，但不直接写入数据库。
- `creator_signature` 是用户拥有的跨项目、不可变版本配置，不是 Agent 或规划资产。`book_soul` 是 Story Direction 的组成部分，由方向智能体生成并走既有审查/锁定流程。显式 rebind 会递归标记 Direction 及后代为 `stale`，但不自动重生成。
- 用户项目文件夹投影由 `scripts/novelos_render_projection.py` 单向渲染 Markdown，支持原子替换、路径逃逸拒绝与 `manifest.json` 逐文件 Hash 校验；直接修改投影文件不回写数据库。项目删除由 `scripts/novelos_delete_project.py` 完成，详见 [关键流程·删除项目](./flows.md)。
- 仓库当前没有 CI；测试是本地交付门禁，不应被描述为受保护分支检查。

## 相关文档

- [关键流程](./flows.md)
- [权限矩阵](./permissions.md)
- [变量与配置](./variables.md)
- [测试覆盖](./tests.md)
- [Agent 与自动化](./automation.md)
- [世界观与规划层设计重构讨论稿](./worldbuilding-redesign.md)
