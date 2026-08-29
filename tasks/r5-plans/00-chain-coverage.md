# R5 · 管线链条覆盖盘点(主控自查)

> 目的:确认「立项 → direction → … → chapter_plan → 写作 → 审查 → 连续性收尾」全链条、两个 git 库、MySQL 三者均已被实际阅读,并记录深读规划链后发现的吸收通道修正信号。供红方轮核查与整合轮消费。

## 1. 覆盖矩阵

| 管线环节 | 权威文件 | 阅读状态 | 阅读者 |
|---|---|---|---|
| 小说立项 | AGENTS.md 项目创建向导节 + .agents/skills/novel-project/SKILL.md + sql-reference.md 签名链 | 深读 | 主控 |
| direction | catalog/skills/planning/story-direction/prompt.md(137 行) | **深读(本轮补)** | 主控 |
| architecture | catalog/skills/planning/story-architecture/prompt.md(131 行) | **深读(本轮补)** | 主控 |
| strategy | catalog/skills/planning/story-strategy/prompt.md(109 行) | **深读(本轮补)** | 主控 |
| world | catalog/skills/planning/world-contract/prompt.md(143 行) | **深读(本轮补)** | 主控 |
| character | catalog/skills/planning/character-contract/prompt.md(150 行) | **深读(本轮补)** | 主控 |
| story_arc | catalog/skills/planning/story-arc/prompt.md(63 行) | **深读(本轮补)** | 主控 |
| volume_outline | catalog/skills/planning/volume-outline/prompt.md(71 行) | **深读(本轮补)** | 主控 |
| chapter_plan | catalog/skills/planning/chapter-plan-execution-card/prompt.md(53 行) | **深读(本轮补)** | 主控 |
| 写作 | writing/chapter-draft-generation/prompt.md + craft 全卡 + expansions/prose-revision | 深读(前轮) | 主控 |
| 审查 | review/prose-quality-review/prompt.md + manifest + .agents/skills/novel-review/SKILL.md | 深读(前轮) | 主控 |
| 连续性收尾 | AGENTS.md 工作流节 + sql-reference 六账本;novel-continuity SKILL 由 D5 规划员深读 | 机制级掌握,SKILL 细读委派 D5 | 主控+D5 |

外部源:lieflat-less-ai-tone(SKILL.md 454 行全文 + RESEARCH.md + 三个 py 脚本全文 + README/模板)、writing-dna-skill(SKILL.md 全文 + README + usage-boundaries + templates + openai.yaml)、MySQL nwriter(31 张 kb_ 表全列出,核心表字段级抽样)——均主控亲读。

## 2. 深读规划链的关键发现(整合轮必读)

**发现一:「可选方法素材」机制是现成的知识吸收通道,规划链每级都有。**
八个规划 prompt 里有六个带「方法素材(可选)/可选方法素材」节(direction 引 story-expectation-design;architecture 引 causal/expectation/pov-tone 三件;world 引 scenario-atlas/universe-atlas/world-rule-system/world-growth-resource/world-social-power/power-ecology/world-system-interaction 七件),机制是「主控或对应 agent 按需 Read 注入,不能替代主干产出」。
**含义**:kb_* 知识(书摘要/框架/爽点/原型/世界设定)蒸馏后的自然落点是**扩充这套可选素材体系**(如 kb_world_settings → universe-atlas 簇文件、kb_character_archetypes → 题材人物光谱模块的取材池、kb_book_summaries → 新的「成品书参照」expansion),而不是(或不只是)新发明 composer knowledge 槽。D3 方案若只走新槽,必须论证为什么不复用「可选素材 Read 注入」通道——**交给 D3 红方重点审查**。

**发现二:规划链已有极重的对账纪律,知识注入必须做「非权威素材」。**
strategy 七行翻译表/十三字段处置/三组数字对账(fulfillment_count↔escalation_levels↔beats×卷数);story_arc 种收台账双对账;volume_outline 高潮门量化公式(间距×target≤30万字)。kb 参照若以结构化数据形态进入,可能被 agent 误当「对账对象」——参照必须显式标注「非 Canon、无对账义务」,否则污染对账纪律。

**发现三:各阶段的吸收点已可精确定位。**

| 阶段 | 现有结构 | kb 吸收点(精确) |
|---|---|---|
| direction | 反泛化参照(scenario-atlas 当镜子);承诺类型(正向/负向) | kb_book_summaries.core_appeal/核心魅力 → 承诺类型与读者承诺的成品参照;kb_story_genres → 题材信息包缺位时的兜底参照 |
| architecture | 统合层节拍表(beats/空窗/爆发点);变奏器 | kb_plot_frameworks.turning_points/vol_distribution → 节拍表形态参照(非对账源) |
| strategy | 阶段收益配比/存债爆发周期 | kb_cool_point_patterns.frequency/intensity_curve → payoff heavy/light/debt 配比的成品书参照 |
| world | universe-atlas 七件可选素材;lexicon 四件套(词表红线) | kb_world_settings/economic/social/faction → universe-atlas 簇文件与 world-social-power 素材扩充;**绝不进 lexicon** |
| character | 题材人物光谱条件模块(genre_profile 取材) | kb_character_archetypes 506 条 → 光谱模块取材池;signature_techniques→essence 写法参照 |
| story_arc | 变奏分配(换处境/答案/代价);弧转折 | kb_emotional_arc_patterns.stages+intensity → 弧转折节奏参照 |
| volume_outline | 高潮门公式;卷型三型 | kb_scene_blueprints.hook_placement/cool_point_placement + kb_cool_point_patterns.frequency(每50-80章)→ 高潮门与卷型参照 |
| chapter_plan | 场景三拍(分级/执行/结算);钩子强度分级 | kb_scene_blueprints.internal_structure + kb_technique_scene_maps.scene_type → 场景序列与三拍参照;开篇技法类技巧 → 第1章强钩子参照 |

**发现四:写作/审查端已发现的问题在规划端同样存在——但形态不同。**
规划 prompt 无「反向清单」问题(其自检全是正向);规划端真正的风险是**参照素材被当权威**(发现二)。审查端(planning-*-review)对「参照非 Canon」的识别力是 D5 编排要覆盖的点。

## 3. 对五个方向的修正指令(整合时执行)

1. D3:评估「可选素材 Read 注入」vs「composer knowledge 槽」两条通道的取舍(或并用:静态参照走素材文件、场景级动态检索走槽)。
2. D4:签名链的 measured_features 豁免,direction/strategy 的 persona 消费条款是消费方——接口要对齐「persona 四用法」的现有形态。
3. D5:R6 演练的规划段检查点应包含「参照素材未被当 Canon 消费」的红方任务。
4. D1/D2:不受影响(语言层与规划链无交集)。
