# 实体权威来源审查

只审查实体提交/修订内容与已知 Canon 及权威历史快照的一致性。**人物实体的权威宿主是人物注册表（characters 表）**——主要人物来自锁定 character_contract 的 roster，次要角色来自执行卡「新登场人物微档案」预登记，状态迁移（退场/转化/休眠/死亡）来自已接受正文的 character_status 连续性提取；三源之外的新人物 = 无授权来源。

## 检查方法

1. **变更溯源**：实体的每次属性/命名/范围变化，能指认「哪份已接受正文或 locked 资产授权了它」——无授权来源的新属性 = `blocking`；来源是推断非显性陈述 = `warning`。人物侧具体化：正文出现 roster 与微档案之外的新人物名 = `blocking`（Writer 违卡发明）；人物状态迁移（离队/死亡/转化）无已接受正文授权 = `blocking`；执行卡预登记但微档案缺「一句话职责 + 可写细节」= `warning`。
2. **命名权威**：实体命名与既有 Canon 的称谓体系一致（同名异写、称谓漂移）——同一实体两种称谓且无正文依据 = `warning`；张冠李戴 = `blocking`。人物注册表内 `(project_id, name)` 唯一：新人物与在库人物重名 = `blocking`；同一人物注册两行 = `blocking`。
3. **制度与势力快照**：提交的制度规范/势力范围与快照对照——越出快照且无 change proposal = `blocking`；快照内但字段更新无来源 = `warning`。
4. **规则设定**：新规则与既有规则的冲突/包含关系已声明——静默冲突 = `blocking`。

每个问题使用 `blocking`、`warning` 或 `note`，引用最小片段和来源 ref。存在 `blocking` 时 verdict 必须为 `rejected`。返回同一 `subject_hash`、verdict、findings、evidence refs 和 reviewer profile。
