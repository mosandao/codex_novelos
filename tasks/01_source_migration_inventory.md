# Task 01：源工程迁移盘点

状态：`DONE`

## 完成结论

- 来源仓库固定为 `/Users/yiyi/github/novelos`，迁移期间保持只读。
- 只使用 commit `902d7e62f55bc8bc2862e2b9574b5ee2f5f33403` 的已提交内容。
- 来源 tree 为 `3d0d32221a9d5332dd25a82868b840469288be60`。
- 1,260 个已提交文件均具有唯一迁移 disposition；108 个 dirty 状态项全部排除并单独记录。
- 37 张主表、138 个 Skill 以及授权和测试映射均已盘点。

## 验收结果

- [x] 每个来源文件都有 commit、SHA-256、处理方式和目标信息。
- [x] `direct`、`adapt` 条目具有测试映射且目标路径无冲突。
- [x] 未核权内容失败关闭。
- [x] 旧 Agent Runtime、LLM、Presentation 和 Frontend 明确拒绝迁移。

## 证据

- 来源快照：[`migration/source_snapshot.toml`](./migration/source_snapshot.toml)
- 文件清单：[`migration/source_manifest.csv`](./migration/source_manifest.csv)
- dirty 清单：[`migration/dirty_inventory.csv`](./migration/dirty_inventory.csv)
- Skill 清单：[`migration/skill_inventory.csv`](./migration/skill_inventory.csv)
- 数据表清单：[`migration/table_inventory.csv`](./migration/table_inventory.csv)
