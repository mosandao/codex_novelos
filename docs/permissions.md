# 权限矩阵

> ⚠️ 零 Python 过渡期版本（重组于本轮）：写路径门暂存 legacy-python/，R2 交付后本文档随 JS 门收敛。路线图见 ../tasks/README.md。

## 角色

| 角色 | 来源 | 生命周期 | 权限原则 |
|---|---|---|---|
| 用户 | 当前 harness 会话 | 外部 | 提供意图并决定是否继续，不直接写 SQLite |
| 主控智能体 | 当前 harness 会话 | 唯一常驻 | 唯一数据库执行者：写唯一经 `legacy-python/scripts/novelos_create_project.py` 校验门及受控 SQL，读用一次性 node:sqlite 查询或 viewer 面板（Python MCP 已删除）；必须遵守审查前置、版本/Hash 与状态机约束 |
| 规划资产 Agent | 主控用 Agent 工具创建 + 注入 `catalog/skills` 方法论 | 临时 | 无数据库权限；只返回自己拥有的候选或上游 change proposal |
| 写作智能体 | 主控用 Agent 工具创建 | 临时 | 无数据库权限；只返回正文候选 |
| 审查智能体 | 主控用 Agent 工具创建（独立上下文） | 临时 | 无数据库权限；只返回审查意见 |
| 上下文构建智能体 | 主控用 Agent 工具创建 | 临时 | 无数据库权限；只返回上下文包 |
| 引导融合智能体（onboarding） | 主控用 Agent 工具创建 | 临时 | 无数据库权限；只返回 `creator_derivation_candidate` |

V1 没有用户登录、tenant、管理员角色或 RLS。Scope 来自主控查询数据库关系重新确认的 `project_id`、资源 ID 和版本，而不是不可信 token claim。

## 操作矩阵

主控是唯一数据库执行者；sub agent 在所有写操作上都是「禁止直接写」（它们只返回候选，由主控落库）。

| 资源/操作 | 主控 | 规划/Writer/Context/Onboarding | Reviewer | 主控落库前置条件 |
|---|---:|---:|---:|---|
| 读取 Project/Canon/Planning/Catalog | 允许（SQL/Read） | 无直接 DB 权限（主控注入上下文） | 无直接 DB 权限（主控注入 subject） | ID 存在、项目关系有效 |
| 打开/提交项目创建向导 | 允许 | 禁止 | 禁止 | V3 仅接受系统叙事原型 `derive`、精确父版本/Hash、固定题材选项、最多两项美学风格和 10,000 字资料；jsonschema 校验签名合规；项目与绑定同事务 |
| 管理 Creator Profile | 允许 | 只读（主控注入） | 只读（主控注入） | 内容修订创建不可变 revision；禁止人口属性推导和具体作者模仿目标 |
| rebind 项目作者版本 | 允许 | 禁止 | 禁止 | 提供用户原因；Direction 及后代递归 `stale`，不自动重生成 |
| 删除项目 | 允许（`legacy-python/scripts/novelos_delete_project.py`） | 禁止 | 禁止 | 先 `--dry-run` 调查；保护共享 creator_profile 资源 |
| 创建 sub agent | 允许 | 禁止 | 禁止 | 临时角色、注入方法论 prompt 与最小输入 |
| 登记规划候选 | 允许 | 禁止 | 禁止 | 算 content_hash、`CAST(? AS BLOB)` 写 resource、锁定上游、记录 `planning_asset_dependencies` |
| 锁定规划资产 | 允许 | 禁止 | 禁止 | 独立审查通过、无 blocking finding、`UPDATE status='locked'` |
| 创建章节草稿 | 允许 | 禁止 | 禁止 | 绑定 Chapter Plan、`style_refs` 含当前作者与 locked Direction ref |
| 接受章节 | 允许 | 禁止 | 禁止 | 精确正文 Hash、approved 审查、`UPDATE status='accepted'` |
| 记录审查 | 允许 | 禁止 | 禁止直接写 | 独立审查 sub agent 输出、`INSERT INTO reviews` |
| 修改实体 | 允许 | 禁止 | 禁止 | 重要变更经审查；`UPDATE state_json, version=version+1` |
| 晋升连续性 | 允许 | 禁止 | 禁止 | accepted 章节、单事务 INSERT 事实/承诺/期待/关系/故事弧状态 |
| 直接执行 SQL | 允许（受控 SQL + 校验门脚本） | 禁止 | 禁止 | 主控是唯一数据库执行入口；R2 后写旁路由插件 defineTool 收口 |

## 工具面

- Python SQLite MCP（`execute_sql`）通道已删除。过渡期主控的数据库手段：写 = 唯一经 `legacy-python/scripts/novelos_create_project.py` 校验门（jsonschema 门 + `BEGIN IMMEDIATE` 单事务）及配套确定性脚本；读 = 一次性 node:sqlite 查询（插件查询工具就绪后切换）。不再有领域工具层或运行时工具白名单（`config/agents.yaml` 为历史留档，无脚本依赖）；R2 交付后写入口收敛为插件 defineTool。
- sub agent 不持有任何数据库读写工具——它们由主控用 Agent 工具创建，只接收主控注入的只读上下文，返回候选文本。所有持久化由主控完成。
- 确定性脚本（`legacy-python/scripts/*.py`，只维护不新增）由主控在需要时调用，不调 LLM，不依赖 `config/agents.yaml`。

## 失败关闭与硬约束

- jsonschema 校验签名/book_soul 失败时拒绝落库。
- SQL `CHECK` 约束与状态机：`planning_assets.status` 仅允许 candidate/locked/stale/superseded；`revision`/`version` 必须 > 0；`asset_type` 仅允许枚举值。
- sub agent 失败或超时不得携带部分输出；主控决定是否重新路由并创建新 sub agent。
- change proposal 必须绑定当前项目 locked 上游的 ID、版本和 Hash。
- 删除项目时 `legacy-python/scripts/novelos_delete_project.py` 保护共享 creator_profile 系统原型资源；`--dry-run` 不写数据；删除按单事务提交。
- 绑定项目的 Direction 缺少/错绑 `creator_signature_ref` 或 `book_soul` 时拒绝；Chapter Plan 缺少/错绑 `soul_pressure` 与 `moral_residue` 时拒绝；Writer `style_refs` 缺少当前作者或 locked Direction ref 时拒绝。
- 落库约定：写 `resources.content` 必须用 `CAST(? AS BLOB)`，否则存为 TEXT 导致下游解码出错；写 resource 时必须同时算 `content_hash`。
