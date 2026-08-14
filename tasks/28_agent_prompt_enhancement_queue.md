# Task 28: 各级 Agent Prompt 增强队列（按创作阶段拆分）

**状态**: `IN PROGRESS`（阶段 0-2 已完成，阶段 1 补丁起待执行）

按小说创作 pipeline 的阶段顺序组织，每阶段一个工作单元：完成该阶段全部改动 → 合成素材实测 → 验证全绿 → 单独提交。阶段的执行顺序即依赖顺序（阶段 4 内人物‖世界观可并行）。

## 问题根因总览

1. **方法论空泛**：全库 43 个 skill 零 few-shot；8 张 expansion 方法卡仅 130-310 字（三句口号）；story-arc/volume-outline 等主干只有职责无方法
2. **题材/频道/平台叙事语法缺失**：男频力量轴 vs 女频规则轴未处理（串味风险）；力量货币（各题材「什么等同于更强」）未定义；代价语法劣化（LLM 默认「得到1失去2」等价交换记账）；女频道德债权/债务机制未显性化；平台耐心结构未适配 promise_cadence
3. **世界观语言纪律缺失**：前现代题材混入现代科学术语/现代计量/现代认知框架（三层污染）；无术语语域表与例外通道
4. **生成-审查脱节**：rubric 查的生成端没产出；生成端无自检
5. **机械伤**：`skill_catalog.get()` 死链（写作主干 6 处）、`planning.extract_decision_points` 死链（策略）；形式阈值四处重复维护；SKILL 内嵌 SQL 与 schema 漂移（novel-memory / novel-continuity 疑似）

---

## 阶段 0：创建项目 · 作者人格融合（onboarding）—— ✅ 已完成 `8a0042e`

「先立人，再落规」：persona（五维生平×双向拟合×盲区清单）+ 带体温七字段；creator-signature schema v2；投影渲染 persona；Direction/Writer 的 persona 消费通路；sql-reference 补 creator 链落库模板。

补丁：防指纹补丁（响应外部同质化审查——世代/创伤源多样化、道具指纹禁令、inner_tension 形态菜单、不体面缺点、条目数自然浮动、示例意象中性化）已并入 prompt，验证四命令绿；对照重测按用户决定取消（2026-08-14）。

## 阶段 1：方向智能体（direction）—— ✅ 主体已完成 `57f1e38`，**补丁待执行**

主体：从 persona 长出 book_soul（v2 十二字段 + organizing_principle + promise_cadence）；清退创作种子（migration 017）；候选比较表；九项自检。

### 阶段 1 补丁（TODO）：频道×题材语法 + 力量货币 + 代价形态学 + 道德债权

| 落点 | 改动 |
|---|---|
| `story-direction/prompt.md` | ①**频道语法段**：男频力量轴（秩序由力量定义，两难建立在力量获取代价上，承诺主形态=力量兑现）/ 女频规则轴（秩序由规则与关系定义，力量是规则内筹码，两难建立在规则内胜利或破规的代价上，承诺主形态=价值确认与关系走向）/ 全向须声明主轴 / 出版·剧本按单本幕章结构承诺；防刻板化条款（频道定叙事轴非内容禁区，主轴归属不明确即不合格）。②**力量货币**：每候选显式定义「本书什么等同于更强」（境界/金钱/信息/真相揭示权/情感主导权/道德债权/地位…）+ 对价（获取付出什么、买不到什么）；central_contradiction 至少一端锚在力量货币上。③**代价形态菜单**：五种非对称形态（异化型=得到即变质 / 关系型=关系质地改变 / 路径收窄型 / 债务型=有债主利息到期日 / 汇率延迟型）；禁纯「得到1失去2」等价交换记账；limits/weaknesses/costs 三件套至少其二；好代价四检验（兑现性/不可预算性/增值性/论证性）。④**道德债权机制**（女频形态）：债权积累（先受害授权）→ 兑付（打脸=讨债，有债权依据）→ 不过额（超额=女主新债务）；道德债务反向显性化（债主/到期日，与 protected_dignity 联动）；白莲花/黑莲花双陷阱禁令；选择性道德（可狠但有底线）。⑤**平台耐心结构**：promise_cadence 按平台适配（免费算法平台开篇即冲突高密度兑现 / 付费平台养书容忍 / 女频社区平台情感线密度与基调敏感）——写结构适配不写死数字 |
| `config/schemas/book-soul.schema.json` | v2 直接新增 `power_currency`（string，required——v2 尚无存量资产可自由改）；投影 `_SOUL_LABELS` 加「力量货币」 |
| `planning-direction-review/prompt.md` | 加检查项：串味检测（频道轴是否立对）/ 力量货币已定义且被矛盾锚定 / 代价质量（对称可预算代价 = warning） |
| `novel-planning/SKILL.md` | Direction 输入清单补 channel/platform 显式传入 |
| `catalog/skills/onboarding/creator-signature-fusion/prompt.md`（阶段 0 联动） | **双向拟合扩展「频道资格」**：频道核心情感登记进题材资格检验——女频核心登记（被辜负后的重新掌控/情感主导权争夺/规则内博弈）要求 persona 库存与人生轨迹有**经历来源**（非性别来源，如经历过权力不对称的关系）；男频核心登记（力量兑现/地位翻盘/秩序掌控）同理要求库存覆盖相应圈子；覆盖不了 → 调生平 / 进盲区清单 / 上报错配。**声音样本平台匹配**：吆喝语言对目标平台读者气质发声（检验自然度，不改人格内核）。**错配上报扩展**：频道×人格根本错配（库存无法覆盖频道核心登记且不可调）时上报。**防刻板化条款**：频道要求叙事资格而非性别/年龄/刻板人格；跨频道人格合法，资格缺口必须显式处理。咬合关系：阶段 0 保证人格**有资格**写该频道核心情感登记，阶段 1 频道语法保证 book_soul 在正确轴上构建——一个管人一个管书 |
| `creator-signature-fusion/prompt.md` + `creator-signature.schema.json`（阶段 0 联动·心理学补强，依据 McAdams 人格三层理论 / agency-communion 双主题 / LLM persona 信念-行为一致性研究） | ①**特质层补齐**（McAdams：完整人格=特质→关注→叙事三层；现有关注层=五维生平、叙事层=narrative+inner_tension，缺特质层）：anchors 加 `trait_profile`（3-5 维行为倾向），**每维必须行为化**——「尽责性高」写成「他的教案边角每年都重新抄一遍」（LLM 研究教训：抽象特质不配行为锚点必然漂移，GCA 情境化>特质描述）。②**主题倾向声明**：anchors 加 `theme_orientation`（agency 主导=自主/成就/掌控 / communion 主导=联结/归属/关系 / 双高 / 双低——双低=疏离叙事，长篇不可用即重做；两主题人人混合只有主导不同）；给频道资格加心理学判据：主题错配（communion 主导人格×男频核心登记）进错配上报，与 direction 层频道语法双向咬合。③**fear 补进血肉要素**：wound→motivation→fear 链补全——烙印事件→执念已有，补「他怕什么」；`refuses` 盲区从平铺清单变成有心理来源的禁令（因为伤过所以不碰）。④**行为锚点纪律进自检**：加「行为锚点测试」——抽 persona 任何一条抽象声明，必须能指认对应的具体行为/习惯/偏好，指认不出即重写 |
| 实测 | 男频修仙 vs 女频宅斗两个合成场景对比：验证频道轴、力量货币、代价形态、道德账户的差异化落地；频道资格对 persona 的拟合效果（女频场景的 persona 库存应覆盖规则/关系登记的来源、theme_orientation 应与频道轴咬合）；行为锚点测试抽检 |

## 阶段 2：架构智能体（architecture）—— ✅ 已完成 `1f98893`，**小补丁随阶段 1 补丁联动**

主体：Direction→叙事引擎（双引擎/四段式/咬合闭环/防火墙/压力油耗测试/POV 契约）；三张卡加深（causal-structure / pov-tone-contract / expectation-design）；rubric 8 条对齐。

### 阶段 2 补丁（TODO，随阶段 1 补丁一起做）

- `story-architecture/prompt.md` 力量与代价机制节补一句：代价收取机制须引用代价**形态**（五种非对称形态，非只有价格）；力量货币（power_currency）进入翻译表（架构层将其翻译为力量与代价机制）

## 阶段 3：策略智能体（strategy）—— TODO

| 落点 | 改动 |
|---|---|
| `story-strategy/prompt.md` | 接 v2 上游：机制**节奏表**→卷节奏骨架、释放阶梯→层×卷映射、promise_cadence→阶段收益配比、晋升-收费配对表、主导螺旋轮换表；阶段数量与字数体量指引（对齐 novel-planning SKILL「每阶段平均≥20万字」）；阶段性收益+承诺-收益配对保留深化；decision_points（全库最细字段定义）保留；清 `planning.extract_decision_points` / `planning.create_revision_candidate` 死链（改为「附在 metadata，主控呈现给用户」）；交付前自检前移 |
| `planning-strategy-review/prompt.md` | 与生成端自检对齐（上游机制消费完整性 / 体量合规 / 收益配比） |
| 实测 | 合成素材（延续阶段 2 实测的分诊线 direction+architecture）产出阶段骨架，验机制节奏消费与 decision_points |

## 阶段 4：人物智能体 ‖ 世界观智能体（可并行）—— TODO

### 4a 世界观（world-contract）

| 落点 | 改动 |
|---|---|
| `world-contract/prompt.md` | 重组：去特定项目样板（「经济分两档」类泛化）、修中英混杂段；**新增「术语语域表」节**：`lexicon` 正面词汇表（本书超自然现象的本土词汇，可引用 universe-atlas 簇文件原生体系）/ `banned_categories` 四类分禁（物理术语/生物医学术语/现代计量/现代认知框架——分类禁防绕过）/ `measure_system` 计量体系（里丈尺+一炷香弹指+斤两，或自定义）/ `exceptions` 例外通道（科学修仙流显式声明 / 现代题材 / 穿越者内心 OS / 修辞对照白名单） |
| **新建** `catalog/skills/craft/worldview-lexicon/` | 术语语域纪律（执行端）：正文遵守 world_contract 语域表；无语域表时的保底纪律（非现代题材默认禁科学术语类+现代计量类）；**认知边界**（前现代人物用推演/内观/望气，不用假设-验证思维；穿越者内心除外且需 POV 设置声明）；判定分档（计量穿越=blocking，科学词汇混用=按密度） |
| 四张 world 卡加深 | world-rule-system / world-growth-resource / world-social-power / world-system-interaction（现各仅 130-270 字）——各带方法步骤与好坏对照 |
| `planning-world-contract-review/prompt.md` | 加术语语域表存在性与完整度检查 |
| `planning-cross-consistency-review/prompt.md` | 补方法论（现仅 7 行 257 字）：能力vs规则、势力vs动机、角色vs制度的具体检查法 |
| 实测 | 合成修仙项目：语域表生成 + 抽查违规判定 |

### 4b 人物（character-contract）

| 落点 | 改动 |
|---|---|
| `character-contract/prompt.md` | 失稳空间/核心执念等好设计补好坏对照示例；接架构移交清单（施压螺旋的人物载体 / 对手自洽账簿模板 / 行为残迹预埋清单 / 回归面孔名单）；**女频选择性道德与道德债权账户在人物层落地**（人物带的债、底线声明）；字段要求与标题结构要求整理分节 |
| `planning-character-contract-review/prompt.md` | 对齐（移交消费完整性 / 道德账户一致性） |
| 实测 | 合成素材产出人物契约，验移交清单消费 |

## 阶段 5：故事弧智能体（story-arc）—— TODO

- `story-arc/prompt.md` 重写：弧线数量/粒度/弧↔卷映射方法；recurring_tests 的跨卷变奏分配（接架构变奏器：每卷换处境/答案/代价）；伏笔种收平衡（标注兑卷次）保留深化；自检 + rubric 对齐（`planning-story-arc-review`）
- 实测：合成素材

## 阶段 6：卷规划智能体（volume-outline）—— TODO

- `volume-outline/prompt.md` 重写：卷内节奏方法（副高潮间隔/并行冲突线数量——对齐 novel-planning SKILL「每卷≥3 条并行冲突线、每 20-30 万字一个副高潮、POV 多样性」，消除要求与方法的脱节）；接卷级主线引擎四段结构（加压/排序/对撞/结算）与主导螺旋轮换；自检 + rubric 对齐
- 实测：合成素材

## 阶段 7：章节规划智能体（chapter-plan-execution-card）—— TODO

- 场景序列指引（接章级单元机器三拍：分级/执行/结算——每章场景数与长度建议）；**钩子强度分级收口**：prose-webnovel-accessibility §3 为唯一权威源，本 prompt 与审查端改引用（消除四处重复维护）；soul_pressure / moral_residue 与道德债权账户对接（女频章纲的债权兑付标注）；自检 + rubric 对齐
- 实测：合成素材

## 阶段 8：写作智能体（chapter-draft-generation + scene 三件套 + craft 补强）—— TODO

| 落点 | 改动 |
|---|---|
| `chapter-draft-generation/prompt.md` | **清除 6 处 `skill_catalog.get()` 死链**（改 Read 语法，与第 7 处 accessibility 统一）；persona 消费深化（声音样本语感锚点 / 盲区场景的绕开转喻写法 / 有限视角逐场景执行 / 目光入场顺序接 POV 契约）；形式阈值收口（数字阈值以 craft 为唯一权威源，本 prompt 改引用注入）；引用 worldview-lexicon（术语语域执行） |
| `scene-dialogue` / `scene-fight-craft` / `scene-pacing` | 三件套加深（现各仅 134-256 字）：各带方法步骤与好坏对照；scene-pacing 支撑起审查端「必须调用」的定位 |
| `prose-anti-ai-fingerprint/prompt.md` | 补六项真人感门槛的起草期执行说明（如何在生成时主动融入而非事后检查） |
| 实测 | 合成素材起草一章，验死链清除后的素材引用与语域遵守 |

## 阶段 9：审查智能体（review 系）—— TODO

| 落点 | 改动 |
|---|---|
| `prose-quality-review/prompt.md` | 形式阈值第三次复述改引用（craft 权威源）；加**术语语域一致性**检查项（采样正文术语 vs world_contract 语域表，计量穿越=blocking）；引用 direction v2 的频道轴/力量货币/代价质量作为审查依据 |
| 三个短 rubric 补方法论 | planning-cross-consistency（若阶段 4 未补全）/ entity-authority / continuity-quality（现各仅 7 行） |
| review 系 metadata | 13 个包补 use_when/avoid_when |
| 实测 | 用阶段 8 实测的章节跑审查，验引用链与判定 |

## 阶段 10：连续性智能体（continuity）—— TODO

- `continuity-candidate-extraction/prompt.md`：补「什么算正文明确发生」判定标准（推断 vs 确认 / 隐含状态变化 / 对话承诺 vs 叙述承诺的边界案例）+ 好坏对照
- `novel-continuity` / `novel-memory` SKILL.md：内嵌 SQL 复查对齐 sql-reference.md（旧列名漂移）
- 实测：合成章节提取候选五类

## 横切收尾（阶段 10 后）—— TODO

- planning/review 系 metadata 的 use_when/avoid_when 补全；stage 枚举统一（craft 独有值收编）
- **三阶段串测**：合成素材走 direction → architecture → strategy 最小闭环（验移交链路：四段式下游影响 → strategy 消费）
- documentation 全面复核（automation/flows 与新机制一致）
- 四条验证命令终验
- **原型库审美多样性（待专项设计）**：18 个系统原型的 forbidden_conveniences 全偏高级文学禁令（无代价机械降神/无理由碾压/巧合），血缘继承导致不同人格共享同一套审美洁癖，系统性压制纯爽型/娱乐型人格（对应平台真实市场）。治本需扩娱乐向原型或为原型配置可选爽型滤镜——涉及全部原型 subject_hash 与派生校验链，须专项设计后再动。

---

## 通用验收标准（每阶段）

1. prompt 四要素齐：方法步骤 / 输出骨架 / 好坏对照示例（合成，无真实项目内容） / 交付前自检
2. 生成端自检与对应 review rubric 检查项一一对齐
3. 无旧 MCP 工具名残留（`skill_catalog.get` / `planning.extract_*` / `creation_seed.get`）
4. 实测：合成素材跑一次 sub agent 过对应校验门，不落库不留文件
5. 四条验证命令全绿：unittest / compileall / hygiene / manifest
6. 每阶段单独提交，commit message 说明实测结果

## 进度记录

- 2026-08-14：阶段 0（`8a0042e`）、阶段 1 主体（`57f1e38`）、阶段 2（`1f98893`）完成；项目内容清理（`3bb14eb`：全库清除测试项目数据/投影/派生 creator 链/示例措辞，关键词复扫零命中）
- 补充决策：阶段 1 补丁并入阶段 0 联动项——persona 双向拟合扩展「频道资格」（channel/platform 从「零消费」变为拟合维度：频道核心情感登记进资格检验、声音样本平台匹配、错配上报扩展、防刻板化条款；人格内核不硬绑频道）
- 补充决策（心理学补强，联网调研）：persona 结构对齐 McAdams 人格三层（补特质层 `trait_profile` 且必须行为化）；`theme_orientation`（agency/communion 主题倾向）作为频道资格的心理学判据；wound→motivation→fear 链补全使 refuses 有心理来源；行为锚点测试进自检（依据 GCA 情境化评估与信念-行为一致性研究：抽象声明不配行为锚点必然漂移）
- **阶段 0 补强已完成**：fusion prompt 升级（频道资格/人格三层/血肉五要素含 fear/主题倾向/行为锚点纪律/坏味道 +2/自检十项/输出格式加新键）；schema anchors 加 `trait_profile`（3-5 条行为化）+ `theme_orientation`（dominant 枚举拒绝双低）；投影渲染特质简档与主题倾向段。schema 行为验证全 PASS（缺键拒绝/dominant=none 拒绝/v1 系统原型与既有派生不受影响）；实测（晋江宅斗合成场景）：频道资格显式核验（经历来源非性别刻板）、agency 主导 + communion 居次的主题咬合（且印证「女频≠必须 communion 主导——被辜负后的重新掌控本质是 communion 场景中的 agency 叙事」）、trait_profile 5 条零抽象形容词、refuses 3/3 带恐惧来源、声音匹配晋江气质。实测附带发现：压缩版注入导致 sub agent 键名漂移（`generation_and_age` 等自造变体）——真实流程注入完整 prompt.md（含精确 JSON 示例）+ schema 校验门（additionalProperties:false）双重兜底
- 下一步：阶段 1 补丁（direction 层：频道语法段 + 力量货币 + 代价形态学 + 道德债权 + 平台耐心结构）→ 阶段 2 小补丁 → 阶段 3
