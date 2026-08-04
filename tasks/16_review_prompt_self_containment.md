# Task 16：审查 prompt 自包含约束

## 状态

`DONE`

## 背景

Task 15 复盘标注了一个"观察项（暂不处理）"：Strategy 审查 sub-agent 消耗 613K tokens（Architecture 审查的 15.5 倍）。用户要求修复。

## 问题定位

| Agent | tokens | tool_uses |
|---|---|---|
| Architecture 审查 | 39,458 | 0 |
| Strategy 审查 | 612,985 | 22 |

Architecture 审查 0 次 tool_uses（纯推理），Strategy 审查 22 次 tool_uses（大量文件读取）。token 暴涨 15.5 倍，但候选长度只差 2K 字，差异不可能来自 prompt 长度。

### 根因

| 审查 | prompt 传入的上游内容 | sub-agent 行为 |
|---|---|---|
| Architecture | Direction **完整原文**（含 book_soul 9 字段全文） | 0 tool_uses，纯推理 |
| Strategy | Direction/Architecture **摘要**（"上游铁律速查"） | 22 tool_uses，自行读文件补充 |

摘要不完整 → sub-agent 发现审查依据不够 → 自己用 Read/grep 读上游文件 → 22 次探索性工具调用 → token 失控。

这不是 sub-agent 的错误（它正确地需要完整依据来做审查），而是 **Main Agent 传给审查 sub-agent 的 prompt 不自包含**——把"提供完整审查依据"的职责泄漏给了 sub-agent 的探索行为。

## 优化

### novel-review SKILL.md：新增「审查 prompt 自包含约束」

三条规则：

1. **传入完整原文**：候选正文全文 + 全部已锁定上游资产的正文全文（不是摘要）。多层资产审查时所有上游都要传完整原文。
2. **禁止依赖 sub-agent 自行读文件**：prompt 自包含后，明确指示"依据已在 prompt 中提供，不需要读取文件或搜索"。
3. **token 预算**：候选+上游原文超过约 2 万字时，优先压缩候选摘要（保留关键段落原文引用），但上游铁律（forbidden_resolutions、central_contradiction、守恒律等）必须保留原文不可摘要化。

## 来源信息

- 来源 commit：本次变更所在 commit（待回填）
- 触发实例：Strategy 审查（Trace `a8c573e7`，review_agent run `a2ecb32f`）
- 对比实例：Architecture 审查（Trace `bd206236`，review_agent run `7717aa90`）

## 改动文件

| 文件 | 变更 |
|---|---|
| `.agents/skills/novel-review/SKILL.md` | 新增「审查 prompt 自包含约束」段 |
| `tasks/16_review_prompt_self_containment.md` | 本文件 |

## 验收标准

- [x] novel-review SKILL 包含审查 prompt 自包含约束段。
- [x] 约束包含根因实例（Architecture 39K/0 tools vs Strategy 613K/22 tools）。
- [x] 根测试、MCP 测试、compileall 全部通过。

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```
