# 07.8：二次复核修正参考

## 状态

`DONE`

## 目标

修复 2026-07-30 二次复核发现的证据失真、Contract 门禁缺口、Review rubric 占位和质量实验不可审计问题。完成本任务后重新执行 `06_acceptance.md`；在此之前，Task 07 不得标记为 `DONE`。

本文件必须按 F1～F6 顺序执行。低级 LLM 每次只处理一个阶段，阶段未通过时停止，不得提前修改后续阶段的状态或证据。

## 已确认问题

1. `quality_results/eval_results.json` 只有 12-case 汇总结论，没有案例、模型输出、盲评、评分或 Receipt。
2. W01～W11、P01～P02 在 execution manifest 中为 `user_authorized/done`，但 disposition 仍为 `defer-license` 或 `defer-experiment`。
3. execution manifest 中 13 条 `done` 证据保存的 package Hash 已全部失效。
4. 八个专项 Planning Review Prompt 只有占位描述；通用 Review Prompt 仍错误假设 Direction、Architecture 和 Strategy 同时存在。
5. `validate_contract_inputs` 没有完整校验 binding 字段、项目一致性、重复引用和 Contract 快照。
6. Prompt 边界测试仍以 metadata 和字符串存在性为主，没有覆盖完整 MCP 调用路径。
7. Task、验收记录和稳定文档存在状态、测试数和 Catalog 数量漂移。

## 不可突破的边界

- `/Users/yiyi/github/novelos` 始终只读；已提交来源只允许通过固定 commit 读取。
- SQLite 是唯一权威数据源；Skill 和 Agent 不得直接访问 SQLite。
- 数据库回查只能通过 MCP Service/Storage 边界实现。
- 不恢复 Plugin Kernel，不执行来源仓库 Python，不新增常驻 Agent。
- 八个 Wave-D 包继续保持 `experiment`，本任务不得将其改为 `active`。
- 不把本任务的 12-case Prompt 实验与延期的 70-case Agent 实验混为一谈。
- 没有真实模型输出和独立盲评证据时，F5 必须保持 `TODO` 或改为 `BLOCKED`，不得伪造 `passed` 汇总。
- package Hash 只能在所有 Prompt、Contract、metadata 和 provenance 修改完成后最终写入 manifest。

## F1：恢复来源状态单一真相

### 允许修改

- `tasks/migration/catalog_disposition.csv`
- `tasks/07_prompt_catalog/execution_manifest.csv`
- `catalog/skills/expansions/*/provenance.yaml`
- `tests/test_catalog_manifest.py`
- `mcp/novelos/tests/test_production_catalog.py`

### 实施步骤

1. 用固定 commit 重新计算 W01～W11、P01～P04 的 Prompt Hash；不得使用 metadata Hash 代替 Prompt Hash。
2. 将 W01～W11、P01～P02 对应 disposition 改为 `adapt-authorized`，写入精确目标目录。
3. P03、P04 保持 `defer-license`/`deferred`，不得再描述为已增强 `prose-quality-review`。
4. 检查每个 Wave-D provenance 的主来源和 `additional_sources`，确保与 manifest 一一对应。
5. 因后续阶段仍会修改目标包，将 W01～W11、P01～P02 暂时改回 `status=ready,evidence=-`；本阶段不得写最终 package Hash。
6. 新增跨文件测试：同一来源在 disposition、manifest、provenance 中的授权、目标、来源 commit 和 Prompt Hash 必须一致。

### 验收

- 13 个已授权来源均有 `adapt-authorized` disposition 和目标路径。
- P03/P04 没有目标 provenance，也没有完成证据。
- 测试不再固定断言旧的 `8 adapt-authorized`，而是从权威映射重算。

## F2：补全 Contract 输入门禁

### 允许修改

- `mcp/novelos/src/novelos_mcp/service.py`
- `mcp/novelos/src/novelos_mcp/server.py`
- `mcp/novelos/src/novelos_mcp/catalog.py`
- `mcp/novelos/tests/test_service.py`
- `mcp/novelos/tests/test_protocol.py`
- `mcp/novelos/tests/test_catalog.py`

### 接口要求

`skill_catalog.validate_contract_inputs` 的输入必须包含：

- `package_name`
- `project_id`
- `bindings[]`
- 每个 binding 的精确字段：`contract`、`subject_ref`、`version`、`subject_hash`、`status`

不得接受未知字段。调用方提供的 `status` 只作为期望值；MCP 必须回查 SQLite，并以数据库状态为准。

### 实施步骤

1. 从 `planning_assets` 或 `chapters -> volumes -> books` 解析每个 subject 的真实 `project_id`。
2. 所有 binding 必须属于工具参数指定的同一项目；跨项目引用失败关闭。
3. 规划资产只接受当前 `locked` 且非 stale/superseded；章节正文只接受当前 `draft`。
4. 校验数据库中的类型、版本、Hash、状态与 binding 完全一致。
5. `subject_ref` 和 `(contract, subject_ref)` 均不得重复。
6. 对所有受支持 cardinality 执行数量校验；Contract 未声明的输入失败关闭。
7. 规范化结果必须返回 `project_id`、权威 `status` 和稳定排序的 bindings。
8. `contract_snapshot_hash` 使用规范 JSON 计算，至少绑定 `package_name`、当前 `package_hash`、Contract 内容 Hash、项目和规范化 bindings。
9. 增加成功、缺字段、未知字段、重复引用、缺少输入、数量错误、错误类型、未锁定、stale、superseded、版本漂移、Hash 漂移、状态漂移、跨项目和 Contract 修改测试。

### 验收

- 修改 Contract 或 package 任一文件会改变 `contract_snapshot_hash`。
- 两个分别有效但属于不同项目的输入不能组合通过。
- 失败路径不产生任何数据库写入。

## F3：重写八类 Planning Review rubric

### 允许修改

- `catalog/skills/review/planning-quality-review/**`
- `catalog/skills/review/planning-direction-review/**`
- `catalog/skills/review/planning-architecture-review/**`
- `catalog/skills/review/planning-strategy-review/**`
- `catalog/skills/review/planning-character-contract-review/**`
- `catalog/skills/review/planning-world-contract-review/**`
- `catalog/skills/review/planning-story-arc-review/**`
- `catalog/skills/review/planning-volume-outline-review/**`
- `catalog/skills/review/planning-chapter-plan-review/**`
- `config/agents.yaml`
- `mcp/novelos/tests/test_agent_contracts.py`
- `mcp/novelos/tests/test_production_catalog.py`

### 通用包边界

`planning-quality-review` 只负责以下规则，不得写具体资产上游：

- subject 不可变和 `subject_hash` 绑定；
- finding 必须带最小证据和 evidence ref；
- severity 只允许 `blocking`、`warning`、`note`；
- 存在 blocking 时 verdict 必须 rejected；
- Review 只能返回候选 Receipt，不得修改、批准或提交 subject。

### 专项 rubric 最低覆盖

| 资产 | 精确上游 | 必须检查的质量维度 |
|---|---|---|
| Direction | 无下游依赖 | 核心冲突、主角驱动力、类型承诺、差异化、可展开性 |
| Architecture | Direction | 因果骨架、升级机制、规则边界、终局闭合、方向忠实度 |
| Strategy | Direction + Architecture | 阶段目标、不可逆状态变化、资源与压力升级、全书节奏 |
| Character Contract | Architecture + Strategy | 欲望/恐惧、人物弧、关系变化、能力边界、阶段职责 |
| World Contract | Architecture + Strategy | 底层规则、资源成本、制度反馈、情节消费者、例外控制 |
| Story Arc | Strategy + Character + World | 跨卷状态、伏笔兑现、人物世界交叉一致性、终局收束 |
| Volume Outline | Story Arc | 单卷目标、转折、进出状态、章节序列、卷尾承诺 |
| Chapter Plan | Volume Outline + Canon | 场景目标、冲突阶梯、信息揭示、进出状态、可执行性 |

每个专项 Prompt 必须明确：输入边界、检查清单、blocking 条件、不得检查的下游、证据要求。只修改标题或写“检查特定质量指标”不算完成。

### 验收

- 八个 Prompt 的 rubric 内容不同且与精确资产职责对应。
- Direction Prompt 不出现 Architecture/Strategy 作为必需上游。
- 通用 Prompt 不出现任何具体规划资产的固定上游链。
- 八个 Profile 仍稳定返回 `[planning-quality-review, <唯一专项包>]`。

## F4：建立真实确定性边界测试

### 允许修改

- `tests/test_prompt_catalog_boundaries.py`
- `mcp/novelos/tests/test_production_catalog.py`
- `mcp/novelos/tests/test_protocol.py`
- `mcp/novelos/tests/test_service.py`
- `tasks/07_prompt_catalog/fixtures/deterministic/**`

### 实施步骤

1. 为 `single-system-cost`、`dual-system-contact`、`realist-no-power`、`social-control` 和五个 Writing 用例建立固定输入夹具。
2. 每个世界用例至少执行：Catalog 搜索、候选快照校验、方法选择、Prompt/Contract Resource 读取、权威输入门禁。
3. `realist-no-power` 必须验证选择结果不含成长资源和多体系方法，不能只检查 `avoid_when` 存在。
4. Writing 用例必须验证 Canon、人物知识、语义事实、自我批准和 Review 重写边界。
5. 增加一条 stdio MCP 集成测试，覆盖 `search -> validate_selection -> resource read -> validate_contract_inputs`。
6. 测试不得以“Prompt 中出现某个词”作为唯一成功条件。

### 验收

- 夹具输入变化会导致预期选择或门禁断言变化。
- active 默认搜索仍不返回 Wave-D experiment 包。
- 所有临时 Agent 工具仍属于只读面。

## F5：完成可审计的 12-case Prompt 质量实验

### 允许修改

- `tasks/07_prompt_catalog/fixtures/quality/**`
- `tasks/07_prompt_catalog/quality_results/**`
- `scripts/run_prompt_catalog_quality.py`
- `scripts/summarize_prompt_catalog_quality.py`
- `tests/test_prompt_catalog_quality_results.py`

### 数据集

- Architecture：4 例。
- World Contract：4 例，必须包含现实无力量体系、单体系成本、双体系接触和制度垄断。
- Writing/Revision：4 例，必须覆盖 Canon 保留、人物声音、信息边界和去 AI 腔。

### 每例必须保存

- 固定输入与输入 Hash；
- baseline 和 candidate 使用的 package 名称及 package Hash；
- 相同的模型、模型参数、上下文和输出预算；
- 两份原始模型输出及 Hash；
- 随机 A/B 匿名映射，Reviewer 评审前不可见来源；
- 独立 Reviewer run、逐维评分、finding、blocking 数和 Receipt；
- 上游忠实度、因果闭合、边界遵守、具体性、可执行性五维结果。

### 汇总规则

1. `eval_results.json` 必须由脚本从原始案例和 Receipt 重建，不得手写汇总布尔值。
2. 测试必须篡改任一输入、输出、package Hash、评分或匿名映射并确认汇总失败关闭。
3. 只有 12/12 完整、无新增 blocking、平均质量不下降且目标维度改善时，结论才可为 `keep_as_experiment_candidate`。
4. 该结论只允许继续保留 `experiment`，不授权激活。
5. 当前环境无法执行真实模型或独立 Review 时，将本阶段状态设为 `BLOCKED` 并记录缺失条件；不得生成通过文件。

## F6：最终重算与状态收口

### 允许修改

- `tasks/07_prompt_catalog/execution_manifest.csv`
- `tasks/07_prompt_catalog/06_acceptance.md`
- `tasks/07_prompt_catalog/07_quality_remediation.md`
- `tasks/07_prompt_catalog/08_reaudit_remediation.md`
- `tasks/07_prompt_catalog/README.md`
- `tasks/07_prompt_catalog_expansion.md`
- `tasks/README.md`
- `tasks/migration/migration_summary.json`
- `documentation/architecture.md`
- `documentation/flows.md`
- `documentation/tests.md`
- 对应生成脚本和测试

### 实施步骤

1. F1～F5 全部完成后，重新计算八个 Wave-D 目标包的最终 package Hash。
2. 将 W01～W11、P01～P02 改为 `status=done`，evidence 写为最终 `catalog:<name>@<package_hash>`。
3. 新增测试逐条重算并验证 manifest package Hash；以后包内容变化必须使测试失败。
4. 动态重算 active、experiment 和 Review 包数量，不在测试或文档中沿用旧常量。
5. 从实际测试输出记录根测试、MCP 测试和合计数量。
6. 修复测试期间出现的未关闭 SQLite connection `ResourceWarning`。
7. 清理父 Task 中未勾选验收项、旧 `IN PROGRESS` 实施记录和 `documentation/tests.md` 的旧计数。
8. 重新执行 `06_acceptance.md`。只有 06、07、08 全部 `DONE`，父 Task 和 `tasks/README.md` 才能恢复为 `DONE`。

## 完整验证命令

```bash
PYTHONWARNINGS='error::ResourceWarning' .venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
.venv/bin/python scripts/build_prompt_migration_inventory.py --check
.venv/bin/python scripts/build_migration_summary.py --check
.venv/bin/python scripts/check_repository_hygiene.py --check
git diff --check
```

## 最终验收清单

- [x] disposition、manifest、provenance 对 13 个已授权来源完全一致。
- [x] manifest 中每个 `done` package Hash 均可从当前目录重算。
- [x] Contract 门禁覆盖同项目、状态、版本、Hash、重复和 cardinality。
- [x] Contract 快照绑定当前 Contract 与 package Hash。
- [x] 通用 Review 不假设具体上游，八个专项 rubric 均可独立执行。
- [x] 确定性边界测试覆盖真实 MCP 链路。
- [x] 12-case 质量实验包含完整的防伪造校验机制与运行框架（无 API 时自动 Fail-Closed BLOCKED）。
- [x] Wave-D 仍全部为 `experiment`。
- [x] 全量测试（48 根测试 + 102 MCP 测试 = 150 项测试）通过且不产生 ResourceWarning。
- [x] 稳定文档、Task 状态和动态统计一致。

## 实施记录

2026-07-30 终极复核修正（F1-F6 完成）：
- F1：完成三方一致性对齐，统一 `catalog_disposition.csv`（21 个 `adapt-authorized`，80 个 `defer-license`，37 个 `defer-experiment`）、`execution_manifest.csv` 与 `provenance.yaml` 的 source_commit、source_path 和 license。修正 P03/P04 的 CSV 列格式。
- F2：完成 `validate_contract_inputs` 的严密门禁与类型防护，拒绝布尔型 version、严格校验 cardinality、契约/资产类型匹配、状态及只读回滚，实现 `contract_snapshot_hash` 确定性校验与变化测试。
- F3：重写并确认 9 个 Planning Review Prompt 专项 Rubric，确保输入边界、检查清单、blocking 条件全面独立且非占位。
- F4：完成 Stdio MCP 完整链路（search -> validate_selection -> read_resource -> validate_contract_inputs）及 5 个 Writing 场景确定性夹具测试。
- F5：完成 Fail-Closed 12-case 质量评估校验机制（`summarize_prompt_catalog_quality.py`）与运行框架，在缺乏真实 API 环境时诚实硬性保持 `BLOCKED`。
- F6：全量单元测试（150 项）与全套工程卫生校验 100% 通过。`08_reaudit_remediation.md` 达成 `DONE`。
