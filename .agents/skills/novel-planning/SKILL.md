---
name: novel-planning
description: 识别小说规划层级并准备对应权威资产的最小输入。探索或生成故事方向、故事架构、全书战略、人物或世界契约、跨卷故事弧、卷纲、章纲，以及修订已失效规划资产时使用。
---

# 小说规划

识别资产阶段、选择方法和准备输入；不要把整条规划链压成一个 Prompt，也不要替代资产所有者 Agent。

## 资产路由

| `asset_type` | 唯一生产者 | 必需上游类型 | Review Profile |
|---|---|---|---|
| `direction` | Direction Agent | 无 | `planning-direction` |
| `architecture` | Architecture Agent | `direction` | `planning-architecture` |
| `strategy` | Strategy Agent | `direction`、`architecture` | `planning-strategy` |
| `character_contract` | Character Agent | `architecture`、`strategy` | `planning-character-contract` |
| `world_contract` | World Agent | `architecture`、`strategy` | `planning-world-contract` |
| `story_arc` | Story Arc Agent | `strategy`、`character_contract`、`world_contract` | `planning-story-arc` |
| `volume_outline` | Volume Planner | `story_arc` | `planning-volume-outline` |
| `chapter_plan` | Chapter Planner | `volume_outline` | `planning-chapter-plan` |

## 工作流

1. 从用户目标判断唯一目标 `asset_type` 和 `scope_ref`。
2. 用 `planning.list` 读取当前资产；复用所有有效 `locked` 上游，拒绝使用 `stale` 或 `superseded` 资产。
3. 用 `skill_catalog.search` 按 `stage=plan`、`asset`、`capability=generate` 和题材硬条件获取轻量候选，再由 Codex 做语义选择。
4. 用 `skill_catalog.validate` 校验选择属于同一候选快照；只对选中项调用 `skill_catalog.get` 读取 Prompt、Schema 或 examples。
5. 探索性讨论直接返回方案，不创建 Agent、不持久化。
6. 需要正式版本时，只创建目标资产对应的临时 Agent，提供精确上游 refs、选中 Catalog refs、用户约束和必要 Canon。创建 Codex Task sub-agent 时，必须把其返回的 agentId 作为 `isolation_evidence`（形如 `{"source":"codex_task","agent_id":"..."}`）传入 `agent.start`；缺凭据的 run 无法通过 `planning.lock`。
7. Agent 返回候选后，由 Main Agent 调用 `planning.create_candidate`；再使用 `$novel-review` 取得精确 Profile 的独立审查，最后由 Main Agent 调用 `planning.lock`。

若下游 Agent 发现上游问题，只返回 change proposal；不要把上游修改混入本层候选。Character 与 World 可并行，但进入 Story Arc 前必须完成交叉一致性审查。
