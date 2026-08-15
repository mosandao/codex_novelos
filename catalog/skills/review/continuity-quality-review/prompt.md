# 连续性事实审查

只审查从章节提取的连续性候选与已接受正文及现有 Canon 的匹配度，不重写候选。

## 检查清单

1. **判定标准合规**：逐条对照提取端五条边界——推断入账（无显性确认的心理/动机/状态）= `blocking`；对话承诺与叙述承诺混装 = `blocking`；implicit 条目未标注证据级 = `warning`。
2. **事实变更**：提取的 fact 与正文原文一致（引用最小片段核对）——正文无此陈述 = `blocking`。
3. **关系变化**：relationship 条目锚定可观察行为/事件，非概括形容——概括式（「关系恶化」）= `warning`，无正文依据 = `blocking`。
4. **伏笔与承诺**：narrative_promise / expectation 的种收状态与既有 Canon 台账一致——重复种收、状态漂移 = `warning`；张冠李戴（把叙事承诺记成人物承诺）= `blocking`。
5. **arc 状态**：弧线状态推进与已接受正文的实际进度一致。
6. **Hash 对应**：每条候选的 `subject_hash` 与被审章节一致——错绑 = `blocking`。
7. **冲突处理**：正文与既有 Canon 冲突时，提取端应列冲突 finding 而非自行裁决——静默覆盖 = `blocking`。

每个问题使用 `blocking`、`warning` 或 `note`，引用最小片段和来源 ref。存在 `blocking` 时 verdict 必须为 `rejected`。

## 证据要求

- 每个 finding 引用正文原文片段或既有 Canon 条目 ref，禁止「多处」「整体」式模糊描述。

返回同一 `subject_hash`、verdict、findings、evidence refs 和 reviewer profile。
