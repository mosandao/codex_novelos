# 卷纲审查 Rubric (Volume Outline Review Rubric)

审查 `volume_outline` 资产候选。

## 输入边界
- 目标资产：`volume_outline`
- 精确上游：已锁定的 `story_arc`（全文 + metadata：弧清单/映射表/台账/卷计划/变奏分配）、`world_contract`（含人物名册镜像）；`book_soul`/`mechanisms` 机器可读槽（变奏原文/力量货币/机制运转规则/主线密度合同——引用核实的对照物）；上游审查回执随 upstream-reviews 槽注入；前置卷链与连续性实际账本（prev_volume_outline / promise_ledger 含事实与末章摘要）注入时对实际状态核账
- 机器门前置：候选应已对照卷纲规则自查（卷号/字数/高潮门/线弧双向/单元/终卷；机器门待 R4 JS 化）——rubric 查语义与引用属实，漏网的结构缺陷标注 severity=blocking 并点名

## 检查清单
0. **卷型**：volume_form 与 strategy genre_stage_form 对偶（副本难度弧/案件升级弧/赛季弧配单元编排——错配 = blocking）；单元编排的 units 每单元有主题内核与主线渗透（渗透 <1 且非间歇 = blocking）；换图卷（舞台切换）的 exit_settlement 三清单齐——carry 跨卷班底未标升级 / cut 无声消失 / pre_close 拖过图 = warning 起。
0b. **卷内节奏量化**：≥3 条并行冲突线（缺 = blocking，双 scope 均可计数）；climax_positions 相邻间距 ≤30 万字、末位 = 卷末主高潮（违 = blocking——机器门外仍须复核退化是否刻意）；POV 分布已声明且同线连续超 1/3 卷长有理由（缺 = warning）；第一卷末主高潮对平台上架/推荐节点（platform_traits 注入时，悬空 = warning）。
0c. **弧挂接双向**：映射表本卷 duty=推进/兑现/收束的弧全部有冲突线承载（职责蒸发 = blocking）；跨卷弧线必须带 arc_id（无 = blocking）；自含线无独立加压/结算声明 = warning；蓄势/休眠弧反向活跃 = warning；弧载体已退场/死亡仍活跃推进 = blocking；变奏以 variation_alloc 本卷行为准（漏承接/超出分配另造 = warning，另造未走 change proposal = blocking）；计划与实际漂移无 drift 清单 = warning。
0d. **字数与节拍对表**：本卷 word_range 对 volume_plan 本卷行（脱轨 = blocking）；mainline_beats 对 beats_per_volume（±2 外 = warning）；主线 share_pct 与 mainline_density.tier 一致——**低密度主线被卷内排布削平 = blocking**（经上游回执 strength 保护的赌注）；四段各引用架构机制运转规则**原文**（凭转述编造/空名引用 = blocking——mechanisms 槽可核）；对撞赌注引用力量货币定义（自造货币 = warning）。
1. **单卷目标**：本卷的独立叙事目标与高潮定位是否明确。
2. **卷内转折**：本卷的中点转折与卷末危机是否强劲。
3. **进出状态**：符合跨卷故事弧分配；前置卷注入时对齐上卷**实际结算**（promise_ledger 事实/末章摘要优先于计划格）——与实际漂移且无 drift 说明 = warning；stage_span（如有）落 strategy 阶段区间（越界 = warning）。
4. **章节序列**：章节划分与节奏铺排是否合理；章数 × 单章字数与本卷字数同量级（悬殊 = warning）。
5. **卷尾承诺与终卷纪律**：非终卷结尾提供强有力的悬念或下一卷承诺（弱 = warning）；**终卷**按 terminal_mode 收束——closed 留下一卷新压力/新种溢出终卷 = blocking；open 滚动钩子未计入窗口 = warning。
6. **卷级灵魂职责**：落实指定 recurring_test 与变奏轴（对齐 test_alloc）、有代价承诺和卷末未解决压力，并与前后卷形成变化；genre_pack 注入时 reader_expectations/typical_dilemmas/taboos 三件套被消费（无视题材期待 = warning）。
7. **悬念种收双对账**：兑现至少一条前序悬念（static 台账 + promise_ledger 实际账本两本都查）；实际账本有、台账无的承诺被无声蒸发 = warning；只堆积新谜题而不兑现旧悬念 = warning；两账本冲突未列 drift = warning；新种未入 new_plants 结构化回写 = warning。
8. **卷级配角班底**：人物载体逐一指认来源（契约 roster / 在库配角 / 本卷新生成，名册镜像可查）——**无源载体 = blocking**；`volume_characters` 无 main（出现 = blocking）；无跨卷职责（未标「待 change proposal 升级」= warning）；与在库重名 = warning；叙述与数组不一致 = warning；seat_ref 引用不存在的席位 = blocking；**班底 persona 盲区门**：整档落「写不了」场景且微档案无绕开方式 = blocking。
8b. **场景盲区门（结构级）**：主高潮/关键场景整场落在分身「写不了」盲区 = blocking（persona_gate 注入时）——班底不落盲区 ≠ 场景不落盲区；声明结构级转喻的须给降级理由（无理由 = warning）。
9. **世界对账**：消费时序表本卷首次消费的设定逐项认领（漏 = warning 逐条列出）；world_changes 落本卷的变迁在卷内有兑现位置（缺 = warning）；**新设定实体（势力/地点/物品/规则/副本世界）不在 volume_settings 表内 = blocking**（表外就地发明，隐式重写上游）；disposition=登记入world 的条目无对应移交说明 = warning。
10. **上游保护**（upstream-reviews 槽注入时）：story_arc / world 锁定回执的 strength 指认未被卷内排布削平——削平 = blocking；accepted_risk 豁免项不得作为新缺陷重报；无回执注入跳过本项。

## Blocking 条件
- 单卷目标模糊、卷末无危机、偏离跨卷故事弧分配、卷型错配、职责蒸发、无源载体、seat_ref 悬空、表外发明设定、机制空名引用、低密度主线削平、closed 终卷漏压力、结构级场景盲区。

## 不得检查的下游
- 不得检查具体场景行文句子结构；不得检查世界设定本身的自洽性（归 world-contract-review）。

## 证据要求
- 引用卷纲章节序列与跨卷故事弧要求对比；世界对账引用消费时序表/岗位表的对应行；机制/变奏/货币引用给出 book_soul/mechanisms 槽的对应条目。
