---
name: novel-planning
description: 识别小说规划层级并准备对应权威资产的最小输入。探索或生成故事方向、故事架构、全书战略、人物或世界契约、跨卷故事弧、卷纲、章纲时使用。
---

# 小说规划

通过 node:sqlite 只读查询数据库；写路径唯一入口 = 插件门工具（见 AGENTS.md「数据库访问」，锁定/审查落库走状态机三段 `novelos_review_commit` / `novelos_lock_asset` / `novelos_accept_chapter`）。SQL 模板见 `novel-project/sql-reference.md`。

## 资产路由

| `asset_type` | 生产者角色 | 必需上游 |
|---|---|---|
| `direction` | 方向智能体 | 无 |
| `architecture` | 架构智能体 | direction |
| `strategy` | 策略智能体 | direction、architecture |
| `world_contract` | 世界观智能体 | architecture、strategy |
| `character_contract` | 人物智能体 | architecture、strategy、world_contract |
| `story_arc` | 故事弧智能体 | strategy、character_contract、world_contract |
| `volume_outline` | 卷规划智能体 | story_arc、world_contract、character_roster |
| `chapter_plan` | 章节规划智能体 | volume_outline |

依赖顺序：direction → architecture → strategy → world → character → story_arc → volume_outline → chapter_plan（T36 起世界先行：world 设岗位不造人，character 认领席位——sibling 并行与交叉假设清单退役，world 修订沿依赖边自动标 character stale）。

## 工作流

1. 从用户目标判断唯一目标 `asset_type` 和 `scope_ref`。
2. `SELECT * FROM planning_assets WHERE project_id=? AND status='locked' ORDER BY asset_type` 读取当前资产；复用所有有效 locked 上游，拒绝使用 stale/superseded。
3. 方法论获取（以 `scripts/novelos-compose-prompt.mjs` 的 **ASSET_DIRS 注册表**为准）：全部八类规划资产已注册——不 Read prompt.md，组装器 `--asset <asset> --project <project_id>` 一步产出「主干 + 条件模块 + 输入数据区 + 自检汇总」完整注入文本（channel/platform/genre/aesthetic 随 setup 自动路由，upstream 槽位自动注入 locked 上游原文）。
4. 探索性讨论直接返回方案，不持久化。
5. 需要正式版本时，创建 sub agent（用 Agent 工具）生成候选正文。**Direction sub agent 的输入**用组装器一步产出：`node scripts/novelos-compose-prompt.mjs --asset direction --project <project_id>`——组装器查库取①项目绑定的创作者人格（`project_creator_bindings` 签名全文，persona 从这个人身上长出 book_soul）②`project_setup` v2 快照（含 channel/platform/platform_traits/scale/primary_genre/secondary_directions/emotional_surface/emotional_core/tonal_contrast/aesthetic_styles/genre_profile 与 `reference_material`——用户原始意图，按 prompt 的三类意图提炼法消费，**不靠会话记忆回传**）③`scale`（四档分档的可展开性硬约束，在 setup 内，分档要求见 story-direction prompt），并按 setup 取值附加条件模块（频道语法男频力量轴/女频规则关系轴/全向双轨、平台三字段消费、题材信息包、美学基因）。Direction 按其 prompt「上游消费」各节消费 setup：`emotional_core`→book_soul 情感承诺（central_contradiction 情感底色 + protected_dignity 底线）、`emotional_surface`→promise_cadence 表层节奏、`genre_profile`→力量货币候选（非空不现场发明、为 null 现场推导并显式定义）、`platform_traits`→promise_cadence 平台节奏与受众画像翻译，交付前过**表里失联自检**。Direction 必须包含完整 `book_soul`（v2 十三字段，见末尾速查表）和 `creator_signature_ref`。**Architecture sub agent 的输入** = direction 正文 + 上游 metadata（lineage / cadence_plan 随 upstream 槽注入）+ persona（直接注入权威源，不靠 direction 转述）+ setup 全量，核心职责是把 organizing_principle / promise_cadence 翻译成**双层引擎**（生产层单元机器·单元弧粒度 + 统合层卷级统合器·主线节拍表/单元配额/注入配额），主线密度声明与 scale/平台/promise_cadence 对表，交付前按 architecture metadata 速查表逐项自查（validate_architecture 机器门待 R4 JS 化）：机制耦合规格 + 血缘双源 + 油耗/空窗数字门；上游回执在审查侧经 upstream-reviews 槽注入，生成侧不注入）。**Strategy sub agent 的输入** = direction + architecture 双上游正文与 metadata（cadence_plan / mainline_density / engines 已随 upstream 槽注入）+ persona 全文 + genre 信息包 + setup 全量，核心职责是七行上游消费翻译（含 fulfillment_count / escalation_levels / beats_per_volume 三处数字对账）、代价类型学（不可逆/压制分桶，主角永久损伤须 book_soul 声明）、承诺-债务周期（登记承诺三分类，即兴铺垫允许烂尾）、中盘续命换挡与终局纪律（closed 收束预算 / open 喂料声明），交付前按 strategy metadata 速查表逐项自查（validate_strategy 机器门待 R4 JS 化）：阶段数×档位区间 + 存债连续上限 + 收束预算 + 终局字数下限；strength/defer 的跨阶段保护在审查侧注入）。**World sub agent 的输入** = architecture + strategy 双上游正文与 metadata（handoffs.world_changes / midpoint_renewal / costs 随 upstream 槽注入）+ persona 全文（盲区→消费场景类型门）+ genre 信息包 + setup 全量，核心职责是上游消费表逐项处置（world_changes 对消费时序表 / midpoint 演化预留 / open 喂料储备）、岗位表（设位不设人——六角色的人侧席位化，主要席位标注处置）、代价两轴（可逆性×承担者，压制必带解除，不得新增主角永久代价）、术语语域表四件套 + metadata 机器可读形态（正文执行端经 world_lexicon 槽消费），交付前过 `legacy-python/scripts/novelos_validate_world.py metadata.json`。**Character sub agent 的输入** = world 全文（岗位表/力量体系细则/语域表）+ strategy 正文与 metadata（character_arcs / claim_ledger / stages）+ kernel 全文 + persona 全文（盲区→角色类型门/目光→失稳频段/库存→细节原料）+ genre 信息包 + setup 全量，核心职责是席位认领（world 主要席位逐一处置 + roster seat_ref 回指）、能力边界对 world 细则立档、strategy 弧职责与承诺逐条挂接、退场七型与死亡设计卡、essence 人物卡（main 必填——执念/失稳/语域一句话要点，正文执行端 character_essence 槽消费），交付前过 `legacy-python/scripts/novelos_validate_character.py metadata.json --project <project_id>`（scale 与 locked world 自动解析，也可显式 `--scale/--world`；roster 规模×档位区间 + 席位对账——「待契约认领」无人认领 = FAIL）。**Story Arc sub agent 的输入**（T38）= strategy/character/world 三上游全文与 metadata + **book_soul 机器可读槽**（recurring_tests 编号引用、弧终点门 forbidden_resolutions/protected_dignity、cadence_plan 台账间隔）+ **架构机制清单槽**（mech_ref 引用变奏声明原文）+ persona_gate（变奏分配盲区门）+ genre 信息包（弧型与 genre_stage_form 对偶）+ project_setup（scale 档位值），核心职责是八行上游消费表（stages 边界对齐/claim_ledger 对账/handoffs 挂接/时序表挂接/代价两轴/演化预留与喂料）、弧载体指认（carriers: roster/seat/latent）、卷计划（**全书卷数权威**）、映射表与种收台账（close XOR exempt 豁免体系）、变奏分配与开放滚动窗口，交付前过 `legacy-python/scripts/novelos_validate_story_arc.py metadata.json --project <project_id>`（弧数×档位、映射表活跃窗、台账兑现门、载体/机制对账、open 窗口——四上游 locked metadata 自动解析）。**Volume sub agent 的输入**（T39）= story_arc 全文与 metadata（弧挂接 arc_id/映射表职责格/静态台账/变奏分配）+ world 全文 + **book_soul 机器可读槽**（recurring_test 原文/forbidden_resolutions/power_currency 力量货币定义——变奏与赌注计价引用原文不凭转述）+ **架构机制清单槽**（mechanisms + mainline_density：四段引用机制运转规则、beats_per_volume 落位 mainline_beats、低密度主线不被削平）+ **前置卷链**（按卷号取近 2 卷 locked——上卷结算的不可逆/新压力逐项承接）+ **连续性账本**（promise_ledger：实际未决承诺/弧状态/事实切片/上卷末章摘要——种收双对账 + 实际结算优先源）+ 人物名册镜像 + persona_gate（班底盲区门 + 主高潮/关键场景结构级盲区门）+ genre 信息包（reader_expectations 收益承接/typical_dilemmas 变奏原料/taboos 防火墙/genre_stage_form 卷型对偶）+ setup 快照（平台对齐：第一卷末主高潮对上架节点），核心职责是**卷型先行**（连续四段默认/单元编排——副本/案件/赛季 units 编排表/换图清算 exit_settlement 三清单）+ 线粒度双 scope（跨卷弧 arc_id 挂接 + 卷内自含线）+ 高潮门按本卷字数条件化（climax_positions）+ 新设定入 volume_settings 表（班底/势力/地点/物品/规则/副本世界——表外发明 blocking）+ 新种悬念 new_plants 结构化回写，交付前过 `legacy-python/scripts/novelos_validate_volume_outline.py metadata.json --project <project_id>`（卷号连续/字数对表 volume_plan/高潮门/线弧双向/单元编排/换图/终卷纪律/班底预检）。**Chapter Plan sub agent 的输入**（T38）= 卷纲 + character/world 契约全文 + 名册镜像 + persona_gate + setup 快照 + promise_ledger（弧线挂接 arc_id 与兑现对照实际账本），必须给出 `soul_pressure` 与 `moral_residue`。
6. sub agent 返回候选后落库为**候选**（仅允许 `status='candidate'`——`locked`/`stale`/`superseded` 状态变更一律走门工具，禁止手工 UPDATE）：
   ```sql
   -- 候选暂存（candidate 专用；锁定必须经门工具 novelos_lock_asset）
   INSERT INTO resources (id, media_type, content, content_hash) VALUES (?, 'text/markdown', CAST(? AS BLOB), ?);
   INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role, metadata_json, version)
   VALUES (?, ?, ?, ?, ?, 'candidate', ?, ?, ?, 1);
   -- 记录上游依赖
   INSERT INTO planning_asset_dependencies (asset_id, upstream_asset_id, upstream_version) VALUES (?, ?, ?);
   ```
7. 用 `$novel-review` 审查（sub agent 审查 → 主控调用插件门工具 `novelos_review_commit` 落回执：参数 `subjectRef`+`verdict`+`findingsJson`+`reviewerProfile`（格式 `model:<provider:model>` 或 `agent:<name>@<model>`）；裸 INSERT reviews 已退役）。direction 的审查 rubric 同样按项目组装：`node scripts/novelos-compose-prompt.mjs --asset direction-review --project <project_id> --subject <候选资产ID>`——频道语法/平台画像/题材信息包/美学基因的专项检查随项目路由，与生成端对称。direction 产出 2-3 候选时按 novel-review「横向回执」汇总比较呈报用户，用户裁决选定后仅对选定候选走锁定循环。
8. 审查通过后锁定：调用插件门工具 `novelos_lock_asset`（参数 `assetId`+`lockedReviewId`，可选 `dryRun`）。门内硬性约束：① `lockedReviewId` 必须指向存在且 `verdict='approved'` 且 `subject_ref`=该资产的 review——跳审锁定 FAIL；② 单事务内自动先把同 scope 旧 locked 行翻 `superseded` 再置本行 `locked`（部分唯一索引 `idx_planning_assets_current`）；③ 直接上游未全部 locked 时按依赖顺序拒绝（`dryRun=true` 跳过此项仅告警）。裸 `UPDATE planning_assets SET status='locked' ...` 已退役。**character_contract 锁定后**：主控调用插件门工具 `novelos_register_characters`（参数 `project`+`roster`+`world`=JSON 文本）落人物注册表（main/secondary + arc_role/预期退场/登场卷/seat_ref/essence 随 state_json；席位对账 + 近重名 WARN）。**volume_outline 锁定后**：若候选 metadata 带 `volume_characters`（卷级配角班底，secondary/minor），主控随即调用门工具 `novelos_register_characters`（`entries`=`volume_characters.json` + `world`）落人物注册表（条目带 source:"volume_outline"、arc_role、预期退场、来源卷、seat_ref；席位对账：seat_ref 引用不存在 = FAIL，未认领承诺席位 WARN 终核）；随后 `auditEntries=true` 只读终核班底落表（漏跑即报告非空）；`volume_settings` 中 disposition=登记入world 的条目走 world change proposal 增补，`new_plants`/`drift` 经 change proposal 增补 story_arc 台账与映射表。
9. 若下游 Agent 发现上游问题，返回变更提案由主控路由给上游所有者，不在下游候选中隐式重写上游。

## 上游变更与 stale 传播

上游资产修订（新 revision locked）后，调用插件门工具 `novelos_propagate_stale { asset: '<上游id>' }` 标记下游 stale。

## Expansion Skill（可选方法素材）

expansion 方法卡是**共享模块库**（原位保留在 `catalog/skills/expansions/`），两种消费方式：① 组装器 manifest 声明——skill 的 `modules/manifest.json` 可跨包引用 expansion 卡（`file` 相对路径）随项目路由注入；② 按需 Read——`catalog/skills/expansions/<name>/prompt.md` 注入 sub agent 上下文。含 clusters/ 子目录的 atlas 包，按题材 Read 对应簇文件。

## book_soul 字段速查表

Direction 候选的 `metadata.book_soul` 必须符合 `config/schemas/book-soul.schema.json`（v2，十三字段）：

| 字段 | 类型 | 约束 |
|---|---|---|
| `schema_version` | const | 固定值 `2` |
| `organizing_principle` | string | 组织原则：本书独有的组织过程，1-1000 字符 |
| `central_contradiction` | string | 两难结构的核心矛盾，1-1000 字符 |
| `promise_cadence` | string | 承诺兑现节奏（strategy 展开为阶段收益），1-1000 字符 |
| `unresolved_claims` | string[] | 1-24 项，每项 ≤500 字符 |
| `costly_commitments` | string[] | 同上 |
| `protected_dignity` | string[] | 同上 |
| `forbidden_resolutions` | string[] | 同上 |
| `recurring_tests` | string[] | 同上 |
| `narrative_mercy` | string | 1-1000 字符 |
| `narrative_cruelty` | string | 1-1000 字符 |
| `deliberate_silences` | string[] | 同上 |
| `lineage`（可选） | object[] | 逐字段血缘映射：{field, source_type: signature/persona/kernel/setup/reference_material, source_ref, derivation, variation?}；2-24 条，organizing_principle 与 central_contradiction 必须有条目；variation=true 为显式血缘变奏（发散纪律允许至多一个变奏候选） |
| `cadence_plan`（可选） | object | 兑现规划：{fulfillment_count, interval_volumes, notes?}——`--scale` 机器数字门（短篇 1-2 / 中篇 ≥3 / 长篇 ≥3 / 超长篇 ≥5）；新 direction 候选必带 |

校验口径：结构 + lineage 覆盖 + cadence_plan 数字门（validate_book_soul 机器门待 R4 JS 化，当前按本表逐项对照自查）。book_soul 只有 v2 一个版本；既有 v1 资产属历史锁定数据，不参与新候选校验。

## architecture metadata 速查表

Architecture 候选的 `metadata` 必须符合 `config/schemas/architecture-metadata.schema.json`（v1）：

| 字段 | 类型 | 约束 |
|---|---|---|
| `mechanisms[]` | object[] | 2-16 条结构化机制：{name, sources[]（source_type: direction_field/persona_part/genre_pack/setup/reference_material + ref）, rhythm, downstream[]（strategy/character_contract/world_contract）, coupling{form: io/quota/both, spec}}；每机制必须有耦合条目（孤岛 schema 层不合法）；sources 全体须同时含 direction_field 与 persona_part（血缘双源） |
| `mainline_density` | object | {tier: 高/中/低, beats_per_volume, gap_limit_volumes, burst_positions[]}——tier 与 beats 一致性机器校验（高 ≥1 / 中 [0.5,1) / 低 <0.5）；空窗上限×scale 档位（短篇 1 / 中篇 2 / 长篇 3 / 超长篇 4 卷） |
| `unit_arc` | object | {min_chapters, max_chapters}——单元弧粒度（免费平台常规 2-5 章/单元） |
| `engines` | object | {production: {escalation_levels}, integrator: {escalation_levels}}——油耗分级×scale 下限（短篇 ≥2 / 中长篇 ≥3 / 超长篇 ≥5），与 book_soul cadence 数字门同源 |

校验口径：本表逐项对照自查——tier 与 beats 一致性、空窗上限×scale 档位、油耗分级下限与 book_soul cadence 数字门同源（validate_architecture 机器门待 R4 JS 化）。低密度主线（柯南/X 档案式空窗+爆发）合法，前提是空窗有上限、爆发点有位置设计、与上游对表论证。

## strategy metadata 速查表

Strategy 候选的 `metadata` 必须符合 `config/schemas/strategy-metadata.schema.json`（v1）：

| 字段 | 类型 | 约束 |
|---|---|---|
| `consumption[]` | object[] | 恰 7 行上游消费翻译：{output（rhythm_table/reveal_ladder/promise_cadence/power_escalation/spiral_rotation/engine_config/upstream_receipts）, translation, ref}——缺行 = 上游静默蒸发，validate 拦截 |
| `genre_stage_form` | string | 题材阶段阶梯（境界弧/案件弧/赛季弧/副本弧/里程碑弧）；缺位时写显式声明，禁默认模糊升级 |
| `persona_usages` | object | {gaze（揭层节奏）, blindspot_gate（终局场面形态门）, pov_contract, inventory（阶段燃料）}——引用 persona 全文部件 |
| `stages[]` | object[] | 1-12 条：{name, word_range{min,max}（申报非下限）, dominant_spiral, payoff（heavy/light/debt）, progress_types（1-8 类：信息/能力/位置/关系/地位/资源/认知/对手）, pov, costs[], end_condition, cause_bridge} |
| `stages[].costs[]` | object[] | 代价分桶：{type（irreversible/suppression）, landing（world/plot_character/item/protagonist_temporary/protagonist_permanent）, form, source{source_type, ref}}；suppression 必带 release；protagonist_permanent 必带 declared_in_book_soul:true + book_soul_ref（主角永久损伤不在默认菜单） |
| `claim_ledger[]` | object[] | 登记承诺三分类：{claim, disposition（midstory/terminal/silence）, anchor}——即兴铺垫不进账本可烂尾，登记承诺不许遗忘 |
| `pairing_cycle` | object | {debt_streak_limit: 1-3}——连续纯存债阶段上限（validate 核验实际连续段） |
| `midpoint_renewal` | object | {stage, form（换地图/矛盾换轨/势力重组/规则改写/其他）, note}——阶段数 ≥3 必备（中盘塌陷防线） |
| `terminal_mode` | enum | closed（完结设计）/ open（开放引擎，必带 open_note 喂料声明——无尾化必须是设计不是事故） |
| `terminal` | object | closed 必带：{closure_budget（terminal 类承诺条数上限，防赶工烂尾）, echo（首尾呼应：兑付 promise+progress 两笔）, word_floor（终局阶段字数下限万字）} |
| `handoffs` | object | {character_arcs[], world_changes[]}——下游交接清单，character/world 契约不得自创与阶段骨架冲突的弧线 |
| `decision_points[]` | object[] | 0-4 条：{question, options（3-4 个 {label, detail, tradeoff}）, source_excerpt}；无关可空数组，不凑数 |

校验口径：结构 + 七行消费覆盖 + 阶段数×档位区间[短篇 1-2/中篇 2-4/长篇 3-8/超长篇 5-12] + 存债连续 + 中盘续命 + 收束预算/终局字数下限（validate_strategy 机器门待 R4 JS 化，当前按本表逐项对照自查）。

## world metadata 速查表

World 候选的 `metadata` 必须符合 `config/schemas/world-metadata.schema.json`（v1，T36）：

| 字段 | 类型 | 约束 |
|---|---|---|
| `seats[]` | object[] | 1-40 席位（设位不设人）：{name, org, duty, power_tier, rule_links?, first_consumption, disposition?（待契约认领/待卷级班底/显式虚位）}——六角色的人侧与势力结构的岗位化；给人配姓名内心 = 越权造人 blocking |
| `lexicon` | object | 四件套机器可读：{positive_terms 3-60, banned_categories 四类各 ≥1 示例禁词, measure_system, exceptions}——正文执行端（chapter-draft/prose-review）经 world_lexicon 槽消费 |
| `dimension_costs[]` | object[] | 1-12 维度：{dimension, form, reversibility（可逆/压制/不可逆）, threshold?, release?, bearer?, book_soul_ref?}——压制必带 release；不可逆必带 threshold（validate 复核）；bearer=protagonist_permanent 必带 book_soul_ref（世界层不得新增主角永久代价） |
| `decision_points[]` | object[] | 0-4 条世界层命门决策点；无关可省略 |

校验口径：schema + 岗位重名 + 代价两轴（validate_world 机器门待 R4 JS 化，按本表对照自查）。character 侧 roster 规模档位：短篇 2-5 / 中篇 3-8 / 长篇 5-12 / 超长篇 8-16；roster 校验含规模门 + 席位对账——scale/locked world 自动解析，权威校验在 `novelos_register_characters` 门内执行（validate_character 机器门待 R4 JS 化）。

## story arc metadata 速查表（T38）

Story Arc 候选的 `metadata` 必须符合 `config/schemas/story-arc-metadata.schema.json`（v1）：

| 字段 | 类型 | 约束 |
|---|---|---|
| `volume_plan[]` | object[] | 1-40 卷：{index, word_range{min,max}}——**全书卷数权威在此声明**（strategy 只给阶段字数，卷切分归弧层）；卷字数总和与阶段字数同量级（validate 对表） |
| `arcs[]` | object[] | 短篇 1-2/中篇 2-3/长篇 3-5/超长篇 5-7（validate ×scale 机器门）；主线（kind=主线）恰 1 条；{arc_id slug, name, kind（主线/人物/关系/世界/对手/其他）, carriers[{ref, ref_type: roster/seat/latent}], start_state, end_state, turning_points[]}——主线/人物/关系弧必须具名载体；弧首活跃卷 ≥ 载体登场卷（validate 对账） |
| `arc_volume_map[]` | object[] | 行式映射表 {arc_id, volume, duty（推进/蓄势/兑现/收束/休眠）, note}——每卷 ≥1 推进（error）/ 推进 ≤2（warn）/ 同时活跃（推进/兑现/收束）≤4（error）/ 禁全推进全休眠（validate） |
| `plant_payoff_ledger[]` | object[] | {line_id, claim, source_type（book_soul/strategy/arc）+source_ref, plant_volume, partial_payoffs[], close_volume+close_form（兑现/违约/转化）XOR exempt}——收束与豁免二选一；合法豁免仅 deliberate_silences 与 open 喂料；卷 2 起每卷至少兑现一条（validate） |
| `variation_alloc[]` | object[] | {test_ref（引用 book_soul recurring_tests 编号）, volume, changed[]（处境/答案/代价至少其一）, mech_ref（architecture 机制名——validate 存在性对账）, note}；同一母题 >3 次变奏 warn（剩余空间评估） |
| `open_window` | object | strategy terminal_mode=open 必填（validate）：{hard_volumes 1-5, note}——近卷硬格/远卷软格滚动窗口；**增量修订从 arc_states 实际进展出发，写偏的弧是已发生事实** |
| `decision_points[]` | object[] | 0-4 条弧层命门决策点（弧数取舍/终点形态/种收节奏）；无关可空数组，不凑数 |

校验口径：scale 与 character/world/architecture/strategy 四上游 locked metadata 自动解析（validate_story_arc 机器门待 R4 JS 化，按本表对照自查）。连续性侧 `arc_states.arc_ref` 引用 `arc_id` slug（无对应弧用描述性 key，不发明新 id——planned vs actual 对账依赖此约定）。

## volume metadata 速查表（T39）

卷纲候选的 `metadata` 必须符合 `config/schemas/volume-outline-metadata.schema.json`（v1）：

| 字段 | 类型 | 约束 |
|---|---|---|
| `volume_number` | int | 卷号锚定——前置 locked 卷须为 1..N-1 连续，本卷 = N（validate --project 核验，prev 卷链按卷号注入）；乱序规划在此拦截 |
| `word_range` | object | {min, target, max} 本卷字数申报——与 story_arc volume_plan 本卷行有交集（validate）；target 是副高湂数条件化基准 |
| `volume_form` | enum | 连续四段（默认）/单元编排（副本难度弧/案件升级弧/赛季弧对偶——units 必填）；换图清算经 exit_settlement 叠加 |
| `lines[]` | object[] | 3-12 条 {name, scope（跨卷弧/卷内自含）, arc_id（跨卷弧必填，回指存在的弧且本卷 duty 活跃）, share_pct（合计 90-110）, mainline（0-1 条）, pov, note（自含线的加压/结算声明）}——映射表本卷活跃弧必须有承载线（职责蒸发 = error） |
| `mainline_beats` | int | 0-8——对架构 beats_per_volume ±2（validate）；tier=低 允许 0 拍卷 |
| `climax_positions[]` | number[] | 卷长比例升序，末位 = 1（卷末主高潮）；相邻间距 × target ≤ 30 万字；target ≥ 20 万时总数 ≥ target÷25万 向上取整；短篇退化（<20 万字）允许仅主高潮（validate） |
| `units[]` | object[] | 单元编排表（volume_form=单元编排 必填）：{unit_id, theme 主题内核, chapter_window{min,max}, mainline_advance ≥1（interlude 间歇单元除外）, new_setting_ref}——单元章数窗总量超卷容量 warn |
| `exit_settlement` | object | 换图卷三清单 {carry 随行资产, cut 斩前缘（显式处置）, pre_close 离图前收账 line_id}——人际/势力在新图作废的预防针 |
| `new_plants[]` | object[] | 本卷新种悬念 {line_id, claim, close_volume XOR exempt}——收束卷 ≥ 本卷、不与既有台账冲突（validate）；主控据此经 change proposal 增补台账；终卷新种不得溢出终卷 |
| `drift[]` | object[] | 计划 vs 实际漂移 {arc_id, planned, actual, proposal}——arc_id 须存在（validate）；以实际结算为优先源 |
| `test_alloc[]` | object[] | 本卷变奏承接 {test_ref, changed[]}——与 variation_alloc 本卷行双向对账（漏承接/超分配均 warn，validate） |
| `volume_settings[]` | object[] | 本卷新设定表（势力/地点/物品/规则/副本世界）{kind, name, spec, disposition（卷内自闭/登记入world）, seat_ref?}——表外发明 = 审查 blocking；登记入world 锁定后走 world change proposal |
| `volume_characters[]` | object[] | 班底（planning-candidate $defs 同构，secondary/minor）——锁定后经 `novelos_register_characters` 的 `entries` 参数落表，`auditEntries:true` 终核漏跑 |

校验口径：scale 与 story_arc/architecture/strategy locked metadata + 前置卷号 + 注册表名册自动解析（validate_volume_outline 机器门待 R4 JS 化，按本表逐项对照自查）。

## character essence 速查表（T37）

roster 行的 `essence`（main 必填，≤160 字）：执念/失稳点/语域口癖/最要命的关系——「写他时必须抓住什么」。契约锁定后随门工具 `roster` 参数落注册表 state_json，写作端与 prose-review 经 **character_essence 槽**按行消费（出场人物卡：要点 + 死活状态；已退场人物不得无连续性依据出场）。二级造人端（卷纲班底/执行卡微档案）另经 **persona_gate 槽**注入分身硬边界（cannot_write/refuses/表达偏好/负向约束）——新造人物不得整档落在盲区场景，确需涉盲区者微档案带绕开方式。

## 节奏密度约束

战略骨架（Strategy）的阶段数按 scale 档位区间约束（短篇 1-2 / 中篇 2-4 / 长篇 3-8 / 超长篇 5-12，validate --scale 机器门），阶段判据以事件（不可逆变更 + 螺旋轮换）为主，字数区间为申报项。节奏密度在 Volume Outline 及以下实现。Volume Outline 必须产出并行冲突线（每卷 ≥3 条，跨卷弧切片与卷内自含线双 scope）、高潮位置按**本卷字数**条件化（相邻间距 ≤30 万字、target ≥20 万时总数 ≥ target÷25万 向上取整、短篇退化允许仅卷末主高潮——validate 机器门）、POV 多样性（频道轴 POV 配置在条件模块）。

## 用户打断

规划生成或审查进行中用户提出修改：立即停止当前候选，按 AGENTS.md「用户实时打断与修改」协议分流（setup 级/资产级），呈报将 stale 的资产清单后再执行。
