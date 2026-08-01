# 作者签名与书级创作灵魂小规模 A/B

本目录定义 Task 08 的受控语义质量实验，不替代已延期的 70-case Agent 质量实验，也不改变 Writer 或上下文构建智能体的保守触发范围。

固定输入见 `cases.jsonl`，评分维度和阻断规则见 `rubric.yaml`。每个 case 真正执行时必须保存原始模型输入、原始输出、模型标识、Prompt/Catalog 快照、匿名映射、独立 Review run、Review Receipt 和逐维评分，并使所有 Hash 可重算。

当前 `status.json` 为 `BLOCKED`：仓库只有确定性契约和固定输入，没有真实模型输出与独立评审。不得用 Prompt 文本、单元测试或人工编造样例冒充质量通过，不得宣称已消除 AI 感。
