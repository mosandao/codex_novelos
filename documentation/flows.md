# 关键流程

## 项目创建向导

参与者：用户、主控智能体、本地项目向导、NovelOS MCP。

1. 用户要求创建项目时，Main 提供 `mcp/novelos/src/novelos_mcp/ui/project-wizard.html` 的绝对本地路径。
   页面和同目录的 `project-wizard-data.js` 可通过 `file://` 打开，不依赖 MCP Apps proxy。
2. 用户填写项目名、频道、平台、规模和一级题材；页面依据一级题材显示静态的二级方向候选。
   二级方向可多选，主情绪基调可多选，美学风格最多两项，创作资料可留空且最多 10,000 字。
3. 页面按项目定位确定性推荐三个系统叙事原型并显示匹配分；用户仍可浏览全部 18 个原型，
   查看只读继承项，并编辑或清空本书差异。提交只使用 `derive`，不允许 `create` 或 `reuse`。
4. 页面生成 `novelos.project.create.v1` JSON，显示在页面底部并尝试自动复制；复制失败时提供
   手动复制按钮。用户把原始 JSON 发送给 Main。页面产出的 `creator.selected_archetypes` 是
   多原型数组，Main 按 `selected_archetypes` 数量选择签名融合路径：单原型直接调用
   `project.wizard.reconcile_archetypes` 确定性融合为单一 parent 的 derive 结构（`parent_source:"scored"`）；
   多原型（≥2）先在 Trace 内创建临时 `onboarding_agent` run，由 LLM 判定 parent 并深度融合跨原型约束，产出
   `creator_derivation_candidate`，再把 Agent 判定的 parent 与完整融合签名作为 `fused_parent_version_id` /
   `fused_signature` 传给 `project.wizard.reconcile_archetypes` 做确定性合规收口（`parent_source:"fused"`）。
   两条路径最终都以该 derive 结构调用 `project.wizard.submit`。
5. MCP 只接受固定频道、平台、规模、一级题材和该题材对应的二级方向，拒绝已移除的自定义项、
   知乎盐选、无效字段或跨题材二级方向；随后在同一事务中确认或创建不可变 Creator Profile 版本、创建项目、写入
   `metadata.project_setup` 并绑定精确 revision/Hash，随后刷新默认投影。
6. Main 读取项目约束与 `creator_binding.constraint_ref`，启动 Trace，并把精确 ref 交给方向智能体；
   候选 metadata 必须包含同一 ref 和完整 `book_soul`。向导本身不会生成、锁定或提交 Direction。

拒绝路径：本地页面只生成 JSON，不声称项目已创建；参数不符合表单契约时，
`project.wizard.submit` 不写入项目；前端选择不替代规划、审查或 authority commit 门禁。

作者 Profile 新建版本不会改变既有项目绑定。显式 rebind 必须使用当前 `expected_version`、运行中的
本项目 Trace、目标版本精确 Hash 和用户原因；成功后 Direction 及全部规划后代变为 `stale`，
Trace 记录旧/新 ref 和影响列表，系统不自动重生成。

## 规划资产

参与者：主控智能体、对应规划资产 Agent、独立 审查智能体。

前置条件：项目存在；精确上游资产均为 `locked` 且版本匹配。

1. Main 从 Catalog 选择与目标 `asset_type` 匹配的包并冻结候选快照。
2. Main 使用 `agent.start` 创建唯一资产 owner run；MCP 校验最小输入和角色契约。
3. 正式资产 Agent 返回非空文本 `planning_candidate` 或绑定上游精确版本/Hash 的 change proposal；`agent.finish` 按 `output_type` Schema 校验并记录 Destroy。Agent 质量实验的专用结构化规划输出只用于评测，不得登记为权威候选。
4. Main 调用 `planning.create_candidate_from_run`；MCP 直接读取不可变生产输出，并验证唯一 owner 和上游依赖。`planning.create_candidate` 仅保留为兼容入口。
5. Main 创建独立 Review run，随后调用 `review.record_from_run`；MCP 直接读取符合专用 Schema 的 Reviewer 输出，并验证 subject Hash、Profile、输入绑定和 run context 标识。`review.record` 仅保留为兼容入口；`context_id` 本身不证明真实模型上下文隔离。
6. Main 调用 `planning.lock` 并提供当前 `trace_id`；MCP 重新验证 Review Profile、verdict、blocking finding、依赖版本和 Producer/Reviewer Trace 一致性，在同一事务写入 `authority_commits`。
7. 新版本锁定时，旧版本变为 `superseded`，所有后代递归变为 `stale`。

拒绝路径：未锁定上游、错误生产者、输出被 Main 改写、自审、旧 Hash、blocking finding 或越权 change proposal 均不得产生权威版本。

Character 与 World 可以有同时运行的独立 run。提供 `planning_cross_check` 时，必须由独立 Reviewer 对两个精确版本审查并批准；pending、失效或错配的 cross-check 在任何模式下都拒绝，并在 lock 时重新验证。默认 lenient 允许 Story Arc 候选缺少 cross-check，并在 lock 权威事务中记录 `status=completed`、`details.severity=warning`、`details.enforcement_mode=lenient` 的 Trace step 后放行；strict 模式在候选创建和 lock 阶段都阻断缺失 cross-check。

## 完整章节与连续性

参与者：主控智能体、Memory Skill、可选 上下文构建智能体、章节规划智能体、写作智能体、审查智能体、Continuity Skill。

1. Main 使用 `novel-memory` 获取最小 Canon 上下文；仅在跨卷、多线、事实冲突或上下文溢出时允许创建 上下文构建智能体。
2. 没有有效 Chapter Plan 时，按规划流程生成并锁定；执行卡包含可追溯到 locked Direction 的
   `soul_pressure` 和 `moral_residue`，纯过渡场景允许明确降低思想前景强度。
3. 写作智能体 在隔离 run 中返回正文候选；`style_refs` 至少包含当前 Creator Profile 精确 ref
   和 locked Direction 精确 ref。绑定 Chapter Plan 的 `chapter.create_draft` 必须引用该 run。
4. 独立 审查智能体 审查不可变正文 Hash，Main 登记 Review Receipt 后携带同一 `trace_id` 调用 `chapter.accept`；接受和追溯账本原子提交。
5. `novel-continuity` 从已接受正文提取候选，绑定正文 Hash 和 Authority Snapshot。
6. 独立 Review 通过后，`continuity.promote_reviewed` 在单事务内更新事实、承诺、期待、关系和故事弧状态。

拒绝路径：正文修改使旧 Review 失效；Authority Snapshot 变化阻止连续性晋升；任一失败不得部分更新 Canon。

短句修改或未绑定 Chapter Plan 的局部草稿允许 Main + Skill 直接处理，不创建 写作智能体；接受前仍需要独立 Review。

## Authority Entity 修改

参与者：主控智能体、审查智能体。

1. Main 调用 `entity.prepare_mutation`，提供允许的锁定规划来源或已接受章节来源。
2. MCP 将 payload、来源 Hash/版本、目标 ID 和预期版本组成不可变候选。
3. 独立 Reviewer 审查候选，Main 登记 Review Receipt。
4. `entity.commit_mutation` 在单事务内重验来源、Review Profile 和目标乐观版本后写入。

公开 MCP 不注册 `character/world/faction/rule/timeline.upsert`，因此调用者无法跳过两阶段门禁。

## Agent 质量盲评

1. Main + Skill 基线通过 `resource.create` 登记 Trace 绑定的不可变输出；临时 Agent 输出由 `agent.finish` 登记。
2. Main 用匿名标签、输入 Hash、输出 refs/Hash 和 Review Profile 调用 `review.prepare_subject`；MCP 同时绑定已完成的 Producer runs。
3. 独立 审查智能体 只读取不可变评测 subject，不读取 execution manifest 的模式映射。
4. `review.record_from_run` 只接受同 Trace、输入和输出完全一致的 Reviewer run，并把质量评测专用的结构化 assessment 保存为不可变 Resource 后绑定到 Receipt。
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

参与者：用户、主控智能体、NovelOS MCP。

1. Main 先定位精确 `project_id`，请求 MCP 生成项目级 Authority Snapshot。
2. MCP 将 `locked` 规划、`accepted` 正文、当前 Authority Entity、已晋升连续性状态、精确作者绑定和 locked Direction 的 `book_soul` 写入权威视图；未绑定或未锁定时明确显示缺失，不合成作者思想，也不把候选当作权威。同时读取候选、非权威规划/正文、完成 Agent 输出和 locked 规划溯源，用于隔离的 `候选/`、`产出/` 和 `档案/` 目录。长内容通过 Resource ref 读取。
3. MCP 在目标根目录内创建临时同级目录，按固定规则生成中文 Markdown 结构、全过程档案和 `manifest.json`。
4. MCP 校验每个文件 Hash、来源 ID/版本/Hash、路径边界和快照未漂移后，原子替换同一项目的旧投影。
5. Main 向用户返回实际目录、Authority Snapshot Hash、文件数和被跳过的非权威内容统计。
6. 可随时调用 `projection.verify_manifest` 独立校验已生成目录：逐文件重算 SHA-256 并核对 `manifest.json` 中记录的 `source_hash`，篡改或不一致即失败。

拒绝路径：目标目录属于其他项目、名称清理失败、路径或符号链接逃逸、生成期间权威版本变化、Resource Hash 不匹配或无法原子完成时，不得留下部分新投影，也不得修改 SQLite。

投影是单向用户视图。用户直接编辑 Markdown 不触发数据库写入；未来如需导入，必须另建候选、差异审查和权威提交流程。

## 删除项目

参与者：用户、主控智能体、NovelOS MCP。

1. Main 先读取项目，取得精确 `project_id` 与当前 `expected_version`。
2. Main 调用 `project.delete`。MCP 在删除前后均校验乐观版本、项目没有运行中的 Trace，
   且不存在该项目的 `authority_commits`。
3. MCP 仅删除默认输出根目录下同名、非符号链接且 `manifest.json` 中 `project_id` 匹配的投影目录。
4. 投影处理成功后，MCP 在事务中删除项目容器及级联业务数据；已完成 Trace 和 Agent run 审计记录
   仍保留，但解除项目关联。

拒绝路径：版本已变化、存在活动 Trace、已有权威提交、投影缺少/无法解析 manifest、manifest 属于
其他项目或路径不安全时均拒绝删除，不得部分删除权威数据。
