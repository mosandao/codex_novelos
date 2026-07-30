# 07.6：总验收与收口

## 状态

`DONE`

2026-07-30 完成 `08_reaudit_remediation.md` 治理并重新通过全量验收。

## 前置

`01` 至 `05`、`07` 和 `08` 已全部为 `DONE`。

## 目标

验证 Prompt Catalog 扩展没有破坏来源边界、Agent 权威、轻量检索、Review 路由和现有纯 Codex 工作流，并把可重算证据写回任务文件。

## 允许修改

- `tasks/07_prompt_catalog/**`
- `tasks/07_prompt_catalog_expansion.md` 的状态和实施记录
- `tasks/README.md` 的 Task 07 状态
- `tasks/migration/catalog_disposition.csv`，仅限已经完成授权、迁移和证据验证的来源行
- `documentation/architecture.md`
- `documentation/flows.md`
- `documentation/tests.md`
- `tests/test_catalog_manifest.py`
- `tests/test_repository_hygiene.py`

## 禁止修改

- 为通过测试删除失败关闭断言。
- 把 `experiment` 包计入生产覆盖或描述为生产可用。
- 把 worktree 未提交来源写入固定 commit provenance。
- 把延期 70-case 实验描述为已完成。

## 验收步骤

1. 运行 inventory `--check`，确认固定来源和工作树来源分离。
2. 校验所有 migrated/adapted provenance 的 commit、路径、内容 Hash 和授权字段。
3. 校验普通 Catalog 搜索不返回 Prompt、Schema、Contract 或 examples 内容。
4. 校验 Contract 和 Review Route 修改都会使候选快照或配置测试失败关闭。
5. 校验所有临时 Agent 工具仍是只读面，只有 Main Agent 可调用权威写入。
6. 修改 `test_production_catalog.py` 时不得继续断言 Catalog 包总数等于固定集合；改为断言核心必需包存在、名称唯一、active 包合法、experiment 默认不可见。
7. 更新文档，只描述实际完成并通过测试的能力。
8. 所有命令通过后，依次把本子任务、父 Task 和 `tasks/README.md` 标为 `DONE`。

## 完整验证

```bash
PYTHONWARNINGS='error::ResourceWarning' .venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/build_prompt_migration_inventory.py --check
git diff --check
```

## 必须记录的证据

- 测试汇总：根测试 48 个，MCP 测试 102 个，共计 150 项单元测试 100% 通过。
- 来源统计：inventory (138 提交 + 12 未提交 + 1 修改)，disposition (21 adapt-authorized, 80 defer-license, 37 defer-experiment) 三方完全一致。
- Review 路由与资源：16 个 Review Profile 稳定映射；8 个 Planning Profile 精确绑定 `[planning-quality-review, <唯一专项包>]`。
- Catalog 包：29 个 active 生产包，8 个 Wave-D experiment 包。
- 质量评估：`eval_results.json` 保持 Fail-Closed 诚实 `BLOCKED` 状态 JSON（因为缺真实 API 环境）。

## 停止条件

- 任一验证命令失败。
- manifest 中存在被错误改为 ready/done 的未授权或未提交来源。
- 文档描述超过实际生产能力。

