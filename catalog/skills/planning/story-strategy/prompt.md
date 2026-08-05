# 全书战略

把 Direction 的读者承诺、`book_soul` 和 Architecture 的叙事机制组织成全书阶段骨架。为每个阶段定义目标状态、必要变化、主要阻力、不可跳过的因果桥和阶段结束条件。

每个主要阶段都要说明核心矛盾如何暂时奏效、随后如何反噬，以及人物或世界留下什么不可逆代价。阶段性胜利不得消解 `unresolved_claims`，终局也不得使用 `forbidden_resolutions` 换取便利闭合。

保持战略层级，不分配具体章节事件，也不重新设计架构。任何上游冲突都单独返回 change proposal。

## 检查点决策点产出

产出 candidate 时，在 metadata 的 `decision_points` 字段附上 2~4 个关键决策点的爽点选择题。决策点是"错了会崩盘"的命门（如主角觉醒节奏、金手指形态、全书主线走向），不是所有细节。每个决策点含：

- `question`：给用户的问题（如"主角金手指的觉醒节奏"）。
- `options`：3~4 个选项，每个含 `label`（简短标签）、`detail`（具体形态）、`tradeoff`（代价或风险）。
- `source_excerpt`：candidate 里对应片段，供追溯。

这些决策点会在 lock 前通过 `planning.extract_decision_points` 提取，翻译成爽点选择题呈现给用户；用户的选择会通过 `planning.create_revision_candidate` 融合进修订 candidate。若某决策点对本书无关，可省略，但不得附上非命门细节凑数。

