# Task 39：卷纲深度整改——卷型/高潮门/线弧双向与双通道回写

状态：DONE（2026-08-22）

## 背景

T38 完成故事弧层整改后，对其直接消费方 volume_outline 做同构深度反向审计（persona/setup 四轴/上游链触达/生成-回写闭环/无限流单元剧压力测试/主线支线产能/联网锚点校验），共梳理 24 项问题，收敛为六根病根：

1. **引用不可见实体**：四段结构「引用架构机制运转规则」、男频「以力量货币计价」、灵魂职责 recurring_test 变奏——prompt 硬指令指向注入里不存在的原文（只有 arc 转手的 mech_ref/test_ref 名），幻觉引用/空名引用两失效，审查端同盲无从核「引用属实」。
2. **注入无消费指令**：genre_pack（reader_expectations/typical_dilemmas/taboos/genre_stage_form 卷型）、platform（上架锚/卡点节奏）、scale 三轴死注入；expression_preferences 死注入。
3. **声明无对账**：无 schema 无 validator——≥3 线/副高湂数/弧挂接/字数/POV 全是正文级承诺，下游引用 arc_id 无处核。
4. **增量生产的「实际」太薄**：「以上卷实际结算为优先源」但 prev 注入的是上卷计划全文，实际只有账本三切片，chapter_facts 与末章摘要不注入；卷号无锚定（prev 链按 rowid）。
5. **生成-回写不对称**：人物有完整通道（volume_characters→--entry→席位对账），势力/地点/物品/规则/副本世界无增量通道（对无限流是题材级阻断）；新悬念/drift 止于 advisory；变奏分配（variation_alloc 按卷行）无卷层承接。
6. **卷型概念缺位**：连续剧四段是唯一形态——单元编排（副本/案件/赛季，无限流主线—副本双层）与换图清算（carry/cut/pre_close，玄幻换地图主流卷切分）无承载；≥3 线门与弧活跃窗 ≤4 在短/中篇数学顶牛（强制卷内自含线存在而其无身份）。

研究锚点：卷内五段配比公式（10/20/30/30）、卷长 20-50 万字、上架 10-30 万字按追读分级、换地图三法（新图大纲/斩前缘/带核心人脉）、支线寿命谱系（6000 字～跨卷）、无限流「主线—副本」双层+副本篇幅过长是头号差评、Sanderson PPP 递归（卷级 promise/progress/payoff）、MICE FILO（系列级线程最后收）、series arc 双层结构。

## 变更清单（按层）

**L0 schema**：新增 `config/schemas/volume-outline-metadata.schema.json`（v1）——`volume_number`（卷号锚定）/ `word_range{min,target,max}`（对 volume_plan）/ `volume_form`（连续四段｜单元编排；换图清算经 exit_settlement 叠加）/ `lines[]`（name/scope 跨卷弧｜卷内自含/arc_id/share_pct/mainline/pov/note，3-12 条）/ `mainline_beats` / `climax_positions[]`（卷长比例，末位=1）/ `units[]`（unit_id/theme 主题内核/chapter_window/mainline_advance/interlude/new_setting_ref）/ `exit_settlement{carry,cut,pre_close}` / `new_plants[]`（line_id/claim/close_volume XOR exempt）/ `drift[]` / `test_alloc[]`（对 variation_alloc 双向对账）/ `volume_settings[]`（kind 势力/地点/物品/规则/副本世界 + disposition 卷内自闭｜登记入world）/ `volume_characters`（$defs 同构 planning-candidate）。

**L1 validator**：新增 `scripts/novelos_validate_volume_outline.py`——11 组机器门：schema；卷号连续性（前置 locked 须 1..N-1，本卷=N，乱序拦截；T39 前旧资产降级跳过）；字数对表（volume_plan 本卷行交集 + target 出界 warn）；高潮门（末位=1、相邻间距×target ≤30 万字、target≥20 万时总数 ≥target÷25万 向上取整、短篇/紧凑卷退化分支）；线弧双向（跨卷线必带 arc_id 且弧存在、duty 活跃（挂休眠弧 warn）、活跃弧必有承载线=职责蒸发 error、share 合计 90-110、mainline 0-1 条、tier 低削平/tier 高喂不饱 warn、mainline_beats ±2）；单元编排（units 必填、非间歇单元主线渗透 ≥1、章数窗、窗总量超卷容量 warn）；换图清算（cut/pre_close 引用台账 line_id 核验）；新种（XOR、收束 ≥ 本卷、不撞台账 id、终卷不溢出、closed 终卷禁豁免/open 滚动提示）；drift arc_id 存在；变奏承接双向 warn；stage_span 越界；班底预检（--project 名册）+ volume_settings 重名/待登记。`--project` 自动解析 scale/story_arc/architecture/strategy/前置卷号/注册表。

**L1 composer**：`_slot_prev_volume_outline` 排序改以 metadata.volume_number 为准（无卷号旧资产按 rowid 兜底），节头显示卷号；`_slot_promise_ledger` 扩两节——连续性事实（chapter_facts 近 30 条，卷初实际状态地面真值）+ 上卷末尾章节摘要（近 12 章，上卷实际结算叙事证据），补齐「实际结算优先源」的实际面。双端 manifest 加 `book_soul` + `mechanisms` 槽（生成端 8→10、审查端 11→13）——机制运转规则/力量货币定义/测试原文从 arc 转手名升为可引用实体，审查端同盲解除。

**L2 prompt**：`planning/volume-outline/prompt.md` 重写——卷型节（连续四段默认/单元编排与 genre_stage_form 对偶/换图清算三清单）；弧挂接双向纪律 + 线粒度双 scope（自含线合法化，弧活跃窗解绑线数）+ 变奏对分配表 + 终卷分支（closed 不留下一卷压力）；主线节拍与篇幅对表（beats_per_volume 落位/share_pct 申报/四段引用机制原文/力量货币引用定义）；世界消费并入 volume_settings 表（表外发明 blocking）；节奏量化改按本卷字数条件化 + 平台上架对齐；灵魂职责 + 题材三件套消费 + 表达偏好 + **场景盲区门（主高潮/关键场景整场落「写不了」= blocking——班底不落盲区 ≠ 场景不落盲区）**；种收双对账 + new_plants 结构化回写；自检 10 项；metadata 要求 + validate 命令。`review/planning-volume-outline-review/prompt.md` 重写——0 卷型/0b 高潮门/0c 弧挂接双向/0d 字数与节拍对表（低密度主线削平 blocking、机制空名引用 blocking）/3 实际结算优先/4 章数×字数量级/5 终卷纪律/6 题材三件套/7 结构化回写/8b 场景盲区门/9 volume_settings 表外发明 blocking/10 上游保护；机器门前置声明。频道三模块补 POV 配置（兑现主干宣称）。chapter-plan 双端补 POV 对账 + 章数×target 对 word_range（7e）。

**L1 register**：`novelos_register_characters.py` 新增 `--audit-entries`——locked 卷纲 volume_characters 逐名对注册表，漏跑 --entry 非零退出；附带 WARN 列 volume_settings 待登记入 world 条目；T39 前旧卷纲跳过。

**L5/配置**：`.agents/skills/novel-planning/SKILL.md`——Volume sub agent 段重写（T39 全输入）、步骤 8 锁定后动作扩（--audit-entries 终核 + volume_settings/new_plants/drift 的 change proposal 回写路径）、新增「volume metadata 速查表（T39）」、节奏密度约束段更新（字数条件化+双 scope）。`config/agent-recipes.json` 两行槽位与产出描述更新 + `documentation/agent-recipes.md` 表内两行同步。

**测试**：新增 `tests/test_volume_outline_validate.py`（20 测试：基线/卷号 gap/字数交集/高潮间距与总数/末位/短篇退化/职责蒸发/休眠承载/缺 arc_id/幽灵弧/单元门/清算引用/新种三门/终卷 closed/open/阶段越界/tier 削平与喂不饱/变奏双向/班底与设定预检/设定重名/--project 解析）；`test_slot_resolution.py` 扩 seed（卷号 metadata + facts + 章摘要）+ VolumeT39Slots 5 测试；`test_register_characters.py` 加 planning_assets 表 + audit-entries 3 测试；`test_compose_prompt.py` 卷断言更新。

## 设计取舍记录

1. **volume_form 二元而非三元**：换图清算不是骨架而是叠加件（换图卷仍走四段或单元骨架），独立成 enum 会强迫虚假二选一。
2. **自含线合法化而不是提高弧数下限**：N1 的数学顶牛（≥3 线 vs 活跃 ≤4）正解是承认线的连续谱（研究锚点：支线 6000 字～跨卷），不是逼弧层超载。
3. **高潮门按本卷字数而非 scale 条件化**：卷长行业区间 20-50 万字，同 scale 内卷长差异大到阈值必须挂 target；E4（字数申报）因此从对账礼貌升为条件化前提——一箭三雕（S1+C3+E4）。
4. **volume_settings 走 schema+prompt+review 而不建新登记脚本**：势力/地点/物品的世界侧合流点仍是 world 契约（change proposal 增补），卷层只做「表外发明 blocking」的入口管制 + disposition 分流——与人物通道（注册表）不同构是有意的：设定的一致性权威在 world，人物的死活权威在注册表。
5. **prev 链排序改卷号但 rowid 兜底**：T39 前旧资产无 volume_number，硬切会断存量项目的链；validate 侧同步降级跳过。
6. **终卷豁免 closed=error/open=warn**：closed 终局留坑是对 terminal_mode 的直接违反；open 的滚动钩子合法但须计入 open_window（提示对表）。
7. **场景盲区门放卷层而非章层**：主高潮形态是卷级结构决策，写作端才发现=全书节点降级交付；persona_gate 数据已在注入，缺的只是消费条款与 blocking 定级。
8. **审查端机器门前置声明**：rubric 不重复数数（validate 已数），审查职责改为语义核实（退化是否刻意、引用是否属实、削平是否发生）。
9. **chapter-plan 只加对账不加新槽**：POV 分布与 word_range 已随 upstream:volume_outline 注入，执行卡缺的是对账指令不是数据。
10. **--audit-entries 独立于 --pending-status**：前者查「班底漏登记」（规划侧闭环），后者查「状态漂移」（连续性侧闭环），语义不同不合流。

## 验收

- `python -m unittest discover -s tests`：**274 tests OK**（246→274：+20 validate +5 slots +3 register）。
- compileall / check_repository_hygiene / build_catalog_manifest 四命令全绿。
- SIZE_BUDGET 零变更：volume-outline 81/100、volume-outline-review 45/70、chapter-plan 66/110、chapter-plan-review 44/70。
- CLI 冒烟：显式传参 PASS（单元编排 3 线 3 高潮 0 WARN）；缺陷路径 FAIL exit 1（职责蒸发；字数无交集+高潮间距 63 万字+总数不足三连）；`--project` 真库解析（scale 长篇归一化，无 locked 上游时优雅降级）；`--audit-entries` 真库 PASS（0 卷零迁移）。

## 遗留说明

1. **设定登记回写无脚本**：volume_settings disposition=登记入world 仍靠主控走 world change proposal（--audit-entries 仅 WARN 列出待办）；若实践中高频，可考虑 world 侧增量补丁入口。
2. **章数×字数对账只到量级**：chapter-plan 层的 7e 是 warning 级软对账，未做逐卷累计机器门（需执行卡结构化字数申报，收益/成本待评估）。
3. **stage_span 是申报项**：卷-阶段对齐跨卷单调性（卷 N+1 的 span 不早于卷 N）未做机器门——多卷锁定后可补。
4. **T39 前旧资产不回填**：旧卷纲无 volume_number/结构化 metadata，prev 链与 validate 相应降级；新卷起全量走新 schema。
5. 与 T38 遗留的关系：T38 遗留的「volume_new 台账回写自动化」由 new_plants 结构化 + change proposal 路径半自动化承接；「planned-vs-actual 自动 stale」仍待（arc_states vs 映射表的 drift 自动传播）。
