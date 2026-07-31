# 权限矩阵

## 角色

| 角色 | 来源 | 生命周期 | 权限原则 |
|---|---|---|---|
| 用户 | Codex 当前任务 | 外部 | 提供意图并决定是否继续，不直接写 SQLite |
| 主控智能体 | Codex | 唯一常驻 | 可调用全部 MCP 工具；必须遵守 Review 和版本门禁 |
| 规划资产 Agent | `config/agents.yaml` | 临时 | 只读；只生产自己拥有的候选或上游 change proposal |
| 写作智能体 | `config/agents.yaml` | 临时 | 只读；只返回正文候选 |
| 审查智能体 | `config/agents.yaml` | 临时 | 只读；只返回 Review Receipt candidate |
| 上下文构建智能体 | `config/agents.yaml` | 临时 | 只读；只返回上下文包 |
| MCP | 本地 stdio 进程 | 按任务 | 唯一数据库执行者，实施硬门禁 |

V1 没有用户登录、tenant、管理员角色或 RLS。Scope 来自 Main 提供并由 MCP 查询数据库关系重新确认的 `project_id`、资源 ID 和版本，而不是不可信 token claim。

## 操作矩阵

| 资源/操作 | Main | 规划/Writer/Context | Reviewer | MCP 强制条件 |
|---|---:|---:|---:|---|
| 读取 Project/Canon/Planning/Catalog | 允许 | 白名单内允许 | 白名单内允许 | ID 存在、项目关系有效 |
| 打开/提交项目创建向导 | 允许 | 禁止 | 禁止 | `project.wizard.submit` 仅接受 V2 固定选项、题材匹配二级方向、最多两项美学风格和 10,000 字资料 |
| 删除无权威项目 | 允许 | 禁止 | 禁止 | 当前 `expected_version`、无运行中 Trace、无 `authority_commits`、投影 manifest 归属匹配 |
| 创建 Agent run | 允许 | 禁止 | 禁止 | 临时角色、最小输入、spawn gate |
| 登记规划候选 | 允许 | 禁止 | 禁止 | 完成的唯一 owner run、输出一致、锁定上游 |
| 锁定规划资产 | 允许 | 禁止 | 禁止 | 精确 Review Receipt、Profile、无 blocking finding、同一 Trace |
| 创建章节草稿 | 允许 | 禁止 | 禁止 | 完整章节绑定 Writer run |
| 接受章节 | 允许 | 禁止 | 禁止 | 精确正文 Hash、approved Review、同一 Trace |
| 记录 Review | 允许 | 禁止 | 禁止直接写 | 完成的独立 Reviewer run 与输出一致 |
| 准备质量评测 subject | 允许 | 禁止 | 只读 subject | 运行中 Trace、不可变输出、完成的 Producer runs、精确 Profile |
| 提交 Entity mutation | 允许 | 禁止 | 禁止 | 权威来源、Review、目标版本均有效 |
| 晋升连续性 | 允许 | 禁止 | 禁止 | accepted 章节、Authority Snapshot、Review、单事务 |
| 直接 SQLite | 禁止 | 禁止 | 禁止 | 仅 MCP Storage 层允许 |

## 工具白名单

临时 Agent 的精确工具列表以 `config/agents.yaml` 为唯一机器可校验来源。生产 Agent 白名单只包含 `planning.get/list`、Memory、Knowledge 和 Skill Catalog 的只读方法；只有 审查智能体 额外拥有 `review.get_subject`。任何临时 Agent 都不能调用 `project.wizard.*`、`project.delete`、`resource.create`、`review.prepare_subject/record`、`*.lock`、`*.accept`、`*.commit`、`*.promote` 或 Agent 生命周期工具。

## 失败关闭

- 未知 role、输入字段、输出类型或 Schema 字段拒绝。
- Agent 失败或超时不得携带部分输出。
- Trace 存在运行中 Agent 时不能结束。
- change proposal 必须绑定当前项目 locked 上游的 ID、版本和 Hash。
- `project.delete` 在项目存在 authority commit 或运行中 Trace 时失败关闭；投影目录缺少、损坏或归属不符的 `manifest.json` 时同样拒绝删除。
- 生产 seed 只允许使用授权审计绑定的固定 commit/Hash 副本；runner 禁止环境变量替换，MCP 同时校验 frozen inventory、只读连接和 sidecar。
