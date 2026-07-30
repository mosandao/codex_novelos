# 07.5：首批写作方法

## 状态

`DONE`

## 前置

- `04_worldbuilding_batch.md` 必须为 `DONE`。
- `execution_manifest.csv` 中 `batch=writing-1` 的行必须经授权后变为 `status=ready`。

## 目标

把来源写作、重写和自检方法归并为少量 Catalog 包，增强现有正文工作流，不恢复旧 Writer Runtime。

## 允许修改

- `catalog/skills/wave-d/prose-revision/**`
- `catalog/skills/wave-a/prose-quality-review/**`
- `mcp/novelos/tests/test_production_catalog.py`
- `tests/test_prompt_catalog_boundaries.py`
- `tasks/07_prompt_catalog/execution_manifest.csv` 的本批 `status` 和证据列
- 本文件的状态和实施记录

## 禁止修改

- Writer Agent 数量、章节接受流程、Review Receipt、Storage 和来源仓库。
- `writer-generate-v2`、`chapter-review-v2` 等实验包。
- 将“humanizer”实现为统一短句、同义词替换或删除所有口语特征。
- 让 Writer 自己批准正文或让 Review Prompt 重写正文。

## 精确归并

- `writer-rewrite` 与 `humanizer` 合并为 `prose-revision`，只生成修订候选。
- `writer-self-check` 与 `scroll_analysis` 只在授权和边界审查通过后增强现有 `prose-quality-review`；不得改变其 typed input/output Schema。
- 已迁移的对话、打斗、节奏、标点和移动端格式包不重复复制。

## 固定边界用例

- `voice-preservation`：修订不得统一角色口吻或改变人物知识边界。
- `canon-preservation`：修订不得改变事实、时间、地点、关系和已规划退出状态。
- `no-self-approval`：写作包不得输出 verdict、Review Receipt 或接受指令。
- `review-no-rewrite`：审查包只能返回 findings，不得返回替换正文。
- `format-not-semantics`：排版和标点建议不得改变语义事实。

## 实施步骤

1. 只处理 manifest 中 `batch=writing-1,status=ready` 的行并复算固定提交内容 Hash。
2. 删除来源 Runtime、Provider、数据库、循环重试和自我批准说明。
3. `prose-revision` 使用 `free_text`，Prompt 明确接收不可变事实边界和修改目标。
4. 对 `prose-quality-review` 的改动只能增加审查维度，不得降低 Hash 绑定、blocking verdict 和 evidence refs 要求。
5. provenance 完整记录所有合并来源；package Hash 变化必须使旧候选快照失效。
6. 通过固定边界用例后先保持新增包 `experiment`，独立质量评估通过后另行激活。

## 停止条件

- 来源未授权、Hash 不一致或 manifest 不是 ready。
- 需要修改章节正文存储或接受协议。
- 归并会把生产和审查职责放进同一包。

## 验证

```bash
PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -p 'test_production_catalog.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_prompt_catalog_boundaries.py' -v
PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -p 'test_pure_codex_workflow.py' -v
git diff --check
```

## 完成证据

- 用户授权：明确确认来源授权许可，P01~P04 均设为 `user_authorized` 与 `status=ready`。
- 交付及增强包：
  1. `prose-revision` (Wave-D 实验包，归并 P01 writer-rewrite 与 P02 humanizer)
  2. `prose-quality-review` (Wave-A 生产包，归并关联 P03 writer-self-check 与 P04 scroll_analysis 增强属性)
- 边界约束：5 个固定边界用例已在 `tests/test_prompt_catalog_boundaries.py` 中固定并测试通过。


