# Task 24：reconcile 接收 fused parent + 融合签名收口

## 状态

`DONE`（MCP 确定性收口扩展 + 测试 + 文档统一，验证全部通过）

## 背景

Task 12 引入多原型 LLM 融合路径，但留下一处文档↔实现缺口：AGENTS.md / SKILL / documentation / readme
统一描述「以 **Agent 判定的 parent** 调 `project.wizard.reconcile_archetypes` 做确定性合规收口」，
而 `reconcile_project_wizard_archetypes`（`mcp/novelos/src/novelos_mcp/service/creators.py:213`）只接受
3 个参数，parent 由内部 `recommend_archetypes` 打分决定，**不接受外部 parent**——文档描述了一个
不可能执行的操作。

实证：项目 `project:d80fe455-5d56-415f-8211-b5d26e476bca`（西幻）创建时，4 原型经 onboarding_agent
判定 parent 为 `system-epic-framework`，但确定性打分另选 `system-shadowed-choice`。主控被迫绕过
reconcile 的 parent/overrides 输出，手工把 Agent 完整签名折算成 overrides diff 再 submit，耗时约
10 分钟（含源码考古），且转换逻辑无文档、无测试、易错。

### 暴露的四个问题

| # | 问题 | 根因 |
|---|---|---|
| A | reconcile 名实不符 | 不接受外部 parent，文档描述的操作不可执行 |
| B | handoff 未文档化 | Agent 完整签名（8 字段含 schema_version）→ overrides diff（7 字段、禁 schema_version、禁等于父值）的转换靠主控手工 |
| C | 双 parent 裁决未声明 | 打分 vs Agent 判定分歧时无规则 |
| D | agent.start 隐式约束 | `input_bindings` 必须字符串/字符串数组、`isolation_evidence` 必须含 `source`——只在代码里，无正式契约 |

### 决策（已确认）

- **A 走「扩展 reconcile」**（而非纯文档收口）：给 reconcile 加可选 `fused_parent_version_id` / `fused_signature`
  入参，把脆弱的「完整签名→diff」转换从主控手工挪进 MCP 确定性收口。**推翻 Task 12「不改 reconcile 实现」
  的旧约束**（Task 12 作为历史记录保持 DONE）。
- **范围仅 A–D**，不含 E（onboarding_agent 的语义审查门禁，作为独立后续工作）。

## 目标

### 1. reconcile 扩展（A）

`reconcile_project_wizard_archetypes` 新增两个可选关键字参数
（`fused_parent_version_id: str | None`、`fused_signature: dict | None`，必须同传同缺）：

- 未传（单原型路径）：行为完全不变，打分选 parent + `generate_derivation_draft` + 辅风格融合，
  返回 `parent_source:"scored"`。
- 同传（多原型路径）：在 `selected_archetypes` 内反查 fused parent，校验其 subject_hash 与 config
  一致；**跳过打分**，直接用 fused parent；把完整融合签名折算成 overrides diff（剔除 `schema_version`
  与等于父原值的字段，天然满足 `derive_signature` 的白名单与等值拒绝约束）；返回 `parent_source:"fused"`。

返回结构新增 `parent_source` 字段，供主控/审查区分 parent 来源。

### 2. 文档统一（B + C）

AGENTS.md / SKILL / documentation(flows|architecture|automation) / readme 改写两条路径措辞：
单原型 = `"scored"`，多原型 = fused 入参 `"fused"`；显式声明双 parent 裁决规则（≥2 路径以 Agent
判定为准）；AGENTS.md 补多原型 `creator` payload 权威样例。

### 3. agent.start 契约（D）

`.agents/skills/novel-project/SKILL.md` 新增「`agent.start` 入参契约」小节，写明
`input_bindings` 字符串化要求、`isolation_evidence` 必含 `source`，附 onboarding_agent 调用样例。

## 改动文件

| 文件 | 变更 |
|---|---|
| `mcp/novelos/src/novelos_mcp/service/creators.py` | 导入 `SIGNATURE_FIELDS`；reconcile 新增两可选 fused 入参 + `_reconcile_scored` / `_reconcile_fused` 私有 helper；返回结构加 `parent_source` |
| `mcp/novelos/src/novelos_mcp/server.py` | reconcile 包装函数透传两新可选参数；更新工具 description 提及 fused 路径 |
| `mcp/novelos/tests/test_project_wizard.py` | 新增 `_fused_signature_for` 夹具 + 3 个 fused 测试（uses_fused_parent / rejects_partial_args / fused_output_passes_wizard_submit）；既有 4 个 reconcile 测试零改动 |
| `AGENTS.md` | 向导段两条路径改写 + 双 parent 裁决规则 + creator payload 样例 |
| `.agents/skills/novel-project/SKILL.md` | 多原型路径改 fused 入参措辞 + 新增 `agent.start` 入参契约小节 |
| `documentation/flows.md` | fused 路径措辞 |
| `documentation/architecture.md` | fused 路径措辞 |
| `documentation/automation.md` | fused 路径措辞 |
| `readme.md` | fused 路径措辞 |
| `tasks/24_reconcile_fused_parent_handoff.md` | 本文件 |
| `tasks/README.md` | 登记本任务 |

## 不改动项（显式）

- `config/schemas/creator-derivation-candidate.schema.json` / `creator-signature.schema.json` 不动。
- `derive_signature` / `_resolve_creator_request` / `normalize_project_setup` 不动（已正确，问题在 reconcile 缺 fused 入参）。
- `onboarding_agent` 的 `review_profile: null` 不动（E 不做）。
- 不新增 review profile、不新增 catalog 包、不动 `review_profile_routes`。
- 不动规划链（Direction/Architecture/…）。
- Task 12 保持 DONE（历史记录）。

## 来源信息

- 来源 commit：本任务提交时的 commit。
- 触发实例：项目 `project:d80fe455-5d56-415f-8211-b5d26e476bca`（西幻）创建时，4 原型融合路径暴露 reconcile 名实不符与 handoff 脆弱性。

## 验收标准

- [x] `reconcile_project_wizard_archetypes` 接受 `fused_parent_version_id` + `fused_signature`，多原型路径用指定 parent 并自动折算 overrides diff。
- [x] 单原型路径（不传 fused）行为完全不变，`parent_source:"scored"`，既有 4 个 reconcile 测试零改动仍绿。
- [x] 多原型路径返回 `parent_source:"fused"`，parent 为 Agent 判定而非打分结果。
- [x] `fused_parent_version_id` 与 `fused_signature` 只给一个时被拒（`invalid_project_setup`）。
- [x] fused 路径产出的 `creator` 能被 `normalize_project_setup` + `create_project_with_creator` 端到端消费，binding 的 parent/derivation 正确。
- [x] AGENTS.md / SKILL / documentation / readme 统一描述 fused 路径，含双 parent 裁决规则与 creator payload 样例。
- [x] SKILL 新增 `agent.start` 入参契约小节，覆盖 `input_bindings` 字符串化与 `isolation_evidence.source`。
- [x] 根测试、MCP 测试、catalog/agent/hygiene/cutover 检查脚本、`compileall` 全部通过。

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python scripts/build_catalog_manifest.py --check
.venv/bin/python scripts/build_agent_quality_dataset.py --check
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/check_cutover_readiness.py --check
.venv/bin/python scripts/check_cutover_plan.py --check
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 完成条件

只有 reconcile fused 收口、既有路径回归、文档统一、agent.start 契约文档化均接通，并且全部验收项与
验证命令通过，才可将本任务标记为 `DONE`。

## 后续工作（不在本任务范围）

- **E（onboarding_agent 语义审查门禁）**：为 `creator_derivation_candidate` 新增轻量 review profile，
  检查每个原型的核心 `narrative_principle` 是否在融合签名中有对应承载。当前 `review_profile: null`，
  落库前只有确定性 schema 校验，无人/无 Profile 检查约束覆盖度。作为独立后续工作。
