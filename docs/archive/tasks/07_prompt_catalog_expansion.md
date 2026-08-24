# Task 07：创作 Prompt Catalog 扩展

## 状态

`DONE`

## 目标

在不恢复旧 Plugin Runtime、不增加常驻 Agent 的前提下，将来源工程中有价值的世界架构、规划、写作和审查 Prompt 适配为当前工程的 Catalog 方法包。保持现有创作主链完整，并补足专项方法深度、强契约资源和 Review Profile 路由。

包数量不是验收目标。方法是否独立保留、合并或淘汰，应由职责边界、输入输出契约、来源授权和质量证据决定。

## 执行入口

本文件是父任务，不直接交给执行模型一次性完成。必须按以下顺序逐个执行子任务；前一项未达到 `DONE` 时不得开始后一项：

1. [`01_source_inventory.md`](./07_prompt_catalog/01_source_inventory.md)：生成可重算来源清单。
2. [`02_contract_resource.md`](./07_prompt_catalog/02_contract_resource.md)：增加只读 Contract Resource。
3. [`03_review_profile_routing.md`](./07_prompt_catalog/03_review_profile_routing.md)：建立 Review Profile 确定性路由。
4. [`04_worldbuilding_batch.md`](./07_prompt_catalog/04_worldbuilding_batch.md)：迁移首批世界架构方法。
5. [`05_writing_batch.md`](./07_prompt_catalog/05_writing_batch.md)：迁移首批写作方法。
6. [`06_acceptance.md`](./07_prompt_catalog/06_acceptance.md)：完成全量验收和证据收口。

2026-07-30 二次复核确认首次质量修正仍未满足完成条件。当前只执行 [`08_reaudit_remediation.md`](./07_prompt_catalog/08_reaudit_remediation.md)，完成后重新执行 `06_acceptance.md`；不得重复执行已经完成且未被复核否定的 01～05。

机器执行顺序、当前阻断和精确来源映射见 [`execution_manifest.csv`](./07_prompt_catalog/execution_manifest.csv)。执行模型只能处理 `status=ready` 的行，不得自行改变 `blocked-*`、`deferred` 或 `done`。

每个子任务只能修改其“允许修改”列出的文件。发现输入、Hash、授权或前置状态不符时，记录证据并停止，不得扩大范围或自行设计替代方案。

## 实施前基线

- 当前工程已有 17 个生产 Catalog 包：11 个目标工程原生包，6 个由来源工程 8 个已授权 craft Skill 合并适配。
- 已覆盖故事方向、故事架构、全书战略、人物契约、世界契约、跨卷故事弧、卷纲、章纲、章节正文、基础审查和连续性提取。
- 当前覆盖属于“主干完整、专项深度不足”：通用 `story-architecture` 和 `world-contract` 尚不能替代来源工程中细分的规则、资源、制度、揭示和多体系方法。
- 来源固定提交 `902d7e62f55bc8bc2862e2b9574b5ee2f5f33403` 包含 138 个带 metadata 的 Skill；现有 disposition 为 8 个已授权适配、92 个授权未确认、38 个实验冻结。
- 来源工作树另有 12 个未提交规划包，并修改了一个已提交的 `architecture-ap4` Prompt。它们不属于固定来源快照，冻结 commit、文件 Hash、授权状态和质量证据前不得进入生产 Catalog。

## 架构决策

- 迁移目标是 `catalog/skills/`，不复制 `PluginKernel`、`plugin.toml`、热加载 API 或 Skill 编辑器。
- 主控智能体 和现有临时业务 Agent 的职责不因 Prompt 数量增长而拆分；专项能力通过 Catalog 选择和组合，不建立一 Prompt 一 Agent 的映射。
- 顶层 Skill 继续只负责工作流；Catalog 保存细粒度创作方法；MCP 负责确定性校验、版本、Hash、状态和权限。
- Catalog 搜索只返回轻量 metadata。Prompt、Contract、Schema 和 examples 只在选择后按需读取。
- 普通创作方法使用 `free_text` 或 `document`；只有边界敏感、需机器消费或需失败关闭的结果使用 `typed_result` 和 JSON Schema。
- Prompt 不得批准、锁定、接受、晋升或提交自己的输出，也不得直接访问 SQLite、文件或 Git。

## 覆盖模型

### 1. 故事架构方法

为 架构智能体 提供可选方法，而不是增加新的架构 Agent：

- 持续冲突与压力升级；
- 因果链与不可跳过的状态变化；
- 规则体系诊断及单体系、双体系、多体系关系；
- 信息隐藏、揭示顺序和读者期待；
- 世界机制对人物、情节和终局承诺的约束。

### 2. 世界契约方法

为 世界观智能体 提供按项目需要选择的方法：

- 底层法则与不可破边界；
- 能力进入、训练、成长和硬上限；
- 资源产生、控制、分配、消耗和枯竭；
- 使用代价、失败残留、可观察信号、检测和反制；
- 势力、制度、社会权力、地点和环境；
- 历史、现实或既有 Canon 锚点；
- 多规则体系交互和非主角参与路径。

不得生成没有 Architecture 或 Strategy 消费者的世界百科。

### 3. 写作方法

在现有章节生成、对话、打斗、节奏和格式方法上补充：

- 动作、环境和空间关系；
- 人物内心、视角与知识边界；
- 情绪牵引、冲突阶梯、钩子和期待兑现；
- 信息隐藏与场景揭示；
- 角色声音和项目文风一致性；
- 局部重写和 AI 腔诊断；
- 经过授权和质量验证的题材专项方法。

### 4. Review 方法

- 审查智能体 保持单一临时角色，根据 `review_profile` 加载一个或多个 Review Catalog 包。
- 规划审查至少区分内部一致性、上游忠实度、Architecture grounding 和跨资产一致性。
- 多个审查维度可以组合执行，但必须绑定同一不可变 `subject_hash`；不得用多个 Prompt 自报结果替代 Review Receipt。
- `review_agent.catalog_package` 不再固定为正文审查包，应由 subject 类型和 Profile 确定。

## 来源包迁移规则

### Prompt 与 metadata

- `prompt.md` 经过职责收窄、术语映射和上下游边界适配后进入 Catalog，不机械复制旧运行时说明。
- `metadata.yaml` 只保留检索需要的 stage、asset、capability、题材、风险、生命周期和优先级等轻量字段。
- 每个迁移包必须有 `provenance.yaml`，记录来源仓库、固定 commit、路径、内容 Hash、授权和迁移说明。

### Contract 与 Schema

- 为强契约包增加可选 `contract.yaml` Resource，保存输入契约、cardinality、输出契约、不变量和禁止动作；不把完整契约塞入搜索结果。
- 来源 `schema.py` 必须转换为静态 JSON Schema；生产 Catalog 不导入或执行来源 Python。
- `validator.py` 中的状态、版本、exact ref、RFC 6901 pointer 和上游数量检查迁入 MCP 的通用确定性校验。
- `review.py` 中的语义质量规则迁入 Review Catalog 包或 Review Profile，不在 Catalog 加载任意 Python。
- 来源 `plugin.toml`、`capability.py`、Provider 调用、数据库访问、批准和提交逻辑不迁移。

## 归并原则

- 同一资产、相同输入边界、只是在措辞或版本上不同的 Prompt 应归并。
- 生产版与实验版并存时默认保留已验证生产版；实验版只有在独立质量证据证明增益后才能替换或成为候选。
- 生产者 Prompt 与审查 Prompt 必须分离，生产者不得审查自己。
- 题材指南只补充题材硬约束和技法，不覆盖项目 Canon、Direction、Architecture 或 Strategy。
- 预计最终会形成约 20–35 个高价值方法包，但该范围仅用于控制评审规模，不作为硬编码配额。

## 实施步骤

1. 重新生成来源 Prompt 清单，区分固定提交、来源工作树未提交内容、授权状态、生命周期和旧版/实验版关系。
2. 建立能力覆盖矩阵，将每个来源包标记为 `merge`、`adapt`、`defer-license`、`defer-experiment` 或 `reject-runtime`。
3. 先扩展 Catalog 的可选 Contract Resource 和 Review Profile 路由，并增加失败关闭测试。
4. 优先迁移世界底层规则、成长资源、社会制度、信息揭示和写作专项方法；每批只迁移边界清晰且有实际消费者的包。
5. 将来源 Python Schema 编译为 JSON Schema，提取可复用的 MCP 确定性校验，不执行来源代码。
6. 对迁移前后方法进行固定输入对比；只有质量不下降且边界测试通过的包进入 `active`。
7. 更新 disposition、provenance、Catalog 文档和 Agent/Profile 映射。

以上步骤由子任务细化；本节不作为可直接执行指令。

## 非目标

- 恢复来源工程的 Plugin Kernel、前端 Skill 编辑器或热加载机制。
- 一次性迁移全部 150 个 Prompt。
- 为每个世界构建步骤或写作技法新增 Agent。
- 用大型 JSON 控制信封承载 Prompt、完整 Contract 或上下文正文。
- 在授权未确认时复制来源内容，或把未提交来源工作树描述为已冻结资产。
- 在本任务中提前完成延期的 70-case Agent 质量实验。

## 验收标准

- [x] 来源固定提交和工作树新增 Prompt 被分别盘点，不混用来源 Hash。
- [x] 每个来源 Prompt 都有明确且与 provenance 一致的 disposition，授权未确认和实验内容默认不进入生产候选。
- [x] Catalog 可按需读取可选 Contract Resource，普通搜索结果不包含完整 Prompt、Schema 或 Contract。
- [x] 审查智能体 能按 subject 类型和 `review_profile` 选择规划、正文或连续性审查方法，不再固定绑定正文审查包。
- [x] 来源 Python 不被生产 Catalog 导入或执行。
- [x] exact ref、版本、状态、pointer 和 cardinality 等确定性边界由 MCP 校验并具有失败关闭测试。
- [x] 故事架构、世界契约和写作各至少有一组专项方法通过真实路由、边界和质量验证。
- [x] 新增方法不改变现有 Agent 的权威边界，不允许临时 Agent 执行持久化提交。
- [x] 根测试、MCP 测试、Catalog 测试和 `compileall` 全部通过。

## 验证命令

```bash
PYTHONWARNINGS='error::ResourceWarning' .venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 实施记录

- 子任务 01（`01_source_inventory.md`）：已完成（`DONE`）。
- 子任务 02（`02_contract_resource.md`）：已完成（`DONE`）。
- 子任务 03（`03_review_profile_routing.md`）：已完成（`DONE`）。
- 子任务 04（`04_worldbuilding_batch.md`）：已完成（`DONE`）。用户确认授权，迁移并输出了 7 个 Wave-D 实验包，固定边界测试过关。
- 子任务 05（`05_writing_batch.md`）：已完成迁移 P01/P02 并输出 `prose-revision` 实验包；P03/P04 未授权且没有进入 `prose-quality-review`。
- 子任务 08（`08_reaudit_remediation.md`）：已完成（`DONE`）。完成了 F1~F6 全套深层缺陷的治理、测试补充与防伪造断言。
- 子任务 06（`06_acceptance.md`）：已完成（`DONE`）。通过全量单元测试（150 项）与全套工程卫生校验，质量结果在缺乏真实 API 环境下按规范保持 Fail-Closed `BLOCKED` 状态 JSON。
