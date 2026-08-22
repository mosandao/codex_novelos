# 世界契约审查 Rubric (World Contract Review Rubric)

审查 `world_contract` 资产候选。

## 输入边界
- 目标资产：`world_contract`
- 精确上游：已锁定的 `architecture` 与 `strategy`（含双上游审查回执——strength 指认与 accepted_risk 豁免跨阶段传递，不得推翻已豁免项）

## 检查清单
0. **术语语域表**：语域表四件套存在且完整（lexicon / banned_categories 四类分禁 / measure_system / exceptions）——缺失任件 = blocking；lexicon 与机制命名脱节 = warning；**metadata.lexicon 机器可读形态与正文版一致**——正文有而 metadata 无（或反之）= warning；自造词过量（不必要的新造词堆积）= warning；近重复词条（灵石/灵晶类音近形近）未合并 = warning。
1. **底层规则**：世界观物理与超自然法则是否严密自洽。
1b. **规则六角色与分层**：重要规则是否答全六角色（制定者/承认者/执行者/受益者/豁免者/破坏成本）——缺任一角色记 `warning` 并列出规则名与缺失角色；规则是否归入三层（本体/力量/社会）——层级错装（社会规则越权执行本体效力、本体规则被博弈修改）记 `warning`，越权规则被正文依赖为决定性约束时升级 `blocking`。**人侧岗位化**：六角色里的「人」是否落到岗位表席位（执行者/受益者有席位承载）——规则的关键角色无席位承载 = warning。
2. **资源与成本**：能力与力量的获取是否建立在资源争夺与明确代价之上。
2b. **代价两轴**（metadata.dimension_costs）：每维度声明可逆性（可逆/压制/不可逆）——缺声明 = warning；不可逆档无阈值说明 = warning；**压制型无解除通道 = blocking**；**新增主角永久代价（bearer=protagonist_permanent 而 strategy 未声明 declared_in_book_soul）= blocking**；不可逆档全部落在主角身上 = blocking。
3. **制度与势力**：势力结构与社会制度是否合理反映了力量与资源的掌控关系。
3b. **岗位表**（metadata.seats）：主要席位六要素齐（name/org/duty/power_tier/rule_links/first_consumption）——缺要素 = warning 并列出席位名；**席位不设人**——岗位表或契约正文给人设配了姓名与内心 = blocking（越权造人）；主要席位无处置标注（待契约认领/待班底/显式虚位）= warning。
4. **情节消费者**：世界设定是否具备被剧情与故事线消费的具体切入点。
   - **4a 消费绑定**：每个设定项是否标注了"首次被消费的圈次 / 卷"与"消费场景类型"。未标注的记 `warning`，并在 findings 中列出具体设定项名称与缺失的标注类型。
   - **4b 消费时序表**：产出是否包含至少一张"消费时序表"，使钩子分布可视化。缺失记 `warning`。
5. **例外控制**：严禁创建无代价的规则漏洞或主角专属免费例外。
6. **立场中立承载**：世界规则是否只承载冲突，而没有把作者偏爱的价值判断伪装成客观真理。
7. **strategy 对账**：`handoffs.world_changes` 每条在消费时序表有对应消费行——缺行 = warning 并列出变迁条目；`midpoint_renewal` 对应的演化空间（新地图预埋/重组接口/可重写层）存在——缺 = warning；`terminal_mode=open` 无喂料储备声明 = blocking；力量体系货币与 `power_currency` 另起炉灶 = warning。
8. **persona 盲区门**（persona_full 注入时）：`cannot_write` 场面形态与消费场景类型对表——盲区场面被设计为核心消费场景且无侧写化声明 = blocking；无 persona 注入跳过本项。
9. **规模接线**：设定深度与 setup.scale 明显失配（短篇百科化/超长篇单薄到主线无设定可消费）= warning。

## Blocking 条件
- 存在无代价力量、物理矛盾或主角专属免责例外；压制型代价无解除通道；新增主角永久代价。
- 设定属于纯静态百科，缺乏情节切入点；open 模式无喂料储备。
- 岗位表或契约正文越权造人（世界层给人物姓名与内心）。
- 系统奖励、宇宙法则或设定说明自动证明单一立场正确，使对立答案失去合理生存条件。

注：消费绑定（4a）或消费时序表（4b）缺失是 `warning`，不是 `blocking`——这是经实测后的刻意分级，避免在中等质量产出上过度阻断。warning 不影响 verdict 通过，但必须在 findings 中记录供后续改进。

## 不得检查的下游
- 不得检查人物心理与人物内心（席位是位子不是人——人物归 character_contract）；不得检查章节行文风格。
- 频道轴专项（男频力量-规则循环/女频规则-声誉循环/全向双轨）按项目路由进条件模块，本主干不重复。

## 证据要求
- 对比世界规则与架构法则，列出违规或不自洽的设定片段。
- 审查消费绑定时，对每个未标注消费时机的设定项，引用其最小片段，标明"缺少首次消费圈次"或"缺少消费场景类型"。
- 岗位表、代价两轴、strategy 对账的 finding 逐条引用 metadata 字段或上游条目原文；上游 strength 已指认的优点不重复记缺陷。
