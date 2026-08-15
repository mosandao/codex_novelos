# 正文质量审查

只审查给定的不可变正文和精确上下文，不重写正文。

检查章节执行卡兑现、Canon 连续性、人物知识和动机、世界规则、时间位置、场景升级、信息重复、语言清晰度与结尾状态。同时检查：

- `style_refs` 是否能追溯到精确 Creator Profile revision/hash、锁定 Direction 和适用 POV/风格引用；
- 正文是否忠实表现 `book_soul` 与本章 `soul_pressure` / `moral_residue`，而未自行发明作者思想；
- 对立立场是否由有能力、有合理动机的人物承担，是否出现所有人物同声；
- 思想是否通过选择和后果呈现，是否出现叙述者代替剧情讲道理；
- 是否为了爽点、圆满或推进便利违反 `forbidden_conveniences` / `forbidden_resolutions`；
- **persona 盲区穿透**：签名 `blindspots` 是否被正文穿透——若正文流畅展开了 `cannot_write` 声明写不了的圈子/暗面（如 old money 社交的内部黑话对白），而未按该条目附带的绕开方式处理（转喻/侧写/留白/借他人之口），判定 persona 未生效——`blocking`；正文出现 `refuses` 清单中的写法/题材——`blocking`；
- 与提供的近期章节相比，是否发生作者立场漂移、人物声音趋同或母题机械重复。

同时检查**形式规范与 AI 指纹**——**全部数字阈值以注入的 craft 方法卡为唯一权威源**（prose-format-hardrules / prose-anti-ai-fingerprint / prose-webnovel-accessibility / worldview-lexicon），本 rubric 不复述数字，只保留判级语义与结构性检查：

- **标点规范**：英文直引号（U+0022）出现即 `blocking`；破折号/省略号密度按 prose-format-hardrules 阈值判级。
- **字数**：按执行卡 `target_word_count` 与 hardrules 阈值判级。
- **规划层元标签泄漏**：正文出现执行卡/规划资产内部元标签（L1/Tier1/认知层/伪装层/central_contradiction 等）——`blocking`。
- **段落节奏 / AI 指纹 / 章末钩子 / 节奏密度 / 参差原则**：按注入 craft 卡的规则与阈值逐项判级（金句密度/比喻堆叠/解释零浪费/过度均匀等）。
- **术语语域一致性**：采样正文术语对照 world_contract 语域表（判定分档见注入的 worldview-lexicon）——**现代计量单位出现在非现代场景（计量穿越）= `blocking`**；科学词汇混用按密度判级；无语域表时按保底纪律执行。
- **频道轴与力量货币依据**（direction v2）：叙事是否落在声明的频道轴上（男频力量轴/女频规则关系轴——串味 = `warning`）；力量货币的兑现是否可感（数值播报式兑现 = `warning`）；代价兑现是否非对称（等价交换记账式代价 = `warning`）。

人口属性推导、具体作者模仿、错误/缺失作者或 Direction 精确引用、廉价结局、叙述者替代剧情宣判，以及实质性的长篇立场漂移均为 `blocking`。每个问题使用 `blocking`、`warning` 或 `note`，引用最小正文片段和来源 ref。存在 `blocking` 时 verdict 必须为 `rejected`。

**证据标准**：每个 finding 必须引用具体段落位置和原文片段，禁止使用"多处""全文""整体"等模糊描述。无具体位置或无原文引用的证据视为无效。

返回同一 `subject_hash`、verdict、findings、evidence refs 和 reviewer profile。

## 方法素材（已随组装注入，无需再拉取）

以下 craft 方法卡由组装器按 manifest `craft_refs` **逐字注入**（数字阈值唯一权威源），审查时直接引用注入内容，不得跳过：scene-pacing（节奏停滞/跳跃/重复诊断）、dash-ellipsis-guide（标点语义）、mobile-formatting（移动端密度）、prose-anti-ai-fingerprint（指纹检测与真人感门槛）、prose-format-hardrules（形式阈值）、prose-webnovel-accessibility（通俗度/开头/钩子强度分级）、worldview-lexicon（术语语域判定分档）。

按需额外 Read（未注入项）：`catalog/skills/expansions/prose-revision/prompt.md`（修订建议措辞参考，不改判级规则）。

同时检查以下维度（参照 `prose-webnovel-accessibility`）：

- **通俗度与抽象修辞**：正文是否存在面向高素养少数读者的抽象修辞链（连续概念性比喻），是否考虑商业网文多数读者的文学素养基准。
- **开头吸引力**：前 3 段是否以具体物/动作/对话切入，而非纯意象/意境/氛围描写。
- **钩子强度**：结尾钩子不只是判"有无"，须判强度等级（强/中/弱），弱钩子或纯情绪收尾为 warning。
