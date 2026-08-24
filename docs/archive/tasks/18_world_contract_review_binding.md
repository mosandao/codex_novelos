# Task 18：World Contract Review Rubric 消费绑定检查

## 状态

`DONE`

## 背景

世界观设计重构讨论稿（`documentation/worldbuilding-redesign.md`）第 22.3 条建议在 world-contract 审查 rubric 增加"消费绑定"检查。本 Task 依赖 Task 17 先落地（Task 17 把"每项设定标注消费时机"固化为 world-contract prompt 的要求；本 Task 在审查层校验该要求是否被满足）。

### 实测证据

西幻项目 world_contract v2 的现有审查（`review:28480187`）已通过，说明现有 rubric 的"不生成无叙事消费者的百科"这一条**原则上有效**——但它偏原则性，缺可操作校验点。西幻产出的高质量（§1.4 位面消费时序表、§6.5 神线四态消费时序表）实际上**超出了现有 rubric 的显式要求**，更多靠 world-contract prompt 本身和 Agent 自觉。

讨论稿 22.3 原想"加钩子存在性硬阻断（blocking）"，但因 22.1 经实测降级（不再强制 state 字段），本条相应调整为 **warning 级检查**——审查每个设定项是否标注了消费时机，未标注的记 warning 而非 blocking。理由：西幻实测中现有 rubric 已能通过高质量产出，硬阻断可能过严，反而在中等质量产出上造成不必要的阻断。

### 现有 rubric 的缺口

`catalog/skills/review/planning-world-contract-review/prompt.md` 检查清单第 4 条"情节消费者：世界设定是否具备被剧情与故事线消费的具体切入点"——方向对，但：

1. **粒度不够**：只问"有没有切入点"，不问"每个设定项有没有标注消费时机"。
2. **无可操作的产出要求**：没要求产出含"消费时序表"这类可视化结构。
3. **无 warning 分级**：现有只有 blocking 和通过两档，缺"达标但有改进空间"的中间档。

## 优化

### 优化 1：检查清单第 4 条细化

将现有第 4 条"情节消费者"拆为两个可操作校验点：

- **4a 消费绑定**：每个设定项（位面 / 势力 / 规则 / 资源 / 灾厄机制）是否标注了"首次被消费的圈次 / 卷"与"消费场景类型"。未标注的记 `warning`（而非 blocking），并在 findings 中列出具体设定项。
- **4b 消费时序表**：产出是否包含至少一张"消费时序表"（如位面×圈次、势力×圈次），使钩子分布可视化。缺失记 `warning`。

### 优化 2：Blocking 条件保持不变

不新增 blocking 条件。现有 blocking（无代价力量 / 纯静态百科无切入点 / 立场伪装）维持原样。**消费绑定缺失是 warning，不是 blocking**——这是经实测后的刻意降级，避免在中等质量产出上过度阻断。

### 优化 3：证据要求补充

在"证据要求"段补充：审查消费绑定时，对每个未标注消费时机的设定项，引用其最小片段，标明"缺少首次消费圈次"或"缺少消费场景类型"。

## 改动文件

| 文件 | 变更 |
|---|---|
| `catalog/skills/review/planning-world-contract-review/prompt.md` | 检查清单第 4 条拆为 4a/4b；证据要求补充消费绑定的引用方式 |

## 来源信息

- 来源文档：`documentation/worldbuilding-redesign.md` 第二十二条 22.3（经实测分级，就绪度 🟡，依赖 22.1 先落地）
- 触发实例：西幻项目 `project:ea0831c1` world_contract 审查（`review:28480187-b746-4a4c-a1ed-3fdea3e30664`）
- 实测记录：见 `worldbuilding-redesign.md` 第二十一·二章
- 依赖：Task 17（world-contract prompt 固化"标注消费时机"要求后，本 Task 才能在审查层校验）

## 验收标准

- [ ] `catalog/skills/review/planning-world-contract-review/prompt.md` 检查清单第 4 条拆为 4a（消费绑定，warning 级）与 4b（消费时序表，warning 级）。
- [ ] Blocking 条件段未新增任何 blocking 项（消费绑定缺失是 warning，这是刻意降级）。
- [ ] 证据要求段补充：对每个未标注消费时机的设定项，引用最小片段并标明缺何种标注。
- [ ] 改动与现有"不得检查的下游"（主角心理 / 章节文风）不冲突。
- [ ] `catalog build` 校验通过。
- [ ] 现有测试全部通过。
- [ ] `compileall` 通过。

## 验证命令

```bash
.venv/bin/python scripts/build_catalog_manifest.py --check
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 完成条件

三个优化全部落地、Catalog 校验与现有测试通过、验收项全部勾选，才可将本任务从 `IN PROGRESS` 标记为 `DONE`。

## 风险与回退

- **风险低**：纯 rubric 增强，warning 级检查不改变现有 blocking 判定，不会让原本通过的审查变失败。
- **回退方式**：`git revert` prompt.md 的本次 commit。
- **依赖关系**：建议在 Task 17 落地后再做本 Task，否则审查要求的"消费时机标注"在 world-contract prompt 里还没有对应要求，会造成审查与生成的不对称。
