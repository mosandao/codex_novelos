---
name: novel-project
description: 管理 NovelOS 小说项目、书、卷和章节容器。创建或查询项目层级、定位目标章节、调整项目说明，或需要判断某项操作属于容器管理还是小说语义规划时使用。
---

# 小说项目

只管理创作容器和定位信息；不要生成故事方向、卷纲或正文。

## 工作流

1. 先用 `project.list/get`、`book.list/get`、`volume.list/get`、`chapter.list/get` 定位已有对象，避免重复创建。
2. 只有用户明确要求创建时，才调用对应的 `*.create` 工具。修改项目时携带当前 `expected_version`。
3. 返回新建或定位到的精确 ID、版本和状态；长内容只返回 `resource_ref`。
4. 遇到故事方向、架构、人物契约、卷纲或章纲请求时，转交 `$novel-planning`。
5. 遇到正文请求时，先确认有效 Chapter Plan，再转交 `$novel-memory` 和 `$novel-writing`。

## 多原型 LLM 融合（项目创建）

`novelos.project.create.v1` 的 `creator.selected_archetypes` 决定签名融合路径：

- **单原型**：直接用 `project.wizard.reconcile_archetypes` 确定性收口，再 `project.wizard.submit`。
- **多原型（≥2）**：必须先创建临时 `onboarding_agent` run，把 `selected_archetypes`、`project_setup` 和各原型完整签名交给它，由 LLM 判定 parent 并深度融合跨原型约束，产出 `creator_derivation_candidate`（含完整 `signature` 与 `merge_rationale`）。随后：
  1. 用 `creative_contracts.validate_signature` 校验 Agent 输出的 `signature` 合法；
  2. 以 Agent 判定的 parent 调 `project.wizard.reconcile_archetypes` 做确定性合规收口；
  3. `project.wizard.submit` 落库，trace 记录 onboarding run。

无论哪条路径，落库前签名都必须通过确定性 schema 校验；LLM 只在 `onboarding_agent` run 内推理，MCP 不调 LLM。

不要为一次容器查询或创建临时 Agent，也不要直接访问数据库或文件。

## 操作前置检查

### 项目 ID 前缀

通过 `project.wizard.submit` 创建的项目，其 ID 格式为 `project:<uuid>`（带 `project:` 前缀）。在所有需要 `project_id` 参数的 MCP 工具调用（`planning.list`、`agent.start`、`planning.create_candidate_from_run`、`planning.lock` 等）中，必须使用带前缀的完整 ID。

常见错误：从记忆或文档中只复制 UUID 部分（如 `ea0831c1-...`），遗漏 `project:` 前缀，导致 `not_found: projects 记录不存在`。

确认方法：调用 `project.list`，从返回值的 `id` 字段读取完整 ID。`project.list` 可能返回多个同名项目（历史遗留的裸 UUID 项目与新前缀项目并存），以 `metadata.project_setup` 非空且 `version >= 2` 的那个为准。
