---
name: novel-review
description: 独立审查不可变小说资产并生成 Review Receipt。规划资产锁定、章节接受、连续性事实晋升前，或需要检查 Canon、人物、世界规则、节奏和文本质量时使用。
---

# 小说审查

通过 node:sqlite 操作数据库（读=只读查询；回执落库走受控 SQL，插件门工具已退役）。SQL 模板见 `novel-project/sql-reference.md`。

## 工作流

1. 接收审查目标（资产或章节的 ID）和审查维度（Review Profile 对应的方法论）。
2. 审查标准获取（按资产分流，以 `scripts/novelos-compose-prompt.mjs` 的 **ASSET_DIRS 注册表**为准）：**已注册审查**（direction-review / architecture-review 及后续）用组装器 `--asset <asset>-review --project <project_id> --subject <被审资产ID>`——检查清单 + 随项目路由的条件审查模块 + 被审对象全文 + 上游原文一步产出，与生成端对称；**未注册审查**暂仍 Read `catalog/skills/review/<对应 review skill>/prompt.md` + 手工注入 subject 与上游原文，Task 29 P2 完成后逐一切换。
3. 审查 sub agent 需要**完整的审查依据**：候选正文全文 + 全部已锁定上游原文。直接从数据库 SELECT resources 读取，注入 sub agent prompt。禁止让 sub agent 自行读文件。
4. 按 review prompt 的检查维度逐项审查。finding severity 四档：`blocking` / `warning` / `note`（问题分级）与 `strength`（记录候选独有赌注与亮点，供选型与修复参考，不阻断不修复）；问题类 finding 给出最小直接证据和原文片段，strength 可引用候选对比与推理但须写明依据。
5. 只要有 `blocking`，verdict 必须是 `rejected`。
6. 记录审查结果——主控按 sql-reference.md「审查」模板以受控 SQL 落库：
   - `subjectRef`：被审对象 ID（`planning:xxx` 或 `chapter:xxx`；对象必须已落库）
   - `verdict`：`approved` 或 `rejected`
   - `findingsJson`：`[{"severity":"note","message":"...","evidence_refs":["..."]}]` JSON 数组文本（severity 取 blocking/warning/note/strength；豁免标记见下文豁免通道）
   - `reviewerProfile`：审查者身份，必须携带模型身份前缀——`model:<provider:model>`（异构厂商模型直审，防共谋）或 `agent:<name>@<model>`（具名审查 agent）；匿名裸字符串（如 `prose-v1`）拒绝落库
   - 可选 `evidenceRefsJson`（证据引用数组）、`metadataJson`
   - `subject_hash` 取被审对象库内资源的 content_hash 溯源锚点；落库后把 `reviewId` 交给锁定/接受步骤引用
   - 回执落库前主控先跑 G2 引文验证：`node scripts/novelos-verify-review-evidence.mjs --receipt <回执JSON> --draft <该版草稿>`，FATAL（excerpt 无命中/缺失/subject_hash 错配/空 findings+approved 空查回执——R7-A1 起默认拦截，确需放行空回执加 `--allow-empty`，输出留痕豁免字样）即打回重审、不得落库；该验证只管证据存在性与版本绑定，不验证相关性（归主控/红方抽查）

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
2. **`blocking` 与 `warning` 都必须修复**：修复产生新 revision（candidate），回到步骤 1 重新审查该 revision。**修复经组装器受控重试**：`node scripts/novelos-compose-prompt.mjs --asset <asset> --project <id> --review-feedback <上轮回执.json> --round <N>`——回执的 blocking+warning 注入 review_feedback 槽（note 不注入），组装日志记录轮次。
3. **退出条件**：审查结果只剩 `note`（或无 finding）→ 锁定；旧 revision 标 `superseded`。部分唯一索引 `idx_planning_assets_current` 要求同 scope 同时只有一个 `locked`——锁定 SQL 必须在单事务内**先翻旧 locked 为 superseded，再置新行 locked**（先 supersede 后 lock，模板见 sql-reference.md「规划资产」）。
4. `note` 记录备查，不阻断、不必修复。

### 循环边界（防无限打转，必须执行）

- **轮次上限**：同一 subject 默认 **3 轮**未收敛 → 停止循环，升级用户裁决（附各轮 blocking 摘要）。禁止无限重试。
- **同因复发检测**：本轮 blocking 与上一轮同因（同一问题未解决或换个说法复发）→ **直接升级**，不再重试——修复手段无效的信号，换手段或人工介入。
- 主控在每次重审前查上轮回执做同因判定；`--round` ≥ 3 时组装器日志已标记轮次，主控须核对升级条件后再组装。

### 修复产生新 revision 的纪律
- 每次修复 = 新 revision（candidate），重审该 revision，不直接改已审查的正文。
- 锁定按受控 SQL：单事务内把旧 revision 翻 `superseded`、新 revision 置 `locked` 并绑定 `locked_review_id`（模板见 sql-reference.md「规划资产」）。
- 循环可多轮，直到满足退出条件（无 blocking、无未豁免 warning）。
- **修复不得削平 strength 指认的特质**：上轮回执中 strength 标记的独有赌注是设计意图，修复其他问题时不得顺手抹平（表里反差、激进节奏等被 strength 认定的棱角）。

### 生成侧异议（辩护回合）
修复不是单向服从：主控（或生成 agent）认为某 finding 误判或属有意取舍时，可将异议回传审查 agent **复核一次**（指出 finding 与候选原文的冲突点）。复核后维持原判则进修复或豁免通道，争议不决升级用户裁决——禁止以「审查说了算」静默服从，也禁止以「生成进行中」拒绝异议。

### 横向回执（多候选并列资产）
direction 等按方法论产出多候选供用户裁决的资产：逐候选审查独立出回执，主控收集同轮全部回执后**汇总横向比较呈报用户**（最强候选 / 实质差异维：两难·组织原则·情感登记·承诺类型 / 推荐序 + 各候选 strength 摘要），用户裁决选定后仅对选定候选走锁定循环。未选定候选不锁定，留档备查。

### warning 的豁免通道（两种，均须显式记录）

**① 下游豁免（defer_to_downstream）**：若某 `warning` 确属**下游执行责任**（当前资产层无法修复，本质是给下游资产的执行边界提醒），可在 finding 中显式标注 `"defer_to_downstream": "<下游 asset_type>"`：
- 主控判断是否豁免：豁免则该 warning 不阻断当前资产锁定，但**必须记录跟踪责任**（哪个下游资产、须兑现什么），并在生成该下游资产时强制检查是否兑现。
- 豁免须有充分理由（当前资产确实无法承载该修复）；能在本资产层修复的 warning 不得豁免，必须进循环。

**② 艺术风险豁免（accepted_risk）**：若某 `warning` 指向的是**有意的创作取舍**（大胆的表里反差、激进慢热、负向承诺主导等 strength 认定的设计意图被审查判为风险），不得静默修复削平，走显式豁免：
- finding 标注 `"accepted_risk": true`，**呈报用户确认**（说明风险与对应的 strength/设计意图）后记录 `"accepted_by": "user"`；未获用户确认不得豁免。
- 豁免后该 warning 不阻断锁定；用户否决则进修复循环。
- 适用边界：方法论硬约束（schema 完整性、两难结构、血缘真实性）不得用 accepted_risk 豁免——只有「方向选择类」风险可豁免。

### 查询未解决项
```sql
-- 未豁免的 warning（仍需进循环修复）
SELECT subject_ref, findings_json FROM reviews
WHERE findings_json LIKE '%warning%'
  AND findings_json NOT LIKE '%defer_to_downstream%'
  AND findings_json NOT LIKE '%accepted_risk%';
```
