# Task 38：story_arc 阶段深度反向审计与全量落地

状态：`DONE`（2026-08-22）

## 背景

继 T33-T37 五阶段审计波后对 story_arc 做全量反向审计（五轮）：①盘点说明（发现其为全链唯一零结构化出口阶段，停在 T29 形态）；②与 volume_outline 的边界/合并/换位分析（合并三方向否决、换位否决——单向依赖 + 指令性语义 + 增量生产）；③persona + setup 四轴反向审计（发现规划中段断供带：story_arc→volume→chapter_plan 三层全缺 project_setup/genre_pack）；④direction/architecture/character/world 消费审计（真消费只有 strategy，character/world 全文直注却各消费一句）；⑤深度补挖 + 联网研究。累计 28 项问题（A 装备缺失 4 / B 边界错位 6 / C 横向断供 4 / D 消费倒挂 12 / E 横切 4）+ 深度补挖 6 项（卷数无权威来源、台账豁免体系缺失、增量修订模式缺失、volume-review 缺回执槽、chapter-plan-review 缺契约上游、SKILL 生成侧回执描述漂移）。本批全量落地，含破坏性改动（story-arc 双端 prompt 重写）。

## 研究锚点

- [ZRainy 网文学习](http://zrainy.top/2020/04/09/网文学习/)（《龙血》分析：~30 万字/卷、每卷两小一大高潮、~10 万字一档货币推进）——volume_plan 卷字数区间与副高潮间隔的工业基准。
- [Doctorow 车灯论](https://www.bookarchitecture.com/doctorows-headlights/) / [Royal Road 滚动大纲实践](https://www.reddit.com/r/royalroad/comments/1ce6zjc/how_do_you_guys_write_your_chapters/)（每 5 章滚动更新）——open 模式滚动窗口（近硬远软）的写作工业依据。
- [Stage 32 多季规划](https://www.stage32.com/blog/the-secrets-to-mapping-out-a-multi-season-story-3924) / [OutWrd season arcs vs series arcs](https://www.outwrdplus.com/post/how-to-write-a-tv-series-a-step-by-step-guide)——A/B/C 故事线跨季追踪即弧↔卷映射表；续订超季导致弧线回收复读 = open 端无重映射的失败模式。
- [换地图工艺](https://www.wangwen666.com/post/45.html)（旧图关系/赌注延续不归零）——弧线跨换图延续、世界变迁弧不随地图重置。

## 变更清单（按层）

- **schema**：新建 `config/schemas/story-arc-metadata.schema.json`（v1，7 字段族）——`volume_plan[]`（卷数权威）/ `arcs[]`（载体指认 carriers: roster/seat/latent）/ `arc_volume_map[]`（行式职责格）/ `plant_payoff_ledger[]`（close XOR exempt 豁免体系 + 违约/转化收束形态）/ `variation_alloc[]`（mech_ref 引用架构机制）/ `open_window`（滚动窗口）/ `decision_points[]`。
- **scripts**：新建 `scripts/novelos_validate_story_arc.py`——弧数 ×scale 档位（短篇 1-2/中篇 2-3/长篇 3-5/超长篇 5-7）、主线恰 1、映射表机器门（每卷 ≥1 活跃、推进 ≤2 warn、同时活跃 ≤4、禁全推进/全休眠）、载体对账（roster/席位存在性、人物弧必具名、弧首卷 ≥ 登场卷）、台账门（close XOR exempt、收束晚于种下、卷 2 起每卷兑现 ≥1）、变奏对账（mech_ref 存在性、>3 次 warn）、卷计划对表（卷号连续、字数比值 [0.6,1.6]）、open 窗口必填；`--project` 自动解析 scale + 四上游 locked metadata（character/world 未提供时对账整体跳过，不按空集误伤）。`novelos_compose_prompt.py` 四新槽：`book_soul`（direction metadata 机器可读，recurring_tests 逐条编号供 test_ref 引用）、`mechanisms`（architecture 机制清单 + mainline_density）、`prev_volume_outline`（最近 2 卷 locked 卷纲全文——卷际链）、`promise_ledger`（未决承诺 30 + 弧状态 12 + 期待 12——规划端连续性最小集）；canon_minimal 弧窗口 4→8。
- **manifests/recipes/文档表**：story-arc（3→8 槽：+project_setup/persona_gate/genre_pack/book_soul/mechanisms）、story-arc-review（2→12 槽：+双契约全文 + 三上游回执 + 四横向）、volume-outline（4→8：+project_setup/genre_pack/prev_volume_outline/promise_ledger）、volume-outline-review（5→11：+双上游回执 + 四新槽）、chapter-plan（5→7：+project_setup/promise_ledger）、chapter-plan-review（4→9：+character/world 契约 + 卷纲回执 + setup + 账本）；`agent-recipes.json` 同步六行 + slot_vocabulary +4；`documentation/agent-recipes.md` 表再生 6 行。
- **prompts**：story-arc 重写（八行上游消费表：stages 边界对齐/claim_ledger 对账/handoffs 挂接/时序表挂接/代价两轴/演化预留与喂料/book_soul 终点门与 cadence 间隔/架构变奏原文与 burst 对表；载体指认；卷计划；台账三来源与豁免体系；短篇退化形态；open 滚动窗口与增量修订纪律——「写偏的弧是已发生事实」；metadata 出口与 validate 指令；自检 10 项）。story-arc-review 重写（rubric 7→16 项：结构化出口/消费表/载体/两份弧清单对账/时序表挂账/终点门 forbidden_resolutions+protected_dignity/变奏机制引用/盲区门/题材对偶/open 窗口/卷计划对表/上游保护）。volume-outline（弧挂接与前置卷承接节：arc_id 挂接、进出状态双源以上卷实际优先、drift 清单、已退场载体不推弧；种收双对账重写；自检 8→10）。volume-outline-review（+0c 弧挂接、3 双源、7 双对账、10 上游保护）。chapter-plan（+弧线挂接条目）。chapter-plan-review（+7d 弧线挂接：引用已 closed 承诺 = blocking 重复收账）。continuity-candidate-extraction（arc_ref 引用 arc_id slug 约定，不发明新 id）。
- **SKILL.md**：step 5 新增 Story Arc/Volume/Chapter Plan 三段完整输入描述（接替「其余资产按各自 prompt」兜底句）；E4 漂移修正（生成侧回执描述改为「审查侧注入」——架构/战略/世界/人物四处）；新增「story arc metadata 速查表（T38）」。
- **tests**：新建 `tests/test_story_arc_validate.py` 14 项；`tests/test_slot_resolution.py` 新增 `StoryArcT38Slots` 9 项 + `_seed_arc_chain`；存量适配 2 处（canon 弧窗口标题、P2Routing 断言随 prompt 重写更新）。

## 设计取舍记录

1. **弧 id 用 slug 不用 uuid**：弧是少量人工产物（同席位先例——T36 记录过「ID 仪式感不值」），arc_states.arc_ref 与 prompt/回执引用要可读可 grep。
2. **不合并、不换位**：线程轴 vs 事件轴分工正确，坏的是边界装备；换位在依赖方向（volume 消费 arc 三产物、反向零消费）、语义（指令性→事后归纳丢前瞻决策）与增量生产三层面断裂——审计轮已论证，本任务按「装装备」路线落地。
3. **book_soul/mechanisms 走最小集槽而非 upstream 直注**：direction/architecture 全文已注入其直接下游，弧层需要的是机器可读本体（编号引用/机制名核对）——`world_lexicon`/`character_essence` 先例。
4. **persona_gate 而非 persona_full**：弧层 persona 用法是「分配约束」（变奏盲区门/终点校准），不造人不写正文——硬边界渲染足够，重用法（四用法）留给造人与写作层。
5. **台账 close XOR exempt**：`deliberate_silences` 与 open 喂料是仅有两类合法「只种不收」；违约/转化是合法收束形态（收束 ≠ 兑现，违约式收束须让读者看清代价）——修掉了旧 prompt「禁止只种不收」对合法沉默的误伤。
6. **prev_volume_outline 取最近 2 卷**：超长篇 10+ 卷全量注入 token 爆炸；结算承接的时效窗约 2 卷（rolling outline 工业实践）。
7. **E4 修文档不修 manifest**：T34/T35 的 upstream-reviews 是审查侧设计（strength 在审查时强制修复），SKILL 生成侧描述超前了——对齐现实而非扩槽（生成侧注入需动 5 manifest + 预算，收益边际）。
8. **每卷 ≥1 推进放宽为「≥1 活跃 + 无推进 warn」**：终卷全收束是合法形态（CLI 冒烟实测该场景），机器门不误伤终局卷。
9. **卷数权威归弧层**：strategy 只有阶段字数、架构只有 beats_per_volume，卷切分此前无来源（补挖 F1）；网文工业基准 ~30 万字/卷对齐 volume_outline 的副高潮间隔既有设定。
10. **character/world 对账输入可选**：未提供时跳过对账而非按空集全拦（对齐 validate_character 对 world 的 None-跳过先例）——裸跑只查结构与纯内部机器门。

## 验收

- `tests/test_story_arc_validate.py` 新建 14 项（base 全绿/四档位边界/主线恰一/映射表三门/终卷形态 warn/活跃上限/载体四态/登场卷/台账四门/变奏两门/卷号连续/open 窗口/--project 自动解析含 scale 归一化）。
- `tests/test_slot_resolution.py` 新增 9 项（book_soul 编号渲染与缺位占位/mechanisms 含密度与降级/前置卷最近 2 卷与首卷占位/promise_ledger 双态/story-arc 全槽装配 8 节/volume 装配含前置链与账本）。
- **246 tests 全绿**（223→246：+14 +9），compileall / hygiene / manifest 四命令全过；SIZE_BUDGET 零调整（实测 story-arc 73/100、story-arc-review 48/70、volume 80/100 等，重写在原预算内）。
- CLI 冒烟三路径：显式全参 PASS（终卷无推进 WARN 合法）；构造缺陷 FAIL exit 1（载体悬空/只种不收/兑现空窗三缺陷精确命中）；`--project` 真库自动解析（超长篇归一化生效、无 locked 上游时对账跳过只报档位门）。

## 遗留说明

1. **planned-vs-actual 自动 reconcile 未自动化**：目前靠卷纲 prompt 的 drift 清单 + validate 重跑人工触发；正文偏离映射表自动标 story_arc stale（arc_states 对账脚本）留待需要时做。
2. **volume_new 台账行的回写**：卷纲新种悬念进 story_arc metadata 走 change proposal 手工修订，无自动合并（有意——台账是 locked 资产，改它必须走修订流程）。
3. **chapter-plan 的 genre_pack 未加**：章级题材消费经 craft 卡与卷纲转述；需要时一行 manifest 补上。
4. **旧 story_arc 资产（无 metadata）不回溯**：修订时经 change proposal 补齐即可被下游消费（同 T36 world 契约先例）。
