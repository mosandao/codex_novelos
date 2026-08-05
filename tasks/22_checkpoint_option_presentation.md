# Task 22：Strategy/Character 检查点"选项呈现"原子能力

## 状态

`DONE`（MCP 原子能力 + prompt + 测试已落地；Codex 侧编排与生成验证待实际生成流程执行）

## 背景

世界观设计重构讨论稿（`documentation/worldbuilding-redesign.md`）第 22.6 条建议在 strategy/character 的 candidate→lock 流程之间，插入"选项呈现"步骤——把关键决策翻译成爽点选择题，用户选完反向固化进 candidate 再 lock。

### 证据基础（随 Task 21 一起成立）

Task 21 已确认"用户介入需求真实"（训练数据 + 西幻实证）。检查点选项呈现是同一套介入体验的中段，证据同源，不需单独再证。

### 决策（已确认：选项 A）

- 选项 B（MCP 内建交互状态机）否决——MCP 是原子工具入口，不应变成有状态交互引擎，且 MCP 无法主动向用户提问。
- 选项 C（纯 prompt，无固化机制）否决——用户选完后无法可靠写回 candidate。
- **选项 A 确定**：MCP 只提供两个原子能力（提取选项 + 创建修订 candidate），交互编排（何时提取、如何呈现给用户、何时固化）由 Codex 侧主控完成。

### 与现有 candidate 机制的关系（关键约束）

经查 `planning.py`，candidate 一旦创建内容不可变（`content_resource_id` 固定），生命周期是 candidate→locked 或 candidate→superseded。**没有"原地更新 candidate 内容"的机制**。

因此"反向固化"的形态只能是：**用户选完后，主控创建一个新的修订 candidate**（内容已融合用户选择），旧 candidate 由新 candidate 顶替时自动 superseded（现有机制，`planning.py:500-506`）。这完全契合现有流程，不需要改 candidate 生命周期。

## 优化

### 优化 1：新增 MCP 工具 `planning.extract_decision_points`

```
planning.extract_decision_points(asset_id) -> {
  decision_points: [
    {
      key: "protagonist_power_pacing",        # 决策键
      question: "主角金手指的觉醒节奏",          # 给用户的问题
      options: [                                # 3~4 个选项
        {label: "A. 快爽流", detail: "第3章觉醒，前20章纯打脸", tradeoff: "中段需新爽点续"},
        {label: "B. 无敌流", detail: "第1章满级碾压", tradeoff: "易腻"},
        {label: "C. 成长流", detail: "缓慢觉醒", tradeoff: "开局不抓人"}
      ],
      source_excerpt: "..."                     # candidate 里对应片段（供追溯）
    },
    ...
  ]
}
```

**重要约束**：此工具**不调用 LLM**。它只做机械提取——从 candidate 的 `metadata_json` 里读一个可选的 `decision_points` 字段（由生成 Agent 在产出 candidate 时写入），原样返回。决策点的内容设计是 strategy/character Agent 的 prompt 职责（见优化 3），不是这个工具的职责。工具只是"读出并格式化"。

这样设计的理由：MCP 不内建 LLM 调用（AGENTS.md 原则），提取逻辑放 prompt 层（Agent 写），工具层只搬运。

### 优化 2：新增 MCP 工具 `planning.create_revision_candidate`

```
planning.create_revision_candidate(
  project_id, asset_type, scope_ref,
  content, upstream_refs,
  producer_role, producer_run_id,
  supersedes_candidate_id,   # 新参数：声明这个修订版顶替哪个旧 candidate
  metadata
) -> 修订 candidate（旧 candidate 自动 superseded）
```

这其实是现有 `create_planning_candidate` 的一个包装：创建新 candidate + 显式把 `supersedes_candidate_id` 指向旧 candidate 并标 superseded。比让主控手工"创建新的再废弃旧的"更显式、留痕更清晰。

**注意**：是否需要独立工具，还是给 `create_planning_candidate` 加一个可选参数——待实现时定，两者都符合选项 A。

### 优化 3：strategy/character prompt 新增"决策点产出"职责

`catalog/skills/planning/story-strategy/prompt.md` 和 `character-contract/prompt.md` 各新增一段：

"产出 candidate 时，在 metadata 的 `decision_points` 字段附上 2~4 个关键决策点的爽点选择题（每个含问题、3~4 选项、每选项的代价/爽点说明、对应 candidate 片段）。这些决策点是'错了会崩盘'的命门（如主角觉醒节奏、核心性格底色），不是所有细节。用户在 lock 前通过这些选择题介入，选择会被融合进修订 candidate。"

决策点的设计原则呼应讨论稿第十五章：把"抽象契约的 review"翻译成"具体爽点的多选一"。

### 优化 4：AGENTS.md 补充编排指引

在 AGENTS.md 的主控智能体职责段，补充检查点编排流程（何时调 extract、何时呈现、何时调 create_revision）。这是给 Codex 侧主控的指引，不是 MCP 代码。

## 改动文件

| 文件 | 变更 |
|---|---|
| `mcp/novelos/src/novelos_mcp/service/planning.py` | 新增 `extract_decision_points`（机械读取 metadata.decision_points）；新增 `create_revision_candidate` 或给 `create_planning_candidate` 加 `supersedes_candidate_id` 参数 |
| MCP 工具注册处 | 注册新工具 |
| `catalog/skills/planning/story-strategy/prompt.md` | 新增决策点产出职责 |
| `catalog/skills/planning/character-contract/prompt.md` | 同上 |
| `AGENTS.md` | 主控职责段补充检查点编排指引 |
| `tasks/migration/catalog_disposition.csv` | 无需改（现有 skill 改 prompt） |

**不碰 schema、不碰 candidate 生命周期、不碰依赖图。** 新工具只读 metadata 和创建新 candidate（都是现有能力的组合）。

## 来源信息

- 来源文档：`documentation/worldbuilding-redesign.md` 第二十二条 22.6、第十六章"检查点翻译"
- 证据基础：随 Task 21 同源（用户介入需求真实）
- 决策记录：选项 A（MCP 原子能力 + Codex 编排）
- 机制约束发现：candidate 内容不可变，反向固化 = 创建修订 candidate 顶替旧 candidate

## 验收标准

- [ ] `planning.extract_decision_points(asset_id)` 工具可用，机械读取 metadata.decision_points 并返回结构化选项（不调 LLM）。
- [ ] `planning.create_revision_candidate` 可用（或 create_planning_candidate 支持 supersedes 参数），创建修订 candidate 时旧 candidate 自动 superseded。
- [ ] `story-strategy/prompt.md` 和 `character-contract/prompt.md` 各新增决策点产出职责，要求 metadata 附 decision_points。
- [ ] 新增测试：extract 工具读取正确、无 decision_points 时返回空、create_revision 正确顶替旧 candidate。
- [ ] 现有测试全部通过（不破坏 candidate 生命周期、lock、supersede 机制）。
- [ ] AGENTS.md 补充检查点编排指引。
- [ ] `compileall` 通过。

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python scripts/build_catalog_manifest.py --check
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 完成条件

四个优化全部落地、测试通过且新增测试覆盖 extract/revision 边界、验收项全部勾选，才可标记为 `DONE`。

**注意**：本 Task 落地的只是 MCP 原子能力 + prompt 职责。完整的"检查点体验"还需 Codex 侧主控按 AGENTS.md 指引编排（提取→呈现→固化），这部分不在 MCP 可测范围，应在实际生成流程中验证。

## 风险与回退

- **机制风险低**：不碰 schema、不碰 candidate 生命周期。新工具是现有能力（读 metadata + 创建 candidate）的组合。
- **质量风险**：决策点的好坏取决于 strategy/character Agent 的 prompt，不在工具层。若 Agent 产出的 decision_points 泛泛，工具无能为力——需在实际生成中观察并迭代 prompt。
- **回退方式**：移除两个新工具 + revert prompt 改动。旧 candidate 机制不受影响。
- **与 Task 21 协调**：种子层（入口）和检查点（中段）是同一套介入体验。Task 22 的 AGENTS.md 编排指引应参考 Task 21 种子层的介入形态，保持一致。
