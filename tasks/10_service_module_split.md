# Task 10：service.py 模块拆分

## 状态

`DONE`

代码拆分、协议兼容和仓库全量验证均已完成。正式数据库已恢复至 Schema 12 备份基线，恢复前状态另有独立可恢复备份。

## 目标

把 `mcp/novelos/src/novelos_mcp/service.py`（近 4000 行单文件、单类 `NovelOSService`）按命名空间拆成 8 个领域 Mixin + 1 个共享内部 Mixin，并由 `service/__init__.py` 聚合为 `NovelOSService`。这是纯机械重构：外部 MCP 工具契约、工具名集合、构造签名、包级导入路径和全部测试零行为变化，只改善单文件过胖导致的定位与维护困难。

本任务不改任何业务逻辑、校验规则或运行时行为，是 Task 11（审计架构修剪）的前置基础——后者需要清晰的文件结构才能安全地修改隔离强制行为。

## 背景

`service.py` 在一个类里塞了 Memory / Planning / Catalog / Review / Trace / Chapter / Creator / Entity 全部逻辑，外加约 25 个 `_validate_*` / `_record_*` 私有事务 helper。定位任何一个写路径都要在近 4000 行里翻找。但这个文件的外部契约是干净的：

- `server.py` 是纯薄路由表（81 条 `工具名 → service.xxx 方法对象` 直连 + 1 个 wizard 编排），零业务逻辑、零 try/except。
- 全部测试直接 `NovelOSService(Path(...))` 实例化，无 `conftest.py`、无 pytest fixture、无 mock，唯一共享 helper 是 `agent_test_support.py` 的两个自由函数（按鸭子类型访问 `service.xxx`）。
- 6 个依赖对象（`database` / `knowledge` / `catalog` / `agent_contracts` / `creative_contracts` / `system_archetypes`）在 `__init__` 中 new 出来并持有，彼此无状态解耦，只有 `database` 是共享事务边界。

这意味着只要保持 `NovelOSService(path)` 单参数构造和所有方法名不变，Mixin 聚合可以让测试和 server.py 零改动。

## 核心决策

### 1. Mixin 聚合，不引入子服务委托

聚合类 `NovelOSService` 继承 `_ServiceInternals` 和全部领域 Mixin，方法仍以 `self.xxx()` 互相调用。领域 Mixin 不互相继承，也不导入 `NovelOSService`；所有 Mixin 共享 `__init__` 中创建的 `self.database` / `self.agent_contracts` / `self.creative_contracts` / `self.catalog` / `self.knowledge`，与现有代码的访问模式完全一致，避免菱形继承和循环 import。

不采用子服务委托（`PlanningService` / `ChapterService` 等独立对象）：它需要引入子服务间的引用传递，改动面大且收益不抵成本。

### 2. 保持构造签名不变

`NovelOSService.__init__` 仍只接收路径参数（`database_path` / `seed_database_path` / `catalog_path` / `agent_contract_path` / `seed_inventory_path`），内部 new 6 个依赖。所有测试的 `setUp` 里 `NovelOSService(Path(self.temporary.name) / "novelos.db")` 一行式构造无需改动。

### 3. 区分模块 helper、共享类 helper 与领域私有 helper

- 当前模块级函数 `_id` / `_json` / `_require_text` / `_require_sha256` 移到 `service/_helpers.py`，各 Mixin 显式导入，保持现有 `_id(...)` / `_json(...)` 调用形式不变。
- 所有 class-private 方法暂统一移到 `_ServiceInternals`，包括事务、校验、投影快照和领域私有 helper；这样保留原有 `self._xxx()` 调用语义，避免 Mixin MRO 因跨领域调用产生隐式依赖。模块级函数仍单独放在 `_helpers.py`。

搬移前以调用点搜索确认归属；不得仅按 `_` 前缀批量移动，也不得为了适配拆分而改写调用语义。

### 4. 模块级常量移到 `service/_constants.py`

`PLANNING_UPSTREAM_TYPES` / `PLANNING_REVIEW_PROFILES` / `PLANNING_PRODUCERS` / `CONTINUITY_OWNERS` / `ENTITY_AUTHORITY_ASSETS` 五个模块级常量移到 `service/_constants.py`。`service/__init__.py` 继续 re-export 这些常量，保持 `from novelos_mcp.service import ...` 向后兼容；现有 `test_agent_contracts.py` 顶层导入断言不得改成只测试内部路径。

### 5. `service` 包取代 `service.py`，二者不得并存

Python 在同一目录同时存在 `service.py` 与 `service/` 时，`import novelos_mcp.service` 会解析到包目录，导致文件中的聚合类不可达。因此拆分完成时删除原 `service.py`，把聚合类、构造函数和兼容 re-export 全部放到 `service/__init__.py`。外部仍使用原导入路径 `novelos_mcp.service`，`server.py` 和调用方无需改动。

## 文件切分

```
mcp/novelos/src/novelos_mcp/
├── service/
│   ├── __init__.py                 # 聚合类：__init__ + 继承所有 Mixin + 顶层 re-export 常量
│   ├── _constants.py               # 5 个模块级常量
│   ├── _helpers.py                 # _id / _json / _require_text / _require_sha256 模块函数
│   ├── _internals.py               # _ServiceInternals：跨领域共享的类私有 helper
│   ├── projects.py                 # ProjectMixin：Project + Book + Volume 容器的 create/get/list/update/delete
│   ├── creators.py                 # CreatorMixin：profile + system_archetypes + binding + create_project_with_creator/rebind + Creator 私有 helper
│   ├── planning.py                 # PlanningMixin：create_candidate/from_run/get/list/lock/withdraw + cross_check prepare/approve/get + entity mutation prepare/commit + upsert_character/world/faction/rule/timeline + get/list 各实体
│   ├── chapters.py                 # ChapterMixin：create/update_chapter_draft + get/list_chapter + accept + supersede + prepare_review_subject + get_review_subject
│   ├── reviews.py                  # ReviewMixin：record_review + record_review_from_run + get_review + search/get_skill_catalog + validate_skill_* + get_review_catalog_route + validate_contract_inputs
│   ├── agents.py                   # AgentMixin：start_trace/start_agent_run/finish_agent_run/get/list_agent_runs + record_trace_step/finish_trace/get_trace/audit_authority_trace
│   ├── memory.py                   # MemoryMixin：recent_chapters/search_facts/get_entity_states/get_authority_snapshot + record/get/promote_continuity + search/get_knowledge + create/get_resource
│   └── projection.py               # ProjectionMixin：get_projection_snapshot/render_project_projection/verify_project_projection（薄转发到 ProjectionEngine）
```

注：现有 `projection.py`（615 行的 `ProjectionEngine` 类）保持不动；新增的 `service/projection.py` 只是 `NovelOSService` 上 3 个投影方法的归属 Mixin，内部仍按现有模式局部 `import` 并临时实例化 `ProjectionEngine`。

## 实施顺序

1. 创建 `service/` 包、`_constants.py` 与 `_helpers.py`，搬移常量和模块级 helper。
2. 创建 `_internals.py` 的 `_ServiceInternals` Mixin，搬移全部 class-private 方法；模块级 helper 仍由 `_helpers.py` 提供。
3. 逐个创建 8 个领域 Mixin（projects / creators / planning / chapters / reviews / agents / memory / projection），其中 ProjectMixin 必须包含 Book/Volume 容器方法。
4. 在 `service/__init__.py` 定义聚合类：保留原 `__init__` 实现与完整五参数签名，继承 `_ServiceInternals` 和 8 个领域 Mixin，并 re-export 5 个兼容常量。
5. 删除原 `service.py`；确认仓库中不存在同名模块文件与包目录并存。
6. 保持 `server.py`、`novelos_mcp/__init__.py` 和现有测试的 `from novelos_mcp.service import ...` 导入不变，另加结构测试确认导入目标为 `service/__init__.py` 且公开方法完整。
7. 运行仓库规定的全量验证确认零行为变化。

## 验收标准

- [x] 所有 81 个 MCP 工具仍可被 `test_runner_protocol.py` 校验（注册名集合不变，总数仍为 82）。
- [x] `test_protocol.py` 的 stdio 端到端协议测试全部通过。
- [x] `NovelOSService(Path(...))` 单参数构造方式不变；所有测试 `setUp` 无改动。
- [x] `NovelOSService.__init__` 的五参数签名、默认值和参数顺序与拆分前一致。
- [x] `from novelos_mcp.service import NovelOSService, PLANNING_UPSTREAM_TYPES, PLANNING_REVIEW_PROFILES, PLANNING_PRODUCERS` 继续通过；现有顶层常量 import 测试保持不变。
- [x] Project / Book / Volume / Chapter 全部公开方法仍存在且协议测试覆盖对应 MCP 工具。
- [x] 原 `service.py` 已删除，`novelos_mcp.service.__file__` 指向 `service/__init__.py`。
- [x] `compileall` 通过，无循环 import。
- [x] 根测试、MCP 测试及 `AGENTS.md` 规定的仓库检查全部通过。

## 完成证据

- 2026-08-03：`service.py` 已由 8 个领域 Mixin、`_ServiceInternals`、共享 helper/constant 与聚合 `service/__init__.py` 完整取代。
- `test_runner_protocol.py` 继续确认 82 个 MCP 工具；stdio 协议测试通过。
- 根测试 53 项、MCP 测试 154 项全部通过；全部 manifest、seed、备份、导出、hygiene、cutover 与 `compileall` 检查通过。
- 正式库恢复前快照保存在 `data/migration/novelos-v2-before-task10-11-20260803.db`，恢复演练清单为 `tasks/migration/novelos-v2-before-task10-11-20260803.json`。

## 非目标

- 不改任何 MCP 工具名、参数签名或返回结构。
- 不动 `server.py`（它已经是薄路由表，不是问题所在）。
- 不改任何业务逻辑、校验规则或运行时行为——纯文件重组。
- 不引入新的抽象层、子服务对象或依赖注入框架。

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

只有原 `service.py` 被无冲突的 `service/` 包完整取代、所有公开方法与兼容导出保留、外部工具契约与构造签名不变，且仓库规定的全部验证通过，才可将本任务从 `TODO` 标记为 `DONE`。仅有目录结构或部分方法搬运时不得标记完成。
