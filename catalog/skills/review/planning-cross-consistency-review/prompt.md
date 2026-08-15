# 规划交叉一致性审查

只审查人物契约与世界契约（必要时含 architecture 机制）的交叉关系，不直接重写资产。

## 三组交叉检查法（逐组执行，引用双方原文对照）

1. **能力 vs 规则**：人物契约的每项能力成长上限/形态，对照世界规则的获取通道与代价条款——人物能突破世界明令的代价或上限 = `blocking`；能力有通道但人物契约未声明代价 = `warning`；世界规则未覆盖人物已用的能力域 = `warning`（规则缺口，交 world 补）。
2. **势力 vs 动机**：人物所属/对抗的势力，其资源分配与制度激励是否能支撑该人物的动机与行为模式——人物动机与势力激励完全脱节（在制度里无人这么行动）= `blocking`；势力给得出但代价未在人物代价清单 = `warning`。
3. **角色 vs 制度**：人物与制度机制的每次交互（钻空子/守规/破规）在世界契约的制度条款里有依据——破规无制度后果 = `blocking`；钻空子的口子在规则里找不到 = `warning`。

## 交叉假设核对

Character 对 World 的显式假设清单逐条核销：世界契约已承载 / 未承载（退回）/ 相反（`blocking`）。

每个问题使用 `blocking`、`warning` 或 `note`，引用最小片段和来源 ref。存在 `blocking` 时 verdict 必须为 `rejected`。返回同一 `subject_hash`、verdict、findings、evidence refs 和 reviewer profile。
