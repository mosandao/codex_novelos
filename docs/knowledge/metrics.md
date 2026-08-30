# 度量记账（M1-M7）

> 依据：R5 总计划 §6 + D5 §4（单一权威）；**责任者=主控**。存储形式=单张 Markdown 表，**追加行**（不覆盖历史行），不建 DB 表、不上脚本仪表盘（过度工程红线）。
> 列结构照 D5 §4：`日期 | 轮次/章 | 指标 | 值 | 阈值判定 | 处置动作 | 留痕链接`。
> 口径纪律（D5 §4 原文）：① M1 误报 = **对话抑制后的叙述层** screen 命中（裁-8），分母按各规则 denominator 三分母口径，跨口径比较无效；② M3 分母 = **预筛候选数**不是 finding 数（`json_each` 条数级统计 + `code LIKE 'fpr-deny:%'` 过滤 note 二义性，裁-2），deny 的对象是机器候选；③ 所有指标先记录后判读，禁止先看数字再挑口径。

| 日期 | 轮次/章 | 指标 | 值 | 阈值判定 | 处置动作 | 留痕链接 |
|---|---|---|---|---|---|---|
| 2026-08-29 | R0 基线 | M1 金丝雀误报率（screen 层 · 22 篇女频短篇叙述层） | L01 0.0581/千字(12)、L02 0.1405/千字(29)、L03 0.9155/千字(189)、L06 0.0048(1)、L07a 0.0388(8)、L08 0.0775(16)、L09 0.0242(5)、L10 0.0339(7)、L11 0.0048(1)、P01 0.0747/百段(11)、P02 0(0)、P03 5.44%(8) | 零容忍语义仅 L06/L11/P02 成立；L03/L02 等 7 条规则在人类叙述层有命中（U1 呈报，按方案 A 分档判级） | 基线留档；此后任何规则/阈值/卡面变更过 `canary --compare`（exit 1 只拦 screen 层） | `docs/knowledge/canary-baseline.json`（rule_table_hash `sha256:1b0cca0e9aae2b04e87047e86e1484eb48970ed2aa949478efe6340752fd9876`，2026-08-29 现值） |
| 2026-08-29 | R2 | M1 规则表回归 | rule_table_hash 与基线一致（`sha256:1b0cca0e…`），`canary --compare` PASS；本轮未动 rule_table（F-5/F-6/F-8 登记不实施） | 无回归 | 无 | `docs/knowledge/canary-baseline.json` + 本轮四命令重跑记录（tasks 账本） |
| 2026-08-29 | R2 | M2 引文验证失败数 | **0**（机器自证：`test-verify-review-evidence.mjs` 15/15 全绿；R2 首测合成回执 verify PASS exit 0；构造 no_hit 实例正确 exit 1） | >0 → Receipt 作废打回；同 reviewer 连 2 次 → 换模型 | 无失败，无 Receipt 作废记录 | `scripts/novelos-verify-review-evidence.mjs` + `scripts/test-verify-review-evidence.mjs` |
| 2026-08-29 | R2 首测（合成夹具） | M3 deny 率 | **43.5%（10 deny / 23 候选）**；分规则：L01 0/4、L03 3/9、L08 0/1、L11 7/9 | =0 且候选 ≥5 → 锚定偏差告警；连续 3 章趋零升级用户 | 首测值仅作 G3 校准基线——**折扣声明：非真实章节数据**（合成 AI 味段、特征高密度埋入），不代表生产分布；真实章节首测后追加行 | `docs/knowledge/redteam/fixtures.md`「R2 轮登记」（回执纯文件级演练，未落库） |
| —（待 R6） | R6 演练 | M4 收敛轮数 | — | 单 subject >3 轮；同因复发 | 升级用户（G6 既有纪律） | — |
| 2026-08-29 | R1→R2 记账 | M5 注入体积 | fingerprint 卡 27,172B / prose-revision 卡 9,585B / prose-review 组装产物 69,433B（R1 G5 实测时点数字；`8badbba` 文本修订后现值 26,720B / 8,167B，组装产物未复测） | 每场景条数/总字节超上限 → 组装 fail()（R3 设计前置） | 七卡 craft_refs 总预算影响随 R3 注入预算对账（U4） | `tasks/r5-plans/r1-g5-redteam.md` F-9 |
| —（待 R6） | 各轮 G4/G5 | M6 红方 finding 修复率 | — | P0 未 100%；P1 <90% | 该轮不得记 DONE（账本纪律） | 各 redteam 文档 |
| 2026-08-29 | R3 | M5 注入体积（card 落盘 + knowledge 槽预算声明） | chapter-draft craft_refs 五卡落盘后现值 **43,836B**（hardrules 8,090 + fingerprint 26,720 + accessibility 5,537〔含 kg-opening 知识模块〕+ worldview-lexicon 1,730 + dialogue-techniques 1,759〔R3 新卡〕）；scene-pacing 1,993B（含 kg-pacing 知识模块，prose-review 侧）；**knowledge:techniques 槽预算声明 4096B**（单条 ≤512B、top-5×2 组、超限按排名截断；scene-maps 转换 155/772 可解析未接线） | 槽渲染 ≤4096B（composer 硬预算）；craft 卡 ≤2,560B 卡面模块（KG1 校验） | 卡面扩充+新卡经 craft_refs 全量注入，对固定层总增量随 U4 注入预算呈报对账 | `scripts/novelos-compose-prompt.mjs`（resolveKnowledge）+ `config/knowledge/distilled.{dialogue,opening,pacing}.json` + `config/knowledge/scene-maps.json` |
| —（待 R6，U11/U-dirs 后） | R6 S0 | 全指标采集时点 | M1=演练前 canary --compare 终值；M2=S4 每次 Receipt verify 后；M3=S4 每章 deny 统计；M4=S3-S5 各 subject 收敛轮数；M5=S4 首章组装产物字节数；M6=全程 G4/G5 findings 修复勾选 | 同各行既定阈值 | 收口报告六指标终值+零污染终证入 `tasks/r5-plans/r6-drill-book.md` §S6 | `scripts/novelos-drill-prepare.mjs`（S0 报告）+ `tasks/r5-plans/r6-drill-book.md` |
| 2026-08-29 | R6 关闭裁决 | M4 收敛轮数 / M6 红方修复率 / R6 S0 全指标采集时点 | **关闭**（用户指令「R6 关闭，待定项关闭」：演练取消，三项指标不再采集，上方「待 R6」占位行按追加纪律作废留档不删） | 指标级关闭，无阈值判定 | 无处置 | `tasks/README.md`「R6 关闭与待定项关闭裁决记录」（2026-08-29） |
| 2026-08-29 | R7-T5 | M5 注入体积（语态槽增量） | chapter-draft 组装产物现值 **54,915B**（R7 基线端到端实测：T4 夹具库+prev_chapter_tail 槽；T0 基线 69,433B 为生产库口径不可直比——项目已清理，两值均为 fixture/现态参考值）；语态节=最近 accepted 章结尾 800 字（不足整段注入），渲染位于 craft 卡后自检节前 | 槽渲染 ≤ 组装 fail() 上限（R3 前置），现值远低于 | 无 | `scripts/novelos-compose-prompt.mjs`（slotPrevChapterTail+TAIL_SLOT 延迟渲染）+ `tasks/README.md` R7 条目 |
| 2026-08-29 | R7-T1 | M2 引文验证口径更新（A1） | `novelos-verify-review-evidence.mjs` v1.1.0：空 findings+approved 从「--strict 才 FATAL」升为**默认 FATAL**（`--allow-empty` 显式豁免留痕）；M2 失败数口径自此含空查回执拦截 | 空回执 exit 1 → Receipt 不得落库（红方 F7 防线默认生效） | 无 | `scripts/novelos-verify-review-evidence.mjs` + `scripts/test-verify-review-evidence.mjs`（15/15） |
| 2026-08-30 | R8-T1 | M7 模型依从性（建档，A8） | 生产库 reviews=0 / chapters=0，**无历史数据可采**——三指标（M7a FATAL 率 / M7b 审查轮次 / M7c deny 率）自首个真实项目章节流起采集，定义与判读纪律见下节 | 低于阈值**只呈报用户裁决，不自动从档位除名**（判读纪律①） | 无处置 | 本文件 M7 节 + `sql-reference.md`「M7 对账查询」（/tmp 夹具库 2-3 行假数据验证过） |
| 2026-08-30 | R8-T3 | M1b 漏报试点（一次性，人工 ground truth，A10） | 试点组（标准管线产出 2 章）：screen 句层 12 规则 **6,334 叙述层汉字零命中**，段层 P01×7/章；人工初标残留 AI 味 **阳性 3/254 段=1.18%**（含边缘 3.15%）——残留全是**表外变体**（抒情点题收束/跨章工整回环/格言句）。参照组（R1 A 组合成段）：11/3/25 命中，表内特征全被抓住（A1 与 R1 登记逐规则一致） | **折扣声明：AI 自评初标+小样+用户抽检未做**——数字只作量级参考不作门禁依据；升格常设基线与否=用户裁决（报告 §6 建议：先抽检复核，表外变体走校准批次流程而非直接扩表） | 无处置 | `docs/knowledge/redteam/missrate-pilot.md`（语料 sha256/逐段标注/方法全录；语料全文在 /tmp 不入仓，rule_table 零接触 canary PASS 自证） |

## M7 模型依从性（A8 · R8 建档）

> 依据：对抗审查 P1-3（「模型无关 ABI」无依从性度量）/P2-7（同一 69KB 产物无差别注入任何模型）；外部实证 dreampowers `tested_model.md`（弱模型多约束并行依从性 15/100）。**本节只定义与记账，不做任何自动处置。**

**三指标定义**：

- **M7a · per-model FATAL 率** = 该模型被 G2 引文验证三路 FATAL（no_hit/missing/hash_mismatch，含 R7-A1 空回执）+ `commit-review` 门拦（reviewer_profile 前缀缺失等）拦下的回执尝试数 ÷ 该模型回执落库尝试总数。分母=尝试数（含被拦未落库者）：落库成功者自 `reviews.reviewer_profile` 聚合，被拦者自门 CLI 输出/组装日志人工归集（门拦零写入，无库内痕迹——口径声明，不为此建表）。
- **M7b · per-model 平均审查轮次** = 同一 subject（`reviews.subject_ref`）从首个 review 到 verdict='approved' 所需 review 数，按 `reviewer_profile` 前缀（`model:`/`agent:`）分列聚合。
- **M7c · per-model deny 率** = 预筛候选中被证伪 deny 的候选数 ÷ 候选总数，自 `chapters.metadata_json` 的 `prescreen` 字段聚合。**分母口径完全复用 M3**（裁-2：分母=预筛候选数不是 finding 数；`code LIKE 'fpr-deny:%'` 过滤 note 二义性；deny 的对象是机器候选）。

**判读纪律**（先记录后判读，沿用口径纪律③）：
1. 低于阈值**只呈报用户裁决，不自动从档位除名**——除名=门耦合指标（过度工程），且在积累一个项目周期数据前任何阈值都是拍脑袋。
2. 模型身份以 `reviewer_profile` / producer 的 `model:` 前缀为权威（P4-2 机器强制，R7 起 gate commit-review 强制）；无前缀行计入「未标记」桶并视为口径违规呈报，不计入 per-model 分列。
3. 对账 SQL 见 `.agents/skills/novel-project/sql-reference.md`「M7 对账查询」节（一次性只读查询，与读路径纪律一致）。
