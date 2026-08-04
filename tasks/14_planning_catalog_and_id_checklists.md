# Task 14：Catalog 搜索与项目 ID 前缀操作前置检查

## 状态

`DONE`

## 背景

Architecture 生成（Trace `bd206236`）的治理链本身干净——5 个 Trace step 全部 completed，0 个 isolation evidence 警告（对比 Direction 阶段的 2 个），审查 0 blocking / 1 warning / 11 notes。但工具调用层面暴露了 4 个操作前置检查覆盖空白，与 Task 13 同类。

## 问题记录

| # | 问题 | 根因 | 处理 |
|---|---|---|---|
| 1 | `planning.list` 报 `not_found` | 项目 ID 是 `project:<uuid>`（带前缀），记忆中只存了裸 UUID。`project.list` 返回多个同名项目，加剧混淆 | 调 `project.list` 确认完整 ID |
| 2 | Catalog 搜索返回空 candidates | 用 skill name（`story-architecture`）做 `asset` 参数，但正确值是资产类型枚举（`architecture`）。SKILL 资产路由表的 `asset_type` 列才是正确值 | 宽搜索（`stage=plan` 不带 asset）后从结果读取 |
| 3 | Catalog validate 报 `stale_catalog` | `_snapshot_hash` 对返回的 candidates 子集做 hash，不同搜索参数 → 不同子集 → 不同 hash。搜索与验证之间插入了新的宽搜索 | 搜索后立即用同一 hash 验证，不插中间操作 |
| 4 | `planning.create_candidate_from_run` 报 inputSchema 失败 | `upstream_refs` 传了字符串数组，但必须是 `list[dict]`，每个 dict 精确含 `{"asset_id": str, "version": int}` | 读源码确认格式后重传 |

## 优化

### A. novel-project SKILL.md：新增「项目 ID 前缀」操作前置检查

- 项目 ID 格式为 `project:<uuid>`，所有需要 `project_id` 的 MCP 工具必须用带前缀的完整 ID。
- `project.list` 可能返回多个同名项目，以 `metadata.project_setup` 非空且 `version >= 2` 的为准。

### B. novel-planning SKILL.md：新增两条操作前置检查

**Catalog 搜索与校验规则**：
- `asset` 参数值是资产类型枚举（如 `architecture`），不是 skill 展示名（如 `story-architecture`）。
- `snapshot_hash` 锚定本次搜索的 candidates 子集，搜索后必须立即用同一 hash 验证。

**planning.create_candidate_from_run 的 upstream_refs 格式**：
- `upstream_refs` 必须是 `list[dict]`，每个 dict 精确含 `{"asset_id": str, "version": int}`。
- MCP 校验每个上游 `status == "locked"` 且 `version` 匹配。

## 来源信息

- 来源 commit：本次变更所在 commit（待回填）
- 触发实例：Architecture 生成（project `project:ea0831c1-cb35-4404-8df4-b69e2a136967`，Trace `bd206236`）
- 上一轮同类 Task：[Task 13](./13_planning_skill_schema_checklists.md)

## 改动文件

| 文件 | 变更 |
|---|---|
| `.agents/skills/novel-project/SKILL.md` | 新增「操作前置检查」段：项目 ID 前缀 |
| `.agents/skills/novel-planning/SKILL.md` | 新增「Catalog 搜索与校验规则」和「upstream_refs 格式」两个检查段 |
| `tasks/14_planning_catalog_and_id_checklists.md` | 本文件 |

## 验收标准

- [x] novel-project SKILL 包含项目 ID 前缀提醒。
- [x] novel-planning SKILL 包含 Catalog asset 参数值与 snapshot hash 校验规则。
- [x] novel-planning SKILL 包含 upstream_refs `list[dict]` 格式规则。
- [x] 根测试、MCP 测试、compileall 全部通过。

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```
