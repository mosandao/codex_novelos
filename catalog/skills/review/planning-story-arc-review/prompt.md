# 跨卷故事弧审查 Rubric (Story Arc Review Rubric)

审查 `story_arc` 资产候选。

## 输入边界
- 目标资产：`story_arc`
- 精确上游：已锁定的 `strategy`、`character_contract` 与 `world_contract`（全文 + metadata 注入）；上游审查回执（strength/豁免）随 upstream-reviews 槽注入；book_soul 与架构机制清单以机器可读槽注入

## 检查清单
0. **结构化出口**：metadata 五件套齐（arcs/volume_plan/arc_volume_map/plant_payoff_ledger/variation_alloc）——缺任一 = blocking；`validate_story_arc` 机器门缺陷未清零 = blocking。
0b. **上游消费表**：八行各有引用或显式豁免——静默丢弃 = warning；静默自创上游没有的弧职责/结构 = blocking。
1. **弧↔卷映射表**：每卷 1-2 条推进弧、主导螺旋与活跃弧一致——机器门已拦数字，审查核语义（职责格与该卷阶段职责是否匹配）；弧转折对齐 strategy 阶段边界（cause_bridge 附近）——错位无说明 = warning。
2. **载体指认**：主线/人物/关系弧具名（roster 人物或 world 席位）；latent 载体出现在近硬窗内 = warning（远卷待造须显式）；弧首活跃卷早于载体登场卷 = blocking。
3. **两份弧清单对账**：character 契约已具名认领的 `handoffs.character_arcs` 逐条在本层弧清单有着落（弧 id ↔ 交接项），错位/丢失 = blocking；claim_ledger 登记承诺（midstory/terminal）在台账无对应行 = warning。
4. **跨卷状态**：多条故事线在卷际之间的推进与交织是否清晰。
5. **伏笔兑现**：台账行 close/exempt 二选一；豁免仅引用 `deliberate_silences` 或 open 喂料储备——其他理由的豁免 = warning；兑现间隔与 `cadence_plan.interval_volumes` 对表——超间隔无说明 = warning；每条悬念线标注预计开始给出阶段性答案的卷次。
6. **交叉一致性**：人物成长弧与世界规则变迁协调——世界变迁弧的推进卷与 world 消费时序表逐行对账（弧推进第 N 卷 ⇔ 时序表第 N 卷首次消费），缺行 = warning；变迁弧代价形态不引用代价两轴 = warning。
7. **终局收束**：所有弧线最终合力收束于终局高潮；**弧终点对表 `forbidden_resolutions`——以被禁方式收束核心矛盾 = blocking**；受保护人物死于 `protected_dignity` 覆盖范围 = blocking；终点形态与 `narrative_cruelty`/`mercy` 气质相悖 = warning。
8. **跨卷思想漂移**：重复测试改变处境、答案和代价（`changed` 声明与实际内容一致——声明换了处境实际复读 = blocking），保持 Creator Profile 与 `book_soul` 约束而不机械复述。
9. **变奏机制引用**：`mech_ref` 回指 architecture 真实机制且引用其变奏声明原文——凭空引用或只写转述 = warning；同一母题 >3 次变奏无剩余空间评估 = warning。
10. **变奏盲区门**（persona_gate 槽注入时）：变奏形态整卷落在分身「写不了」的场景类型且 note 无绕开方式 = blocking；无注入跳过本项。
11. **题材形态对偶**（genre_pack 槽注入时）：支线弧型与 `genre_stage_form` 对偶（阶段形态是案件弧，线程侧另造形态 = warning）；`taboos` 违反 = blocking。无注入跳过本项。
12. **规模形态**：短篇按退化形态（弧×段）；open 模式有 `open_window` 滚动窗口声明且远卷软格带待重映射标注——缺 = blocking（机器门同拦）。
13. **卷计划对表**：`volume_plan` 卷字数总和与 strategy 阶段字数同量级；每卷字数与副高潮间隔（20-30 万字基准，短篇/中篇按比例放宽）匹配——越界无说明 = warning。
14. **上游保护**：上游回执的 strength 指认（如低密度主线赌注）在弧分配中未被削平——削平 = blocking；accepted_risk 豁免项不得作为新缺陷重报。

## Blocking 条件
- 结构化出口缺失、机器门缺陷未清零；弧线严重断层、无豁免的未收悬念或与人物/世界契约冲突。
- 弧终点违反 forbidden_resolutions/protected_dignity；载体悬空或早于登场卷活跃。
- 静默自创上游结构；跨卷作者立场漂移、相同母题声明变奏实际复读。

## 不得检查的下游
- 不得检查单章正文文字润色；不得检查卷内事件排布（归 volume-outline-review）。

## 证据要求
- 引用故事弧节点与人物/世界契约文本对照；机器门类缺陷引用 validate 输出行；回执类缺陷引用上游 findings 条目。
