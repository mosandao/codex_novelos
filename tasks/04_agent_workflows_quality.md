# Task 04：Agent 工作流与质量门禁

状态：`DONE`

## 完成结论

- Main Agent 是唯一常驻 Agent 和权威提交者。
- 临时角色包括八个规划资产 Agent、Writer、Review 和按条件创建的 Context Builder。
- 不存在泛化 Planning Agent；连续性由 Skill 生成候选，不设置 Continuity Agent。
- Character 与 World 可并行，但 Story Arc 前必须经过独立交叉一致性审查。
- 临时 Agent 只能读取白名单工具并返回候选；MCP 强制 Producer、Reviewer、Hash、版本、Trace 和状态机门禁。
- 完整规划、章节接受和连续性晋升共用同一生产路径并已通过端到端测试。

稳定角色与流程见 `config/agents.yaml`、[`documentation/automation.md`](../documentation/automation.md) 和 [`documentation/flows.md`](../documentation/flows.md)。

## 验收结果

- [x] 只有 Main Agent 常驻。
- [x] 八类规划 Agent 具有唯一资产所有权。
- [x] 临时 Agent 无法绕过权威提交门禁。
- [x] 规划、章节、Entity 和连续性流程通过端到端及负向测试。
- [x] Agent 生命周期、Review 隔离和权威提交可追溯。

## 延期项

70-case 真实质量实验由用户明确延期，不构成质量通过结论。当前完成 `2/70`，不得据此计算胜率或改变路由。

- Writer 暂限完整章节或长场景。
- Context Builder 暂限跨卷、多线、事实冲突或上下文溢出。
- 恢复条件和证据入口：[`experiments/agent_quality/deferral.json`](./experiments/agent_quality/deferral.json)

## 证据

- Agent 契约：`config/agents.yaml` 和 `config/schemas/`。
- 工作流测试：`mcp/novelos/tests/test_agent_workflows.py`。
- 完整链路：`mcp/novelos/tests/test_pure_codex_workflow.py`。
- 实验数据与恢复点：[`experiments/agent_quality/`](./experiments/agent_quality/)
