# 07.7：Prompt Catalog 质量修正

## 状态

`IN PROGRESS`

2026-07-30 二次复核确认 R1、R3、R4、R5 的完成证据不足。本文件的原完成结论撤销，后续修正以 `08_reaudit_remediation.md` 为执行入口。

## 触发原因

2026-07-30 独立复核确认协议测试全部通过，但首次 Task 07 验收不能证明新增方法可用或质量合格：

- Contract 只校验 YAML 结构，没有校验实际输入 cardinality、权威状态、版本、Hash 或 pointer。
- 新增 Story Architecture、World 和 Writing 包使用了与现有工作流不一致的 `asset`/`capability`，标准检索返回空列表。
- 八个实验 Contract 都依赖当前没有生产者的 `fundamental_rules`。
- 正式 disposition、execution manifest 和 provenance 对同一来源给出互相矛盾的授权及迁移状态。
- `prose-quality-review` 没有实际合并 P03/P04 内容，却被记录为已增强。
- 边界测试只检查 metadata/tag；`realist-no-power` 用例没有验证排除力量体系。
- 八类规划 Profile 共用一个未区分资产职责的宽泛 Review Prompt。
- 首次验收记录 123 个测试，复核实际为根测试 40 个、MCP 测试 87 个，共 127 个。

本修正不激活任何 Wave-D 包，不恢复旧 Plugin Runtime，不提前完成延期的 70-case Agent 实验。

## 总体完成条件

必须按 R1～R6 顺序执行。每阶段完成后在本文件记录变更文件、测试和证据；任一阶段失败时停止，不能跳到后续阶段。

### R1：收口来源与执行状态

目标：同一来源在 disposition、execution manifest 和 provenance 中只有一个结论。

允许修改：

- `tasks/migration/catalog_disposition.csv`
- `tasks/07_prompt_catalog/execution_manifest.csv`
- `catalog/skills/expansions/*/provenance.yaml`
- `catalog/skills/review/prose-quality-review/provenance.yaml`
- `tests/test_catalog_manifest.py`
- `mcp/novelos/tests/test_production_catalog.py`

步骤：

1. 逐行复算 W01～W11、P01～P04 的固定提交 Prompt Hash。
2. 将明确授权且已形成目标包的 disposition 改为 `adapt-authorized`，写入精确目标路径；未授权行继续失败关闭。
3. execution manifest 已交付行改为 `done`，`evidence` 写为 `catalog:<target_name>@<target_package_hash>`；不能使用来源 Prompt Hash冒充 package Hash。
4. 从 `source_prompt_inventory.csv` 复制真实 lifecycle；不得把来源 `experiment` 写成 `active`。
5. P03/P04 当前没有实际进入 `prose-quality-review`。选择以下唯一方案，不得混用：
   - 保守方案：恢复该包 target-native provenance，P03/P04 保持未迁移；
   - 实验方案：创建独立 experiment Review 方法包并记录 P03/P04 provenance。
6. 更新测试，要求三份记录对同一来源的授权、目标和状态一致。

停止条件：找不到用户授权证据、目标 package Hash 无法重算、来源 lifecycle 与清单冲突。

### R2：统一 Catalog 路由分类

目标：每个方法能通过现有 Skill 使用的标准查询被发现。

允许修改：

- `catalog/skills/expansions/*/metadata.yaml`
- `mcp/novelos/src/novelos_mcp/catalog.py`
- `mcp/novelos/tests/test_catalog.py`
- `.agents/skills/novel-planning/SKILL.md`
- `.agents/skills/novel-writing/SKILL.md`
- `tests/test_prompt_catalog_boundaries.py`
- `mcp/novelos/tests/test_production_catalog.py`

目标映射：

| 方法 | `stage` | `asset` | `capability` |
|---|---|---|---|
| `story-causal-structure` | `plan` | `architecture` | `generate` |
| `story-expectation-design` | `plan` | `architecture` | `generate` |
| `story-pov-tone-contract` | `plan` | `architecture` | `generate` |
| 四个 `world-*` 包 | `plan` | `world_contract` | `generate` |
| `prose-revision` | `write` | `chapter` | `revise` |

步骤：

1. 按表修正 metadata，不新增同义 asset 名称。
2. 每个专项包增加简短、非空、去重的 `use_when` 与 `avoid_when`；`CatalogStore._summary()` 返回这两个轻量字段，但仍不得返回 Prompt 或 Contract 正文。
3. `novel-planning` 明确生产候选用 `generate`；专项方法与主包可同时进入候选快照。
4. `novel-writing` 明确完整起草查询 `write/chapter/generate`，局部修订查询 `write/chapter/revise`。
5. 新增真实路由测试，以下查询必须分别包含预期包：
   - `plan + architecture + generate + experiment`
   - `plan + world_contract + generate + experiment`
   - `write + chapter + revise + experiment`
6. 继续验证 experiment 包在默认 `lifecycle=active` 搜索中不可见。

停止条件：修正需要新增规划资产类型，或同一方法需要两个冲突 asset。

### R3：建立可执行 Contract 门禁

目标：Contract 从只读说明升级为能验证实际权威输入的失败关闭门禁。

允许修改：

- `catalog/skills/expansions/*/contract.yaml`
- `mcp/novelos/src/novelos_mcp/catalog.py`
- `mcp/novelos/src/novelos_mcp/service.py`
- `mcp/novelos/src/novelos_mcp/server.py`
- `config/agents.yaml`
- `mcp/novelos/tests/test_catalog.py`
- `mcp/novelos/tests/test_protocol.py`
- `mcp/novelos/tests/test_planning.py`
- `mcp/novelos/tests/test_service.py`

Contract 输入只使用当前系统可解析的权威类型：

- Story Architecture 方法：`direction: one`。
- World 方法：`architecture: one`、`strategy: one`。
- Prose Revision：`chapter_plan: one`、`chapter_draft: one`。
- 不得继续使用没有生产者的 `fundamental_rules`。

实现要求：

1. 增加只读工具 `skill_catalog.validate_contract_inputs`。
2. 输入绑定至少包含 `contract`、`subject_ref`、`version`、`subject_hash`、`status`。
3. MCP 从 SQLite 重新读取 `planning_assets` 或 `chapters`，验证类型、项目、版本、Hash 和状态，不信任调用方自报。
4. 规划输入只接受当前 `locked` 且非 stale/superseded；章节草稿只接受当前 `draft`；Hash 或版本漂移立即失败。
5. 根据 `one`、`zero_or_one`、`one_or_more`、`zero_or_more`、`exactly_two`、`three_or_more` 校验实际绑定数量。
6. 返回规范化输入 refs 和 `contract_snapshot_hash`，供 Agent run 输入证据绑定。
7. 当前包没有 RFC 6901 pointer 字段，因此删除父任务对 pointer 已实现的描述；只有将来 Schema 真正包含 pointer 时再实现 pointer 校验。
8. 增加缺失输入、重复输入、数量错误、错误类型、stale 状态、版本漂移、Hash 漂移和跨项目引用测试。

停止条件：实现只验证调用方 JSON 而不回查权威状态，或要求 Skill/Agent 直接访问 SQLite。

### R4：恢复 Prompt 方法深度与 Review 分层

目标：迁移包保留来源方法的关键判断维度，Review Profile 不再共用错误的上游假设。

允许修改：

- `catalog/skills/expansions/*/prompt.md`
- `catalog/skills/review/planning-quality-review/prompt.md`
- `catalog/skills/review/planning-*-review/**`
- `config/agents.yaml`
- `mcp/novelos/tests/test_agent_contracts.py`
- `mcp/novelos/tests/test_production_catalog.py`
- `tasks/07_prompt_catalog/method_coverage.csv`

步骤：

1. 建立 `method_coverage.csv`：`target_name,source_path,source_dimension,target_section,coverage_status,evidence`。
2. 对每个来源 Prompt 列出物质性方法维度；目标 Prompt 必须逐项标为 retained、merged 或 intentionally_removed，并给出理由。
3. `planning-quality-review` 只保留所有 Review 通用规则：不可变 subject、Hash 绑定、证据、severity 和 verdict，不再假设具体上游。
4. 为八种规划资产建立独立 Review rubric 包，路由改为 `[planning-quality-review, <asset-specific-review>]`。
5. Direction rubric 不得要求下游 Architecture/Strategy；每个其他 rubric 只检查该资产的精确上游、所有权边界和质量维度。
6. 所有 Review 包继续只返回候选 Receipt，不重写、批准或提交 subject。
7. 测试八个 Profile 得到通用包加唯一专项包，包顺序稳定、名称唯一、全部 active。

停止条件：无法说明来源维度为何删除，或 Review rubric 跨越资产所有权。

### R5：替换伪边界测试并建立质量证据

目标：测试真实路由、Contract 和方法边界；不再用 tag 存在性冒充质量验证。

允许修改：

- `tests/test_prompt_catalog_boundaries.py`
- `tasks/07_prompt_catalog/fixtures/**`
- `tasks/07_prompt_catalog/quality_results/**`
- `tasks/07_prompt_catalog/execution_manifest.csv` 的 evidence
- `tasks/07_prompt_catalog/04_worldbuilding_batch.md`
- `tasks/07_prompt_catalog/05_writing_batch.md`

确定性测试：

1. `realist-no-power` 的确定性部分必须证明候选摘要含明确 `avoid_when`；实际选择不包含成长/多体系方法由本阶段的盲评质量案例验证，不能只断言包存在。
2. `single-system-cost`、`dual-system-contact`、`social-control` 必须验证标准查询、选中方法和 Contract 输入。
3. 写作五个用例必须验证 prompt/contract 明确禁止改变 Canon、自我批准和 Review 重写，不只检查 review 包 metadata。
4. 添加一次真实 MCP 路径测试：搜索、快照校验、读取 Prompt/Contract、验证输入，再启动只读临时 Agent。

质量验证：

1. 建立最小 12-case 对比集：Architecture 4、World 4、Writing/Revision 4。
2. 每例比较“现有主包”与“主包 + 实验方法”；输入、模型、上下文和输出预算一致。
3. 使用隔离 审查智能体 盲评上游忠实度、因果闭合、边界遵守、具体性和可执行性。
4. 只有无新增 blocking、平均质量不下降且目标维度改善的包才可保留为 experiment 候选；证据不足继续 experiment，不得激活。
5. 本实验不改变 70-case Agent 实验的延期状态。

停止条件：没有真实模型执行却记录为文学质量通过，或 Reviewer 看见候选来源标签。

### R6：重新验收与状态收口

目标：只根据重算证据恢复 Task 状态。

允许修改：

- `tasks/07_prompt_catalog/06_acceptance.md`
- `tasks/07_prompt_catalog/07_quality_remediation.md`
- `tasks/07_prompt_catalog_expansion.md`
- `tasks/README.md`
- `tasks/migration/migration_summary.json`
- `scripts/build_migration_summary.py`
- `tests/test_migration_summary.py`
- `documentation/architecture.md`
- `documentation/flows.md`
- `documentation/tests.md`

必须运行：

```bash
PYTHONWARNINGS='error::ResourceWarning' .venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
.venv/bin/python scripts/build_prompt_migration_inventory.py --check
.venv/bin/python scripts/build_migration_summary.py --check
.venv/bin/python scripts/check_repository_hygiene.py --check
git diff --check
```

收口规则：

- 测试数量从实际命令输出记录，不沿用 123。
- `production_package_count` 只统计 `active`；experiment 数量单列，不能把 29 个目录全部称为生产包。
- manifest 的 done 行必须有目标 package Hash 证据。
- disposition、provenance、manifest 三方一致。
- 07 完成后重新执行 06；两者均 `DONE` 才能将父 Task 和 `tasks/README.md` 改回 `DONE`。

## 实施记录

- **R1 收口来源与执行状态**：`IN PROGRESS`，二次复核发现 disposition 仍冲突且 manifest Hash 全部过期。
- **R2 统一 Catalog 路由分类**：`DONE`
- **R3 建立可执行 Contract 门禁**：`IN PROGRESS`，缺少同项目、重复引用和 Contract 快照绑定。
- **R4 恢复 Prompt 方法深度与 Review 分层**：`IN PROGRESS`，八个专项 rubric 仍为占位内容。
- **R5 替换伪边界测试并建立质量证据**：`IN PROGRESS`，12-case 原始证据不存在。
- **R6 重新验收与状态收口**：`TODO`，等待 `08_reaudit_remediation.md` 完成。
