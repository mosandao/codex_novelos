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
6. 需要正式版本时，只创建目标资产对应的临时 Agent，提供精确上游 refs、选中 Catalog refs、用户约束和必要 Canon。Direction 必须额外接收项目当前的精确 `creator_signature_ref`，候选 metadata 必须包含同一 ref 和契约完整的 `book_soul`；不得根据人口属性推导思想或模仿具体作者。Chapter Plan 必须给出可追溯到锁定 Direction 的 `soul_pressure` 与 `moral_residue`，纯过渡场景允许明确降低思想前景强度。创建 Codex Task sub-agent 时，必须把其返回的 agentId 作为 `isolation_evidence`（形如 `{"source":"codex_task","agent_id":"..."}`）传入 `agent.start`；缺凭据的 run 无法通过 `planning.lock`。
7. 正式资产 Agent 必须把 `planning_candidate` 作为非空文本返回；Main Agent 调用 `planning.create_candidate_from_run` 直接登记不可变输出，不读取后重传正文。延期的 Agent 质量实验可使用专用结构化规划输出，但该输出不能登记为权威候选。再使用 `$novel-review` 取得精确 Profile 的独立审查，最后由 Main Agent 调用 `planning.lock`。

若下游 Agent 发现上游问题，只返回 change proposal；不要把上游修改混入本层候选。Character 与 World 可并行，但进入 Story Arc 前必须完成交叉一致性审查。

## 操作前置检查

以下规则来自实际规划资产生成中遇到的工具调用失败，在构造数据前必须确认。

### Agent input_bindings 构造规则

调用 `agent.start` 前，从 `config/agents.yaml` 读取目标角色的 `minimum_inputs`，确认：

- `input_bindings` 的 key 集合必须**精确等于** `minimum_inputs`——不能多、不能少、不能改字段名。
- 每个 value 必须是**非空字符串**或**非空字符串数组**；不能是嵌套 dict、`list[dict]` 或 number。
- 复杂约束（项目 setup、catalog 选择、探索方向等）须序列化为单个字符串（如用 ` | ` 分隔的键值摘要）或字符串数组，不能直接传 JSON 对象。

### Agent output 格式规则

调用 `agent.finish` 时：

- `output_type=planning_candidate` 的 `output` 直接传**正文 markdown 文本字符串**，不是 `resource_ref` 对象或 `{content_hash, resource_ref}` 结构。
- `planning_candidate` schema 接受非空字符串（正式候选）或实验结构化对象（延期实验专用），不接受 resource ref 对象。
- 系统在 finish 事务内自动把 output 字符串存为 resource，不需要先手动创建 resource 再传 ref。

### Catalog 搜索与校验规则

调用 `skill_catalog.search` 和 `skill_catalog.validate` 时：

- `asset` 参数值是**规划资产类型枚举**（如 `architecture`、`direction`、`strategy`），不是 Catalog skill 的展示名（如 `story-architecture`）。常见错误：用 skill name 做搜索参数，导致返回空 candidates。本文件「资产路由」表的 `asset_type` 列即为正确的 `asset` 值。
- `snapshot_hash` 锚定的是**本次搜索返回的 candidates 子集**，不同搜索参数（宽窄不同）会返回不同 candidates 子集 → 不同 hash。因此搜索后必须**立即**用同一返回值里的 hash 调 `validate`，中间不能插入新的搜索或任何会改变候选集的操作；否则会报 `stale_catalog: Catalog 候选快照已变化`。

### planning.create_candidate_from_run 的 upstream_refs 格式

调用 `planning.create_candidate_from_run` 登记候选时：

- `upstream_refs` 必须是 `list[dict]`，每个 dict 精确包含 `{"asset_id": str, "version": int}` 两个 key——不能多、不能少、不能传字符串数组或 novelos:// URI。
- `asset_id` 是锁定资产的 ID（如 `planning:0eab6bf8-...`），`version` 是该资产锁定时的版本号（整数，从 `planning.list` 或 `planning.lock` 返回值的 `version` 字段读取）。
- MCP 会校验每个上游资产的 `status == "locked"` 且 `version` 匹配；版本号错误会报 `stale_upstream`。

### book_soul 构造规则

构造 Direction 候选的 `metadata.book_soul` 前，参考本文件末尾「book_soul 字段速查表」。常见错误：

- `schema_version: 1` 是必填字段，遗漏会导致整条 book_soul 被拒。
- `central_contradiction`、`narrative_mercy`、`narrative_cruelty` 是**字符串**（≤1000 字符），不是数组。
- 其余 6 个字段是**字符串数组**（1-24 项，每项 ≤500 字符，uniqueItems）。

## book_soul 字段速查表

派生自 `config/schemas/book-soul.schema.json`：

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
