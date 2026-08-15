# 实体权威来源审查

只审查实体提交/修订内容与已知 Canon 及权威历史快照的一致性。

## 检查方法

1. **变更溯源**：实体的每次属性/命名/范围变化，能指认「哪份已接受正文或 locked 资产授权了它」——无授权来源的新属性 = `blocking`；来源是推断非显性陈述 = `warning`。
2. **命名权威**：实体命名与既有 Canon 的称谓体系一致（同名异写、称谓漂移）——同一实体两种称谓且无正文依据 = `warning`；张冠李戴 = `blocking`。
3. **制度与势力快照**：提交的制度规范/势力范围与快照对照——越出快照且无 change proposal = `blocking`；快照内但字段更新无来源 = `warning`。
4. **规则设定**：新规则与既有规则的冲突/包含关系已声明——静默冲突 = `blocking`。

每个问题使用 `blocking`、`warning` 或 `note`，引用最小片段和来源 ref。存在 `blocking` 时 verdict 必须为 `rejected`。返回同一 `subject_hash`、verdict、findings、evidence refs 和 reviewer profile。
