# Task 03：Skill Catalog 迁移

状态：`DONE`

## 完成结论

- 顶层业务入口固定为 `novel-project`、`novel-planning`、`novel-memory`、`novel-writing`、`novel-review`、`novel-continuity`。
- 细粒度创作方法进入 `catalog/skills/`，按 stage、asset、capability、题材和 scope 检索。
- 搜索只返回轻量候选；Prompt、Schema 和 examples 在选择后通过 Resource 按需读取。
- Catalog 强制唯一名称、严格 metadata、来源信息、候选快照绑定和 typed output 校验。
- 138 个来源 Skill 均有明确 disposition；未核权和实验内容不进入生产候选。

## 验收结果

- [x] 六个顶层 Skill 职责清晰且不持久化。
- [x] 八类规划资产均有可用 Catalog 方法。
- [x] 普通检索不加载完整 Prompt 或大型 JSON。
- [x] 高风险输出保持严格 Schema 和失败关闭行为。

## 证据

- 顶层 Skill：`.agents/skills/`。
- 生产 Catalog：`catalog/skills/`。
- 来源 disposition：[`migration/catalog_disposition.csv`](./migration/catalog_disposition.csv)
- Catalog 与 Skill 测试：`tests/test_project_skills.py`、`mcp/novelos/tests/test_catalog.py`、`test_production_catalog.py`。
