# Task 12：原型 LLM 融合 Agent

## 状态

`DONE`

## 背景

Task 09 完成了 18 个系统叙事原型与仅派生向导，其中 `project.wizard.reconcile_archetypes` 用确定性打分算法在用户选中子集内选 parent，并把其余原型的 `reader_promise` 追加到 `recurring_attention` 作为辅风格融合。该确定性融合是纯模板拼接：只有 parent 原型的 7 个签名字段被全量继承，其余原型仅贡献 1 条 `recurring_attention` 脚注，跨原型的 `sympathies / distrusts / narrative_principles / forbidden_conveniences / expression_preferences / negative_constraints` 约束被丢弃。

当用户选择多个原型、且这些原型的约束需要实质性合流时（例如「体系史诗」为骨架、「经营复兴」承载起点、「暗影博弈」融入基调），确定性融合产出的签名过于单薄，不能体现用户「LLM 判定 parent + 深度融合」的意图。

## 目标

把「LLM 判定 parent archetype + 深度融合多 archetype 签名」从一次性人工操作固化为项目能力：新增一个受契约约束的临时 `onboarding_agent` 角色，LLM 推理在 Codex Agent run 内发生，MCP 负责确定性收口（校验 + 落库），全程走 Trace 治理链。

## 对 Task 09 非目标的修订

Task 09 非目标第 1 条「新增作者 Agent、叙事原型 Agent 或任何常驻生成角色」与第 3 条「声称确定性草稿是模型生成」按本任务修订如下：

- 允许新增一个 **temporary（非常驻）** 的 `onboarding_agent`，它在项目创建 Trace 内做多原型 LLM 融合推理，run 结束后销毁，不是常驻生成角色。
- `onboarding_agent` 的 LLM 输出明确标注为模型生成，并通过 `creator-derivation-candidate` schema 与 `creator-signature` schema 双重校验；落库前仍经 `project.wizard.reconcile_archetypes` 确定性收口，不跳过 Trace 门禁。
- Task 09 的确定性 reconcile 流程保持不变，继续作为单原型路径与多原型路径的合规校验收口。Task 09 本身保持 `DONE`，作为历史记录。

## 核心决策

### 1. 角色定位

`onboarding_agent` 类比 `writer_agent`（不拥有规划资产、review_profile 为 null、must_destroy 为 true）：

- `kind: onboarding`（加载器不校验 kind 枚举，新值可安全使用）
- `owned_asset_type: null`（Creator Profile 不是 planning asset，不进入 `service/_constants.py` 的硬编码映射）
- `review_profile: null`（签名融合产物的合规性由 `validate_signature` + `derive_signature` 确定性校验保证，不需要独立 Review Receipt）
- 输出类型 `creator_derivation_candidate`，注册独立 schema 做结构校验
- `catalog_package: null`（向导阶段不消费 Catalog skill 包）

### 2. 边界

不新增 MCP 工具、不新增 DB 表、不新增规划资产类型、不改 `reconcile_archetypes` 实现、不改 planning 链路的 `_constants.py`。Creator Profile 的落库仍走现有的 `project.wizard.submit` / `creator_profile.revise` / `project.creator.rebind` 三个确定性工具。MCP 内不调 LLM。

### 3. 编排路径

| `selected_archetypes` 数量 | 路径 |
|---|---|
| 1 | 直接 `reconcile_archetypes`（确定性）→ `project.wizard.submit` |
| ≥2 | Trace 内创建 `onboarding_agent` run → LLM 判定 parent + 深度融合 → `creator_derivation_candidate` → `reconcile_archetypes` 确定性收口 → `project.wizard.submit` |

## 改动文件

| 文件 | 变更 |
|---|---|
| `config/schemas/creator-derivation-candidate.schema.json` | 新建输出 schema |
| `config/agents.yaml` | 注册 `creator_derivation_candidate` output_schema；新增 `onboarding_agent` 角色 |
| `.agents/skills/novel-project/SKILL.md` | 新增「多原型 LLM 融合」工作流 |
| `AGENTS.md` | 向导段落新增多原型 LLM 融合路径；角色清单计数 12→13；执行 Agent 表加引导融合智能体 |
| `tasks/12_archetype_llm_merge_agent.md` | 本文件 |
| `tasks/09_narrative_archetype_derivation.md` | 顶部加指针指向 Task 12 的非目标修订 |
| `mcp/novelos/tests/test_agent_contracts.py` | 新增 onboarding_agent 加载与输出 schema 校验测试 |

## 来源信息

- 来源 commit：`5b4b6ef` feat: 新增临时 onboarding_agent 固化多原型 LLM 深度融合
- 触发实例：项目 `project:ea0831c1-cb35-4404-8df4-b69e2a136967`（西幻）创建时，4 原型经人工 LLM 融合为 revision 2 签名（22 条约束），证明确定性融合不足以承载多原型场景。

## 验收标准

- [x] `onboarding_agent` 角色在 `AgentContractStore` 加载成功，13 个角色全部就绪。
- [x] `onboarding_agent` 的 `lifecycle: temporary`、`must_destroy: true`、`review_profile: null`、`owned_asset_type: null`，能通过 `start_agent_run` 的生命周期门控。
- [x] `creator_derivation_candidate` schema 注册到 `runtime.output_schemas`，合法 payload 通过校验，缺字段 payload 被拒绝。
- [x] `creator_derivation_candidate.signature` 能通过 `CreativeContractStore.validate_signature`，保证确定性收口可用。
- [x] `.agents/skills/novel-project/SKILL.md` 与 `AGENTS.md` 一致描述单/多原型两条路径。
- [x] Task 09 顶部指针指向本任务的非目标修订。
- [x] 根测试、MCP 测试、`compileall` 全部通过。

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 完成条件

只有新角色加载、输出 schema 校验、确定性收口链路、文档一致性均接通，并且全部验收项与验证命令通过，才可将本任务从 `IN PROGRESS` 标记为 `DONE`。
