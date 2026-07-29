---
name: novel-project
description: 管理 NovelOS 小说项目、书、卷和章节容器。创建或查询项目层级、定位目标章节、调整项目说明，或需要判断某项操作属于容器管理还是小说语义规划时使用。
---

# 小说项目

只管理创作容器和定位信息；不要生成故事方向、卷纲或正文。

## 工作流

1. 先用 `project.list/get`、`book.list/get`、`volume.list/get`、`chapter.list/get` 定位已有对象，避免重复创建。
2. 只有用户明确要求创建时，才调用对应的 `*.create` 工具。修改项目时携带当前 `expected_version`。
3. 返回新建或定位到的精确 ID、版本和状态；长内容只返回 `resource_ref`。
4. 遇到故事方向、架构、人物契约、卷纲或章纲请求时，转交 `$novel-planning`。
5. 遇到正文请求时，先确认有效 Chapter Plan，再转交 `$novel-memory` 和 `$novel-writing`。

不要为一次容器查询或创建临时 Agent，也不要直接访问数据库或文件。
