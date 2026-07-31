# 07.4：首批世界架构方法

## 状态

`DONE`

## 前置

- `03_review_profile_routing.md` 必须为 `DONE`。
- `execution_manifest.csv` 中目标行必须由 主控智能体 在授权确认后改为 `status=ready`。
- 来源 commit 和 Prompt Hash 必须与 manifest 完全一致。

## 目标

将首批世界架构方法适配为隔离的 Catalog 候选，补充底层规则、成长资源、社会权力、多体系交互、因果结构、读者期待和视角基调能力。

## 允许修改

- `catalog/skills/expansions/world-rule-system/**`
- `catalog/skills/expansions/world-growth-resource/**`
- `catalog/skills/expansions/world-social-power/**`
- `catalog/skills/expansions/world-system-interaction/**`
- `catalog/skills/expansions/story-expectation-design/**`
- `catalog/skills/expansions/story-causal-structure/**`
- `catalog/skills/expansions/story-pov-tone-contract/**`
- `mcp/novelos/tests/test_production_catalog.py`
- `tests/test_prompt_catalog_boundaries.py`
- `tasks/07_prompt_catalog/execution_manifest.csv` 的本批 `status` 和证据列
- 本文件的状态和实施记录

## 禁止修改

- 来源仓库、现有生产 Prompt、Agent 配置、Storage 和数据库。
- 迁移 manifest 未列出的 Worldbuilding 包。
- 直接复制 `schema.py`、`validator.py`、`review.py` 或运行其中代码。
- 在质量证据完成前设置 `lifecycle: active`；首批一律先设为 `experiment`。

## 精确来源映射

只执行 manifest 中 `batch=world-1` 且 `status=ready` 的行。多个来源映射同一目标时，写入一个 `provenance.yaml` 主来源和有序 `additional_sources`，不得生成重复目标包。

## 边界夹具

在 `tests/test_prompt_catalog_boundaries.py` 固定以下选择用例，不调用在线模型：

- `single-system-cost`：一个有训练、资源、失败和反制的能力体系，应允许规则与成长资源方法，不允许双/多体系分支。
- `dual-system-contact`：两个独立体系发生翻译冲突，应允许交互方法并要求保留双方原始成本。
- `realist-no-power`：现实题材且无超自然体系，不得强制选择成长资源或力量交互方法。
- `social-control`：资源由制度垄断并产生阶层冲突，应允许社会权力方法。

测试只验证 metadata、Contract、选择条件和禁止边界，不把它描述为 LLM 文学质量通过。

## 实施步骤

1. 对每行用 `git show <source_ref>:<source_path>` 读取 Prompt 并复算 Hash；不一致立即停止整批。
2. 按目标包职责合并方法，删除旧 Runtime、批准、提交、数据库和固定流水线说明。
3. 为每包编写轻量 metadata、适配后的 prompt、严格 provenance 和 `contract.yaml`。
4. 只有机器消费结果才转换为 `typed_result`；否则使用 `document`，不为追求结构化强制大型 Schema。
5. 将来源 Pydantic 字段作为设计参考人工转换为 JSON Schema；禁止导入来源模块生成 Schema。
6. 运行边界夹具和 Catalog 测试；结果通过后仍保持 `experiment`，等待独立质量评估再决定 active。

## 停止条件

- 任一行不是 `status=ready`。
- 授权字段不是明确允许复制/适配的值。
- 来源 Hash 不匹配或来源路径来自工作树未提交包。
- 合并后无法维持单一职责或需要修改规划资产模型。

## 验证

```bash
PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -p 'test_production_catalog.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_prompt_catalog_boundaries.py' -v
.venv/bin/python -m compileall -q catalog mcp/novelos/src mcp/novelos/tests tests
git diff --check
```

## 完成证据

- 用户授权：明确确认来源授权许可，Manifest 中 W01~W11 均设为 `user_authorized` 与 `status=ready`。
- 交付包（7 个 Wave-D 实验包）：
  1. `world-rule-system` (hash: `sha256:b09ee30290376501b46bfde6f16c06647f21e1421c9bc27ecdbb47f2e22706b0`)
  2. `world-growth-resource` (hash: `sha256:b78f6d9d663f2dcb6c9785b03be06631c1a8dbae727dfb97cc203a3e8c2bc714`)
  3. `world-social-power` (hash: `sha256:af86502b190dc6de19f7dbe5ad5409c59a563a178aafa324de116ccf0652ce91`)
  4. `world-system-interaction` (合并 W04, W05, W06)
  5. `story-expectation-design` (合并 W07, W08)
  6. `story-causal-structure` (hash: `sha256:e98d50a736cba695eb892f4510f9794d4edbef4a3aaf239081ced794709847e2`)
  7. `story-pov-tone-contract` (合并 W10, W11)
- 测试验证：`tests/test_prompt_catalog_boundaries.py` 固定选择夹具测试 100% 通过。

