# `seed.db` 授权审计

结论：`authorized`。用户于 2026-07-29 在当前任务中明确允许复制完整 `seed.db` 并用于 NovelOS 本地生产检索，同时确认其有权作出该授权。

## 已确认事实

- 固定来源 commit：`902d7e62f55bc8bc2862e2b9574b5ee2f5f33403`。
- 来源路径：`backend/src/infrastructure/sqlite/seed.db`。
- 来源文件未偏离固定 commit，SHA-256 为 `59c7af0bca916824e3b4ff272da918cda1e4deb485b9ff46ed4faadba2a7c53a`。
- `PRAGMA quick_check=ok`；23 张 `kb_*` 表合计 8,108 条记录。
- 来源仓库固定快照没有根级 `LICENSE`、`COPYING` 或 `NOTICE`。
- 文件历史只有 `fe3b36097f2f2a7390e443978b5202423b4d66da` 的一次二进制新增，提交信息没有声明数据许可或来源授权。
- `docs/database_design.md` 和 `knowledge_repo.py` 将其描述为 “NWriter” 写作知识库。
- 多张表包含 `book_source`，语料表包含 `source_url`，并存在 `kb_corpus_excerpts`；数据库 Schema 中没有 `license`、`copyright` 或等价授权字段。

## 授权范围

授权只绑定以下精确来源，不扩展到来源仓库的其他未核权文件：

- commit：`902d7e62f55bc8bc2862e2b9574b5ee2f5f33403`
- 路径：`backend/src/infrastructure/sqlite/seed.db`
- SHA-256：`59c7af0bca916824e3b4ff272da918cda1e4deb485b9ff46ed4faadba2a7c53a`
- 允许操作：复制到 `mcp/novelos/resources/seed.db`，并通过只读 MCP 在本地生产使用。
- 不包含：公开再分发、改变来源归属，或自动授权 `catalog_disposition.csv` 中其他 `defer-license` 内容。

生产 runner 固定使用目标副本和冻结清单，不直接读取 `/Users/yiyi/github/novelos`，也不允许用环境变量替换为另一份未审计数据库。

## 完整性证据

`seed_source_inventory.json` 由以下命令从只读 `immutable=1` 连接生成：

```bash
.venv/bin/python scripts/build_seed_inventory.py --check
```

清单生成器与 MCP 运行时共用 `novelos_mcp.seed_inventory` 的确定性算法。来源清单继续保留原始绝对路径作为盘点证据；生产清单保留固定 commit 内的相对来源路径，并绑定目标副本的相同文件、Schema 和内容 Hash。
