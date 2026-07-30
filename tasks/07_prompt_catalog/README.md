# Task 07 子任务索引

## 执行规则

- 历史子任务 `01` 到 `05` 已完成。当前只执行 `08`，完成后重新执行 `06`；不得跳过 `08` 直接收口。
- 开始时把当前子任务状态从 `TODO` 改为 `IN PROGRESS`；只有全部验收项和证据完成后才能改为 `DONE`。
- 只修改子任务“允许修改”中的路径；其他变化视为越界。
- `/Users/yiyi/github/novelos` 始终只读。读取已提交来源必须使用固定 commit，不得用工作树内容代替。
- `execution_manifest.csv` 中只有 `status=ready` 的迁移行可以复制或适配内容。
- `blocked-license` 必须等待明确授权；`blocked-source-freeze` 必须等待来源提交和快照更新；`deferred` 不执行。
- 不创建新 Agent，不直接访问 SQLite，不执行来源仓库中的 Python。
- 失败时保留失败命令、错误摘要和未满足条件；不得把部分结果标为完成。

## 顺序

| 子任务 | 产物 | 前置 |
|---|---|---|
| [01 来源 Prompt 梳理与盘点](./01_source_inventory.md) | 盘点来源 Prompt、生命周期与授权门禁 | `DONE` |
| [02 Contract 资源暴露](./02_contract_resource.md) | 暴露 Catalog Contract 资源与校验接口 | `DONE` |
| [03 Review Profile 与 Routing](./03_review_profile_routing.md) | 补齐 16 个 Profile 的 Review 包路由 | `DONE` |
| [04 设定与架构 Prompt 批次适配](./04_worldbuilding_batch.md) | 适配 Worldbuilding/Architecture Prompt 批次 | `DONE` |
| [05 写作与润色 Prompt 批次适配](./05_writing_batch.md) | 适配 Writing/Polishing Prompt 批次 | `DONE` |
| [06 总验收与收口](./06_acceptance.md) | 全量自动化测试与完成度验收 | `TODO` |
| [07 质量修正](./07_quality_remediation.md) | 首次质量修正已执行，二次复核进行中 | `IN PROGRESS` |
| [08 二次复核修正参考](./08_reaudit_remediation.md) | F1-F6 二次复核全量修正与质量证据 | `IN PROGRESS` |

## 规约

子任务状态只使用 TODO、IN PROGRESS、DONE 或 BLOCKED。08 与全量重算验收通过后，才允许将 07 与父任务恢复为 DONE。
