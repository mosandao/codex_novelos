# 故事方向

根据用户约束、Project Profile 和精确 `creator_signature_ref` 生成少量可比较方向。每个方向说明主角驱动力、核心冲突、读者承诺、长期压力来源、可持续性和主要风险。

每个候选必须：

- 原样绑定输入中的 `creator_signature_ref`，列出继承的作者约束，不根据年龄、性别、学历、职业或地域推导思想与文风，也不设置具体作者模仿目标；
- 生成契约完整的 `book_soul`：`unresolved_claims`、`central_contradiction`、`costly_commitments`、`protected_dignity`、`forbidden_resolutions`、`recurring_tests`、`narrative_mercy`、`narrative_cruelty`、`deliberate_silences`；
- 让 `central_contradiction` 包含两个都能成立却无法同时完整满足的判断，让每项承诺明确牺牲爽点、圆满、推进速度、主角正确性或即时认同中的至少一种便利；
- 说明本书约束与作者签名的继承关系、差异和冲突。无法兼容时返回 change proposal，不得静默改写作者签名。

方向必须回答“这本书长期无法放下什么问题”，不要提前创建世界百科、人物传记、卷事件或章节事件。用户确认前保持候选状态。候选的结构化 metadata 必须包含精确 `creator_signature_ref` 与完整 `book_soul`。
