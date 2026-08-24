# legacy-python · 过渡期暂存区（待整体删除）

> 零 Python 演进路线的债务标记。本目录内全部代码是**已被替代方案锁定、等待移植**的旧写路径守门人。

## 内容

- `scripts/` — 12 个 py 校验门脚本：`novelos_create_project.py`（jsonschema 门 + BEGIN IMMEDIATE 单事务）、`novelos_compose_prompt.py`（方法论组装器）、`novelos_hash.py`、`novelos_validate_*` ×8、`novelos_propagate_stale.py`、`novelos_register_characters.py`、`novelos_build_adapters.py`、`novelos_delete_project.py`、`novelos_export_kernel_roster.py`，以及 `backup/build_catalog_manifest/check_repository_hygiene/export_novelos_data.py`
- `tests/` — 对应 unittest 用例（JS 门重写时的**验收基准**：行为等价以这些用例的断言语义为准）

## 已删除（不在本目录）

- 视图链：`novelos_render_projection.py`（HTML 成为唯一人类视图）
- Python MCP 通道：`mcp/sqlite-mcp/` + `run_sqlite_mcp.*` + `.codex/config.toml` + `requirements-mcp.txt`

## 退出条件（三件套捆绑交付，缺一不删本目录）

1. **JS 写门**：插件 host 内 `node:sqlite` 单事务落库 + ajv 消费 `config/schemas/*.json`（21 个 schema 原样复用）+ `crypto` 实现 content_hash
2. **写旁路封死**：agent 不再有任何裸 SQL 写通道，唯一入口 = 插件 defineTool
3. **测试等价迁移**：legacy-python/tests 中门相关断言用 vitest 重写并通过

完成之日：`Remove-Item -Recurse -Force legacy-python`，仓库零 Python。
