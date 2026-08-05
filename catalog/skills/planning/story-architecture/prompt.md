# 故事架构

从锁定 Direction 推导能够持续兑现读者承诺并反复检验 `book_soul` 的叙事机制。定义冲突如何升级、信息如何释放、规则如何产生代价，以及故事需要哪些人物和世界能力。

明确给出核心矛盾的重复施压机制、立场通过选择与后果呈现的机制、`deliberate_silences` 的信息留白规则，以及 `narrative_mercy` 和 `narrative_cruelty` 如何同时生效。不得用旁白宣布标准答案，也不得以机械降神绕过 `forbidden_resolutions`。

每个架构决定都要引用 Direction 约束并说明下游影响。不要修改 Direction，不要编写人物传记、具体卷纲或章节事件；无法兼容时返回上游 change proposal。

## 可选方法素材

以下 expansion skill 提供架构方法的细化参考，**均为可选输入，不能替代本主干产出**。主控智能体或 Architecture Agent 可按需调用 `skill_catalog.get("<name>")` 拉取其完整 prompt 作为方法灵感：

- **story-causal-structure**：当需要梳理"情节因果链与不可逆状态推演"时，参考其因果节点设计方法，确保每次状态变化不可跳过且逻辑自洽。
- **story-expectation-design**：当需要设计"核心叙事承诺、信息揭示顺序与读者期待兑现节点"时，参考其线索悬念与阶段性期待管理方法。
- **story-pov-tone-contract**：当需要约定"视角人物的知识边界、感知受限与整体叙事基调"时，参考其 POV 契约方法，防止全知全能上帝视角。

这些素材的使用条件见各自 metadata 的 `use_when` / `avoid_when`。未覆盖的场景应依靠 Direction 约束直接推导，不强行套用不相关素材。
