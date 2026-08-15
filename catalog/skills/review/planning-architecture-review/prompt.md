# 叙事架构审查 Rubric (Story Architecture Review Rubric)

审查 `architecture` 资产候选是否忠实于已锁定的 `direction`，并具备可运转的叙事引擎。

## 输入边界
- 目标资产：`architecture`
- 精确上游：已锁定的 `direction`（含 book_soul v2 十三字段）；创作者 persona（来自项目绑定签名）

## 检查清单
1. **翻译完整度**：book_soul 十三字段（含 `organizing_principle`、`promise_cadence` 与 `power_currency`）是否每个都有机制形态，或附显式豁免声明；组织原则是否被翻译成支撑机制而非复述。
2. **双引擎**：章级单元机器与卷级主线引擎是否都有实体设计（输入→运转→产出）；只有主线无单元机器（中段塌方风险）或反之（爽而无根）均为缺陷。
3. **咬合闭环**：施压机制之间是否声明咬合关系并构成闭环；独立并列的机制清单（孤岛）不合格。
4. **四段式**：每个机制是否具备 引用（direction 血缘）→ 机制（运转方式）→ 节奏（施压/兑现频次）→ 下游影响（strategy/character/world 各拿什么）；节奏段是否可被 strategy 直接使用。
5. **防火墙**：是否逐条反验 `forbidden_resolutions`；新机制（尤其预知/探测/复活类）是否构成绕禁令通道。
6. **因果与升级**：转折是否由前置推演自然引发；冲突是否具备层层递进的升温结构（压力测试与油耗测试是否通过）。
7. **POV 契约**：persona 的有限视角是否机制化（知识边界/感知时序/全知侵入判定）；`deliberate_silences` 是否只经可见征兆呈现。
8. **边界**：是否越界产出静态设定（判定测试：换人物事件后能否继续生产情节）、人物传记或卷章事件（应显式移交 world/character/strategy）。

## Blocking 条件
- 脱离或违背已锁定的 `direction` 承诺；`organizing_principle`/`promise_cadence` 无对应机制。
- 机制孤岛无咬合、只有单引擎、或压力/油耗测试不过（撑不起 `scale`）。
- 逻辑断层、机械降神、无代价规则，或存在绕过 `forbidden_resolutions` 的机制通道。
- POV 契约缺失或全知渗漏无判定标准。

## 不得检查的下游
- 不得检查具体的全书分卷计划 (Strategy)、人物弧契约或世界设定细节。

## 证据要求
- 必须对比 `direction` 上游文本与当前 `architecture` 候选文本，逐机制引用两侧原文。
