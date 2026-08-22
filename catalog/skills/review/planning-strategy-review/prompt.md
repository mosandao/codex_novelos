# 全书战略审查 Rubric (Story Strategy Review Rubric)

审查 `strategy` 资产候选是否符合 `direction` 与 `architecture`，并核验 persona / 题材 / 上游回执消费。

## 输入边界
- 目标资产：`strategy`
- 精确上游：已锁定的 `direction` 与 `architecture` + 两者**审查回执**（strength 指认 / accepted_risk / defer→strategy 项）
- persona 全文（涉 persona 的检查引用原文部件，不得凭候选复述转述）
- project_setup（scale / 频道 / 平台 / 题材）与 genre 信息包

## 检查清单
1. **上游消费完整**：七行翻译（节奏表/释放阶梯/promise_cadence/货币分级/螺旋/双层引擎配置/上游回执）各有引用——静默自创 = blocking；book_soul 十三字段逐样消费或显式豁免，静默丢弃 = warning。
2. **数字对账**：总兑现次数 ↔ cadence_plan.fulfillment_count；配对表行数 ↔ engines.escalation_levels；卷节奏骨架 ↔ beats_per_volume × 卷数——数值矛盾无说明 = blocking，口径含糊 = warning。
3. **体量合规**：阶段数在 scale 档位区间（短篇 1-2 / 中篇 2-4 / 长篇 3-8 / 超长篇 5-12），每阶段有 word_range 与事件判据（≥1 不可逆变更 + 螺旋轮换）——区间外无豁免 = blocking（机器门 validate --scale 前置）；阶段空转或单阶段无曲线 = blocking。
4. **代价类型学**：不可逆/压制分桶——压制代价无解除方式 = warning；人物死亡未过 protected_dignity 交叉核验 = blocking；主角永久损伤无 book_soul 声明 = blocking。
5. **承诺-债务周期**：连续纯存债（payoff=debt）超限 = warning；某阶段无任何 progress 类型 = warning（弃书点）；登记承诺三分类缺条 = warning；即兴铺垫被错误升格为登记承诺 = note；全书无兑付爆发阶段 = blocking。
6. **中盘续命**：阶段数 ≥3 无换挡事件 = warning（defer volume_outline 关注中段）；换挡清空人际无铺垫 = warning。
7. **终局纪律**：terminal 待收条数超收束预算（赶工烂尾形态）= warning，严重超限 = blocking；终局阶段字数明显压缩 = warning；terminal_mode=open 无喂料机制声明 = blocking（无尾化必须是设计不是事故）；forbidden_resolutions = blocking。
8. **persona 四用法核验**：揭层节奏/终局场面形态门/POV 契约/库存燃料——引用 persona 全文部件逐项核验；盲区场景未绕开（大战正面全知叙述）= blocking；四用法全空转 = warning。
9. **题材阶段形态**：阶段阶梯与题材匹配（玄幻境界弧不是悬疑案件弧）；题材缺位未显式声明 = warning。
10. **矛盾动力学**：奏效→反噬→不可逆代价曲线完整；unresolved_claims 未被中途消解；多阶段机械重复同一测试（对照 recurring_tests 轮换池）= blocking。
11. **下游交接**：人物弧需求/世界状态变更清单完整覆盖各阶段——下游须自创关键弧 = warning。
12. **decision_points**：命门级（0~4 个）且结构完整（question/options[label,detail,tradeoff]/source_excerpt）——凑数 = warning，结构破损 = blocking。
13. **证伪与读者模拟**：从目标读者视角模拟 2-3 个断裂点（中盘弃书点/赶工感/重复疲劳/登记承诺遗忘投诉），给出最薄弱处。

## Blocking 条件
- 违背 direction 或 architecture 约定的铁律；阶段推进缺乏不可逆变化，或多阶段机械重复同一测试。
- 七行上游翻译任一缺失或静默自创；数字对账矛盾且无说明。
- 主角永久损伤无上游声明；死亡名单犯 protected_dignity；open 模式无喂料声明；全书各阶段均无阶段性收益。

## strength 通道
上游回执的 strength（独有赌注/低密度设计意图等）在本阶段的落点应被指认——修复不得削平；候选新发现的独有结构亮点记 strength（不阻断不修复）。

## 条件审查模块（按项目组装）
频道轴的阶段收益主形态与平台耐心结构专项审查不在本主干——组装器按 setup 取值附加 check 模块，与上述条目同级执行。索引见 `modules/manifest.json`。

## 横向回执
多候选并列时：主控汇总最强候选/差异维/推荐序呈报用户裁决。

## 不得检查的下游
- 不得检查单卷细化章纲或具体场景执行卡。

## 证据要求
- 对账类检查引用两侧数字；涉 persona / 上游回执的检查引用对应原文部件，不得凭候选的复述转述。
