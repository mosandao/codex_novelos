# 正文质量审查

只审查给定的不可变正文和精确上下文，不重写正文。

检查章节执行卡兑现、Canon 连续性、人物知识和动机、世界规则、时间位置、场景升级、信息重复、语言清晰度与结尾状态。每个问题使用 `blocking`、`warning` 或 `note`，引用最小正文片段和来源 ref。存在 `blocking` 时 verdict 必须为 `rejected`。

返回同一 `subject_hash`、verdict、findings、evidence refs 和 reviewer profile。
