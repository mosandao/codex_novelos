# 关键流程

## 规划资产

参与者：Main Agent、对应规划资产 Agent、独立 Review Agent。

前置条件：项目存在；精确上游资产均为 `locked` 且版本匹配。

1. Main 从 Catalog 选择与目标 `asset_type` 匹配的包并冻结候选快照。
2. Main 使用 `agent.start` 创建唯一资产 owner run；MCP 校验最小输入和角色契约。
3. 临时 Agent 返回 `planning_candidate` 或绑定上游精确版本/Hash 的 change proposal；`agent.finish` 校验 Schema 并记录 Destroy。
4. Main 调用 `planning.create_candidate`；MCP 验证生产 run、输出正文、唯一 owner 和上游依赖。
5. Main 创建独立 Review run，随后调用 `review.record`；MCP 验证 subject Hash、Reviewer 输出和隔离 context。
6. Main 调用 `planning.lock` 并提供当前 `trace_id`；MCP 重新验证 Review Profile、verdict、blocking finding、依赖版本和 Producer/Reviewer Trace 一致性，在同一事务写入 `authority_commits`。
7. 新版本锁定时，旧版本变为 `superseded`，所有后代递归变为 `stale`。

拒绝路径：未锁定上游、错误生产者、输出被 Main 改写、自审、旧 Hash、blocking finding 或越权 change proposal 均不得产生权威版本。

Character 与 World 可以有同时运行的独立 run。Story Arc 前必须创建 `planning_cross_check`，由独立 Reviewer 对两个精确版本审查并批准；缺少、失效或错配时拒绝 Story Arc 候选。

## 完整章节与连续性

参与者：Main Agent、Memory Skill、可选 Context Builder、Chapter Planner、Writer Agent、Review Agent、Continuity Skill。

1. Main 使用 `novel-memory` 获取最小 Canon 上下文；仅在跨卷、多线、事实冲突或上下文溢出时允许创建 Context Builder。
2. 没有有效 Chapter Plan 时，按规划流程生成并锁定。
3. Writer Agent 在隔离 run 中返回正文候选；绑定 Chapter Plan 的 `chapter.create_draft` 必须引用该 run。
4. 独立 Review Agent 审查不可变正文 Hash，Main 登记 Review Receipt 后携带同一 `trace_id` 调用 `chapter.accept`；接受和追溯账本原子提交。
5. `novel-continuity` 从已接受正文提取候选，绑定正文 Hash 和 Authority Snapshot。
6. 独立 Review 通过后，`continuity.promote_reviewed` 在单事务内更新事实、承诺、期待、关系和故事弧状态。

拒绝路径：正文修改使旧 Review 失效；Authority Snapshot 变化阻止连续性晋升；任一失败不得部分更新 Canon。

短句修改或未绑定 Chapter Plan 的局部草稿允许 Main + Skill 直接处理，不创建 Writer Agent；接受前仍需要独立 Review。

## Authority Entity 修改

参与者：Main Agent、Review Agent。

1. Main 调用 `entity.prepare_mutation`，提供允许的锁定规划来源或已接受章节来源。
2. MCP 将 payload、来源 Hash/版本、目标 ID 和预期版本组成不可变候选。
3. 独立 Reviewer 审查候选，Main 登记 Review Receipt。
4. `entity.commit_mutation` 在单事务内重验来源、Review Profile 和目标乐观版本后写入。

公开 MCP 不注册 `character/world/faction/rule/timeline.upsert`，因此调用者无法跳过两阶段门禁。

## Agent 质量盲评

1. Main + Skill 基线通过 `resource.create` 登记 Trace 绑定的不可变输出；临时 Agent 输出由 `agent.finish` 登记。
2. Main 用匿名标签、输入 Hash、输出 refs/Hash 和 Review Profile 调用 `review.prepare_subject`；MCP 同时绑定已完成的 Producer runs。
3. 独立 Review Agent 只读取不可变评测 subject，不读取 execution manifest 的模式映射。
4. `review.record` 只接受同 Trace、输入和输出完全一致的 Reviewer run，并把结构化 assessment 保存为不可变 Resource 后绑定到 Receipt。
5. 离线汇总器逐层复核原始输入、匿名输出、subject、Receipt、assessment 和 Hash，最后才解盲计算角色策略。

评测 Receipt 不进入 `authority_commits`，不能锁定规划、接受正文或修改 Canon。

## 数据迁移与回滚

1. 来源数据库先冻结文件 Hash、Schema 和计数，来源仓库保持只读。
2. 使用 SQLite backup API 创建目标备份，验证 `quick_check` 和逻辑快照 Hash。
3. 只通过顺序前向 Migration 升级目标数据库。
4. 回滚演练从备份恢复到临时数据库，比较全部表逻辑 Hash、Schema 版本和计数，不覆盖正式数据库。
5. 若切换后需要降级旧入口，先用 `scripts/export_novelos_data.py --output-dir <目录>` 导出表定义、后置 Schema、逐表 JSONL 和 Hash Manifest；导出目录已存在时拒绝覆盖。
6. 导出恢复演练必须在临时数据库重建全部行、索引、触发器和视图，并与正式库逻辑 Hash 一致；正式演练不保留正文导出副本。
7. 只有授权和完整性同时成立的数据才可接入生产配置。

## 用户项目文件夹投影

参与者：用户、Main Agent、NovelOS MCP。

1. Main 先定位精确 `project_id`，请求 MCP 生成项目级 Authority Snapshot。
2. MCP 只选择 `locked` 规划、`accepted` 正文、当前 Authority Entity 和已晋升连续性状态，长内容通过 Resource ref 读取。
3. MCP 在目标根目录内创建临时同级目录，按固定规则生成中文 Markdown 结构和 `manifest.json`。
4. MCP 校验每个文件 Hash、来源 ID/版本/Hash、路径边界和快照未漂移后，原子替换同一项目的旧投影。
5. Main 向用户返回实际目录、Authority Snapshot Hash、文件数和被跳过的非权威内容统计。
6. 可随时调用 `projection.verify_manifest` 独立校验已生成目录：逐文件重算 SHA-256 并核对 `manifest.json` 中记录的 `source_hash`，篡改或不一致即失败。

拒绝路径：目标目录属于其他项目、名称清理失败、路径或符号链接逃逸、生成期间权威版本变化、Resource Hash 不匹配或无法原子完成时，不得留下部分新投影，也不得修改 SQLite。

投影是单向用户视图。用户直接编辑 Markdown 不触发数据库写入；未来如需导入，必须另建候选、差异审查和权威提交流程。
