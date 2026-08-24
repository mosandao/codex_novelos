# NovelOS Tasks

本目录只记录可执行工作和交付证据。稳定设计以 `documentation/` 为准。

## 当前架构：NovelOS 轻量化（SQLite MCP 完全替代 NovelOS MCP）

源自外部商业网文评估暴露的审查标准盲区 → 全链路追踪发现 130+ 次 MCP 调用中 55% 是治理开销 → 架构评估确认 89 个工具 90% 可被 SQLite MCP 替代。

| Task | 状态 | 说明 |
|---|---|---|
| [Task 39](./39_volume_outline_overhaul.md) | `DONE` | 卷纲阶段深度整改——卷型/高潮门/线弧双向与双通道回写（24 项六病根全量落地）：volume-outline-metadata schema 新建（**volume_number 卷号锚定**（乱序规划拦截，prev 链按卷号排序）+ word_range 对 volume_plan + volume_form 连续四段｜**单元编排**（units 编排表：主题内核/章数窗/主线最小渗透/间歇单元——无限流副本与案件/赛季卷的承载）+ **exit_settlement 换图清算三清单**（carry 随行/cut 斩前缘/pre_close 离图收账）+ lines 双 scope（跨卷弧 arc_id｜卷内自含线合法化——解 ≥3 线门与弧活跃窗 ≤4 的数学顶牛）+ share_pct 篇幅配比 + climax_positions + new_plants 结构化回写 + drift + test_alloc 变奏承接 + **volume_settings 新设定表**（势力/地点/物品/规则/副本世界，表外发明 blocking，disposition 卷内自闭｜登记入world））；validate_volume_outline.py 11 组机器门（卷号连续/字数交集/**高潮门按本卷字数条件化**（间距 ≤30 万、总数 ≥target÷25万、短篇退化）/线弧双向（职责蒸发 error、挂休眠 warn）/单元门/清算引用/新种 XOR+终卷纪律（closed 禁豁免）/变奏双向/tier 削平与喂不饱/班底预检）+ --project 五路自动解析；composer——prev 槽卷号排序 + promise_ledger 扩**连续性事实（chapter_facts）与上卷末章摘要**（「实际结算优先源」补齐实际面）+ 双端 manifest 加 book_soul/mechanisms（机制原文/力量货币/测试定义从转手名升可引用实体，审查同盲解除）；双端 prompt 重写（卷型节/主线节拍对表 beats_per_volume±2/平台上架对齐/题材三件套消费/**场景盲区门**（主高潮整场落「写不了」=blocking——班底不落盲区≠场景不落盲区）/终卷分支/审查 16 项+机器门前置）；频道模块补 POV 配置；chapter-plan 双端 POV+章数×字数对账；register `--audit-entries` 班底漏跑终核（非零退出）；SKILL Volume 段+速查表+节奏约束更新；274 tests 四命令全绿。 |
| [Task 38](./38_story_arc_overhaul.md) | `DONE` | story_arc 阶段深度反向审计与全量落地（28+6 项：装备缺失/边界错位/横向断供/消费倒挂/横切+补挖——全链唯一零结构化出口阶段补齐）：story-arc-metadata schema 新建（arcs 载体指认 roster/seat/latent + volume_plan **卷数权威** + 行式映射表 + 种收台账 close XOR exempt 豁免体系（deliberate_silences/open 喂料；违约/转化是合法收束）+ 变奏分配 mech_ref + open 滚动窗口 + decision_points）；validate_story_arc.py 八类机器门（弧数×scale 档位 1-2~5-7/主线恰一/每卷 ≥1 活跃、同时活跃 ≤4/卷 2 起每卷兑现 ≥1/载体存在性与登场卷对账/机制存在性/open 窗口必填）+ --project 四上游自动解析；composer 四新槽（book_soul 编号引用/mechanisms 机制清单/prev_volume_outline 卷际链最近 2 卷/promise_ledger 规划端账本）+ canon 弧窗口 4→8；story-arc 双端 prompt 重写（八行消费表/弧终点门 forbidden_resolutions+protected_dignity/短篇退化形态/open 增量修订「写偏的弧是已发生事实」/审查 7→16 项）；volume 挂接 arc_id + 种收双台账对账（static+实际）+ 前置卷承接 + 已退场载体不推弧；chapter-plan 弧线挂接（引用已 closed 承诺=blocking）；continuity arc_ref slug 约定；规划中段断供带修复（story_arc/volume/chapter 补 project_setup，volume+story_arc 补 genre_pack）+ E4 生成侧回执描述漂移修正；246 tests 四命令全绿。 |
| [Task 37](./37_character_execution_delivery.md) | `DONE` | 人物阶段深度整改——执行端投递、席位闭环硬门与二级造人约束：roster + `essence` 人物卡（main 必填，执念/失稳/语域一句话，正文端经 character_essence 槽注入 chapter-draft/prose-review——出场人物卡带死活状态防无因复活，修复「契约只设计不交付」结构断裂）；`persona_gate` 轻量槽通卷纲/执行卡（盲区 refuses/cannot_write 自带绕开方式——班底/微档案不得整档落盲区，补齐二级造人约束）；执行卡 +出场人物要点字段 + character_roster 槽（微档案查重从空头支票变有名册可查）；席位闭环：register roster 白名单补 seat_ref/essence（修文档-代码不符实 bug）+ `--world` 对账（引用不存在 FAIL/未认领承诺席位 WARN 终核）+ validate 处置分级（待契约认领无人认领=error，标注不是免检标签）+ `--project` 自动解析 scale/world（含 setup.scale 全标签归一化）；近重名归一化 WARN（NFKC/空白/大小写）。223 tests 四命令全绿。 |
| [Task 36](./36_character_world_serialization.md) | `DONE` | 人物‖世界串行化与世界/人物阶段深度重构：链形 world→character（sibling 并行退役，world 增量修订沿依赖边自动标 character stale）；world 岗位表（设位不设人，六角色人侧席位化，主要席位处置枚举）+ 代价两轴（可逆性三档+阈值/承担者，压制必带解除，不得新增主角永久）+ 上游消费表（world_changes↔时序表对账/midpoint 演化预留/open 喂料储备）+ 女频全向频道模块三对偶 + world-metadata schema/validate；character 世界移交消费（席位认领 seat_ref/能力边界对 world 细则/语域分化/代价认领）+ persona 四用法（盲区角色类型门/目光失稳频段/库存细节原料）+ strategy 挂接（弧载体/承诺认领）+ roster 规模档位机器门（短篇 2-5~超长篇 8-16）+ 题材人物光谱模块；执行端语域表接通（world_lexicon 槽注入 chapter-draft/prose-review）+ 卷纲盲区修复（world 全文+人物名册镜像+世界对账+禁止就地发明）。209 tests 四命令全绿。 |
| [Task 35](./35_strategy_stage_overhaul.md) | `DONE` | 战略阶段深度反向审计与全量落地：上游消费表 v3 七行（+双层引擎配置/上游回执，三处数字对账）+ book_soul 十三字段逐样处置；题材阶段形态位；persona 四用法（揭层节奏/终局场面形态门/POV 契约/阶段燃料）；代价类型学（不可逆/压制分桶，主角永久损伤须 book_soul 声明，死亡过 protected_dignity）；承诺-债务周期（progress 八类/存债连续上限/登记承诺三分类，即兴铺垫允许烂尾）；阶段量化档位区间化（短篇 1-2/中篇 2-4/长篇 3-8/超长篇 5-12，旧 ≥20 万下限废除）；中盘续命换挡 + 终局纪律（closed 收束预算/open 喂料声明双模式）；下游交接清单 + 发散纪律；审查 7→13 项 + 槽位 3→8（双上游回执/persona/genre）；新 schema/validate/20 项测试。188 tests 四命令全绿。 |
| [Task 33](./33_direction_reverse_audit.md) | `DONE` | 方向阶段反向审查批次：direction 双侧强化——审查侧补 check-aesthetic 对偶、规模数字门、证伪与读者模拟、库存反向对账、血缘逐字段核验、cruelty 落点、check 执行纪律、strength 通道、横向回执；生成侧七维比较表（情感登记错开）、发散纪律（最大反差档+血缘变奏）、负向承诺语法（暗色主轨合法）、逐字段血缘映射、画像薄声明；novel-review 加 accepted_risk 豁免/辩护回合/strength；receipt schema severity+豁免字段；book_soul v2 可选扩展 lineage + cadence_plan（validate --scale 机器数字门）。151 tests 四命令全绿。 |
| [Task 34](./34_architecture_two_layer_engine.md) | `DONE` | 架构阶段深度反向审计与双层引擎重构：并列双引擎→嵌套模型（生产层单元机器·单元弧粒度 + 统合层统合器·主线节拍表/单元配额/注入配额），柯南式低密度主线显式合法（空窗上限×scale 机器门，主线膨胀同罪）；耦合双形态（I/O‖配额注入，声明式空话不合格）；题材死槽激活（母题→输入源/桥段→变奏对象/禁忌→防火墙）；persona 四用法+血缘双源+库存对账；验证记录落正文+油耗×档位数字门；管线修复：upstream 槽补注 metadata（cadence_plan/lineage 不再蒸发）+ upstream-reviews 槽（strength 跨阶段保护）+ 审查侧槽位贫血补齐；新 schema/validate/15 项测试。168 tests 四命令全绿。 |
| [Task 32](./32_volume_characters.md) | `DONE` | 卷级配角班底（动态配角第二造人口）：volume_outline 候选 metadata.`volume_characters`（冲突线载体逐一指认来源，无源 blocking；禁 main/禁跨卷/禁重名）→ 锁定后经 `--entry` 落人物注册表（arc_role/预期退场/来源卷/source）→ 本卷执行卡直接消费。schema $defs + 脚本校验 + 三 prompt + 两审查 + SKILL/flows 同步。138 tests 四命令全绿。 |
| [Task 31](./31_chain_seam_gaps.md) | `DONE` | 创建链路衔接缺陷修复（Task 30 后复查）：单次调用建核+建项目链路打通、内核近重复/孤儿 WARN、账本↔人物注册表对账（--pending-status）、旧版内核绑定 WARN、roster 重锁对账、复活清退场痕迹+状态史审计；连带修复 revise 信封 CLI 崩溃（存量）。135 tests 四命令全绿，库副本 CLI 冒烟全链复验。 |
| [Task 30](./30_author_kernel_and_character_lifecycle.md) | `DONE` | 作者内核双层架构（跨书内核+每书派生，取代原型直连）+ 创作链深度参与 + 人物全量设计与生命周期（死亡/退场/状态账本/动态配角）+ 世界规则深化（六角色/三类规则/力量-规则循环）+ 道德债功能化。119 tests 四命令全绿，端到端冒烟在库副本验证。 |
| [Task 28](./28_agent_prompt_enhancement_queue.md) | `DONE` | 各级 Agent Prompt 增强队列（阶段 0-2 原位完成；剩余范围经 Task 29 组装管线交付——P0-2/P2-1..P2-9）。 |
| [Task 29](./29_dynamic_prompt_composition.md) | `DONE`（P0-P5 全部完成：24 skill 模块化 + 配方矩阵 + 数据槽四件套 + 循环边界 + adapters 三 harness + AGENTS 瘦身 -44% + 精细 stale；98 tests；唯一遗留=codex 复验一条命令，被用户中转 API 403 拦截——环境侧故障，非本仓） | 动态 Prompt 组装流水线 + 三 harness 适配（codex/zcode/deepseek）：组装器通用化（manifest schema v2 + 声明式槽位 + 组装日志）→ 全链路 skill 模块化（吸收 Task 28 剩余）→ 题材×材料数据槽 → adapters 单源生成 + AGENTS.md 瘦身 → 可选精细 stale。可追溯（commit 规约 + 组装日志）可核验（每任务项带验收命令）。 |
| [Task 25](./25_sqlite_mcp_poc.md) | `DONE` | SQLite MCP server + POC 验证 + 5 个桥接脚本（stale 传播/hash/book_soul/reconcile/projection）。纯增量，不停 NovelOS MCP。 |
| [Task 26](./26_creation_flow_sql_migration.md) | `DONE` | migration 016 在真实数据库执行（35→26 表）+ NovelOS MCP 停用 + 6 个 SKILL.md/AGENTS.md 重写 + 端到端 7/7 验证通过。 |
| [Task 27](./27_prose_webnovel_accessibility.md) | `DONE` | craft skill prose-webnovel-accessibility（通俗度/开头/钩子强度）+ writer/reviewer/章纲三端引用。 |

## 仍有用的历史 Task

以下 Task 的产出（方法论/功能/catalog skill）在当前 SQLite MCP 架构下仍然有效：

| Task | 说明 |
|---|---|
| [Task 06](./06_user_project_projection.md) | 用户项目文件夹投影（`scripts/novelos_render_projection.py` 仍用） |
| [Task 07](./07_prompt_catalog_expansion.md) | 创作 Prompt Catalog 扩展（`catalog/skills/` 仍在用） |
| [Task 08](./08_author_signature_and_book_soul.md) | 作者签名与 book_soul（概念和 schema 仍在用） |
| [Task 09](./09_narrative_archetype_derivation.md) | 叙事原型与项目化作者派生（项目创建向导仍用） |
| [Task 15](./15_volume_outline_pacing_density.md) | Volume Outline 节奏密度约束（novel-planning SKILL.md 保留） |
| [Task 16](./16_review_prompt_self_containment.md) | 审查 prompt 自包含约束（novel-review SKILL.md 保留） |
| [Task 17](./17_world_contract_prompt_enhancement.md) | World Contract Prompt 维度处理 |
| [Task 18](./18_world_contract_review_binding.md) | World Contract Review Rubric 消费绑定 |
| [Task 20](./20_scenario_atlas_genre_seeds.md) | 桥段图集 Skill |
| [Task 21](./21_creation_seed_entry_layer.md) | 创作种子非权威入口层 |

## 延期工作

| 工作 | 状态 | 恢复条件 |
|---|---|---|
| [70-case Agent 质量实验](./experiments/agent_quality/README.md) | `DEFERRED` | 按 `deferral.json` 完成剩余案例、独立盲评和可重算汇总 |

## 目录边界

- `migration/`：来源、迁移、备份、恢复、导出证据（只读参考）
- `cutover/`：切换与仓库卫生证据
- `experiments/agent_quality/`：延期质量实验的数据/恢复点/证据
- `07_prompt_catalog/`：Task 07 的执行批次明细
- 顶层 `Task NN`：一个文件 = 一个可独立验收的阶段
