# 系统架构

## 产品范围

NovelOS V1 是面向本地单用户长篇小说创作的纯 Codex 系统。Codex 是唯一长期存在的 Main Agent；项目 Skill 提供方法，统一 `novelos` MCP 提供确定性工具和 Resource，SQLite 保存权威状态。

当前没有 UI、账号体系、网络服务、邮件、定时任务或公开 SEO 页面，因此不建立 `emails.md`、`cron.md` 或 `seo.md`。

## 运行结构

```text
用户
  -> Codex Main Agent
      -> 项目 Skill / Catalog Prompt
      -> 临时业务 Agent（只返回候选）
      -> novelos MCP（唯一权威读写边界）
          -> data/novelos-v2.db
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

MCP 不依赖模型 Provider，不保存 Prompt，不作语义选择。长文本保存在不可变 Resource，工具控制信封只携带 ID、版本、Hash、状态和 Resource ref。

## 信任边界

- 用户到 Codex：用户决定创作意图和最终接受范围。
- Main Agent 到临时 Agent：Main 只提供配置白名单允许的只读工具和最小输入；临时 Agent 没有权威提交权限。
- Main Agent 到 MCP：所有持久化动作在 MCP 服务端重新验证，不信任 Prompt 或 Agent 自述。
- MCP 到 SQLite：只有 `novelos_mcp` 导入 `sqlite3`；业务 Agent 和 Skill 不直接访问数据库。
- 来源仓库到当前仓库：`/Users/yiyi/github/novelos` 只读；迁移必须绑定固定 commit、Hash 和授权状态。

本地 V1 没有身份认证、session、tenant claim 或行级安全。操作系统文件权限和 Codex 工作区权限是外层信任边界；MCP 内部仍按 Main/临时 Agent 契约限制工具面。

## 权威数据

- 正式数据库：`data/novelos-v2.db`，当前 Schema 9。
- Legacy 迁移来源：`data/migration/backend-novelos-aaadc9bedf499e.db`，只读冻结。
- `seed.db`：固定 commit/Hash 的授权副本位于 `mcp/novelos/resources/seed.db`，只通过 inventory 校验后的只读 Knowledge 工具访问。
- Agent 契约：`config/agents.yaml`。
- 顶层业务 Skill：`.agents/skills` 下固定 6 个。

## 已知风险与假设

- `.codex/config.toml` 仍指向旧 `novelos-memory` Server；切换前新旧 Runtime 暂时并存，Task 05 禁止把两者同时作为默认生产入口。
- seed 授权只覆盖当前固定 commit/Hash 的本地复制和生产检索，不扩展到公开再分发或来源仓库的其他未核权内容。
- Agent run 的 `context_id` 和工具白名单可证明协议隔离，真实模型上下文隔离仍依赖 Main Agent 正确创建新的 Codex 临时 Agent。
- Writer 与 Context Builder 的最终保留和触发频率尚未经过真实 70 样本质量实验。
- 仓库当前没有 CI；测试是本地交付门禁，不应被描述为受保护分支检查。

## 相关文档

- [关键流程](./flows.md)
- [权限矩阵](./permissions.md)
- [变量与配置](./variables.md)
- [测试覆盖](./tests.md)
- [Agent 与自动化](./automation.md)
