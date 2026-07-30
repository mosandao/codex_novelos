# 07.1：来源 Prompt 清单

## 状态

`DONE`

## 目标

用固定来源提交和独立工作树清单生成可重算的 Prompt inventory。不得复制 Prompt 内容，不得改变现有迁移快照。

## 精确输入

- 来源仓库：`/Users/yiyi/github/novelos`
- 固定提交：读取 `tasks/migration/source_snapshot.toml` 的 `source_commit`，预期为 `902d7e62f55bc8bc2862e2b9574b5ee2f5f33403`。
- 已提交 disposition：`tasks/migration/catalog_disposition.csv`，预期 138 行。
- 首批映射：`tasks/07_prompt_catalog/execution_manifest.csv`。

## 允许修改

- `scripts/build_prompt_migration_inventory.py`
- `tasks/07_prompt_catalog/source_prompt_inventory.csv`
- `tests/test_prompt_migration_inventory.py`
- 本文件的状态和实施记录

## 禁止修改

- `/Users/yiyi/github/novelos/**`
- `tasks/migration/**`
- `catalog/**`、`config/**`、`mcp/**`
- `tasks/07_prompt_catalog/execution_manifest.csv` 的决策字段

## 输出字段

`source_prompt_inventory.csv` 固定使用以下列并按 `source_state,source_path` 排序：

```text
source_state,source_ref,source_path,source_hash,metadata_path,lifecycle,license_origin,existing_disposition
```

- `committed` 行必须用 `git show <commit>:<path>` 读取并计算 Prompt SHA-256。
- `worktree_uncommitted` 行记录新增包当前文件 Hash；`worktree_modified` 行记录相对固定提交发生变化的已有 Prompt。两类行的 `source_ref` 均为 `WORKTREE`，`existing_disposition` 均为 `excluded_from_committed_source`。
- 不扫描 `nwriter/*.md` 等没有 `metadata.yaml` 的旧散文件；把数量作为检查结果记录，不纳入 Catalog Prompt inventory。

## 实施步骤

1. 新增脚本，支持默认写入和 `--check` 两种模式；`--check` 只比较预期内容，不写文件。
2. 已提交包只从 `git ls-tree` 和 `git show` 读取，不读取来源工作树同路径文件。
3. 将提交内 Prompt 与 `catalog_disposition.csv` 按 Skill 目录关联；缺失或重复关联立即失败。
4. 从 `git status --porcelain` 识别未提交且同时具有 `metadata.yaml`、`prompt.md` 的新增包，以及已跟踪但内容变化的 Prompt，分别追加为 `worktree_uncommitted` 和 `worktree_modified` 行。
5. 原子写入 CSV，换行固定为 LF，编码 UTF-8，输出稳定排序。
6. 测试固定提交恰好 138 行、`source_state + source_path` 唯一、Hash 格式正确；工作树新增或修改行不得改变 committed 计数。

## 停止条件

- `source_commit` 不存在或不是 40 位 Git commit。
- 固定提交 Skill 数不等于 138。
- 已提交路径与 disposition 无法一一对应。
- 脚本需要写入来源仓库才能工作。

## 验证

```bash
.venv/bin/python scripts/build_prompt_migration_inventory.py --check
.venv/bin/python -m unittest discover -s tests -p 'test_prompt_migration_inventory.py' -v
git diff --check
```

## 完成证据

- `committed`: 138
- `worktree_uncommitted`: 12
- `worktree_modified`: 1
- `adapt-authorized`: 8
- `defer-license`: 92
- `defer-experiment`: 38
- 所有验证命令（`build_prompt_migration_inventory.py --check`、`test_prompt_migration_inventory.py` 和 `git diff --check`）均无错误通过。

