# Task 15：Volume Outline 节奏密度约束

## 状态

`DONE`

## 背景

Strategy 生成（Trace `a8c573e7`）的治理链质量是三轮中最高的——工具调用零摩擦（Task 13/14 的 9 类检查全部生效），isolation evidence 零缺失。但用户提出"节奏是否能快一些，塞入更多的冲突"，暴露了一个流程缺口：当前规划链缺少"节奏密度"维度的显式约束。

### 问题的根源

三轮 trace 对比：

| 指标 | Direction | Architecture | Strategy |
|---|---|---|---|
| isolation evidence missing | 2 | 0 | 0 |
| 工具调用失败次数 | 6 | 4 | 0 |

工具调用层面已无新问题。但分析 11 个战略阶段摊在 500 万字上的分布（每阶段平均 40-50 万字），发现"节奏密度"维度在所有层级都未定义：

| 层级 | 当前定义了什么 | 没有定义的 |
|---|---|---|
| Direction | 读者承诺（四项爽感） | 爽感交付频率 |
| Architecture | 代价管道、冲突升级引擎 | 引擎触发频率 |
| Strategy | 11 个战略阶段 | 每阶段允许多少并行冲突线 |
| Volume Outline | 单卷职责、转折序列 | 每卷允许多少副线、副弧、POV |

`novel-planning` SKILL.md 和 Catalog prompt 中"节奏"、"密度"、"并行"、"副弧"、"POV"这些词**一个都没出现**。这意味着 Volume Outline Agent 不知道需要塞并行线和副弧，500 万字可能变成单一主线慢走。

### 决策

不修改已锁定的 Strategy——战略骨架（11 阶段）是"可审计代价"承诺的底盘，碎掉就毁了。节奏密度在 Volume Outline 层实现。

## 优化

### novel-planning SKILL.md：新增「节奏密度约束」段

三层约束：

1. **战略骨架不可碎**：Strategy 每阶段平均不少于 20 万字，保证代价积累。不得为了加快节奏增加阶段。
2. **Volume Outline 必须塞入并行结构**（4 项硬约束）：
   - 每战略阶段拆 3-4 个卷弧，每卷有自洽进入/退出状态
   - 每卷至少 3 条并行冲突线（主线+2 副线，副线有独立压力源）
   - 每 20-30 万字一个可独立满足的副高潮（不等阶段结束就给爽感，但不消解 unresolved_claims）
   - POV 多样性（对手/受害者/暗线至少三类非主角 POV）
3. **节奏阀门**：爽感每 5-8 万字交付一次；代价追讨至少延迟一个卷弧（10-15 万字）；副高潮解决卷级冲突但不触碰战略级不可逆。

## 来源信息

- 来源 commit：本次变更所在 commit（待回填）
- 触发实例：Strategy 生成（project `project:ea0831c1`，Trace `a8c573e7`）后用户提出节奏问题
- 累积效果：Task 13（9 类工具调用失败）+ Task 14（4 类 Catalog/ID 失败）+ Task 15（节奏密度流程缺口）= 规划链全链路操作前置检查覆盖

## 附：Agent token 消耗观察

| Agent | Architecture | Strategy | 倍数 |
|---|---|---|---|
| 生成 | 39K | 289K | 7.3x |
| 审查 | 39K | 613K | 15.5x |

Strategy 审查消耗 61 万 tokens（Architecture 的 15 倍），原因是完整候选正文（1 万字）作为审查 prompt 传入。不产生错误、不违反治理链，但随规划链深入候选会越来越长。记录为观察项，若后续阶段 token 持续恶化再处理。

## 改动文件

| 文件 | 变更 |
|---|---|
| `.agents/skills/novel-planning/SKILL.md` | 新增「节奏密度约束」段（战略骨架不可碎 + Volume Outline 并行结构 4 项 + 节奏阀门 3 项） |
| `tasks/15_volume_outline_pacing_density.md` | 本文件 |

## 验收标准

- [x] novel-planning SKILL 包含节奏密度约束段。
- [x] 约束区分战略层（不可碎）与 Volume Outline 层（必须塞并行结构）。
- [x] 根测试、MCP 测试、compileall 全部通过。

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```
