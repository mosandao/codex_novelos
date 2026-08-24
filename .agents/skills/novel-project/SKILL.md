---
name: novel-project
description: 管理 NovelOS 小说项目、书、卷和章节容器。创建或查询项目层级、定位目标章节、调整项目说明时使用。
---

# 小说项目管理

通过 node:sqlite 只读查询数据库（Python MCP 通道已退役）；写路径唯一入口 = `dsh-novelos-viewer` 插件六个门工具（见 AGENTS.md「数据库访问」）。SQL 模板见 `sql-reference.md`。

## 工作流

1. **查询项目层级**：`SELECT * FROM projects` → `SELECT * FROM books WHERE project_id=?` → `SELECT * FROM volumes WHERE book_id=?` → `SELECT * FROM chapters WHERE volume_id=?`。
2. **创建项目**：向导 HTML（`plugin/client/project-wizard.html`，或面板「项目向导」）产出 JSON → 主控运行 `node scripts/novelos-compose-prompt.mjs --asset fusion --payload <json>` 产出完整注入文本（方法论主干 + 按项目条件路由的模块 + 输入数据区：选中原型条目全文 / 全库一行式清单 / `user_persona_hints` / `project_setup`（v2）/ 按量化范围取数的 `existing_persona_fingerprints`），整段注入引导融合智能体（onboarding_agent）sub agent → 经插件门工具落库：先 `novelos_gate_entry` 校验向导 payload（只读），mode=create 时 `novelos_kernel_commit` 建核/修订内核，分身派生后 `novelos_project_commit` 单事务六表落库。**不再手工 Read prompt.md 拼注入**（详见 AGENTS.md「项目创建向导」第 4-5 步）。
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

删除前确认无运行中的工作。用插件门工具 `novelos_delete_project`（参数 `project`；建议先 `dryRun:true` 调查影响面、`backup:true` 备份库文件）——禁止手工 DELETE 绕过门。
