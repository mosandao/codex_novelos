# 系统架构

## 产品范围

NovelOS V1 是面向本地单用户长篇小说创作的纯 Codex 系统。Codex 是唯一长期存在的 主控智能体；项目 Skill 提供方法，统一 `novelos` MCP 提供确定性工具和 Resource，SQLite 保存权威状态。

当前没有独立 HTTP/Web 前端、账号体系、网络服务、邮件、定时任务或公开 SEO 页面。用户阅读入口采用由 SQLite 权威数据生成的 Markdown 项目文件夹；项目创建提供可直接打开的本地 HTML 向导，并保留 MCP Apps 资源兼容入口。独立 HTML 只生成结构化 JSON，不建立第二套权威业务状态，也不替代投影，因此不建立 `emails.md`、`cron.md` 或 `seo.md`。

## 运行结构

```text
用户
  -> Codex 主控智能体
      -> 项目 Skill / Catalog Prompt
      -> 临时业务 Agent（只返回候选）
      -> novelos MCP（唯一权威读写边界）
          -> data/novelos-v2.db
          -> ui://novelos/project-wizard-v3.html（MCP Apps 项目创建向导）
          -> novels/<项目目录>（可重建的用户只读投影）
          -> catalog/skills（只读）
          -> config/agents.yaml（只读契约）
```

## 技术栈

| 层 | 实现 | 责任 |
|---|---|---|
| 主控智能体 | Codex | 理解请求、路由、创建临时 Agent、调用权威工具 |
| Skill | `.agents/skills/*` | 可复用业务流程，不持久化 |
| Catalog | `catalog/skills/*` | 细粒度 Prompt、输入输出 Schema 和来源信息 |
| MCP | `mcp/novelos`、FastMCP | Schema、Hash、版本、Review、事务和 Resource |
| Storage | SQLite | 权威数据、append-only Trace 和 `authority_commits` |
| 项目创建向导 | MCP Apps resource、`project-wizard.html` | 收集项目约束并调用 `project.wizard.submit`，不保存独立前端状态 |
| 用户投影 | `novels/<项目目录>`、Markdown | 从权威快照生成的可读规划、正文和连续性视图 |

MCP 不依赖模型 Provider，不保存 Prompt，不作语义选择。长文本保存在不可变 Resource，工具控制信封只携带 ID、版本、Hash、状态和 Resource ref。

MCP 的稳定服务入口是 `novelos_mcp.service.NovelOSService`。实现由 `service/__init__.py` 聚合 projects、creators、planning、chapters、reviews、agents、memory、projection 8 个领域 Mixin；共享事务、校验和审计 helper 位于 `_ServiceInternals`。原单文件 `service.py` 已移除，外部导入路径、五参数构造签名和工具方法保持不变。`server.py` 只负责 81 条工具直连和 1 个 wizard 编排，不承载领域逻辑。

`config/agents.yaml` 的 `review_profile_routes` 是 Profile 名唯一注册表，roles、`cross_consistency_gate` 与 `review_profile_bindings` 只引用注册 key。`AgentContractStore` 在启动时精确验证这些消费者，并为规划资产、章节接受、连续性晋升和 Entity 提交提供运行时查询。包级 `PLANNING_REVIEW_PROFILES` 仅是由默认配置派生的兼容快照，自定义 `agent_contract_path` 下的 Service 不读取它作为业务权威。

用户项目文件夹不是 Storage。它只能由 MCP 从一致的 Authority Snapshot 单向生成，可以删除并重新生成；直接修改其中的 Markdown 不会回写数据库，也不得用于绕过规划锁定、章节接受或连续性晋升门禁。`规划/`、`正文/`、`连续性/` 与 `创作约束/` 是当前权威视图；`创作约束/作者签名.md` 来自项目精确绑定，`创作约束/本书创作灵魂.md` 只来自 locked Direction。`候选/`、`产出/` 与 `档案/` 分别保存候选诊断、全部中间产出/完成 Agent 输出，以及已锁定规划的可读审计溯源。

## 信任边界

- 用户到 Codex：用户决定创作意图和最终接受范围。
- 主控智能体 到临时 Agent：Main 只提供配置白名单允许的只读工具和最小输入；临时 Agent 没有权威提交权限。
- 主控智能体 到 MCP：所有持久化动作在 MCP 服务端重新验证，不信任 Prompt 或 Agent 自述。
- MCP 到 SQLite：只有 `novelos_mcp` 导入 `sqlite3`；业务 Agent 和 Skill 不直接访问数据库。
- 本地向导到 MCP：独立 HTML 只输出 `novelos.project.create.v1` JSON；Main 解析 `setup` 后通过 `project.wizard.submit` 写入，保持 MCP 原子事务和校验门禁。
- MCP 到用户投影：MCP 负责快照、确定性渲染、路径约束、Hash 清单和原子替换；其他层不直接构造权威投影。
- 来源仓库到当前仓库：`/Users/yiyi/github/novelos` 只读；迁移必须绑定固定 commit、Hash 和授权状态。

本地 V1 没有身份认证、session、tenant claim 或行级安全。操作系统文件权限和 Codex 工作区权限是外层信任边界；MCP 内部仍按 Main/临时 Agent 契约限制工具面。

## 权威数据

- 正式数据库：`data/novelos-v2.db`，当前 Schema 12。
- Legacy 迁移来源：`data/migration/backend-novelos-aaadc9bedf499e.db`，只读冻结。
- `seed.db`：固定 commit/Hash 的授权副本位于 `mcp/novelos/resources/seed.db`，只通过 inventory 校验后的只读 Knowledge 工具访问。
- Agent 契约：`config/agents.yaml`。
- 顶层业务 Skill：`.agents/skills` 下固定 6 个。
- 用户展示目录：默认 `novels/`；属于可重建派生数据，不进入权威备份，也不替代灾备 JSONL 导出。

## 已知风险与假设

- `.codex/config.toml` 只注册统一 `novelos` Server，仓库不保留第二套 Agent Runtime。
- seed 授权只覆盖当前固定 commit/Hash 的本地复制和生产检索，不扩展到公开再分发或来源仓库的其他未核权内容。
- Agent run 的 `context_id` 只标识系统生成的 run context，不能证明真实模型上下文隔离；真实隔离仍依赖 主控智能体 正确创建新的 Codex 临时 Agent。权威提交（lock/accept/promote）路径按 `runtime.enforcement` 处理 `isolation_evidence`：默认 lenient 在同一事务记录 warning Trace step 后放行，strict 模式缺凭据才阻断。Trace 串联、独立 `review_agent` run、不可变 subject/hash、Review 输出绑定和上游 locked 等检查始终强制。该凭据仍是声明性证明，不能由进程内密码学自证真实隔离。
- Writer 与 上下文构建智能体 的质量实验已延期；Writer 暂限完整章节或长场景，上下文构建智能体 暂限跨卷、多线、事实冲突或上下文溢出，部分实验结果不构成质量结论。
- 项目创建向导已接通：以 Task 09 的“系统叙事原型 + 项目化最小派生”替代了直接新建与复用；V3 要求 `derive` 作者签名模式，页面按项目约束确定性推荐 Top 3 系统原型。单原型经 `project.wizard.reconcile_archetypes` 确定性融合；多原型（≥2）由临时 `onboarding_agent` 做 LLM 深度融合，再经 reconcile 确定性收口（Task 12）。MCP 在同一事务中创建项目与精确 Creator Profile revision/Hash 绑定；二级方向仍是随一级题材切换的静态 LLM 预生成候选。落库事务不执行运行时 LLM 生成，LLM 只在 `onboarding_agent` 的 Codex run 内运行；也不创建规划资产；本地 `file://` 页面可以生成 JSON，但不直接写入数据库。

- `creator_signature` 是用户拥有的跨项目、不可变版本配置，不是 Agent 或规划资产。`book_soul` 是 Story Direction 的组成部分，由方向智能体生成并走既有独立 Review/lock 门禁。显式 rebind 会递归失效 Direction 及后代，但不会自动重生成。
- 用户项目文件夹投影已接通（`projection.*` 工具集）：从一致的 Authority Snapshot 单向渲染 Markdown，支持原子替换、路径/符号链接逃逸拒绝与 manifest 逐文件 Hash 校验；直接修改投影文件不回写数据库。`project.delete` 只在无活动 Trace、无 authority commit 且版本匹配时删除项目，并只删除 manifest 归属匹配的投影。
- 仓库当前没有 CI；测试是本地交付门禁，不应被描述为受保护分支检查。

## 相关文档

- [关键流程](./flows.md)
- [权限矩阵](./permissions.md)
- [变量与配置](./variables.md)
- [测试覆盖](./tests.md)
- [Agent 与自动化](./automation.md)
