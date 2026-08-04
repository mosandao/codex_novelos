# Task 13：规划/审查 Skill 操作前置检查与错误提示改进

## 状态

`DONE`

## 背景

西幻项目（`project:ea0831c1`）首次生成 Story Direction（Direction「次子铸权」，revision 1，locked）的全流程中，治理链路本身完整通过（Trace `trace:530a5150`：方向智能体 run → 候选登记 → `planning-direction` 独立审查 approved → `planning.lock` → authority commit verified → 投影刷新），但执行阶段发生了 **6 次 MCP 工具调用失败**，全部源于「没有先读 schema / 契约定义就构造数据」。

6 次失败的根因可归纳为三类：

| 类型 | 失败次数 | 根因 |
|---|---|---|
| Agent input_bindings 格式错误 | 3 | 没读 `agents.yaml` 确认 `minimum_inputs` 精确字段名与值类型约束 |
| Agent output / book_soul schema 不匹配 | 2 | 没读对应 schema 确认 required 字段与类型（`schema_version`、string vs list、output 是正文而非 resource_ref 对象） |
| Review 路径选错 | 1 | 没确认 `review.prepare_subject` 只接受 `agent_quality_evaluation`，规划资产审查走另一条路径 |

这些知识散落在 `agent_contracts.py`、`planning-candidate.schema.json`、`book-soul.schema.json`、`review-receipt-candidate.schema.json`、`chapters.py` 等代码文件里。每次规划资产生成都要重新从失败中学习，成本高且可避免。

## 目标

把本轮 6 次失败的教训固化为三层改进，降低未来每次规划/审查资产时的试错成本：

1. **优化 A（Skill 文档）**：在 `novel-planning` 和 `novel-review` Skill 中新增「操作前置检查」清单和「Schema 字段速查」，让 Agent 在构造数据前就知道精确格式。
2. **优化 B（错误提示）**：改进 `creative_contracts.py` 的 `_validate` 错误信息，把 jsonschema 的 `message` 加入 details，使校验失败时能直接看到缺了什么字段或类型不对。
3. **优化 C（book_soul 速查表）**：在 `novel-planning` SKILL.md 末尾附 book_soul 字段速查表。

## 非目标

- 不改变任何 MCP 工具的签名、校验逻辑或数据库 schema。
- 不改变 `agent_contracts.py` 的 `validate_inputs` 逻辑（它已正确返回 required/actual 差异）。
- 不新增 MCP 工具、不新增 Schema 文件、不新增角色。
- 不改变规划资产的治理流程（Trace → Agent → 候选 → 审查 → 锁定 → authority commit）。
- 本任务不修改 AGENTS.md 的规则文本（Skill 是执行辅助，不是规则来源）。

## 改动清单

### 优化 A：`.agents/skills/novel-planning/SKILL.md`

在现有「工作流」第 6-7 步之后，新增一节「## 操作前置检查」，包含：

**Agent input_bindings 构造规则**（对应失败类型 1）：
- 调用 `agent.start` 前，从 `config/agents.yaml` 读取目标角色的 `minimum_inputs`，确认精确字段名。
- `input_bindings` 的 key 集合必须**精确等于** `minimum_inputs`（不能多、不能少、不能改名）。
- 每个 value 必须是**非空字符串**或**非空字符串数组**；不能是嵌套 dict / list[dict] / number。
- 复杂约束（项目 setup、catalog 选择等）须序列化为单个字符串（如用 ` | ` 分隔的键值摘要）或字符串数组，不能直接传 JSON 对象。

**Agent output 格式规则**（对应失败类型 2）：
- 调用 `agent.finish` 时，`output_type=planning_candidate` 的 `output` 直接传**正文 markdown 文本字符串**，不是 `resource_ref` 对象或 `{content_hash, resource_ref}` 结构。
- `planning_candidate` schema 接受非空字符串（正式候选）或实验结构化对象（延期实验专用），不接受 resource ref 对象。
- 系统会在 finish 事务内自动把 output 字符串存为 resource，不需要先手动创建 resource。

**book_soul 构造规则**（对应失败类型 2）：
- 构造 Direction 候选的 `metadata.book_soul` 前，参考本文件末尾「book_soul 字段速查表」。
- `schema_version: 1` 是必填字段。
- `central_contradiction`、`narrative_mercy`、`narrative_cruelty` 是**字符串**（1-1000 字符），不是数组。
- 其余 6 个字段是**字符串数组**（1-24 项，每项 1-500 字符，uniqueItems）。

### 优化 A：`.agents/skills/novel-review/SKILL.md`

在现有「工作流」第 7 步之后，新增一节「## 操作前置检查」，包含：

**规划资产审查路径**（对应失败类型 3）：
- 规划资产审查**不走** `review.prepare_subject`（该方法只接受 `subject_kind=agent_quality_evaluation`，是质量实验专用）。
- 正确路径：
  1. 创建 `review_agent` run（`input_bindings` 含 `immutable_subject_ref`、`subject_hash`、`review_profile`、`authority_context_refs` 四个精确字段）。
  2. 在隔离上下文中完成审查，`agent.finish` 时 `output_type=review_receipt_candidate`，`output` 传 `review_receipt_candidate` dict。
  3. Main 调用 `review.record_from_run(reviewer_run_id)` 登记。

**review_receipt_candidate 构造规则**（对应失败类型 3）：
- 每个 finding 必须含 `evidence_refs`（required，非空字符串数组）。
- `subject_type != review_subject` 时不得包含 `assessment` 字段。
- findings 的 `severity` 只接受 `blocking`、`warning`、`note`。

### 优化 B：`mcp/novelos/src/novelos_mcp/creative_contracts.py`

改进 `_validate` 方法（约第 100-111 行）的错误信息：

当前：
```python
raise NovelOSError(code, f"{label}不符合 Schema", {"path": list(exc.path)}) from exc
```

改进后：把 jsonschema 的 `exc.message` 加入 details，使校验失败时能直接看到「缺了什么字段」或「类型不对」：

```python
raise NovelOSError(
    code,
    f"{label}不符合 Schema：{exc.message}",
    {"path": list(exc.path), "schema_path": list(exc.schema_path)},
) from exc
```

此改进同时提升 `validate_signature`、`validate_book_soul`、`validate_chapter_soul` 三者的错误可读性，因为它们共用 `_validate`。

### 优化 C：`.agents/skills/novel-planning/SKILL.md` 末尾

新增「## book_soul 字段速查表」，内容直接派生自 `config/schemas/book-soul.schema.json`：

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `schema_version` | const | ✅ | 固定值 `1` |
| `unresolved_claims` | string[] | ✅ | 1-24 项，每项 1-500 字符，uniqueItems |
| `central_contradiction` | string | ✅ | 1-1000 字符 |
| `costly_commitments` | string[] | ✅ | 1-24 项，每项 1-500 字符，uniqueItems |
| `protected_dignity` | string[] | ✅ | 同上 |
| `forbidden_resolutions` | string[] | ✅ | 同上 |
| `recurring_tests` | string[] | ✅ | 同上 |
| `narrative_mercy` | string | ✅ | 1-1000 字符 |
| `narrative_cruelty` | string | ✅ | 1-1000 字符 |
| `deliberate_silences` | string[] | ✅ | 同上 |

## 改动文件

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `.agents/skills/novel-planning/SKILL.md` | 修改 | 新增「操作前置检查」节 + book_soul 速查表 |
| `.agents/skills/novel-review/SKILL.md` | 修改 | 新增「操作前置检查」节 |
| `mcp/novelos/src/novelos_mcp/creative_contracts.py` | 修改 | `_validate` 错误信息加入 `exc.message` 与 `schema_path` |
| `mcp/novelos/tests/test_creative_contracts.py`（或相邻测试文件） | 修改 | 新增测试断言改进后的错误信息包含 message |
| `tasks/13_planning_skill_schema_checklists.md` | 新建 | 本文件 |

## 来源信息

- 来源 commit：本变更所在 commit（待回填）
- 触发实例：项目 `project:ea0831c1-cb35-4404-8df4-b69e2a136967`（西幻）Direction「次子铸权」生成全流程
- Trace：`trace:530a5150-5c3a-4f25-a9be-5ab7b533ffc8`
- 失败记录：6 次 MCP 工具调用失败（3 次 input_bindings、2 次 output/book_soul schema、1 次 review 路径）

## 验收标准

- [x] `novel-planning` SKILL.md 新增「操作前置检查」节，覆盖 input_bindings 构造规则、output 格式规则、book_soul 构造规则。
- [x] `novel-planning` SKILL.md 末尾新增「book_soul 字段速查表」，字段与 `book-soul.schema.json` 一致。
- [x] `novel-review` SKILL.md 新增「操作前置检查」节，覆盖规划资产审查正确路径与 `review_receipt_candidate` 构造规则。
- [x] `creative_contracts.py` 的 `_validate` 错误信息包含 `exc.message`。
- [x] 新增测试断言：传入缺 `schema_version` 的 book_soul 时，错误信息包含可读的 message（如 "'schema_version' is a required property"）。
- [x] 现有测试全部通过（不破坏已有行为）。
- [x] `compileall` 通过。

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 完成条件

只有三个优化全部落地、测试通过且验收项全部勾选，才可将本任务从 `IN PROGRESS` 标记为 `DONE`。
