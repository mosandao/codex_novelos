# Agent 质量实验

状态：`DEFERRED`，保留现有证据和恢复点，完整实验推后执行。

## 数据集

- `planning.jsonl`：8 类规划资产各 5 个任务，共 40 个；每类包含一个诱导越权修改上游的样本。
- `character_world.jsonl`：10 组 Character/World 交叉冲突检测任务。
- `writer_ab.jsonl`：10 组 Main + Skill 与隔离 写作智能体 的匿名对照任务。
- `context_builder_ab.jsonl`：10 组合法的跨卷/多线或冲突事实任务，对照 Memory Skill 与 上下文构建智能体；简单任务的禁止 Spawn 由 Agent 工作流负向测试覆盖。
- `execution_manifest.jsonl`：70 个 case 的输入 Hash、执行模式到盲标签映射和 Review Profile；只提供给执行者，不提供给盲评 Reviewer。
- `rubric.yaml`：评分维度、权重、阻断规则和角色保留标准。

数据集由 `scripts/build_agent_quality_dataset.py` 从 `source.yaml` 确定性生成。不得手工修改 JSONL；修改源数据后重新生成并运行 `--check`。

## 执行要求

1. 每个生产输出必须保存原始输入、Agent run、输出 Resource、原始输出文件和 Trace；Main + Skill 基线通过 `resource.create` 登记不可变输出。
2. A/B 输出按 `execution_manifest.jsonl` 的稳定随机映射标为 A/B；Reviewer 只能读取不含执行模式的输出包。
3. Main 调用 `review.prepare_subject` 将匿名标签、输入 Hash、输出 refs/Hash 和 Review Profile 登记为不可变盲评包；不得包含执行模式。
4. 审查智能体 必须是新的隔离 run；`review.record` 以 `review_subject` 登记 Receipt，并把结构化分数和判断保存为不可变 assessment Resource。
5. 规划样本出现跨层要求时，本层候选不得吸收修改，只能返回 typed change proposal。
6. 失败、超时或 Schema 不合法的输出记为失败，不使用硬编码语义 fallback。
7. 在 `results/` 中保存匿名输出、Review Subject、Receipt、assessment 和逐 case evidence；没有原始证据不得填写结果。
8. 使用 `scripts/summarize_agent_quality_results.py` 校验全部 70 个 case 并生成 `summary.json`；不得手工创建或编辑汇总结论。

## 当前执行

用户已明确授权创建临时业务 Agent 并接受模型成本。`scripts/record_agent_quality_experiment.py` 使用专用 `data/agent-quality.db` 和真实 stdio MCP，以 `start -> prepare -> finalize` 三阶段录制每个 case；正式数据库不接收实验数据。

当前已完成 2 个 Direction case 的 Producer、独立 Reviewer、不可变 Subject、Receipt、assessment 和 Evidence Schema 2 闭环，其余 case 保留恢复点。`deferral.json` 固化用户延期决定和保守路由；`summary.json` 不存在，已有部分结果不构成 Writer 或 上下文构建智能体 的质量结论。
