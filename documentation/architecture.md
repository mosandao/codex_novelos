# 系统架构

## 产品范围

NovelOS V1 是面向本地单用户长篇小说创作的纯 Codex 系统。Codex 是唯一长期存在的 Main Agent；项目 Skill 提供方法，统一 `novelos` MCP 提供确定性工具和 Resource，SQLite 保存权威状态。

当前没有 UI、账号体系、网络服务、邮件、定时任务或公开 SEO 页面。用户阅读入口采用由 SQLite 权威数据生成的 Markdown 项目文件夹，HTML UI 不在当前范围，因此不建立 `emails.md`、`cron.md` 或 `seo.md`。

## 运行结构

```text
用户
  -> Codex Main Agent
      -> 项目 Skill / Catalog Prompt
      -> 临时业务 Agent（只返回候选）
      -> novelos MCP（唯一权威读写边界）
          -> data/novelos-v2.db
          -> novels/<项目目录>（可重建的用户只读投影）
          -> catalog/skills（只读）
          -> config/agents.yaml（只读契约）
```

## 技术栈

| 层 | 实现 | 责任 |
|---|---|---|
| Main Agent | Codex | 理解请求、路由、创建临时 Agent、调用权威工具 |
| Skill | `.agents/skills/*` | 可复用业务流程，不持久化 |
| Catalog | `catalog/skills/*` | 细粒度 Prompt、输入输出 Schema 和来源信息 |
| MCP | `mcp/novelos`、FastMCP | Schema、Hash、版本、Review、事务和 Resource |
| Storage | SQLite | 权威数据、append-only Trace 和 `authority_commits` |
| 用户投影 | `novels/<项目目录>`、Markdown | 从权威快照生成的可读规划、正文和连续性视图 |

MCP 不依赖模型 Provider，不保存 Prompt，不作语义选择。长文本保存在不可变 Resource，工具控制信封只携带 ID、版本、Hash、状态和 Resource ref。

用户项目文件夹不是 Storage。它只能由 MCP 从一致的 Authority Snapshot 单向生成，可以删除并重新生成；直接修改其中的 Markdown 不会回写数据库，也不得用于绕过规划锁定、章节接受或连续性晋升门禁。默认视图只包含 `locked` 规划资产、`accepted` 正文和已晋升连续性状态。

## 信任边界

- 用户到 Codex：用户决定创作意图和最终接受范围。
- Main Agent 到临时 Agent：Main 只提供配置白名单允许的只读工具和最小输入；临时 Agent 没有权威提交权限。
- Main Agent 到 MCP：所有持久化动作在 MCP 服务端重新验证，不信任 Prompt 或 Agent 自述。
- MCP 到 SQLite：只有 `novelos_mcp` 导入 `sqlite3`；业务 Agent 和 Skill 不直接访问数据库。
- MCP 到用户投影：MCP 负责快照、确定性渲染、路径约束、Hash 清单和原子替换；其他层不直接构造权威投影。
- 来源仓库到当前仓库：`/Users/yiyi/github/novelos` 只读；迁移必须绑定固定 commit、Hash 和授权状态。

本地 V1 没有身份认证、session、tenant claim 或行级安全。操作系统文件权限和 Codex 工作区权限是外层信任边界；MCP 内部仍按 Main/临时 Agent 契约限制工具面。

## 权威数据

- 正式数据库：`data/novelos-v2.db`，当前 Schema 9。
- Legacy 迁移来源：`data/migration/backend-novelos-aaadc9bedf499e.db`，只读冻结。
- `seed.db`：固定 commit/Hash 的授权副本位于 `mcp/novelos/resources/seed.db`，只通过 inventory 校验后的只读 Knowledge 工具访问。
- Agent 契约：`config/agents.yaml`。
- 顶层业务 Skill：`.agents/skills` 下固定 6 个。
- 用户展示目录：默认 `novels/`；属于可重建派生数据，不进入权威备份，也不替代灾备 JSONL 导出。

## 已知风险与假设

- `.codex/config.toml` 只注册统一 `novelos` Server，仓库不保留第二套 Agent Runtime。
- seed 授权只覆盖当前固定 commit/Hash 的本地复制和生产检索，不扩展到公开再分发或来源仓库的其他未核权内容。
- Agent run 的 `context_id` 和工具白名单可证明协议隔离，真实模型上下文隔离仍依赖 Main Agent 正确创建新的 Codex 临时 Agent。
- Writer 与 Context Builder 的质量实验已延期；Writer 暂限完整章节或长场景，Context Builder 暂限跨卷、多线、事实冲突或上下文溢出，部分实验结果不构成质量结论。
- 用户项目文件夹已确定为展示方向，但生成工具仍属于 Task 06，完成验收前不得描述为已接通能力。
- 仓库当前没有 CI；测试是本地交付门禁，不应被描述为受保护分支检查。

## 相关文档

- [关键流程](./flows.md)
- [权限矩阵](./permissions.md)
- [变量与配置](./variables.md)
- [测试覆盖](./tests.md)
- [Agent 与自动化](./automation.md)
