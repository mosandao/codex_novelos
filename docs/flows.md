# 关键流程

## 项目创建向导

参与者：用户、主控智能体、内核融合智能体、分身融合智能体（onboarding 双段）。

1. 主控与用户交互确认项目约束：项目名、频道（男频/女频/全向）、平台（列表随频道级联，女频=晋江/番茄/七猫 + 女频题材库与基调池）、规模、一级题材与二级方向（可多选）、表里基调（表层最多 2 项、内核恰 1 项可留空）、美学风格（最多两项）、创作资料（可留空，最多 10,000 字）。产出 `novelos.project.create.v3` 形态的 JSON 载荷。
2. **作者内核双模式**：`select` 从内核名册单选（主控经 node:sqlite 只读直查，建核/修订即时生效）；`create` 填写内核素材六字段（口味锚点/最想写的人与圈子/绝不触碰/执念话题/核心问题/知识背景，新建至少一条）。系统原型已退出创建链（Task 30 决策：内核完全取代原型，config 降为参考资料库）。
3. 载荷落库前主控对照 `config/schemas/project-create-request.schema.json`（v3）自查：结构 + 词表级联 + 表里互斥 + platform_traits/genre_profile 随行快照核对 + select 模式内核库内反查（版本存在 + ownership='author_kernel' + status='active' + subject_hash 相符）。自查 FAIL 拒绝继续。
4. **mode=create 先建核**：主控运行 `node scripts/novelos-compose-prompt.mjs --asset kernel-fusion --payload <json>` 产出内核融合注入文本（identity 八字段 + 心理运作八维五段式 + 有限知识生态 + growth_log 四归因方法论；模式模块 mode-create/mode-revise；输入数据区 kernel_hints + project_setup 语境 + persona_fingerprints 撞车基准），注入内核融合智能体 → 产出 `novelos.kernel.candidate.v1` → 主控对照 `config/schemas/author-kernel.schema.json` 自查后按 sql-reference.md「作者内核链」落库。内核修订（独立于项目）走同一链路的 revise 基底反查路径，growth_log 只追加。
5. **分身派生**：主控运行 `node scripts/novelos-compose-prompt.mjs --asset fusion --payload <json>` 产出分身融合注入文本（kernel_full 内核全文第一因 + 频道/库规模/题材/kernel-derive 条件模块 + 指纹去重基准），注入分身融合智能体——内核层继承不变（核心问题/价值公理/八维/知识边界语义继承），表达层按本书频道/题材/平台适配（voice_samples/trait_profile/七字段）→ 产出 `creator_derivation_candidate`（signature 带 `kernel_origin` 溯源）→ 主控对照 `config/schemas/creator-signature.schema.json` 自查（persona 必填、`cannot_write` 非空、七字段无逐字复制内核 identity 条目）。
6. 主控以 node:sqlite `BEGIN IMMEDIATE` 单事务六表落库（模板见 sql-reference.md「作者签名链」）：签名资源 + 派生资源（完整用户输入快照：author_kernel + setup 全文）+ creator_profiles（ownership='user'）+ creator_profile_versions（双资源链，parent 指向内核版本）+ projects（metadata_json 写入 setup v3 快照）+ project_creator_bindings（`binding_mode='kernel_derive'` + `kernel_version_id`）。content_hash 用 node:crypto 计算（`sha256:`+hex）。任一步失败整体回滚零写入；禁止手工逐条 INSERT 绕过自查。
7. **上报裁决**：`parent_rationale` 含错配标记（内核与基调相斥/频道错配）时，主控把冲突与调和建议呈报用户裁决，裁决通过后方可落库；候选解析失败或自查 FAIL 时要求 agent 重新输出，禁止主控手工改写候选内容。
8. 主控从 `projects.metadata_json` 读取 setup 快照，连同绑定签名中的 persona，启动方向智能体生成该项目的 `book_soul`（book_soul 从创作者人格与项目约束长出来；表里基调/题材信息包/平台耐心的消费规则见 story-direction prompt「上游消费」节）。创建链本身不会生成、锁定或提交 Direction。

拒绝路径：自查 FAIL（结构/词表级联/内核反查不符）时拒绝继续；用户约束确认不替代规划或审查；候选 JSON 解析失败或字段错位时要求 agent 重出，不接受手工改写的候选；错配标记未经用户裁决不得落库。

作者 Profile 新建版本不会改变既有项目绑定。显式 rebind 必须提供用户原因；成功后 Direction 及全部规划后代变为 `stale`，不自动重生成。内核出新 revision 后绑定旧版的项目照常运行（分身自带完整人格），是否重派生由用户裁决（novel-memory 构建上下文时标注内核陈旧，不静默换绑）。

## 人物生命周期（注册表状态机）

参与者：主控智能体、规划智能体、写作链、`$novel-continuity`。

1. **立档**：character_contract 锁定时，主控按 sql-reference.md「人物注册表」模板以 node:sqlite 直写，把 metadata.character_roster 落人物注册表（main/secondary，arc_role 与预期退场写 state_json）。**重锁对账**：曾在旧 roster 但不在新 roster 的人物输出 WARN——契约修订删除的用状态迁移退役，误删的补回。
2. **动态创建**：次要角色有两个人口——卷级配角由卷纲「卷级配角班底」生成（volume_outline 候选 metadata.`volume_characters`：secondary/minor + arc_role + 预期退场 + 微档案；不得生成 main、不得承载跨卷职责），卷纲锁定后主控用 entries 登记落注册表（条目可带 arc_role/预期退场/来源卷/source:"volume_outline"）；章级新面孔由章纲执行卡「本章新登场人物微档案」预登记（规划端造人，正文只消费不发明——Writer 写到未预登记新名字 = 违卡，entity-authority-review 判 blocking），章节接受后主控用 entries 登记落注册表（minor/secondary）。执行卡可直接消费本卷班底人物（标注「卷纲已登记」，不重复微档案）。
3. **状态迁移**：`$novel-continuity` 提取 character_status 候选（正文确认的退场/转化/休眠/死亡；新登场与下落不明不算），晋升后主控按 sql-reference.md 模板直写更新注册表（单对象或数组；dead 必带 死亡型 exit_type；非退场状态不带 exit_type 并整体清空退场痕迹——复活场景；每次迁移在 state_json.状态史 留审计记录；未登记人物按 minor 补登）。
4. **升级**：动态配角需要卷级职责/回归时走 change proposal → character_contract 新 revision（回归面孔名单为判定清单）→ 新 roster 重跑登记（升级 role_class，不覆盖 status）。
5. **对账**：连续性收尾主控必跑 node:sqlite 只读对账——比对 promoted 候选集中每人物最新 character_status 候选与注册表现状，漂移（漏跑迁移/迁移被回滚）即处理，处理完才能开下一章。
6. **消费**：canon 最小集注入「人物状态」节（死/退/眠优先近 20 人）；人类查看注册表走 novels/ 投影（`连续性/人物状态注册表.md`）。

## 用户实时打断

创作链任何阶段用户提出修改：主控立即暂停进行中的生成与提交，按影响面分流（setup 级 → UPDATE + propagate_stale；资产级 → change proposal；章内级 → `--review-feedback` 受控重组装），呈报将 stale 的资产清单获确认后执行（详见 AGENTS.md「小说工作流」第 5 条）。

## 规划资产

参与者：主控智能体、对应规划资产 sub agent、独立审查 sub agent。

前置条件：项目存在；精确上游资产均为 `locked` 且版本匹配。

1. 主控从 `catalog/skills/planning/<对应 skill>/prompt.md` 读取方法论，确定目标 `asset_type` 与 `scope_ref`。
2. 主控用 Agent 工具创建临时 sub agent，注入方法论 prompt、最小输入与必要的 locked 上游内容；sub agent 在隔离上下文返回候选正文（或绑定上游精确版本/Hash 的 change proposal）。
3. 主控以 node:sqlite 单事务直写落库候选（模板见 sql-reference.md）：content_hash 用 node:crypto 计算（`sha256:`+hex）→ BLOB 写入 resources → planning_assets 登记 `candidate` → `planning_asset_dependencies` 记录上游依赖。
4. 主控创建**独立**审查 sub agent（不同上下文）审查候选 → 审查意见登记 reviews，绑定 subject（候选 ID/Hash）与审查意见。
5. 审查通过后主控将资产状态置 `locked` 并绑定 locked_review_id；旧版本变为 `superseded`。
6. 上游资产修订（新 revision locked）后，主控以 node:sqlite UPDATE 沿依赖边递归标记所有下游 `stale`。

拒绝路径：未锁定上游、错误 producer、候选被主控改写、自审、blocking 审查意见或越权 change proposal 均不得产生 locked 版本。

Character 与 World 可以并行生成（上游相同、互不依赖），全部 locked 后才能启动 Story Arc。

## 完整章节与连续性

参与者：主控智能体、`$novel-memory`、可选上下文构建智能体、章节规划智能体、写作智能体、审查智能体、`$novel-continuity`。

1. 主控使用 `$novel-memory` 获取最小 Canon 上下文；仅在跨卷、多线、事实冲突或上下文溢出时创建上下文构建智能体。
2. 没有有效 Chapter Plan 时，按规划流程生成并锁定；执行卡包含可追溯到 locked Direction 的 `soul_pressure` 和 `moral_residue`，纯过渡场景允许明确降低思想前景强度。
3. 主控创建写作智能体 sub agent，注入 `style_refs`（至少含当前 Creator Profile 精确 ref 和 locked Direction 精确 ref）；sub agent 返回正文候选，主控 `INSERT INTO chapters (...,'draft',...)`。
4. 主控创建独立审查 sub agent 审查不可变正文 Hash → `INSERT INTO reviews`；审查通过后 `UPDATE chapters SET status='accepted'`。
5. `$novel-continuity` 从已接受正文提取候选（事实/承诺/期待/关系/故事弧状态/人物状态迁移），绑定正文 Hash，主控 SQL INSERT 到对应连续性账本；character_status 晋升后主控按 sql-reference.md 模板直写更新人物注册表，收尾跑只读对账。

拒绝路径：正文修改使旧审查失效则不得接受；任一失败不得部分更新连续性账本。

短句修改或未绑定 Chapter Plan 的局部草稿允许主控 + Skill 直接 SQL UPDATE，不创建写作智能体；接受前仍需独立审查。

## 实体修改

参与者：主控智能体、可选审查智能体。

characters/worlds/factions/rules/timelines 等实体的状态（`state_json`）与描述（`description_resource_id`）由主控经 SQL 直接维护：

1. 主控读取当前实体状态与允许的锁定规划来源或已接受章节来源。
2. 局部状态更新可直接 `UPDATE <实体表> SET state_json=?, version=version+1`。
3. 涉及描述资源变更时，先 `INSERT resources`（新内容，`CAST(? AS BLOB)`）再 `UPDATE` 实体的 `description_resource_id`。
4. 重要变更（影响 Canon 一致性）由主控创建审查 sub agent 审查后再提交。

不再有独立的两阶段 entity mutation 门禁工具；实体是主控可直接读写的业务表，由 SQL 状态机与审查 sub agent 约束。

## Agent 质量盲评

1. 当前 70-case Agent 质量实验已延期（见 `tasks/experiments/agent_quality/`），部分 case 仅作恢复证据，不用于宣称胜率或改变路由。
2. 盲评复用时：主控用匿名标签、输入 Hash 和输出 refs/Hash 构造评测 subject；审查 sub agent 只读取不可变 subject，不读取执行模式映射。
3. 评测审查意见只用于评测证据，不具备小说权威提交权限。

## 数据迁移与回滚

1. 来源数据库先冻结文件 Hash、Schema 和计数，来源仓库保持只读。
2. 使用 SQLite backup API 创建目标备份，验证 `quick_check` 和逻辑快照 Hash。
3. 只通过 `db/migrations/` 顺序前向 Migration 升级目标数据库。
4. 回滚演练从备份恢复到临时数据库，比较全部表逻辑 Hash、Schema 版本和计数，不覆盖正式数据库。
5. 降级导出工具 `export_novelos_data.py` 已随零 Python 整体退役，不再有导出/重建通道；灾备口径 = 直接复制 `data/novelos-v2.db` 文件（任何 schema 变更前先复制备份）。
6. 恢复演练在临时数据库上以备份副本验证 `quick_check` 与逻辑 Hash 一致，不覆盖正式数据库。
7. 只有授权和完整性同时成立的数据才可接入生产配置。

## 人类视图（md 投影渲染器）

参与者：用户、主控智能体（`scripts/novelos-render-projection.mjs`）。

1. 人类视图 = md 投影：`node scripts/novelos-render-projection.mjs --project <id> [--verify]`（node:sqlite 只读直连）把权威库单向渲染为 `novels/<项目目录>/`（创作约束/规划/大纲/正文/人物/世界/连续性 + manifest.json），临时目录写入后原子替换；投影只读、可删除重建、不构成第二存储。viewer 面板已退役，不要重建。
2. 「渲染—校验—原子替换」流程已按用户裁决恢复为 JS 实现（`scripts/novelos-render-projection.mjs`，移植自 py 版）：渲染后 manifest 逐文件 SHA-256 可经 `--verify` 复核；直接修改投影文件不会回写数据库。
3. agent 查库用一次性 node:sqlite 只读查询；写路径不经任何视图——主控 node:sqlite 受控直写（见 AGENTS.md「数据库访问」节）。

## 删除项目

参与者：用户、主控智能体（node:sqlite 受控直写）。

一个项目分布在 projects、books、volumes、chapters、planning_assets、characters、worlds、连续性账本、reviews、resources 等多张表，且存在大量 `ON DELETE RESTRICT` 约束（`planning_asset_dependencies.upstream_asset_id`、`reviews`、`resources` 等不级联），不能简单 `DELETE FROM projects`。删除由主控以 node:sqlite 受控直写完成（确定性 SQL、不调 LLM；SQL 模板见 `.agents/skills/novel-project/sql-reference.md`）。

1. 主控先以 `dryRun:true` 调查项目范围，确认将删除的 books/volumes/chapters、各 `asset_type`/`status` 的 planning_assets、待删 resources 与 reviews 数量。
2. 需要安全网时加 `backup:true`，在 `data/` 下写出 `.db.bak-<时间戳>`（已被 gitignore 覆盖）。
3. 执行删除：主控在 `foreign_keys=OFF` 下按依赖逆序逐表删除——先解除 `planning_asset_dependencies` 与 `reviews`（避免 RESTRICT 与留孤儿），再删连续性账本、chapters、volumes、planning_assets、characters、worlds、project_creator_bindings、books、projects，最后删项目专属 resources。全程单事务显式 `BEGIN IMMEDIATE`/`COMMIT`，避免连接关闭未提交而回滚。
4. 门只删项目专属内容资源（planning_assets/chapters/实体/连续性的 `resource_id`），**不动** `creator_profile_versions` 引用的共享系统原型资源（跨项目共享）。
5. 删除后主控用 `foreign_keys=ON` 复验：项目残留为 0、全库孤儿 reviews/dependencies 计数。`cleanOrphans:true` 可顺手清理全库历史遗留孤儿（非本次删除造成）。

拒绝路径：项目不存在时门返回 FAIL；共享 creator_profile 资源一律保留；`dryRun` 不写任何数据；删除按单事务提交，不产生部分删除。
