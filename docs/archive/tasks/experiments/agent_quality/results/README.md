# Agent 质量实验结果契约

本目录只接收真实执行证据，不存放占位输出。

## 必需文件

- `outputs/<case_id>-<label>.<ext>`：从 MCP Resource 原样导出的匿名生产输出；execution 必须记录媒体类型，文件 Hash 必须与 Resource 一致。
- `subjects/<case_id>.json`：`review.prepare_subject` 创建的不可变盲评包导出，只包含原始输入 Hash、匿名标签、输出 refs/Hash 和 Review Profile，不得包含执行模式。
- `assessments/<case_id>.json`：审查智能体 生成并由 Review Receipt 绑定的结构化评分、blocking 与边界/冲突/winner 判断。
- `receipts/<case_id>.json`：`review.get` 返回值的规范化导出，保存 subject、Reviewer run、Profile、findings、evidence refs 和 `assessment_ref`。
- `evidence/<case_id>.json`：Schema 2 evidence，保存完整原始输入、按盲标签记录的 Trace/Producer run、上述文件路径与 Hash。
- `case_results.jsonl`：完整覆盖 70 个 case；其中评分与判断必须逐字等于 Receipt 绑定的 assessment，不能作为独立事实来源。
- `summary.json`：只能由 `scripts/summarize_agent_quality_results.py` 从上述证据生成。

Reviewer 不得读取 `execution_manifest.jsonl` 中 A/B 标签对应的执行模式。评审完成后，汇总器才使用该映射解盲并计算 Writer 与 上下文构建智能体 决策。

运行：

```bash
.venv/bin/python scripts/summarize_agent_quality_results.py
.venv/bin/python scripts/summarize_agent_quality_results.py --check
```

缺少 case 或原始文件、复用 Reviewer run/Receipt、输入/输出/subject/Receipt/assessment Hash 不一致、盲评包泄漏模式字段、评分未绑定 Receipt、评分维度不完整、winner 与加权分数矛盾时，汇总失败且不得解除切换门禁。
