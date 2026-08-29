# 度量记账（M1-M6）

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
