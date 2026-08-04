# Task 11：审计架构中度修剪

## 状态

`DONE`

Profile 注册表、strict/lenient 双模式、启动期 fail-closed 校验、边界测试、文档与仓库全量验证均已完成。

前置依赖：Task 10（service.py 模块拆分）完成。

## 目标

针对 Agent 审计架构中两处对单用户创作过重的设计做中度修剪：

1. **统一 Review Profile 权威源**——消除 profile 名在多处硬编码、权威多源、改名易漏的脆弱点。
2. **降级声明性门禁**——把 `isolation_evidence` 与 Character/World 交叉审查的“无凭据则拒绝”降级为可配置 strict 模式（默认 lenient：在权威提交事务中记录告警但放行），保留 trace 串联、hash 一致性、上游 locked、Reviewer role 与不可变输入绑定等真实强制。

本任务兼容旧数据：默认 lenient 不破坏任何已有数据，strict 开关可切回原阻断行为。

## 背景

### Profile 名权威多源

当前 Review Profile 的注册、推导与业务用途散落在多处，且部分靠隐式约定（snake_case → kebab-case 拼接）维持一致：

1. `service.py` 的 `PLANNING_REVIEW_PROFILES` 由 planning asset_type 拼接推导。
2. `config/agents.yaml` roles 的 `review_profile` 字段引用 planning Profile。
3. `config/agents.yaml` `review_profile_routes` 的 key 注册全部 Profile。
4. `config/agents.yaml` `cross_consistency_gate.profile` 引用交叉审查 Profile。
5. `service.py` 的 Entity、章节接受和连续性晋升路径仍含 Profile 字面量。
6. `agent_contracts.py` `_validate_routes` 另有 `expected_profiles` 字面量全集。

`agent_contracts.py` 的元校验只检查一组代码内字面量存在于 routes，**没有遍历并校验所有配置消费者的 Profile 引用**。改名时如果漏改 role、cross-consistency gate 或业务写路径，启动校验无法完整发现。

### 声明性隔离凭据

`isolation_evidence` 的现有代码注释自承认：

> 这是声明性证明（非密码学证明）：真实隔离仍由 主控智能体 用独立 Codex Task 创建 sub-agent 兑现。

而唯一拥有提交权限、唯一负责收集这个凭据的，正是 `main_agent` 自己。这构成"审计对象收集审计证据"的自证清白结构。对自用单用户项目，强求一个自己给自己签发的隔离凭据，边际收益低于成本。同理，`context_builder` 的 spawn gate（`complexity_reasons` 白名单）也只校验字段在白名单内，真实复杂度判断不参与。

### 被降级影响的测试

- `test_agent_workflows.py:338-384` `test_lock_rejected_without_isolation_evidence`：当前断言 `missing_isolation_evidence` raise。
- `test_planning.py:162-163` 断言缺少 cross_check 时创建 Story Arc 候选失败。
- `test_projection.py:95-109`、`test_creator_profiles.py:351-362` 依赖 cross_check 的完整路径。
- `agent_test_support.py:20` 默认传 `{"source":"test_harness"}`。

## 核心决策

### 1. Review Profile 名以 agents.yaml 为唯一权威源

`config/agents.yaml` 的 `review_profile_routes` key 是合法 Review Profile 名的唯一注册表。其他位置只能引用注册表 key，不再在 Python 中维护 Profile 名全集：

- 从 `roles` 推导 `{owned_asset_type: review_profile}` 映射（针对 `owned_asset_type` 非 null 的 planning_asset role），作为 `review_profile_for_asset(asset_type)` 的查询源，取代 `service.py` 的 `PLANNING_REVIEW_PROFILES` 推导常量。
- 保留 `cross_consistency_gate.profile` 作为交叉一致性用途到注册表的引用。
- 新增 `review_profile_bindings`，声明章节接受、连续性晋升和各 Entity 权威提交所用的 Profile 引用：

```yaml
review_profile_bindings:
  chapter_acceptance: prose-v1
  continuity_promotion: continuity-v1
  entity_authority:
    character: entity-character
    world: entity-world
    faction: entity-faction
    rule: entity-rule
    timeline: entity-timeline
```

- `agent_contracts.py` 启动时遍历 `roles[*].review_profile`、`cross_consistency_gate.profile` 和 `review_profile_bindings` 的全部叶子引用，校验每个非 null 值都是 `review_profile_routes` 的 key；删除 `expected_profiles` 及任何 Python 字面量名称全集。
- 业务代码只能通过 `review_profile_for_asset()`、`review_profile_for_binding()`、`review_profile_for_entity()` 和 `cross_consistency_profile()` 查询，不直接硬编码 Profile 名。

Task 10 保留的包级 `PLANNING_REVIEW_PROFILES` 继续兼容，但必须通过共享配置加载函数从默认 `agents.yaml` 的 roles 派生为只读快照，不再按命名规则拼接，也不维护第二份字面量。运行中的 `NovelOSService` 始终查询自身 `AgentContractStore`，以支持自定义 `agent_contract_path`。

### 2. 隔离强制降级为可配置 strict 模式

新增配置块 `runtime.enforcement`，两个开关默认 `false`（lenient）：

```yaml
runtime:
  enforcement:
    strict_isolation_evidence: false   # true 维持当前 raise 行为
    strict_cross_consistency: false     # true 维持当前 raise 行为
```

`AgentContractStore` 必须校验 `runtime.enforcement` 只包含这两个已知 key，且值必须是 JSON/YAML boolean；缺失配置时使用上述默认值，未知 key 或字符串形式的 `"false"` 均以 `configuration_error` 拒绝，避免静默切换安全模式。

**lenient 模式**（默认）：缺 `isolation_evidence` 或 Story Arc 未绑定 approved cross_check 时不 raise，在对应权威提交事务中记录 trace step 后放行。现有 `trace_steps.status` 只允许 `started/completed/failed`，因此告警 step 使用 `status=completed`，并在 `details` 写入 `severity: warning`、`enforcement_mode: lenient`、缺失项和相关 run/asset ref；不得写入不存在的 `status=warning`。

**strict 模式**：维持当前 raise 行为，适合团队多人审计场景。

### 3. 保留的真强制（不动）

以下检查**全部保留不变**，无论 strict/lenient：

- `_validate_authority_trace` 中 trace 串联（producer/reviewer 必须在同一 running trace、同项目）。
- producer run output hash 与 resource 一致（防 Main 中间篡改）。
- `_validate_planning_dependencies` 上游必须 locked 且版本匹配。
- Reviewer 必须来自已完成的 `review_agent` run，且 Reviewer 输入中的 subject ref/hash/profile、不可变输出和最终 Review Receipt 完全一致。
- reviewer 与 producer 的 `context_id` 不能相同。`context_id` 是系统为每个 run 自动生成的唯一关联标识，只能阻止同一 run/context 被复用，**不证明真实 Codex 模型上下文隔离**；真实隔离仍由 主控智能体 按项目规则创建临时 Agent 兑现。
- Review Profile 必须匹配资产类型。
- Review verdict 必须 approved 且无 blocking finding。
- 上游变更递归标记后代 stale。

## 实施范围

### A. 统一 Profile 权威源

1. `agents.yaml` 新增上述 `review_profile_bindings`；`review_profile_routes` 继续作为唯一合法名称注册表，roles 与 `cross_consistency_gate` 只保留引用。
2. `agent_contracts.py` 新增 `_derive_planning_review_profiles()`，并暴露 `review_profile_for_asset(asset_type)`、`review_profile_for_binding(name)`、`review_profile_for_entity(entity_type)`、`cross_consistency_profile()`；未知用途或类型 fail closed。
3. `_validate_routes` 删除 `expected_profiles`，改为遍历校验所有配置引用；同时校验每个 planning_asset role 恰好有非空 `owned_asset_type` 和已注册 `review_profile`，且 asset_type 无重复 owner。
4. Planning lock、cross-check approval、Entity commit、chapter acceptance 和 continuity promotion 全部改用查询 API，移除对应 Python Profile 字面量。
5. Task 10 后 `service/__init__.py` 的兼容 `PLANNING_REVIEW_PROFILES` 由默认配置派生并标注 deprecated；保留现有包级 import 测试，同时新增运行时自定义配置测试，证明 Service 不读取该兼容快照。

### B. 降级 isolation_evidence 强制

1. `agents.yaml` 新增 `runtime.enforcement.strict_isolation_evidence: false`。
2. `agent_contracts.py` 暴露 `is_strict(name: str) -> bool` 读取经过严格类型校验的开关；未知 name raise `configuration_error`。
3. `_validate_authority_trace`（Task 10 后位于 `service/_internals.py`）的两处 `missing_isolation_evidence` 检查改为：strict 时维持原 raise；lenient 时通过 `_record_trace_step_in_transaction` 写入 `status=completed`、`details.severity=warning` 的 `isolation.evidence.missing` step 后继续。Reviewer 与 producer 分别记录，details 必须绑定具体 run id 和 role。
4. `test_agent_workflows.py:338-384` 改为使用两份临时配置根目录分别构造 Service：复制 `config/agents.yaml` 及其引用的 Schema，修改临时副本的 enforcement 后通过 `agent_contract_path` 注入。strict 断言原错误码，lenient 断言权威提交成功且 warning step 字段完整；不得原地修改仓库配置，也不得只复制 `agents.yaml` 导致相对 Schema 路径失效。
5. `agent_test_support.py:20` 默认仍传 `{"source":"test_harness"}`，保持多数测试默认通过。

### C. 降级 cross_check 强制

1. `agents.yaml` 新增 `runtime.enforcement.strict_cross_consistency: false`。
2. Story Arc 候选创建入口和锁定入口必须同时调整：
   - 创建候选时，strict 模式缺 `cross_check_id` 维持 `cross_check_required`；lenient 模式允许 `cross_check_id=null`，但此阶段不写 warning，因为候选尚未成为权威。
   - 只要调用方提供 `cross_check_id`，无论 strict/lenient 都必须立即验证它已 approved、属于当前项目、来源版本与 Story Arc 上游一致；无效凭据不能按“缺失”降级放行。
   - 锁定 Story Arc 时重新验证已绑定 cross-check，防止候选创建后来源失效。strict 模式缺失则 raise；lenient 模式缺失则在同一 lock 事务写入 `cross_check.missing` step，使用 `status=completed` 和 `details.severity=warning`，随后完成 lock。
3. `test_planning.py` / `test_projection.py` / `test_creator_profiles.py` 中完整 cross-check 路径保持不变；新增 lenient 缺失可创建并锁定、strict 缺失在创建阶段拒绝、两种模式下提供 invalid/stale cross-check 均拒绝、候选创建后 cross-check 失效时锁定拒绝的测试。

### D. 文档同步

1. `AGENTS.md`：明确 `isolation_evidence` 与 cross-check 在 lenient 模式下为声明性记录，strict 模式才阻断；同时说明 `context_id` 只标识 run context，不构成真实模型上下文隔离证明。默认 lenient 服务单用户创作，独立 Reviewer role、不可变 subject/hash 和 Trace 绑定仍强制。
2. `config/agents.yaml` 新增的 `runtime.enforcement` 块附注释说明默认值与切换语义。
3. 更新 `documentation/architecture.md` 中“缺 isolation_evidence 无法锁定”的旧描述，以及 `documentation/flows.md` 中“缺 cross-check 必然拒绝”的旧流程；两处都必须准确区分默认 lenient 与 strict 行为。

## 验收标准

- [x] `review_profile_routes` 是合法 Profile 名唯一注册表；所有 roles、cross-consistency 和业务用途引用均在启动时校验，Python 中不再存在 Profile 名全集或业务写路径字面量。
- [x] 兼容 `PLANNING_REVIEW_PROFILES` 仅由默认配置派生；自定义 `agent_contract_path` 的运行时查询不受兼容快照影响。
- [x] 默认 lenient 模式：无 `isolation_evidence` 的权威提交不再 raise，写入合法 `status=completed` 且 `details.severity=warning` 的 trace step 后放行；strict 模式维持原 raise。
- [x] 默认 lenient 模式：无 approved cross_check 可创建并锁定 Story Arc，warning 只在 lock 权威事务中写入；strict 模式在候选创建阶段维持原拒绝。
- [x] 提供但无效、错配或 stale 的 cross-check 在两种模式下都拒绝；已绑定 cross-check 在 lock 时重新验证。
- [x] trace 串联、producer hash、上游 locked、Reviewer role、Reviewer 输入/输出绑定及 context_id 不复用检查全部保留；文档不再把 context_id 描述为真实隔离证明。
- [x] 现有传入完整 `isolation_evidence` 和 cross_check 的测试路径全部继续通过。
- [x] `config/agents.yaml` 切换 `strict_*: true` 后，原 strict 行为测试全部恢复通过。
- [x] enforcement 缺省值、合法 boolean、未知 key、字符串伪 boolean 和未知 `is_strict()` name 均有 fail-closed 测试。
- [x] `AGENTS.md` 明确标注声明性强制的范围与 strict/lenient 切换。
- [x] 根测试、MCP 测试、`compileall` 全部通过。

## 完成证据

- `review_profile_bindings` 采用精确键集合校验；缺失、拼错、未知、空值和未注册 Profile 均在 `AgentContractStore` 启动时拒绝。
- 自定义 `agent_contract_path` 的规划 Profile 已通过实际 Service lock 路径验证，不读取默认兼容快照。
- isolation evidence 和 cross-check 的 lenient/strict 配置路径均使用临时完整配置测试；pending、错配、stale 和 lock 前失效在两种模式下保持拒绝。
- 根测试 53 项、MCP 测试 154 项与 `AGENTS.md` 全部仓库检查于 2026-08-03 通过。

## 非目标

- 不合并后段 planning 链（StoryArc / Volume / Chapter 维持三层）。
- 不合并 5 个 entity-* Review Profile（维持）。
- 不改 cross_check 为 scope 触发（维持现有全局门禁语义，只降级阻断强度）。
- 不删除 `isolation_evidence` 字段、`agent_runs.isolation_evidence` 列或 `planning_cross_checks` 表（数据兼容）。
- 不动 Task 10 已完成的文件拆分结构。

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python scripts/build_migration_manifest.py --output-dir tasks/migration --check
.venv/bin/python scripts/build_catalog_manifest.py --check
.venv/bin/python scripts/build_agent_quality_dataset.py --check
.venv/bin/python scripts/build_seed_inventory.py --check
.venv/bin/python scripts/build_seed_inventory.py --production --check
.venv/bin/python scripts/backup_novelos_database.py --check
.venv/bin/python scripts/export_novelos_data.py --check
.venv/bin/python scripts/build_migration_summary.py --check
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/check_cutover_readiness.py --check
.venv/bin/python scripts/check_cutover_plan.py --check
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 完成条件

只有 Profile 注册表与全部配置引用的启动校验接通、strict/lenient 双模式在候选创建和权威提交两阶段均符合验收、真实强制全部保留、安全边界与 `AGENTS.md` 同步，且仓库规定的全部验证通过，才可将本任务从 `TODO` 标记为 `DONE`。仅有配置开关或部分测试改动时不得标记完成。
