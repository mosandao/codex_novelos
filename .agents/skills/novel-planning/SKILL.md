---
name: novel-planning
description: 识别小说规划层级并准备对应权威资产的最小输入。探索或生成故事方向、故事架构、全书战略、人物或世界契约、跨卷故事弧、卷纲、章纲时使用。
---

# 小说规划

通过 SQLite MCP 操作数据库。SQL 模板见 `novel-project/sql-reference.md`。

## 资产路由

| `asset_type` | 生产者角色 | 必需上游 |
|---|---|---|
| `direction` | 方向智能体 | 无 |
| `architecture` | 架构智能体 | direction |
| `strategy` | 策略智能体 | direction、architecture |
| `character_contract` | 人物智能体 | architecture、strategy |
| `world_contract` | 世界观智能体 | architecture、strategy |
| `story_arc` | 故事弧智能体 | strategy、character_contract、world_contract |
| `volume_outline` | 卷规划智能体 | story_arc |
| `chapter_plan` | 章节规划智能体 | volume_outline |

依赖顺序：direction → architecture → strategy → character‖world → story_arc → volume_outline → chapter_plan。

## 工作流

1. 从用户目标判断唯一目标 `asset_type` 和 `scope_ref`。
2. `SELECT * FROM planning_assets WHERE project_id=? AND status='locked' ORDER BY asset_type` 读取当前资产；复用所有有效 locked 上游，拒绝使用 stale/superseded。
3. Read `catalog/skills/planning/<对应 skill>/prompt.md` 获取方法论。
4. 探索性讨论直接返回方案，不持久化。
5. 需要正式版本时，创建 sub agent（用 Agent 工具）生成候选正文。Direction 必须包含完整 `book_soul`（见末尾速查表）和 `creator_signature_ref`；**Direction sub agent 的输入必须包含项目绑定的创作者人格**——从 `project_creator_bindings` 查签名（sql-reference.md「作者签名链」查询模板），把 `persona`（narrative + anchors）全文注入 prompt：book_soul 从这个人身上长出来，而不是从原型标签推导。Chapter Plan 必须给出 `soul_pressure` 与 `moral_residue`。
6. sub agent 返回候选后：
   ```sql
   INSERT INTO resources (id, media_type, content, content_hash) VALUES (?, 'text/markdown', CAST(? AS BLOB), ?);
   INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role, metadata_json, version)
   VALUES (?, ?, ?, ?, ?, 'candidate', ?, ?, ?, 1);
   -- 记录上游依赖
   INSERT INTO planning_asset_dependencies (asset_id, upstream_asset_id, upstream_version) VALUES (?, ?, ?);
   ```
7. 用 `$novel-review` 审查（sub agent 审查 → INSERT reviews）。
8. 审查通过后锁定：`UPDATE planning_assets SET status='locked', locked_review_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?`。
9. 若下游 Agent 发现上游问题，返回变更提案由主控路由给上游所有者，不在下游候选中隐式重写上游。

## 上游变更与 stale 传播

上游资产修订（新 revision locked）后，运行 `scripts/novelos_propagate_stale.py --asset <上游id>` 标记下游 stale。

## Expansion Skill（可选方法素材）

主干 skill（`catalog/skills/planning/`）的 prompt 末尾列出了可选 expansion。按需 Read `catalog/skills/expansions/<name>/prompt.md` 注入 sub agent 上下文。含 clusters/ 子目录的 atlas 包，按题材 Read 对应簇文件。

## book_soul 字段速查表

Direction 候选的 `metadata.book_soul` 必须符合 `config/schemas/book-soul.schema.json`：

| 字段 | 类型 | 约束 |
|---|---|---|
| `schema_version` | const | 固定值 `1` |
| `central_contradiction` | string | 1-1000 字符 |
| `narrative_mercy` | string | 1-1000 字符 |
| `narrative_cruelty` | string | 1-1000 字符 |
| `unresolved_claims` | string[] | 1-24 项，每项 ≤500 字符 |
| `costly_commitments` | string[] | 同上 |
| `protected_dignity` | string[] | 同上 |
| `forbidden_resolutions` | string[] | 同上 |
| `recurring_tests` | string[] | 同上 |
| `deliberate_silences` | string[] | 同上 |

用 `scripts/novelos_validate_book_soul.py` 校验。

## 节奏密度约束

战略骨架（Strategy）不宜过碎：每个阶段平均不少于 20 万字叙事空间。节奏密度在 Volume Outline 及以下实现。Volume Outline 必须产出并行冲突线（每卷≥3条）、阶段性副高潮（每20-30万字）、POV多样性。
