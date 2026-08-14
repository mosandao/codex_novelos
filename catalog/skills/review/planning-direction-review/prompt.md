# 故事方向审查 Rubric (Story Direction Review Rubric)

审查 `direction` 资产候选是否满足故事方向质量标准。

## 输入边界
- 目标资产：`direction`
- 创作约束：项目绑定的精确 `creator_signature_ref`（含 persona，schema v2）与 project_setup；无规划资产上游（无上游依赖）

## 检查清单
1. **核心冲突**：`central_contradiction` 是否为两个都能成立却无法同时满足的判断（两难结构），贯穿全书；无单向正确口号。
2. **主角驱动力**：主角是否有不可替代的内驱欲望或外部危机逼迫。
3. **组织原则**：`organizing_principle` 是否为本书独有的组织过程——换一本书即不成立，且可追溯到 persona 的目光/库存，而非题材默认桥段组合。
4. **承诺与节奏**：读者承诺是否清晰、用目标渠道读者的语言表述；`promise_cadence` 是否声明了可被 strategy 展开的兑现节拍。
5. **可展开性**：故事体量与核心设定是否足以支撑 `project_setup.scale` 规模的长篇架构（中段 progress 不塌）。
6. **作者签名与 persona 继承**：是否精确继承 `creator_signature_ref`；persona 是否被消费（矛盾→两难种子、目光→组织原则、盲区→负面清单）；没有绕开 persona 的人口属性刻板推导，没有具体作者模仿目标。
7. **书级创作灵魂**：`book_soul` schema v2 字段完整；承诺确实牺牲便利；recurring_tests 声明「改变处境/答案/代价」；仁慈与残酷同时存在。
8. **项目独立性**：是否针对本项目形成独有追问，而非机械复制作者签名或另一项目的 `book_soul`。

## Blocking 条件
- 缺失明确的核心冲突或主角处于完全被动无动机状态。
- 组织原则泛化（任何书都成立）或承诺无兑现节奏声明。
- 故事方向泛化无看点或无法支撑后续卷级展开。
- 缺失或错绑 `creator_signature_ref`，人口属性刻板推导，具体作者模仿，或静默改写 Creator Profile。
- `book_soul` 字段不完整（v2 含 organizing_principle / promise_cadence）、核心矛盾单向口号、承诺不承担任何叙事代价，或照抄作者签名而没有本书独有追问。

## 不得检查的下游
- 不得审查下游具体的叙事机制 (Architecture)、阶段战略 (Strategy) 或具体卷章安排。

## 证据要求
- 所有结论必须引用方向文本原文片段。
