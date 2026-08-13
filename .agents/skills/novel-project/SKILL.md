---
name: novel-project
description: 管理 NovelOS 小说项目、书、卷和章节容器。创建或查询项目层级、定位目标章节、调整项目说明时使用。
---

# 小说项目管理

通过 SQLite MCP 的 `execute_sql` 工具直接操作数据库。SQL 模板见 `sql-reference.md`。

## 工作流

1. **查询项目层级**：`SELECT * FROM projects` → `SELECT * FROM books WHERE project_id=?` → `SELECT * FROM volumes WHERE book_id=?` → `SELECT * FROM chapters WHERE volume_id=?`。
2. **创建项目**：向导 HTML（`mcp/novelos/src/novelos_mcp/ui/project-wizard.html`）产出 JSON →（可选）sub agent 多原型融合 → `scripts/novelos_reconcile.py` 确定性收口 → SQL INSERT projects + creator_profiles + project_creator_bindings。
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

删除前确认无运行中的工作。直接 `DELETE FROM projects WHERE id=?`（ON DELETE CASCADE 级联删除子表）。
