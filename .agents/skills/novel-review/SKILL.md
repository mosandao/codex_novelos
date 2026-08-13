---
name: novel-review
description: 独立审查不可变小说资产并生成 Review Receipt。规划资产锁定、章节接受、连续性事实晋升前，或需要检查 Canon、人物、世界规则、节奏和文本质量时使用。
---

# 小说审查

通过 SQLite MCP 操作数据库。SQL 模板见 `novel-project/sql-reference.md`。

## 工作流

1. 接收审查目标（资产或章节的 ID）和审查维度（Review Profile 对应的方法论）。
2. Read `catalog/skills/review/<对应 review skill>/prompt.md` 获取审查标准。
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

## 审查后处理

- `blocking` finding：修改后重新审查，不能锁定/接受。
- `warning` finding：不阻断，但记录在 reviews 表。用 `SELECT * FROM reviews WHERE findings_json LIKE '%warning%'` 可查未解决 warning。
- `note`：记录备查。
