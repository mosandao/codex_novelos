# 故事方向审查 Rubric (Story Direction Review Rubric)

审查 `direction` 资产候选是否满足故事方向质量标准。

## 输入边界
- 目标资产：`direction`
- 创作约束：项目绑定的精确 `creator_signature_ref`（含 persona，schema v2）与 project_setup；无规划资产上游（无上游依赖）

## check 执行纪律

组装注入的每个条件审查模块（频道/平台/题材/美学）必须逐条回答并在回执中列出已执行的 check 清单——拿到模块不执行等于未审查。频道模块的好/坏例证是**结构示范不是模板**：候选长得像例证不加分，与例证题材场景高度雷同反须警示。

## 检查清单
1. **核心冲突**：`central_contradiction` 是否为两个都能成立却无法同时满足的判断（两难结构），贯穿全书；无单向正确口号。
2. **主角驱动力**：主角是否有不可替代的内驱欲望或外部危机逼迫。
3. **组织原则**：`organizing_principle` 是否为本书独有的组织过程——换一本书即不成立，且可追溯到 persona 的目光/库存，而非题材默认桥段组合。**辨识度对照**：结合该题材常见组合判断是否撞车（泛化 = blocking；具体但与同类书高度同质 = warning）。
4. **承诺与节奏**：读者承诺是否清晰、用目标渠道读者的语言表述；`promise_cadence` 是否声明了可被 strategy 展开的兑现节拍。正向兑现与负向承诺（见证代价/追讨真相/守护将失之物）都是合法承诺类型，负向承诺的兑现单位须同样可感（真相揭示/代价落地/失去逼近）。
5. **规模数字门**：`project_setup.scale` 档位的兑现次数与间隔必须匹配——短篇完整兑现 1-2 次、中篇 3 次量级间隔 ≤30 万字、长篇 3-4 幂兑现间隔 ≤80 万字、超长篇 ≥5 次间隔 ≤100 万字。优先核 `book_soul.cadence_plan`（机器门：`novelos_validate_book_soul.py --scale <档位>` 已校验次数下限），并查 promise_cadence 文本与 cadence_plan 一致；新候选缺 cadence_plan 或文本与计划矛盾 = warning；既无 cadence_plan 且文本含糊到无法核定兑现次数 = blocking，并注明移交 volume_outline 审查回查实际间隔。
6. **作者签名与 persona 继承**：是否精确继承 `creator_signature_ref`；persona 是否被消费（矛盾→两难种子、目光→组织原则、盲区→负面清单）。**血缘逐字段核验**：以 `book_soul.lineage` 为结构化抓手（无 lineage 的旧形态候选退回叙述核对）——抽查至少两条 derivation 的真实性（字段内容确实从 source_ref 所指签名条目/persona 部件可推导，而非贴标签）；标 `variation: true` 的变奏条目（发散纪律允许至多一个变奏候选）不判血缘断裂，但**未标 variation 的越界**照判 warning。没有绕开 persona 的人口属性刻板推导，没有具体作者模仿目标。注入 `kernel_full` 时另查**内核消费**：organizing_principle 可追溯到内核核心问题、central_contradiction 的价值侧与内核价值公理一致、内核盲区已并入负面清单——血缘断裂 = `warning`；内核与 persona 冲突未走 change proposal = `blocking`。无内核注入（旧项目占位节）时跳过内核子项。
7. **书级创作灵魂**：`book_soul` schema v2 字段完整；承诺确实牺牲便利；recurring_tests 声明「改变处境/答案/代价」；仁慈与残酷同时存在且**残酷有具体落点**——落在谁身上、什么形态、在结局的哪一侧兑现；存在性一句话敷衍（「叙事会比较残酷」）= warning。
8. **项目独立性**：是否针对本项目形成独有追问，而非机械复制作者签名或另一项目的 `book_soul`。
9. **力量货币与代价质量**：`power_currency` 已定义、带对价（获取付出什么、买不到什么），且 `central_contradiction` 至少一端锚在货币上；代价形态非对称——纯「得到1失去2」等价交换记账或代价可被读者提前预算 = warning。
10. **库存反向对账（persona 利用率）**：persona 的差异化库存（career_track / class_circle_inventory / 目光库存）是否被至少一个候选真实消费——全部候选集体绕开差异化库存、只用任何泛化人格都能提供的 inner_tension = warning（persona 存在理由落空）。
11. **证伪与读者模拟**：不满足于核对属性，主动攻击候选——从目标渠道读者视角模拟（看到这个方向会不会点开、追到中段凭什么留下），给出 2-3 个最可能的断裂点（两难被读者找出第三条路的瓦解条件 / 组织原则到第三卷的重复疲劳点 / 兑现空窗弃书点），落 `note` 及以上供修复与下游护栏引用。

## Blocking 条件
- 缺失明确的核心冲突或主角处于完全被动无动机状态。
- 组织原则泛化（任何书都成立）或承诺无兑现节奏声明。
- 故事方向泛化无看点或无法支撑后续卷级展开。
- 承诺次数 × 间隔与 scale 档位明显失配（低于档位下限）。
- 缺失或错绑 `creator_signature_ref`，人口属性刻板推导，具体作者模仿，或静默改写 Creator Profile。
- `book_soul` 字段不完整（v2 含 organizing_principle / promise_cadence / power_currency）、核心矛盾单向口号、力量货币未定义或未被矛盾锚定、承诺不承担任何叙事代价，或照抄作者签名而没有本书独有追问。

## strength 通道（不阻断、不修复）

finding 可用 `severity: "strength"` 记录候选的独有赌注与亮点（如「三候选中唯一让人兴奋的组织原则」「表里反差最大胆的结构」）——供用户选型参考，不进修复循环；可不引原文片段但须说明判断依据。修复轮中修复者须知道哪些棱角是设计意图，不得顺手削平 strength 指认的特质。

## 横向回执（多候选并列时）

direction 通常产出 2-3 候选供用户裁决，但审查逐候选独立进行。主控收集同轮全部候选回执后须汇总横向比较（最强候选 / 实质差异维：两难·组织原则·情感登记·承诺类型 / 推荐序）呈报用户；**变奏候选（lineage 含 variation 条目）与负向承诺主导候选须显式标注**，供用户知情裁决——横向回执是各候选独立 verdict 之外的附加产出，不改变逐候选判定。

## 条件审查模块（按项目组装）

频道语法（男频力量轴/女频规则关系轴/全向双轨）、平台画像（免费/付费三字段消费）、题材信息包（非空/缺位）、美学基因（aesthetic_styles 非空）的专项审查**不在本主干**——组装器按 setup 取值把对应 check 模块附加在本清单之后，与上述条目同级执行。手工阅读完整 rubric 时按 `modules/manifest.json` 索引。

## 不得检查的下游
- 不得审查下游具体的叙事机制 (Architecture)、阶段战略 (Strategy) 或具体卷章安排。

## 证据要求
- blocking / warning / note 结论必须引用方向文本原文片段。
- strength 结论可引用候选间对比与读者模拟推理，不强制原文片段，但须写明依据。
