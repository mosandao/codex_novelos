# R6 · 全链路演练任务书(S0-S6)

> 状态:`READY(待 U11/U-dirs 裁决后执行)`。工具全部就位:drill 隔离 `scripts/novelos-drill-prepare.mjs`(已对 /tmp 副本全流程验证)、组装 `--asset`×25+`--without-slot`、预筛/canary/引文验证/双模式/blindtest。
> 生产库纪律:演练期间**只允许只读打开**;零污染证明 = checkpoint(TRUNCATE) 后主库 sha256 前后一致且 -wal 恒 0 字节(脚本自动输出 `zero_pollution`)。
> 前置裁决:**U11**(019 是否落生产库)——决定 S4 接受步骤可用性;**U-dirs**(演练方向选定,S2 呈报)。

## S0 · 隔离与冒烟(U11 后执行)
1. `node scripts/novelos-drill-prepare.mjs --source data/novelos-v2.db --drill data/novelos-drill.db --checkpoint`
   - 自动:checkpoint(TRUNCATE) → `.bak-drill-<ts>` 备份 → VACUUM INTO 副本 → 双方 sha256/wal/迁移版本/列清单 → S1 冒烟清单。
2. S1 冒烟判定:零污染=true;若 `chapters.review_id=false`(U11 未落),S4 按本任务书 §S4 替代方案执行,**不得造假接受状态**。

## S2 · direction(U-dirs 呈报点)
- 主控:对 drill 库跑 `--asset direction --db data/novelos-drill.db`,产出 2-3 候选 → **呈报用户选定(U-dirs,计划内打断)** → 受控修订锁定。
- 红方任务书 R6-S2:审查 direction 候选——①血缘映射可推导(非贴标签);②候选多样性(两难+组织原则+情感登记两两不同);③**「reference-book-appeal 参照未被当 Canon 消费」**(承诺形态是对照不是抄袭;引用信封句);④keyword:`reference-` 模块内容未出现在 metadata.lineage。

## S3 · 规划链(architecture→chapter_plan,六跳)
- 主控:依依赖序逐级 `--asset <各级>`,每级锁定前对照 schema 自查;参照模块(refERENCE-*×8)按 genre_profile 路由自动注入。
- 红方任务书 R6-S3(每级):①上游消费表逐行有引用或显式豁免;②**八级 reference 模块均未被当对账对象/锁定依据**(抽查 metadata 是否引用参照内容作依据);③数字对账(fulfillment_count/escalation_levels/beats×卷数);④席位认领/种收台账机器门自检过。

## S4 · 写作与审查(R1-R2 机制全开)
- 主控:章纲→`--asset chapter_draft`(knowledge:techniques 槽+craft_refs 自动注入)→落库 draft 前跑 `novelos-prose-fingerprint.mjs`(候选附审查注入尾部,标注仅供证伪)→`--asset prose-review`→Receipt 落库前 `novelos-verify-review-evidence.mjs`(FATAL 即打回)→修订走 prose-revision(按 findings code 定点改,**修订轮重跑预筛更新 prescreen**)。
- 红方任务书 R6-S4:①deny 逐条有因(deny 率异常趋零→G3 告警复核);②修订 diff 未越白名单(未命中句逐字保留);③**「技巧名词不渗入正文」**(knowledge 槽条目名/公式术语不得以名词形态出现在正文叙述层);④指纹类 finding 必带 `[fpr:x]` 编号;⑤ Receipt 引文 100% 机器可验。
- 素材编备:fixtures.md R6 节登记 AI 段生成模型(provider:model)+金丝雀选段;G5 盲测按 D5 §2.5(长度配对±20%/匿名/频道泄漏折扣)。

## S5 · 连续性收尾
- 主控:章接受后连续性提取→账本候选落库(drill 库)→人物注册表对账;六账本+注册表漂移零遗留才开下一章。
- 红方任务书 R6-S5:对账 SQL 与 sql-reference 同源;**「style_dna/measured_features 未被当对账源」**(豁免仅逐特征、经审查引用)。

## S6 · 接受与收口
- U11 已落(019 应用):正常 `acceptChapter(review_id)`;**U11 未落:该步记「接受步骤跳过(待 019)」**,演练收口不受阻。
- 收口报告(本文档追加节):六指标终值(M1 金丝雀误报率/M2 引文失败数/M3 deny 率/M4 收敛轮数/M5 注入体积/M6 P0 修复率)+零污染终证+遗留清单(转 TODO/BLOCKED 入账本)。

## 裁决依赖
| 裁决 | 影响 |
|---|---|
| U11(019 落生产库?) | S4/S6 接受步骤真做还是记跳过;drill 是否含 review_id 列 |
| U-dirs(S2 方向选定) | S3-S5 全部内容的上游 |
| U2/U3(双模式边界/锚点 warning) | S4 审查判级口径 |
| U4(注入预算) | S4 knowledge 槽 4096B/top-5×2 确认 |
