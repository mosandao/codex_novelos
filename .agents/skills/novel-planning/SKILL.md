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
5. 需要正式版本时，创建 sub agent（用 Agent 工具）生成候选正文。**Direction sub agent 的输入**用组装器一步产出：`.venv/bin/python scripts/novelos_compose_prompt.py --asset direction --project <project_id>`——组装器查库取①项目绑定的创作者人格（`project_creator_bindings` 签名全文，persona 从这个人身上长出 book_soul）②`project_setup` v2 快照（含 channel/platform/platform_traits/scale/primary_genre/secondary_directions/emotional_surface/emotional_core/tonal_contrast/aesthetic_styles/genre_profile 与 `reference_material`——用户原始意图，按 prompt 的三类意图提炼法消费，**不靠会话记忆回传**）③`scale`（四档分档的可展开性硬约束，在 setup 内，分档要求见 story-direction prompt），并按 setup 取值附加条件模块（频道语法男频力量轴/女频规则关系轴/全向双轨、平台三字段消费、题材信息包、美学基因）。Direction 按其 prompt「上游消费」各节消费 setup：`emotional_core`→book_soul 情感承诺（central_contradiction 情感底色 + protected_dignity 底线）、`emotional_surface`→promise_cadence 表层节奏、`genre_profile`→力量货币候选（非空不现场发明、为 null 现场推导并显式定义）、`platform_traits`→promise_cadence 平台节奏与受众画像翻译，交付前过**表里失联自检**。Direction 必须包含完整 `book_soul`（v2 十二字段，见末尾速查表）和 `creator_signature_ref`。**Architecture sub agent 的输入** = direction 正文 + book_soul v2 全文 + persona（直接注入权威源，不靠 direction 转述）+ setup 内的 scale 与 genre_profile，核心职责是把 organizing_principle / promise_cadence 翻译成叙事引擎。其余资产按各自 prompt 的输入边界注入。Chapter Plan 必须给出 `soul_pressure` 与 `moral_residue`。
6. sub agent 返回候选后：
   ```sql
   INSERT INTO resources (id, media_type, content, content_hash) VALUES (?, 'text/markdown', CAST(? AS BLOB), ?);
   INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role, metadata_json, version)
   VALUES (?, ?, ?, ?, ?, 'candidate', ?, ?, ?, 1);
   -- 记录上游依赖
   INSERT INTO planning_asset_dependencies (asset_id, upstream_asset_id, upstream_version) VALUES (?, ?, ?);
   ```
7. 用 `$novel-review` 审查（sub agent 审查 → INSERT reviews）。direction 的审查 rubric 同样按项目组装：`.venv/bin/python scripts/novelos_compose_prompt.py --asset direction-review --project <project_id>`——频道语法/平台画像/题材信息包的专项检查随项目路由，与生成端对称。
8. 审查通过后锁定：`UPDATE planning_assets SET status='locked', locked_review_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?`。
9. 若下游 Agent 发现上游问题，返回变更提案由主控路由给上游所有者，不在下游候选中隐式重写上游。

## 上游变更与 stale 传播

上游资产修订（新 revision locked）后，运行 `scripts/novelos_propagate_stale.py --asset <上游id>` 标记下游 stale。

## Expansion Skill（可选方法素材）

主干 skill（`catalog/skills/planning/`）的 prompt 末尾列出了可选 expansion。按需 Read `catalog/skills/expansions/<name>/prompt.md` 注入 sub agent 上下文。含 clusters/ 子目录的 atlas 包，按题材 Read 对应簇文件。

## book_soul 字段速查表

Direction 候选的 `metadata.book_soul` 必须符合 `config/schemas/book-soul.schema.json`（v2，十二字段）：

| 字段 | 类型 | 约束 |
|---|---|---|
| `schema_version` | const | 固定值 `2` |
| `organizing_principle` | string | 组织原则：本书独有的组织过程，1-1000 字符 |
| `central_contradiction` | string | 两难结构的核心矛盾，1-1000 字符 |
| `promise_cadence` | string | 承诺兑现节奏（strategy 展开为阶段收益），1-1000 字符 |
| `unresolved_claims` | string[] | 1-24 项，每项 ≤500 字符 |
| `costly_commitments` | string[] | 同上 |
| `protected_dignity` | string[] | 同上 |
| `forbidden_resolutions` | string[] | 同上 |
| `recurring_tests` | string[] | 同上 |
| `narrative_mercy` | string | 1-1000 字符 |
| `narrative_cruelty` | string | 1-1000 字符 |
| `deliberate_silences` | string[] | 同上 |

用 `scripts/novelos_validate_book_soul.py` 校验。book_soul 只有 v2 一个版本；既有 v1 资产属历史锁定数据，不参与新候选校验。

## 节奏密度约束

战略骨架（Strategy）不宜过碎：每个阶段平均不少于 20 万字叙事空间。节奏密度在 Volume Outline 及以下实现。Volume Outline 必须产出并行冲突线（每卷≥3条）、阶段性副高潮（每20-30万字）、POV多样性。
