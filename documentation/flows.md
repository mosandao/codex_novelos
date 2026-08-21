# 关键流程

## 项目创建向导

参与者：用户、主控智能体、本地项目向导、内核融合智能体、分身融合智能体（onboarding 双段）。

1. 用户要求创建项目时，主控提供 `ui/project-wizard.html` 的绝对本地路径。页面和同目录的 `project-wizard-data.js` 可通过 `file://` 打开，不依赖 MCP Apps proxy。
2. 用户填写项目名、频道（男频/女频/全向）、平台、规模和一级题材；平台列表、一级题材库、二级方向候选、基调池均随频道级联切换（女频=晋江/番茄/七猫 + 女频题材库与基调池），平台选定后显示平台画像。二级方向可多选，表里基调分表层（外显，最多 2 项）与内核（底色，恰 1 项，可留空），美学风格最多两项（按题材标「荐」，可混搭），创作资料可留空且最多 10,000 字。
3. 页面第 07 步为「作者内核」双模式：`select` 从内核名册（`kernel-roster.js` 镜像，由 `novelos_export_kernel_roster.py` 从库生成——建核/修订后重跑刷新）单选既有内核；`create` 填写内核素材六字段（口味锚点/最想写的人与圈子/绝不触碰/执念话题/核心问题/知识背景，新建至少一条）。系统原型已退出创建链（Task 30 决策：内核完全取代原型，config 降为参考资料库）。
4. 页面生成 `novelos.project.create.v3` JSON，显示在页面底部并尝试自动复制；复制失败时提供手动复制按钮。用户把原始 JSON 发送给主控。
5. 主控收到 JSON 后**第一动作**是入口校验：`.venv/bin/python scripts/novelos_create_project.py --payload <json>`——jsonschema 结构（`config/schemas/project-create-request.schema.json`，v3）+ 词表级联 + 表里互斥 + platform_traits/genre_profile 随行快照核对 + select 模式内核库内反查（版本存在 + ownership='author_kernel' + status='active' + subject_hash 相符）。FAIL 拒绝继续。
6a. **mode=create 先建核**：主控运行 `.venv/bin/python scripts/novelos_compose_prompt.py --asset kernel-fusion --payload <json>` 产出内核融合注入文本（identity 八字段 + 心理运作八维五段式 + 有限知识生态 + growth_log 四归因方法论；模式模块 mode-create/mode-revise；输入数据区 kernel_hints + project_setup 语境 + persona_fingerprints 撞车基准 + 原型一行式参考资料），注入内核融合智能体 → 产出 `novelos.kernel.candidate.v1` → 主控运行 `novelos_create_project.py --payload <json> --kernel-candidate <json> --emit-payload <bound.json>`（信封 + author-kernel 两步校验 + 落库 + 机械缝合 select 形态 payload），随后重跑 `novelos_export_kernel_roster.py` 刷新名册。内核修订（独立于项目）走 `--kernel-revise <revise载荷> --kernel-candidate`，growth_log 只追加。
6b. **分身派生**：主控运行 `novelos_compose_prompt.py --asset fusion --payload <bound.json|json>` 产出分身融合注入文本（kernel_full 内核全文第一因 + 频道/库规模/题材/kernel-derive 条件模块 + 指纹去重基准），注入分身融合智能体——内核层继承不变（核心问题/价值公理/八维/知识边界语义继承，逐字复制由校验门拦截），表达层按本书频道/题材/平台适配（voice_samples/trait_profile/七字段）→ 产出 `creator_derivation_candidate`（signature 带 `kernel_origin` 溯源）。
7. 主控运行固化脚本完成校验门与落库：`.venv/bin/python scripts/novelos_create_project.py --payload <bound.json> --candidate <json>`。脚本依次执行——候选容错解析 → jsonschema 信封（creator-derivation-candidate）+ 签名 v2 深层（creator-signature，persona 必填且 `cannot_write` 非空）→ parent=内核版本库内反查 + kernel_origin 一致性 + 七字段无逐字复制内核 identity 条目（语义继承须从 persona 重新长出）→ 融合签名 hash 计算 → `BEGIN IMMEDIATE` 单事务六表落库：签名资源 + 派生资源（完整用户输入快照：author_kernel + setup 全文）+ creator_profiles（ownership='user'）+ creator_profile_versions（双资源链，parent 指向内核版本）+ projects（metadata_json 写入 setup v3 快照）+ project_creator_bindings（`binding_mode='kernel_derive'` + `kernel_version_id`）。禁止手工逐条 INSERT 绕过脚本。
8. **上报裁决**：`parent_rationale` 含错配警告（内核与基调相斥/频道错配）时，主控把冲突与调和建议呈报用户裁决，未获裁决不得落库（脚本检测到警告字样会提示）；候选解析失败或校验门 FAIL 时要求 agent 重新输出，禁止主控手工改写候选内容。
9. 主控从 `projects.metadata_json` 读取 setup 快照，连同绑定签名中的 persona，启动方向智能体生成该项目的 `book_soul`（book_soul 从创作者人格与项目约束长出来；表里基调/题材信息包/平台耐心的消费规则见 story-direction prompt「上游消费」节）。向导本身不会生成、锁定或提交 Direction。

拒绝路径：本地页面只生成 JSON，不声称项目已创建；入口校验 FAIL（结构/词表级联/镜像漂移）时拒绝继续；前端选择不替代规划或审查；jsonschema 校验门 FAIL 时拒绝写入；候选 JSON 解析失败或字段错位时要求 agent 重出，不接受手工改写的候选；错配警告未经用户裁决不得落库。

作者 Profile 新建版本不会改变既有项目绑定。显式 rebind 必须提供用户原因；成功后 Direction 及全部规划后代变为 `stale`，不自动重生成。内核出新 revision 后绑定旧版的项目照常运行（分身自带完整人格），是否重派生由用户裁决（novel-memory 构建上下文时标注内核陈旧，不静默换绑）。

## 人物生命周期（注册表状态机）

参与者：主控智能体、规划智能体、写作链、`$novel-continuity`、`scripts/novelos_register_characters.py`。

1. **立档**：character_contract 锁定时，主控用 `novelos_register_characters.py --project <id> --roster <json>` 把 metadata.character_roster 落人物注册表（main/secondary，arc_role 与预期退场写 state_json）。**重锁对账**：曾在旧 roster 但不在新 roster 的人物输出 WARN——契约修订删除的用 `--status-update` 退役，误删的补回。
2. **动态创建**：次要角色由章纲执行卡「新登场人物微档案」预登记（规划端造人，正文只消费不发明——Writer 写到未预登记新名字 = 违卡，entity-authority-review 判 blocking）；章节接受后主控用 `--entry` 落注册表（minor/secondary）。
3. **状态迁移**：`$novel-continuity` 提取 character_status 候选（正文确认的退场/转化/休眠/死亡；新登场与下落不明不算），晋升后主控用 `--status-update` 更新注册表（单对象或数组；dead 必带 死亡型 exit_type；非退场状态不带 exit_type 并整体清空退场痕迹——复活场景；每次迁移在 state_json.状态史 留审计记录；未登记人物按 minor 补登）。
4. **升级**：动态配角需要卷级职责/回归时走 change proposal → character_contract 新 revision（回归面孔名单为判定清单）→ 新 roster 重跑 `--roster`（升级 role_class，不覆盖 status）。
5. **对账**：连续性收尾必跑 `novelos_register_characters.py --project <id> --pending-status`——比对 promoted 候选集中每人物最新 character_status 候选与注册表现状，漂移（漏跑迁移/迁移被回滚）非零退出，处理完才能开下一章。
6. **消费**：canon 最小集注入「人物状态」节（死/退/眠优先近 20 人）；投影渲染 `连续性/人物状态注册表.md` 与每人物档案的分类/状态/退场头部。

## 用户实时打断

创作链任何阶段用户提出修改：主控立即暂停进行中的生成与提交，按影响面分流（setup 级 → UPDATE + propagate_stale；资产级 → change proposal；章内级 → `--review-feedback` 受控重组装），呈报将 stale 的资产清单获确认后执行（详见 AGENTS.md「小说工作流」第 6 条）。

## 规划资产

参与者：主控智能体、对应规划资产 sub agent、独立审查 sub agent。

前置条件：项目存在；精确上游资产均为 `locked` 且版本匹配。

1. 主控从 `catalog/skills/planning/<对应 skill>/prompt.md` 读取方法论，确定目标 `asset_type` 与 `scope_ref`。
2. 主控用 Agent 工具创建临时 sub agent，注入方法论 prompt、最小输入与必要的 locked 上游内容；sub agent 在隔离上下文返回候选正文（或绑定上游精确版本/Hash 的 change proposal）。
3. 主控落库候选：`scripts/novelos_hash.py` 算 content_hash → `INSERT INTO resources (... CAST(? AS BLOB) ...)` → `INSERT INTO planning_assets (..., 'candidate', ...)` → `INSERT INTO planning_asset_dependencies` 记录上游依赖。
4. 主控创建**独立**审查 sub agent（不同上下文）审查候选 → `INSERT INTO reviews`，绑定 subject（候选 ID/Hash）与审查意见。
5. 审查通过后主控执行 `UPDATE planning_assets SET status='locked', locked_review_id=? WHERE id=?`；旧版本变为 `superseded`。
6. 上游资产修订（新 revision locked）后，主控运行 `scripts/novelos_propagate_stale.py --asset <上游id>` 递归标记所有下游 `stale`。

拒绝路径：未锁定上游、错误 producer、候选被主控改写、自审、blocking 审查意见或越权 change proposal 均不得产生 locked 版本。

Character 与 World 可以并行生成（上游相同、互不依赖），全部 locked 后才能启动 Story Arc。

## 完整章节与连续性

参与者：主控智能体、`$novel-memory`、可选上下文构建智能体、章节规划智能体、写作智能体、审查智能体、`$novel-continuity`。

1. 主控使用 `$novel-memory` 获取最小 Canon 上下文；仅在跨卷、多线、事实冲突或上下文溢出时创建上下文构建智能体。
2. 没有有效 Chapter Plan 时，按规划流程生成并锁定；执行卡包含可追溯到 locked Direction 的 `soul_pressure` 和 `moral_residue`，纯过渡场景允许明确降低思想前景强度。
3. 主控创建写作智能体 sub agent，注入 `style_refs`（至少含当前 Creator Profile 精确 ref 和 locked Direction 精确 ref）；sub agent 返回正文候选，主控 `INSERT INTO chapters (...,'draft',...)`。
4. 主控创建独立审查 sub agent 审查不可变正文 Hash → `INSERT INTO reviews`；审查通过后 `UPDATE chapters SET status='accepted'`。
5. `$novel-continuity` 从已接受正文提取候选（事实/承诺/期待/关系/故事弧状态/人物状态迁移），绑定正文 Hash，主控 SQL INSERT 到对应连续性账本；character_status 晋升后经 `novelos_register_characters.py --status-update` 更新人物注册表，收尾跑 `--pending-status` 对账。

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
5. 若切换后需要降级旧入口，先用 `scripts/export_novelos_data.py --output-dir <目录>` 导出表定义、后置 Schema、逐表 JSONL 和 Hash Manifest；导出目录已存在时拒绝覆盖。
6. 导出恢复演练必须在临时数据库重建全部行、索引、触发器和视图，并与正式库逻辑 Hash 一致。
7. 只有授权和完整性同时成立的数据才可接入生产配置。

## 用户项目文件夹投影

参与者：用户、主控智能体、`scripts/novelos_render_projection.py`。

1. 主控定位精确 `project_id`，运行 `scripts/novelos_render_projection.py --project <id> [--output novels/] [--verify]`。
2. 脚本（裸 sqlite3、零 MCP 依赖）将 `locked` 规划、`accepted` 正文、当前实体、已晋升连续性状态、精确作者绑定和 locked Direction 的 `book_soul` 写入权威视图；未绑定或未锁定时明确显示缺失，不合成作者思想，也不把候选当作权威。人物契约按「## 人物档案：角色｜名字」结构拆成 `规划/人物契约/` 目录（总览 + 每人物一份），不符合结构时退化为单文件并告警。
3. 脚本在目标根目录内创建临时同级目录，按固定规则生成中文 Markdown 结构和 `manifest.json`。
4. 脚本校验每个文件 Hash、来源 ID/版本/Hash、路径边界后，原子替换同一项目的旧投影。
5. 主控向用户返回实际目录、Authority Snapshot Hash、文件数。
6. `--verify` 逐文件重算 SHA-256 并核对 `manifest.json` 中记录的 `source_hash`，篡改或不一致即失败。

拒绝路径：目标目录属于其他项目、名称清理失败、路径或符号链接逃逸、Resource Hash 不匹配或无法原子完成时，不得留下部分新投影，也不得修改权威数据。

投影是单向用户视图。用户直接编辑 Markdown 不触发数据库写入。

## 删除项目

参与者：用户、主控智能体、`scripts/novelos_delete_project.py`。

一个项目分布在 projects、books、volumes、chapters、planning_assets、characters、worlds、连续性账本、reviews、resources 等多张表，且存在大量 `ON DELETE RESTRICT` 约束（`planning_asset_dependencies.upstream_asset_id`、`reviews`、`resources` 等不级联），不能简单 `DELETE FROM projects`。删除由确定性脚本 `scripts/novelos_delete_project.py` 完成，不调用 LLM。

1. 主控先以 `--dry-run` 调查项目范围，确认将删除的 books/volumes/chapters、各 `asset_type`/`status` 的 planning_assets、待删 resources 与 reviews 数量。
2. 需要安全网时加 `--backup`，在 `data/` 下写出 `.db.bak-<时间戳>`（已被 gitignore 覆盖）。
3. 执行删除：脚本在 `foreign_keys=OFF` 下按依赖逆序逐表删除——先解除 `planning_asset_dependencies` 与 `reviews`（避免 RESTRICT 与留孤儿），再删连续性账本、chapters、volumes、planning_assets、characters、worlds、project_creator_bindings、books、projects，最后删项目专属 resources。全过程用 `isolation_level=None` + 显式 `BEGIN/COMMIT`，避免连接关闭未提交而回滚。
4. 脚本只删项目专属内容资源（planning_assets/chapters/实体/连续性的 `resource_id`），**不动** `creator_profile_versions` 引用的共享系统原型资源（跨项目共享）。
5. 删除后脚本用 `foreign_keys=ON` 复验：项目残留为 0、全库孤儿 reviews/dependencies 计数。`--clean-orphans` 可顺手清理全库历史遗留孤儿（非本次删除造成）。
6. 默认同时删除投影目录：按 `manifest.json` 的 `project_id` 匹配（不依赖目录命名），删除该项目的 `novels/<目录>/`。`--no-projection` 跳过。

拒绝路径：项目不存在时脚本报错退出；共享 creator_profile 资源一律保留；`--dry-run` 不写任何数据；删除按单事务提交，不产生部分删除。
