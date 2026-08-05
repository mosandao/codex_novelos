# 人物契约

只创建承担明确叙事职责的核心人物。定义其初始状态、欲望、误判、能力边界、必须付出的代价、人物弧状态变化和关键关系张力，并逐项说明如何服务 Architecture 与 Strategy。

围绕 `book_soul.central_contradiction` 为主要人物分配相互冲突、各有事实依据且各自需要付出代价的答案。至少一个有能力、有合理动机的人物必须能反驳主角或作者偏爱的立场；不得让所有人物共享同一结论、沦为作者扩音器。`protected_dignity` 保护人物不被叙事羞辱，但不免除行为后果。

不要增加没有战略职责的人物，不要重写全书战略。与世界资源或规则有关的假设必须显式列出，供 Character/World 交叉审查。

## 检查点决策点产出

产出 candidate 时，在 metadata 的 `decision_points` 字段附上 2~4 个关键决策点的爽点选择题。决策点是"错了会崩盘"的命门（如主角核心性格底色、主角与核心对手的关系基调、主角驱动力来源），不是所有细节。每个决策点含：

- `question`：给用户的问题（如"主角的核心性格底色"）。
- `options`：3~4 个选项，每个含 `label`、`detail`、`tradeoff`。
- `source_excerpt`：candidate 里对应片段，供追溯。

这些决策点会在 lock 前通过 `planning.extract_decision_points` 提取并呈现给用户；用户的选择会通过 `planning.create_revision_candidate` 融合进修订 candidate。

