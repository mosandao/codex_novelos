---
name: novel-review
description: 独立审查不可变小说资产并生成 Review Receipt。规划资产锁定、章节接受、连续性事实晋升前，或需要检查 Canon、人物、世界规则、节奏和文本质量时使用。
---

# 小说审查

通过 SQLite MCP 操作数据库。SQL 模板见 `novel-project/sql-reference.md`。

## 工作流

1. 接收审查目标（资产或章节的 ID）和审查维度（Review Profile 对应的方法论）。
2. 审查标准获取（按资产分流，以 `scripts/novelos_compose_prompt.py` 的 **ASSET_DIRS 注册表**为准）：**已注册审查**（direction-review / architecture-review 及后续）用组装器 `--asset <asset>-review --project <project_id> --subject <被审资产ID>`——检查清单 + 随项目路由的条件审查模块 + 被审对象全文 + 上游原文一步产出，与生成端对称；**未注册审查**暂仍 Read `catalog/skills/review/<对应 review skill>/prompt.md` + 手工注入 subject 与上游原文，Task 29 P2 完成后逐一切换。
3. 审查 sub agent 需要**完整的审查依据**：候选正文全文 + 全部已锁定上游原文。直接从数据库 SELECT resources 读取，注入 sub agent prompt。禁止让 sub agent 自行读文件。
4. 按 review prompt 的检查维度逐项审查。每个 finding 只使用 `blocking`、`warning` 或 `note`，给出最小直接证据和原文片段。
5. 只要有 `blocking`，verdict 必须是 `rejected`。
6. 记录审查结果：
   ```sql
   INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict,
       findings_json, reviewer_profile, evidence_refs_json)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?);
   ```
   - `findings_json`：`[{"severity":"note","message":"...","evidence_refs":["..."]}]`
   - `verdict`：`approved` 或 `rejected`

## 审查标准来源

| 场景 | Review skill | Craft skill（方法素材） |
|---|---|---|
| 章节接受 | `catalog/skills/review/prose-quality-review/prompt.md` | prose-anti-ai-fingerprint、prose-format-hardrules |
| 规划资产 | `catalog/skills/review/planning-<asset>-review/prompt.md` | — |
| 连续性 | `catalog/skills/review/continuity-quality-review/prompt.md` | — |
| 交叉一致性 | `catalog/skills/review/planning-cross-consistency-review/prompt.md` | — |

审查时 Read 对应 review skill 的 prompt，**必须**也 Read 引用的 craft skill prompt。

## 审查-修复-重审-结束循环（锁定/接受前必须跑通）

锁定或接受前必须通过完整循环，**warning 也必须修复**（不再"记录即放过"）：

1. 审查 candidate → 得到 findings（`blocking` / `warning` / `note`）。
2. **`blocking` 与 `warning` 都必须修复**：修复产生新 revision（candidate），回到步骤 1 重新审查该 revision。
3. **退出条件**：审查结果只剩 `note`（或无 finding）→ 锁定；旧 revision 标 `superseded`。部分唯一索引 `idx_planning_assets_current` 要求同 scope 同时只有一个 `locked`，故**先 supersede 旧版，再 lock 新版**。
4. `note` 记录备查，不阻断、不必修复。

### 修复产生新 revision 的纪律
- 每次修复 = 新 revision（candidate），重审该 revision，不直接改已审查的正文。
- 锁定时旧 revision 标 `superseded`，新 revision 标 `locked` + `locked_review_id`。
- 循环可多轮，直到满足退出条件（无 blocking、无未豁免 warning）。

### warning 的下游豁免（defer_to_downstream）
若某 `warning` 确属**下游执行责任**（当前资产层无法修复，本质是给下游资产的执行边界提醒），可在 finding 中显式标注 `"defer_to_downstream": "<下游 asset_type>"`：
- 主控判断是否豁免：豁免则该 warning 不阻断当前资产锁定，但**必须记录跟踪责任**（哪个下游资产、须兑现什么），并在生成该下游资产时强制检查是否兑现。
- 豁免须有充分理由（当前资产确实无法承载该修复）；能在本资产层修复的 warning 不得豁免，必须进循环。

### 查询未解决项
```sql
-- 未豁免的 warning（仍需进循环修复）
SELECT subject_ref, findings_json FROM reviews
WHERE findings_json LIKE '%warning%'
  AND findings_json NOT LIKE '%defer_to_downstream%';
```
