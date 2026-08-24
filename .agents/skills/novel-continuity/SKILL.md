---
name: novel-continuity
description: 从已接受小说章节提取连续性数据。章节接受后需要更新事实、人物关系、叙事承诺、读者期待或故事弧状态时使用。
---

# 小说连续性

通过 SQLite MCP 操作数据库。SQL 模板见 `novel-project/sql-reference.md`。

## 工作流

1. 确认章节已接受：`SELECT status FROM chapters WHERE id=?` → 必须是 `accepted`。
2. 读取章节正文和当前 Canon：`SELECT content FROM resources WHERE id=(SELECT content_resource_id FROM chapters WHERE id=?)`。
3. 用 sub agent 从章节正文中提取候选：事实（fact）、叙事承诺（promise）、读者期待（expectation）、人物关系（relationship）、故事弧状态（arc）、**人物状态迁移（character_status：退场/转化/休眠/死亡——正文确认才提取，新登场与下落不明不算）**。每项必须有明确来源，不把推测写成事实。
4. 直接写入数据库。SQL 模板以 `novel-project/sql-reference.md`「连续性账本统一模式」为**单一来源**（此处不复制模板，防止两处漂移），写入纪律：
   - 描述文本先存 `resources`（`CAST(? AS BLOB)` + `novelos_hash.py` 算 content_hash），账本行只引用 resource id；
   - 每条必须带 `source_chapter_id` + `source_content_hash` 溯源；
   - 表与列名以 `db/migrations/schema.sql` 为准：`chapter_facts(fact_type/subject/description_resource_id)`、`narrative_promises(promise_key)`、`expectation_ledgers(expectation_key)`、`relationship_states(subject_ref/object_ref/state_resource_id)`、`arc_states(arc_ref/state_resource_id)`。

5. 如果提取的事实与既有 Canon 冲突，列出双方来源让主控决策，不静默覆盖。
6. **character_status 晋升后**：`legacy-python/scripts/novelos_register_characters.py --project <id> --status-update '<json>'` 更新人物注册表（单对象或数组，一章多个迁移一次提交）。条目形如 `{"name": …, "status": dead|departed|transformed|dormant|peripheral|active, "exit_type": 七型之一, "exit_chapter_id": …}`：dead 必须带 死亡型 exit_type；非退场状态（active/peripheral）不带 exit_type，且会整体清空遗留退场痕迹（复活场景）；每次迁移在 state_json.状态史 留审计记录。执行卡预登记的新配角若尚未入库，用 `--entry` 补登。
7. **收尾必跑对账**：`legacy-python/scripts/novelos_register_characters.py --project <id> --pending-status`——比对 promoted 候选集中每人物最新 character_status 候选与注册表现状，非零退出即有漂移（漏跑状态迁移或迁移被回滚），处理完才能开始下一章。

连续性提取不需要独立审查流程——sub agent 直接提取，主控确认后写入。
