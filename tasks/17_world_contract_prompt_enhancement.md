# Task 17：World Contract Prompt 维度处理与消费约束增强

## 状态

`DONE`

## 背景

世界观设计重构讨论稿（`documentation/worldbuilding-redesign.md`）经西幻项目（`project:ea0831c1`）实测后提出九条改造建议，其中四条（22.1 / 22.3 / 22.7 / 22.8）为纯 prompt / rubric 增强，不触及 schema、依赖图或版本机制，风险最低、可先行落地。

### 实测证据

西幻项目 world_contract v2（`planning:43922898`）暴露三类 prompt 缺口：

1. **维度处理无指引**。西幻是领主经营流，经济系统（§3，五要素+生产链+债权-债务账本+脆弱度指标）是第一圈核心爽感来源，写得很厚；人文维度几乎完全隐身（仅魔鬼作为民俗背景一句带过）；历史无编年史，只服务于当下张力的回溯。但当前 `world-contract/prompt.md` 对"经济/人文/历史写多少、砍多少"完全无指引，全靠 Agent 自觉。讨论稿 22.7 判断：经济应按题材分档（经营流重投入 / 其他默认砍）、人文默认符号化、历史默认倒推——西幻实测全部印证。

2. **结构性消费约束未固化**。西幻 world_contract 的钩子密度极高，靠的是 prompt 里两条约束（"每项设定绑定消费圈次+场景类型"、"无消费者的位面不写入"）产出了 §1.4 位面消费时序表、§6.5 神线四态消费时序表等结构性钩子。讨论稿 22.1 原想"强制 state 字段（entry_tensions/plot_hooks 必填）"，但实测证伪——**钩子靠结构不靠字段**。降级后应把西幻已验证有效的两条结构性约束固化进 prompt 默认要求。

3. **增量扩展无合法通道**。西幻 world_contract 经历了 v1→v2 supersede（metadata 标注 `"revision": "cross-check L1 onset fix"`），证明"生成后发现需修正"是真实流程。但当前 prompt 说"只实现 Architecture 与 Strategy 实际需要的"，中途扩展时会让人误以为"不能加 strategy 没提的"。讨论稿 22.8 判断：应补一句增量扩展的合法通道说明，指向 change_proposal，避免 Agent 拒绝或偷加。

## 优化

### 优化 1（22.7）：world-contract prompt 新增「维度处理原则」段

在 `catalog/skills/planning/world-contract/prompt.md` 新增一节，固化三条原则：

1. **经济分两档**：
   - 经营 / 种田 / 基建 / 领主流：经济从"维度"升格为"对象"，必须重投入——产出 / 分布 / 消耗 / 枯竭曲线、债权-债务账本、脆弱度指标都要写。
   - 其他题材（都市 / 玄幻 / 言情等）：经济默认只写"主角钱包四档 + 地基资源曲线"，除非剧情必需。
   - 判定标准：删掉经济设定，主角的成长弧是否还成立？成立→默认砍；垮了→重投入。
2. **人文默认符号化**：只写"一两个标志风俗 + 一个禁忌"，除非题材是民俗 / 东方韵味卖点。
3. **历史默认倒推式**：只留有现在消费者（主角身世、神器来历、恩怨源头）的节点，中间空白留白，需要再补。

### 优化 2（22.1）：world-contract prompt 固化「结构性消费约束」

在 prompt 新增两条约束（从西幻实证提炼），并要求产出包含至少一张"消费时序表"：

1. 每项设定（位面 / 势力 / 规则 / 资源 / 灾厄机制）必须标注"首次被消费的圈次 / 卷"与"消费场景类型"。
2. 产出须包含至少一张"消费时序表"（如位面×圈次、势力×圈次），使钩子分布可视化。
3. 无消费者的设定不写入。

注意：不强制 state 字段名或结构（如 `entry_tensions` / `plot_hooks`），因为不同题材的 state 结构差异极大（经营流的账本结构 vs 修仙流的境界结构），强制统一字段反而有害。关键约束是"标注消费时机"这个行为，不是某个字段名。

### 优化 3（22.8）：world-contract prompt 新增「增量扩展合法通道」说明

在 prompt 补一段："当创作过程中产生架构与战略未覆盖、但剧情必需的新设定时（新势力 / 新位面 / 神国 / 深渊等），应返回 change_proposal 说明影响范围与归属层，而非自行扩张或静默忽略。新增 world 类设定（势力 / 规则 / 位面）归属 world_contract；影响主角主线阶段的归属 strategy；跨卷新线归属 story_arc。"

## 改动文件

| 文件 | 变更 |
|---|---|
| `catalog/skills/planning/world-contract/prompt.md` | 新增「维度处理原则」「结构性消费约束」「增量扩展合法通道」三段 |

## 来源信息

- 来源文档：`documentation/worldbuilding-redesign.md` 第二十二条 22.1 / 22.7 / 22.8（经实测分级，就绪度 🟢/🟡）
- 触发实例：西幻项目 `project:ea0831c1-cb35-4404-8df4-b69e2a136967` world_contract v2（`planning:43922898-a9d8-40b3-961b-a34f1a8081b7`）
- 实测记录：见 `worldbuilding-redesign.md` 第二十一·二章「验证实验：西幻项目实测」
- 累积效果：本 Task 落地讨论稿九条建议中就绪度最高的三条（纯 prompt，零 schema/机制风险）

## 验收标准

- [ ] `catalog/skills/planning/world-contract/prompt.md` 新增「维度处理原则」段，覆盖经济分两档（含判定标准）、人文默认符号化、历史默认倒推。
- [ ] `catalog/skills/planning/world-contract/prompt.md` 新增「结构性消费约束」段，要求每项设定标注消费时机 + 至少一张消费时序表，且不强制具体字段名。
- [ ] `catalog/skills/planning/world-contract/prompt.md` 新增「增量扩展合法通道」段，指向 change_proposal 并给出归属层判定（world/strategy/story_arc）。
- [ ] 新增的三段与 prompt 现有内容（"只实现 Architecture 与 Strategy 实际需要的"、"每项设定说明叙事用途/约束对象/代价/边界/关系"）不冲突——增量扩展段是对"只实现实际需要的"的补充（开书时遵守，中途扩展时走 change_proposal），不是推翻。
- [ ] `catalog build` 校验通过（prompt 变更不破坏 Catalog manifest）。
- [ ] 现有测试全部通过（prompt 变更不应改变任何既有行为）。
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

- **风险极低**：纯 prompt 增强，无 schema 变更、无新 migration、无流程改造、无 entity 校验改动。
- **回退方式**：`git revert` prompt.md 的本次 commit 即可完全回退，不影响任何已锁定的规划资产或权威数据。
- **不覆盖的内容**：本 Task 不改 review rubric（那是 Task 18 的范围），不改 entity payload 校验，不改依赖图。
