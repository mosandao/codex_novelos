# 正文质量审查

只审查给定的不可变正文和精确上下文，不重写正文。

检查章节执行卡兑现、Canon 连续性、人物知识和动机、世界规则、时间位置、场景升级、信息重复、语言清晰度与结尾状态。同时检查：

- `style_refs` 是否能追溯到精确 Creator Profile revision/hash、锁定 Direction 和适用 POV/风格引用；
- 正文是否忠实表现 `book_soul` 与本章 `soul_pressure` / `moral_residue`，而未自行发明作者思想；
- 对立立场是否由有能力、有合理动机的人物承担，是否出现所有人物同声；
- 思想是否通过选择和后果呈现，是否出现叙述者代替剧情讲道理；
- 是否为了爽点、圆满或推进便利违反 `forbidden_conveniences` / `forbidden_resolutions`；
- **persona 盲区穿透**：签名 `blindspots` 是否被正文穿透——若正文流畅展开了 `cannot_write` 声明写不了的圈子/暗面（如 old money 社交的内部黑话对白），而未按该条目附带的绕开方式处理（转喻/侧写/留白/借他人之口），判定 persona 未生效——`blocking`；正文出现 `refuses` 清单中的写法/题材——`blocking`；
- 与提供的近期章节相比，是否发生作者立场漂移、人物声音趋同或母题机械重复；
- **心理解释压过节奏**：连续两段以上纯心理剖析而剧情零推进（对话/行动/信息量无变化）= `warning`；类型回报（升级/对抗/关系确认/讨回）被心理深描挤占 = `warning`；
- **立场突变无触发**：人物立场/态度/关系判断发生实质转变，而正文中找不到触发经验（事件/对话/发现/损失）= `warning`；主角核心动机无触发翻转 = `blocking`。
- **人物卡一致性**（character_essence 槽注入时）：出场人物的语域口癖、行为与注入的人物卡 essence 要点矛盾（执念方向背离、失稳点该显形而毫无痕迹、台词语域与出身分化相悖）= `warning` 并指认要点；已退场/死亡状态的人物无连续性依据出场 = `blocking`。槽未注入或逐行标注旧契约数据时按保底纪律执行。

同时检查**形式规范与 AI 指纹**——**全部数字阈值以注入的 craft 方法卡为唯一权威源**（prose-format-hardrules / prose-anti-ai-fingerprint / prose-webnovel-accessibility / worldview-lexicon），本 rubric 不复述数字，只保留判级语义与结构性检查：

- **标点规范**：英文直引号（U+0022）出现即 `blocking`；破折号/省略号密度按 prose-format-hardrules 阈值判级。
- **字数**：按执行卡 `target_word_count` 与 hardrules 阈值判级。
- **规划层元标签泄漏**：正文出现执行卡/规划资产内部元标签（L1/Tier1/认知层/伪装层/central_contradiction 等）——`blocking`。
- **段落节奏 / AI 指纹 / 章末钩子 / 节奏密度 / 参差原则**：按注入 craft 卡的规则与阈值逐项判级（金句密度/比喻堆叠/解释零浪费/过度均匀等）。
- **术语语域一致性**：采样正文术语对照输入数据区注入的世界语域表（world_lexicon 槽——本书正面词汇/四类分禁/计量体系/例外通道；判定分档见注入的 worldview-lexicon）——**现代计量单位出现在非现代场景（计量穿越）= `blocking`**；科学词汇混用按密度判级；语域表未注入时按保底纪律执行。
- **频道轴与力量货币依据**（direction v2）：叙事是否落在声明的频道轴上（男频力量轴/女频规则关系轴——串味 = `warning`）；力量货币的兑现是否可感（数值播报式兑现 = `warning`）；代价兑现是否非对称（等价交换记账式代价 = `warning`）。

**指纹类 finding 判级纪律（FP/fpr 编号制）**——语言层指纹检查（注入的 prose-anti-ai-fingerprint 卡 + 形式硬规则）的附加约束：

- **规则编号写入 message**：每条指纹类 finding 的 message 文本头部必须携带规则编号——有预筛对照的规则用机器规则号，格式 `[fpr:L03] 原文片段…`；无预筛对照的卡面规则用卡面定位符，格式 `[FP-2.1] 原文片段…`。编号对照以注入指纹卡 §0 的 FP↔fpr 映射表为准。指认不出编号的指纹类意见自动降 `note`，不得作为 `warning`/`blocking`——审查方不得发明卡外规则；对卡内边界有疑问（如句内/句间之分）记 `note` 转规则修订通道，不作为 finding 计级。
- **反向自检（不作为判级理由表）**：每条指纹 finding 落级前对照注入指纹卡 §7「不作为判级理由」表——finding 的依据命中表中任何一行（句长段长参差/句内排比/正文问句/设问自问自答/比喻本身/被动句/名词化/全称重复/单字虚词/整体语感等），该 finding 无效：撤销或降 `note`，不计入判级。此表与正向规则同等硬约束。
- **豁免援引逐字引用**：对指纹 finding 援引签名豁免时，必须逐字引用项目签名中对应特征条目原文（含条目标识与度量依据），finding 标 `"code": "exempt:fpr:<ID>"`。引用「整体风格」「风格文档优先」等整体性表述 = 无效豁免，finding 照常计级。
- **锚点判级上限**：注入指纹卡中标注〔临时锚点〕且金丝雀校准未完成的数值阈值，对应 finding 上限 `warning`；人类基线（`docs/knowledge/canary-baseline.md`）显示人类密度 ≥ 该阈值的，该阈值 finding 降 `note` 并标「待校准」（人类语料会命中的阈值不得用于判级）。
- **判级语义（U1 方案 A）**：零容忍型（FP-1.5b／FP-1.8／FP-6.5，对应 fpr:P02/L06/L11）预筛命中即候选；阈值型（FP-1.1／FP-1.5a／FP-1.6／FP-1.7／FP-3.5／FP-6.1／FP-6.2，对应 fpr:L01/P01/L02/L03/P03/L07a/L08）按本章卡面阈值判级、频率计数以预筛脚本为准；FP-6.3／FP-6.4（fpr:L09/L10）为观察期条目。
- **叙述/对话口径**：语言层指纹规则只判叙述文本；对话与引语内命中不计——对白语域与人设问题走 persona 盲区门（见上文 persona 条目），不得以指纹规则判对话。
- **金丝雀折扣口径（男频项目）**：金丝雀基线（女频叙事语料）对男频项目只用于「过紧检测」（人类密度 ≥ 阈值 → 降级），不得反向收紧（女频密度低 ≠ 男频阈值应收紧）；密度类阈值在男频项目维持既有判级，直至男频语料补采（U13）后二次校准。「结构类语言机制频道间差异小」为**待验假设**，随男频补采一并校验，不当已证事实引用。

修订对接：按需额外 Read 的 `catalog/skills/expansions/prose-revision/prompt.md`（见文末）已升级为双模式修订卡——其输出格式（改动清单含规则编号列、message 头部 `[fpr:<ID>]`/`[FP-x.y]` 编号）是本节 finding 可对接的修订产物形态；修复循环按编号定点修，修订候选须重跑预筛更新计数。

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
