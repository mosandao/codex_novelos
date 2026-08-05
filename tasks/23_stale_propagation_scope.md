# Task 23：Stale 传播按影响范围（scope）精确化

## 状态

`CANCELLED`（经技术评估，当前数据结构下无法安全实现，收益不抵风险）

## 背景

世界观设计重构讨论稿（`documentation/worldbuilding-redesign.md`）第 22.9 条建议区分"扩展性新增"和"矛盾性修订"的 stale 传播范围，让主控只重生成受影响分支。

现状 `_mark_planning_descendants_stale`（`service/_internals.py:941`）是递归 CTE，沿 `planning_asset_dependencies` 把所有后代**无条件**标 stale。

## 评估结论：当前不应推进，取消

经技术评估，**asset 级依赖图无法支撑 scope 精确化**，且有可靠的 scope 判定机制前不应改版本一致性核心算法。

### 关键事实（技术评估依据）

1. **依赖图是 asset 级，无设定项粒度**。`planning_asset_dependencies` 只记 asset→asset（如 `world_contract → story_arc`），不记"world_contract 里的哪个位面/势力依赖哪个 volume"。查西幻项目实际 9 条依赖记录，全部是整资产级链接。

2. **world_contract 不直接是 volume_outline 的上游**。链路是 `world_contract → story_arc → volume_outline`。要知道"加一个深渊位面影响第三卷不影响第一卷"，需要语义理解 world_contract 内容与各 volume_outline 内容的关系——这远超当前依赖图能表达的信息。

3. **scope 判定无法机械化**。可能的实现路径全部不可靠：
   - 依赖图细化到设定项级 = schema 大改 + 所有规划资产重新标注细粒度依赖，工作量巨大且收益不确定。
   - Agent/用户显式声明 scope = 判错会 silently 漏标 stale，等于在"上游一改下游必 stale"的铁律上开口子。

### 为什么全树 stale 是合理代价

1. **判错 scope = silently 数据不一致**。这种 bug 不在测试里暴露，只会在写到第 100 章时才发现——代价远超重生成的浪费。
2. **当前规模下全树 stale 成本可控**。西幻项目仅 6 个 planning_assets，全树 stale 重生成代价小。
3. **成熟项目重生成本就该慎重**。写了很多卷后改上游要重生成大量 volume_outline，这时项目已成熟，重生成成本高是合理的"改上游要慎重"的信号，不是需要优化的浪费。
4. **符合项目纪律**。Task 04 质量实验宁可 DEFERRED 也不草率，同理：没有可靠机制前，不改核心算法。

## 决定：取消本 Task

22.9 的"scope 精确化"在当前数据结构下无法安全实现。**全树 stale 虽有浪费，但保证了版本一致性的铁律，是合理代价。**

### 记入文档的修正

`documentation/worldbuilding-redesign.md` 第 22.9 条应补充评估结论，并将该条从"建议"移入"不建议改的部分"（第二十三章）——因为它属于"不要改版本一致性核心算法"。

## 改动文件

本 Task 取消，无代码改动。仅更新文档。

## 来源信息

- 来源文档：`documentation/worldbuilding-redesign.md` 第二十二条 22.9（就绪度 🔴）
- 评估方法：技术评估——查 `planning_asset_dependencies` 实际结构 + 西幻项目 9 条依赖记录的粒度
- 评估依据：asset 级依赖图无设定项粒度；world_contract→volume_outline 非直接上游；scope 判定不可机械化

## 教训

22.9 是从"重生成成本"角度提出的优化建议，但忽略了"版本一致性铁律"是 NovelOS 的根基。**改核心一致性算法的门槛不是"有没有优化空间"，而是"有没有不降低安全性的实现方式"**。前者 22.9 满足（全树 stale 确实浪费），后者不满足（无可靠 scope 判定）。这类建议在评估时必须先问后者，不能只看前者。
