---
name: novel-continuity
description: 从已接受小说章节提取连续性数据。章节接受后需要更新事实、人物关系、叙事承诺、读者期待或故事弧状态时使用。
---

# 小说连续性

通过 node:sqlite 与插件门工具操作数据库（Python MCP 通道已退役）。SQL 模板见 `novel-project/sql-reference.md`。

## 工作流

1. 确认章节已接受：`SELECT status FROM chapters WHERE id=?` → 必须是 `accepted`。
2. 读取章节正文和当前 Canon：`SELECT content FROM resources WHERE id=(SELECT content_resource_id FROM chapters WHERE id=?)`。
3. 用 sub agent 从章节正文中提取候选：事实（fact）、叙事承诺（promise）、读者期待（expectation）、人物关系（relationship）、故事弧状态（arc）、**人物状态迁移（character_status：退场/转化/休眠/死亡——正文确认才提取，新登场与下落不明不算）**。每项必须有明确来源，不把推测写成事实。
4. 直接写入数据库。SQL 模板以 `novel-project/sql-reference.md`「连续性账本统一模式」为**单一来源**（此处不复制模板，防止两处漂移），写入纪律：
   - 描述文本先存 `resources`（content 经 BLOB 写入并按 `'sha256:'+sha256(utf8)` 格式同步 content_hash，node:crypto 计算），账本行只引用 resource id；
   - 每条必须带 `source_chapter_id` + `source_content_hash` 溯源；
   - 表与列名以 `db/migrations/schema.sql` 为准：`chapter_facts(fact_type/subject/description_resource_id)`、`narrative_promises(promise_key)`、`expectation_ledgers(expectation_key)`、`relationship_states(subject_ref/object_ref/state_resource_id)`、`arc_states(arc_ref/state_resource_id)`。

5. 如果提取的事实与既有 Canon 冲突，列出双方来源让主控决策，不静默覆盖。
6. **character_status 晋升后**：经插件门工具 `novelos_register_characters` 更新人物注册表（参数 `project` + `statusUpdate`=JSON 文本，单对象或数组，一章多个迁移一次提交）。条目形如 `{"name": …, "status": dead|departed|transformed|dormant|peripheral|active, "exit_type": 七型之一, "exit_chapter_id": …}`：dead 必须带 死亡型 exit_type；非退场状态（active/peripheral）不带 exit_type，且会整体清空遗留退场痕迹（复活场景）；每次迁移在 state_json.状态史 留审计记录。执行卡预登记的新配角若尚未入库，用 `entries` 参数补登。
7. **收尾必跑对账**：插件门工具 `novelos_register_characters`（`pendingStatus=true` 只读开关）——比对 promoted 候选集中每人物最新 character_status 候选与注册表现状，报告含漂移项即有漏项（漏跑状态迁移或迁移被回滚），处理完才能开始下一章。

连续性候选须经质量审查后才写入：提取 sub agent 只产候选（`node scripts/novelos-compose-prompt.mjs --asset continuity-extraction --subject <chapter_ref>` 注入 subject+canon_minimal），主控将候选交独立审查（`--asset continuity-quality-review`，同样注入 canon_minimal 供审查者对照 Canon 判漂移）——条目拒绝进修订循环，通过后按第 4 步纪律落库。配方矩阵权威见 `config/agent-recipes.json` 的 continuity-extraction / continuity-quality-review 两资产。
