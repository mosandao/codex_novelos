---
name: novel-project
description: 管理 NovelOS 小说项目、书、卷和章节容器。创建或查询项目层级、定位目标章节、调整项目说明时使用。
---

# 小说项目管理

通过 node:sqlite 操作数据库（读写均走受控 SQL，模板见 `sql-reference.md`；Python MCP 通道与插件门工具均已退役）。

## 工作流

1. **查询项目层级**：`SELECT * FROM projects` → `SELECT * FROM books WHERE project_id=?` → `SELECT * FROM volumes WHERE book_id=?` → `SELECT * FROM chapters WHERE volume_id=?`。
2. **创建项目**：主控与用户确认约束后产出 `novelos.project.create.v3` 形态的 JSON → 主控运行 `node scripts/novelos-compose-prompt.mjs --asset fusion --payload <json>` 产出完整注入文本（方法论主干 + 按项目条件路由的模块 + 输入数据区：选中原型条目全文 / 全库一行式清单 / `user_persona_hints` / `project_setup`（v2）/ 按量化范围取数的 `existing_persona_fingerprints`），整段注入引导融合智能体（onboarding_agent）sub agent → 落库前对照 `config/schemas/*.json` 自查（见 AGENTS.md「项目创建向导」）→ 主控以 node:sqlite 单事务直写落库：先建核/修订内核，分身派生后六表落库（模板见 `sql-reference.md`「作者内核链」「作者签名链」）。**不再手工 Read prompt.md 拼注入**。
3. **创建章节容器**：INSERT resources（存内容）→ INSERT chapters。
4. **判断操作类型**：容器管理（项目/书/卷/章节的 CRUD）用 SQL 直接操作；小说语义规划（方向/架构/策略/人物/世界/卷纲/章纲）加载 `$novel-planning`。

## 数据库表速查

| 表 | 内容 |
|---|---|
| `projects` | 项目容器 |
| `books` / `volumes` / `chapters` | 书→卷→章层级 |
| `resources` | 不可变内容存储（BLOB，正文/规划/JSON） |
| `planning_assets` | 8 类规划资产 |
| `reviews` | 审查 Receipt |
| `creator_profiles` / `project_creator_bindings` | 作者签名绑定 |

完整 SQL 模板见 [sql-reference.md](./sql-reference.md)。

## Creator Profile 绑定

项目创建时绑定 Creator Profile（作者签名）。绑定后 `style_refs` 包含 Creator Profile ref 和 Direction ref，Writer 必须遵守。

```sql
-- 查项目绑定
SELECT * FROM project_creator_bindings WHERE project_id = 'project:xxx';
-- 查 Creator Profile 签名
SELECT * FROM creator_profile_versions WHERE profile_id = (
    SELECT profile_id FROM project_creator_bindings WHERE project_id = 'project:xxx'
);
```

## 删除项目

删除前确认无运行中的工作。由主控以 node:sqlite 显式事务按依赖逆序逐表删（projects/books/volumes/chapters/planning_assets/characters/worlds/reviews/连续性账本/resources，`foreign_keys=OFF` 执行后恢复 ON），先备份库文件；禁止随手 DELETE 产生孤儿。
