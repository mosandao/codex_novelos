# 叙事架构审查 Rubric (Story Architecture Review Rubric)

审查 `architecture` 资产候选是否忠实于已锁定的 `direction`，并具备可运转的双层叙事引擎。你拿到 persona 全文与上游审查回执——persona 消费与 strength 保护是可核验项，不是宣称。

## 输入边界
- 目标资产：`architecture`
- 精确上游：已锁定的 `direction`（正文 + metadata：lineage / cadence_plan）；direction 的最新审查回执（strength 指认与豁免记录跨阶段有效）；创作者 persona 全文；project setup（频道/平台/规模/题材）

## 检查清单
1. **翻译完整度**：book_soul 十三字段是否每个都有机制形态，或附显式豁免声明；组织原则是否被翻译成支撑机制而非复述。**direction 非 book_soul 产出逐样处置**：美学基因/情感登记/读者画像/题材消费结论，每样被消费或显式豁免（移交写作层也是合法豁免，静默丢弃 = warning）。
2. **双层引擎**：生产层单元机器（单元弧 1-N 章粒度声明 + 输入源库存）与统合层统合器（主线节拍表——beats 可为 0 / 单元配额与筛选器 / 注入配额 k 值与载荷类型）是否都有实体设计；缺生产层（中段塌方）或缺统合层（爽而无根）均为缺陷。
3. **主线密度一致性**：密度档与 `setup.scale` 档位、平台耐心结构、`promise_cadence`（上游 metadata 带 cadence_plan 时对照其次数×间隔数字）是否对表论证；低密度（柯南/X 档案式空窗+爆发）合法，但空窗须有上限与爆发点位置设计且不超档位上限；**主线膨胀同样有罪**——信息释放阶梯层数/beats 无上限意识、暗线过度错综 = warning（单元读者被熬走的经典死法）。
4. **耦合双形态核验**：I/O 耦合查实质（写明的产出确实喂入写明的输入，非「A 喂 B」空话）；配额注入耦合查 k 值与载荷类型可指认；metadata 每机制有 coupling 条目，无孤岛。
5. **四段式与血缘双源**：每个机制具备 引用 → 机制 → 节奏 → 下游影响；**血缘逐字段抽查**——至少两个机制，核其 sources 映射真实性（内容确实可从所指 direction 字段/persona 部件推导，非贴标签）；metadata sources 同时含 direction_field 与 persona_part（validate 双源覆盖的语义侧复核）。
6. **防火墙**：是否逐条反验 `forbidden_resolutions` 与题材禁忌（genre_profile 非空时）；新机制（尤其预知/探测/复活类）是否构成绕禁令通道。
7. **因果与升级（测试证据核验）**：压力测试 ≥5 种母题输入与产出摘要**是否落在正文「引擎验证记录」节**——只声称测过而无记录 = warning；油耗分级随 scale 档位（短篇 ≥2 / 中长篇 ≥3 / 超长篇 ≥5），metadata `engines.*.escalation_levels` 对照档位规则复核。
8. **POV 契约与盲区结构化**：persona 有限视角机制化（知识边界/感知时序/全知侵入判定）；`deliberate_silences` 只经可见征兆呈现；**机制不支撑清单逐条覆盖 cannot_write**——整节缺失或只有一句敷衍 = warning。
9. **终局闭合**：矛盾与追问有收束设计、终局不动用哪些禁令已声明——无收束设计的架构不完整 = warning 及以上。
10. **边界**：是否越界产出静态设定（判定测试：换人物事件后能否继续生产情节）、人物传记或卷章事件（应显式移交 world/character/strategy）；移交清单完整（越界内容都在清单里）。
11. **库存反向对账与证伪**：persona 差异化库存（career_track / class_circle_inventory / 目光库存）至少一项成为单元机器输入源——全部绕开只用泛化 inner_tension = warning（persona 存在理由落空）。不满足核对属性：从目标渠道读者视角攻击节拍表——最长空窗卷的弃书点、单元重复疲劳点（第 N 个同类单元凭什么还看）、主线膨胀瓦解点，给出 2-3 个最可能断裂点，落 `note` 及以上。

## Blocking 条件
- 脱离或违背已锁定的 `direction` 承诺；`organizing_principle`/`promise_cadence` 无对应机制。
- 双层缺一（无生产层单元机器或无统合层统合器）、机制孤岛无耦合规格、或油耗低于 scale 档位下限（撑不起 `scale`）。
- 主线密度与 `scale` 档位 / promise_cadence（cadence_plan 数字）明显失配：空窗超档位上限，或主线根本无 beat 且无承载单元注入。
- 逻辑断层、机械降神、无代价规则，或存在绕过 `forbidden_resolutions` 的机制通道。
- POV 契约缺失或全知渗漏无判定标准；终局无收束设计。
- 削平上游审查回执中 strength 认定的特质（strength 跨阶段保护令）。

## strength 通道（不阻断不修复，供选型与修复保护）
- 指认候选独有的引擎发明：独创耦合规格、大胆的低密度主线赌注、变奏器的巧思、库存消费的独到用法——写明依据，供修复循环保护（修复不得削平）与用户裁决参考。

## 不得检查的下游
- 不得检查具体的全书分卷计划 (Strategy)、人物弧契约或世界设定细节。

## 证据要求
- 必须对比 `direction` 上游文本与当前 `architecture` 候选文本，逐机制引用两侧原文；涉 persona 的检查（POV/盲区/库存）引用 persona 全文对应部件，不得凭候选的复述转述。
