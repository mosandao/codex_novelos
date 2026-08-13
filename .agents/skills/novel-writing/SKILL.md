---
name: novel-writing
description: 根据已锁定 Chapter Plan 和已确认 Canon 上下文起草或修改小说正文。续写完整章节、撰写长场景、调整文风时使用。
---

# 小说写作

通过 SQLite MCP 操作数据库。SQL 模板见 `novel-project/sql-reference.md`。

## 工作流

1. 接收已锁定 Chapter Plan（SELECT planning_assets 读取）、精选上下文（`$novel-memory`）、Creator Profile 签名和 Direction。Read `catalog/skills/writing/chapter-draft-generation/prompt.md` 获取方法论和硬约束。
2. 将已确认上游与 Canon 视为约束。缺少关键材料时返回 context gap。
3. 完整章节由 Main Agent 创建 sub agent（Writer）执行；局部改句可直接处理。
4. 写作时保持人物动机、知识边界、地点规则、时间顺序、伏笔和场景状态变化一致。通过选择和后果表现 `book_soul`、`soul_pressure` 与 `moral_residue`；不要自行创造作者思想。
5. 产出正文后：
   ```sql
   -- 存内容
   INSERT INTO resources (id, media_type, content, content_hash) VALUES (?, 'text/markdown', CAST(? AS BLOB), ?);
   -- 创建/更新章节
   INSERT INTO chapters (id, volume_id, number, title, status, content_resource_id, summary, metadata_json, version)
   VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, 1);
   -- 改已有章节：直接更新
   UPDATE chapters SET content_resource_id = ?, summary = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?;
   ```
   content_hash 用 `scripts/novelos_hash.py` 计算。
6. 交给 `$novel-review` 审查。审查通过后接受：`UPDATE chapters SET status='accepted', version=version+1 WHERE id=?`。

修改已接受章节：直接 UPDATE content_resource_id 指向新 resource（不需要重开 draft → review → accept 全流程，除非改动改变章节状态）。

Writer 不接受、锁定或晋升任何结果——这些都是主控的职责。
