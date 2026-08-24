# 07.2：Catalog Contract Resource

## 状态

`DONE`

## 前置

`01_source_inventory.md` 必须为 `DONE`。

## 目标

允许 Catalog 包携带可选、只读、严格校验的 `contract.yaml`，但搜索结果仍保持轻量，且不执行 Catalog 内代码。

## 允许修改

- `mcp/novelos/src/novelos_mcp/catalog.py`
- `mcp/novelos/tests/test_catalog.py`
- `mcp/novelos/tests/test_protocol.py`
- `mcp/novelos/tests/test_production_catalog.py`
- 测试临时目录内创建的夹具
- 本文件的状态和实施记录

## 禁止修改

- `mcp/novelos/src/novelos_mcp/server.py` 的 Resource URI 模板；现有 `novelos://catalog/{name}/{artifact}` 已足够。
- `service.py`、Storage、数据库迁移、Agent 数量和来源仓库。
- 加载或执行 `schema.py`、`validator.py`、`review.py`。

## Contract v1 格式

只接受以下字段，未知字段失败关闭：

```yaml
contract_version: 1
inputs:
  - contract: fundamental_rules
    cardinality: one
outputs:
  - growth_and_resource_system
invariants:
  - 不得创建主角免费例外
forbidden_actions:
  - commit_authority
```

约束：

- 顶层字段必须恰好为 `contract_version`、`inputs`、`outputs`、`invariants`、`forbidden_actions`。
- `contract_version` 只能为整数 `1`。
- `inputs` 是对象数组，每项字段必须恰好为 `contract`、`cardinality`。
- `cardinality` 只允许 `one`、`zero_or_one`、`one_or_more`、`zero_or_more`、`exactly_two`、`three_or_more`。
- 其余三个字段是去重的非空字符串数组；允许空数组。
- Contract 只描述方法边界，不授予工具权限，也不成为权威业务数据。

## 实施步骤

1. `CatalogStore._packages()` 发现 `contract.yaml` 时使用 `yaml.safe_load` 并调用独立 `_validate_contract()`。
2. `CatalogStore.get()` 在文件存在时返回 `resources.contract = novelos://catalog/<name>/contract`。
3. `CatalogStore.get_resource()` 的允许映射增加 `contract: contract.yaml`。
4. `search()` 和 `_summary()` 不增加 Contract 内容、输入列表或不变量。
5. Contract 文件继续参与现有 package Hash；修改 Contract 必须使候选快照失效。
6. 增加合法读取、缺字段、未知字段、非法 cardinality、重复字符串、搜索轻量和快照漂移测试。

## 停止条件

- 实现需要改变 MCP Resource URI。
- 实现试图导入 Catalog Python 文件。
- Contract 内容被放进 `skill_catalog.search` 返回值。

## 验证

```bash
PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -p 'test_catalog.py' -v
PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -p 'test_protocol.py' -v
PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -p 'test_production_catalog.py' -v
.venv/bin/python -m compileall -q mcp/novelos/src mcp/novelos/tests
git diff --check
```

## 完成证据

- 新增测试名称：
  - `test_contract_yaml_loading_and_lightweight_search`
  - `test_invalid_contract_yaml_rejected`
  - `test_invalid_contract_cardinality_rejected`
  - `test_duplicate_string_in_contract_rejected`
  - `test_contract_yaml_change_invalidates_snapshot`
- Resource URI 示例：`novelos://catalog/scene-dialogue/contract`
- 快照变化断言：`test_contract_yaml_change_invalidates_snapshot` 验证了修改 `contract.yaml` 时 `snapshot_hash` 发生变化。
- 完整命令结果：`test_catalog.py`（14/14）、`test_protocol.py`（2/2）、`test_production_catalog.py`（8/8）均测试通过；`compileall` 与 `git diff --check` 无错误退出。

