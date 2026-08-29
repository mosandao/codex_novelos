# R5 · 知识吸收与对抗审查体系(整合版 v2)

> 状态:`TODO`(五方向规划+五红方对抗审查完成,本文为整合裁决后的执行指导;批准后开工)
> 版本:v1(主控单方草案)→ **v2(整合轮)**。v1 的三源资产地图、六道对抗门、七轮骨架被 5 份方向计划细化、经 5 份红方对抗审查(合计 P0×14 / P1×31 / P2×35+),本文是仲裁结果。细节一律以 `tasks/r5-plans/` 各文档为准,本文只持**裁决、契约、排程、验收**。
> 红线继承:零 Python · 单渲染器 · DB 变更先备份 · 3 轮未收敛升级用户 · genre-packs 词表唯一源 · 蒸馏不整表搬运。

## 0. 勘误(v1 → v2 事实修正)

| 项 | v1 说法 | 实测(v2 采信) | 来源 |
|---|---|---|---|
| kb_* 表数 | 31 表 | **23 张**(SHOW TABLES 实数;31 系误计) | D3 红方核查表#7 + 主控复核 |
| kb_writing_techniques 可用条目 | q>=8 | **原始 `BETWEEN 8 AND 10` = 1310 行**;0-100 刻度 133 行(75-93)是另一套打分体系,不混入 | D3 红方 P0-2 |
| 金丝雀文体 | 未声明 | **叙事小说**(女频短篇;非论述文——D5 红方 P1-4 的「论述文」说法有误,主控已抽样复核开头钩子原文) | 主控复核 |
| 生产库迁移状态 | 未声明 | **止于 v18;019(state_machine_links)未应用,chapters 无 review_id 列**;journal_mode=wal | D5 红方核查#12/#13 |
| 唯一项目 | 未声明 | 「诸天无限:从大运开始」(setup v2 完整、规划链空白、chapters=0)——R6 从 direction 起跑成立 | D5 红方核查#9 |

## 1. 整合轮裁决记录(跨方向冲突仲裁)

以下 12 条裁决是五方向红方指出的接口冲突/设计分歧的**唯一权威裁定**,各方向计划与之冲突处以本文为准。

**裁-1 规则编号统一命名空间**(解 D1-P0-2 / D4-P0-1 / D5-P2-5 / D2-C1)
- 主键 = D2 的 **`fpr:<ID>`**(大写编码,如 `fpr:L01`);D2 42 条规则表为权威注册表,B02 增设后 43 条(见裁-8)。
- D1 卡内编号:卡面保留 `FP-x.y` 作**节结构定位符**,每条可判级规则必须登记 `FP-x.y ↔ fpr:<ID>` 映射表(卡头+基线 JSON `adjudication`);T1-T6 真人感门槛改前缀 **`RT-1..RT-6`**(与 D2 翻译腔 T01-T16 消歧)。
- D4 measured_features pattern 改 **`^(fpr:[A-Za-z0-9]+|style:[a-z0-9-]+)$`**;豁免查表键 = `fpr:<ID>`。
- 稳定性纪律(全体系统一):编号发布后**不改义、不复用、只追加**;降级/撤回条目编号保留并标 `retired`(墓碑);映射表由 D1 维护。
- `findings[].code` 前缀注册表(D5 §10 持表):`fpr:`(confirm)/ `fpr-deny:`(deny)/ `exempt:`(豁免落账,值 = `exempt:fpr:<ID>`)。

**裁-2 G3 deny 留痕契约**(解 D5-P0-1):采 **D2 零 schema 方案**——confirm=`findings[].code='fpr:<ID>'`;deny=`code='fpr-deny:<ID>'`+`severity:'note'`+理由;候选总数=`chapters.metadata_json.prescreen.screen_counts`(修订轮 UPDATE 分支须重跑预筛更新)。M3 采集用 `json_each` 条数级统计+`code LIKE 'fpr-deny:%'` 过滤 note 二义性。D5 的 `reviews.metadata_json.prescreen` 结构化对象降级为「schema 合并轮可选升级项」,如落地须带历史 `fpr-deny:` 换算口径。禁止两套并行。

**裁-3 配方注册归属与时序**(解 D5-P0-3):`prose-revision` 的 ASSET_DIRS 注册+modules/manifest 创建+recipes 行 = **R1 前置包**,由 D1 轮执行(D3 出 composer 变更规范,与 knowledge 槽零耦合);约束:**skill 目录/manifest/ASSET_DIRS/recipes 同 commit**,验收 = `--asset prose-revision` 可组装 + guardrails 全绿。`prose-blindtest` 由 D5 自持排 R3;槽位草案改 `slots:["subject"]` + manifest `craft_refs`(craft 卡走独立字段,不是 data_slot——`craft_refs` 不在 SLOT_REGISTRY,G2a 会拦)。

**裁-4 金丝雀数据链**(解 D1-P0-1 / D2-P1-4 / D3-P1-4):选样按实测重写——S 级覆盖 6/13 轴、20 篇 7/13;**甜虐关系(全库第二大轴、20 篇全 B 级)必须补样(A 级 2 篇,优先级并列奇幻轴)**或扩至 22 篇并声明偏离;「危机压身 axis3」失实句删除;`kb_corpus_tags` 由 D3 导出 `data/canary/tags.json` 作选样字典。**格式契约 = D2 装载器**:金丝雀以 `data/canary/g{N}/*.md` 顶级子目录分组交付(jsonl 仅中间产物);基线 `corpus` 记 `dialogue_ratio`;G1「误报」定义 = **对话抑制后的叙述层命中**(显式声明,不靠掩码静默实现);lieflat 母本锚点(全文口径)与金丝雀测量(叙述层口径)对照须标注不可比。

**裁-5 版权与数据通道总原则**(解 D3-P0-3 / D4-P0-2 / D4-P0-3):**入 git 的只有蒸馏后方法论表述;一切原始数据(真书名+原文例句+人类语料+personas 原始卡)落 `data/` 且 gitignore**。具体:D3 原始导出层改落 `data/knowledge/`(gitignore),`config/knowledge/` 只留 distilled/category-map 等蒸馏产物;D4 `data/stylecorp/` 补进 .gitignore 且列为语料落地前置动作(执行步骤含 .gitignore 修改);**personas 走 D4 的 MySQL 直连导入 12-16 条试点**,D3 删除 119 条(97%)staging 导出入 git 的设计(版权红线优先于 staging 便利);导入前 author_name 归并预处理(刘慈欣 5 变体 6 条、前导空格「 Priest」、同作者多行 17 组——归并表进 conversion_notes,无法机械归并呈报裁决)。**本条整体作为 U12 呈报用户确认**(默认方案即上述)。

**裁-6 quality 过滤口径**(解 D3-P0-2):**原始 `BETWEEN 8 AND 10`(1310 行/首批 262 条/14 批)**——0-100 刻度是另一套打分体系(87 分≠8.7 分同质),normScore 仅作排序辅助。全文与 `--verify` 数字统一。

**裁-7 注入通道矩阵**(解 D3-P1-7 / 覆盖文件发现一):
| 通道 | 适用 | 机制 | 轮次 |
|---|---|---|---|
| modules 预组合(selectModules when 路由) | **静态参照**:direction/world 等规划层参照 | 导入时按 genre 预计算模块文件;零 composer 代码改动;组装日志已记 modules id | R4 |
| knowledge: 槽家族 | **动态检索**:techniques/scenes(依赖 locked chapter_plan 场景词) | D3 设计的槽前缀+预算+四步降级 | R3 |
| style_refs 样本 | 签名原文样本(D4) | 槽机制复用 D3,预算区间化:样本 2400-4500 字+摘要 ≤800 字;降级序 5→3 篇保 ≥2 人类语料 | R5 |
| 预筛候选注入 | G3 审查表态 | **过渡(R1-R2)=主控手工附注入文本尾部**;R3 由 D3 落 `prescreen_candidates` 通道(槽或数据区附带,与 knowledge 槽一并定);AGENTS.md 接线措辞用「注入通道以方向3 落地为准」 | R1→R3 |
D3 计划须补「否决 modules 承载动态检索」的理由(参照集随导出更新漂移、预组合生成文件量)——已由本表代裁,回写即可。

**裁-8 G1 tier 分层**(解 D2-P0):`--compare` exit 1 **只拦 screen 层**(rate/count 回归 + 新增 screen 规则误报>0);measure 层只出 diff 报告不拦(`--strict-measure` 显式开关另说)。**L07b(的…的…的)首发 measure**(跨顿号误报前科,RESEARCH 失误#3);**增设 B02**(measure,逐字移植 BASELINE「不是…而是」正则)——与 L01 是交叉包含非覆盖,锚点 0.70/千字属 B02 口径;规则账目 39 源+3 扩展+1 B02 = **43 条**。D2 对 D1 的三条 density×dialogue_ratio 声明(叙述层千字口径/对话内豁免是有意口径/母本锚点仅近似适用叙述密集章)与假阴性监控(`unclosed_quote_spans`/`max_para_mask_ratio`+跨段续引测试)一并采纳。

**裁-9 盲测对照组与素材编备**(解 D5-P1-4 / D5-P1-5 / D1-P1-8;**含对 D5 红方的事实纠错**):
- D5 红方称「金丝雀=论述文」**有误**(与 lieflat 母本语料混淆;金丝雀是女频短篇**叙事小说**,主控抽样复核开头钩子原文确证)。但其批评方向仍成立:**判源泄漏源是「女频 vs 男频」频道差异**,非文体差异。
- 裁决:盲测对照组 = **金丝雀叙事选段**(与 AI 段同为小说文体),选段避开强频道标记;盲测报告对判源结论单列「频道泄漏折扣」;**男频叙事语料授权补采提前至 R0 裁决包**(U13),到位后升级为干净对照。
- 盲测协议以 **D5 §2.5 为单一权威**(长度配对±20%、匿名、判源校准处置),D1 §3.5.d 并入;判据放宽:n=3 不设「≥50% 下降」硬线,改记录项+方向性判断。
- 素材编备规程(R1 起生效):`docs/knowledge/redteam/fixtures.md` 登记每轮 G3/G5 素材来源(AI 段生成模型 `provider:model` 留痕、金丝雀选段 ID);R2 首测允许金丝雀改写段/人工构造段先行校准,标注「非真实章节数据」折扣。

**裁-10 R6 隔离与 019**(解 D5-P0-2 / D5-P1-2):新增裁决点 **U11(019 是否落生产库)**。R6 S0 流程定为:生产库 `wal_checkpoint(TRUNCATE)` → 备份 →(U11 批准则迁移 019)→ `VACUUM INTO`/checkpoint 后 cp 生成 drill 库;S1 冒烟加 `PRAGMA table_info(chapters)`+`schema_migrations` 版本核对;零污染证明 = **checkpoint 后主库 sha256 一致 且 -wal 恒 0 字节**;演练期间生产库只读打开为硬纪律。**drill 库不单独 ALTER**(防副本漂移)。

**裁-11 schema 合并与 migration 编号**(解 D4-F4 / D5 跨方向表):迁移号从 **020 顺序分配**(020-030 非预留段,D4 计划的「031」改 020);R5 轮一次执行 = creator-signature v3 + ownership 枚举重建(020,照 018 模板:CREATE new→INSERT SELECT→DROP→RENAME→重建索引)+ **schema.sql 从生产库重新导出**(夹具基线);review-receipt prescreen 结构化(裁-2 的可选升级)如做,同轮合并。D4 须补 020 SQL 草案进计划(红方 F4)。

**裁-12 红方编排 pairwise**(解 D5-P1-3):写作↔审查、写作↔红方**必须异厂**;红方↔审查**尽量异厂**(撞厂须记录理由,对应 §9 降级条款);§3.4 示例模型改 google/deepseek(与三层表一致)。

## 2. P0 修复清单(各方向进执行的前置门,P0 清零才开工)

| 方向 | P0(红方编号) | 修复动作 | 裁决 |
|---|---|---|---|
| D1 | 金丝雀覆盖失实(P0-1) | 按实测重写选样,甜虐轴补样,删失实句 | 裁-4 |
| D1 | 编号三方断裂(P0-2) | FP↔fpr↔measured_features 映射表+变更纪律+RT- 前缀 | 裁-1 |
| D2 | --compare tier 歧义(F1) | 分层判定+L07b 降 measure+B02 增设 | 裁-8 |
| D3 | 23 表/漏 corpus_tags(P0-1) | 表清单重整+tags.json 导出 | 裁-4 |
| D3 | quality 口径矛盾(P0-2) | 统一原始 BETWEEN 8 AND 10 | 裁-6 |
| D3 | 原始数据入 git(P0-3) | data/knowledge/ gitignore + U12 呈报 | 裁-5 |
| D4 | fp: 接口断裂(F1) | pattern/查表键/§8 全改 fpr: | 裁-1 |
| D4 | stylecorp 未 ignore(F2) | .gitignore 前置动作 | 裁-5 |
| D4 | 种子双通道(F3) | MySQL 直连 12-16 条,D3 删 staging | 裁-5 |
| D5 | G3 双契约(P0-1) | 采 D2 方案,M3/规程四处改写 | 裁-2 |
| D5 | review_id 不存在(P0-2) | U11+S1 冒烟核对+S0 流程 | 裁-10 |
| D5 | 配方注册无主(P0-3) | R1 前置包(D1 执行)+同 commit 约束 | 裁-3 |

**P1 处置原则**:各方向 P1 ≥90% 修复后过**异构红方复审一次**再进执行(红方自己要求的);P2 随批顺手修。主控抽查关键 P1 的落实(尤其 D1-P1-3 编号透传、D1-P1-9 T1×Canon 用例组、D2-F5/F6、D4-F4/F5/F7、D5-P1-5/P1-6)。

## 3. 统一契约注册表(三方引用的单一事实源)

| 契约 | 值 | 持有方 |
|---|---|---|
| 规则编号主键 | `fpr:<大写ID>`(L01 式;43 条注册表) | D2 |
| 卡面定位符 | `FP-x.y`(节结构)+ 映射表;真人感 `RT-1..6` | D1 |
| code 前缀 | `fpr:` / `fpr-deny:` / `exempt:fpr:<ID>` | D5 注册表 |
| 金丝雀格式 | `data/canary/g{N}/*.md` 分组+`tags.json`;基线记 dialogue_ratio | D2 装载器/D1 选样 |
| 留痕位置 | findings[].code + chapters.metadata_json.prescreen | D2 |
| 原始数据 | 一律 data/ + gitignore(data/knowledge/、data/canary/、data/stylecorp/) | D3/D4 执行 |
| 蒸馏产物 | config/knowledge/ 入 git | D3 |
| personas 通道 | MySQL 直连导入 12-16 条,ownership='style_seed' | D4 |
| migration | 020 起顺序;R5 轮合并执行+schema.sql 再导出 | D4 |
| 注入通道 | 静态参照=modules;动态=knowledge: 槽;样本=style 槽(区间预算);预筛候选=R1 手工→R3 机制 | 裁-7 矩阵 |
| 盲测协议 | D5 §2.5 单一权威;对照组=金丝雀叙事选段+频道泄漏折扣 | D5 |

## 4. 轮次计划(修订版)

> 内部节奏不变:G4 规格审→实施→G5 产物审→G1/护栏回归→修复(≤3 轮)→记账。变化处以 ⚡ 标注。

- **R0 基建**:导入脚本(D3)+金丝雀集(**选样按裁-4 重做**)+基线测量(**tier 分层口径**)+素材编备规程建档。⚡裁决包 U1(基线+选样+分组离散度呈报,离散>5 倍标「仅 direction 佐证」)、U12(版权通道)、U13(男频语料授权)。
- **R1 语言层**:⚡**前置包=prose-revision 注册进 ASSET_DIRS/manifest/recipes(裁-3)**;fingerprint 卡修订(编号体系/映射表/RT- 前缀/锚点标注/「不作为」表/豁免条款);prose-revision 双模式(判据编号白名单化,T1×Canon 判定用例组);rubric 增补(编号写入 message 的零代码方案先行);金丝雀回归+盲测(协议按裁-9)。
- **R2 机器校验**:43 条规则表(含 B02)+对话过滤(假阴性监控指标)+canary --compare(分层判定)+引文验证(空 findings 回执防线)+deny 率首测(素材按编备规程)。
- **R3 写作层知识**:蒸馏首批 262 条(裁-6 口径)+knowledge 槽+注入预算(4096B/16% 增量论证补「槽+卡合计」列)+prose-blindtest 配方(D5)+prescreen 候选通道机制化。⚡craft 卡例文「非成稿标准」加机器校验(guardrails 轻规则);跨批 dup_key 聚簇;蒸馏验收加单卡条目下限(≥6 条)。
- **R4 规划层知识**:参照投递走 **modules 预组合通道**(裁-7),词表红线隔离+「非 Canon 无对账义务」标注进参照信封;character 原型取材池、world 设定参照、cool_point/arc 框架参照按 D3/D4 计划分批。
- **R5 立项签名**:⚡备份 DB → migration 020(裁-11)→ schema v3(style_dna+measured_features 按 fpr: 契约)+ schema.sql 再导出;personas 试点 12-16 条(归并预处理);style_refs 样本槽(区间预算+降级序);规划链接口(style_dna 对 direction/strategy 的消费边界=参照素材、无对账义务,溢出影响面入清单)。
- **R6 全链路演练**:S0 隔离流程按裁-10;S1 冒烟含 schema 核对;S2 U-dirs 呈报;S4 接受步骤依赖 U11 已决;红方任务书含「参照素材未被当 Canon 消费」「style_dna 未被当对账源」检查点;收口报告+度量(M1-M6 按 D5 §4,责任者=主控)。

## 5. 用户裁决点总表(预先声明,执行中不再逐次打断)

| # | 时点 | 内容 | 呈报方 |
|---|---|---|---|
| U1 | R0 末 | 金丝雀基线+选样(实测口径)+分组离散度 | D1/D2 |
| U2 | R1 | 双模式边界(编号白名单+T1 用例组) | D1 |
| U3 | R1 | C 级锚点上限 warning(实质收紧确认) | D1 |
| U4 | R3 | 注入预算上限数值(含 style 槽区间) | D3/D4 |
| U5 | R5 前 | schema 变更范围+备份时点(020) | D4 |
| U6 | R5 前 | personas 试点范围(12-16 条+归并表) | D4 |
| U7 | R5 | B 级语料授权(来源/范围/凭证核验) | D4 |
| U8 | R6 前 | 演练项目取材(诸天无限)确认 | D5 |
| U9 | R6 中 | G6 触发的现场裁决 | 主控 |
| U10 | 各轮 | 红方 P0 修复争议仲裁 | 主控 |
| U11 | R6 S0 前 | **019 是否落生产库** | D5/主控 |
| U12 | R0 | **版权数据通道确认**(默认:原始 data/ gitignore、蒸馏入 git、personas 直连) | 主控 |
| U13 | R0 | **男频叙事语料授权补采**(盲测干净对照) | 主控 |
| U-dirs | R6 S2 | 演练方向选定 | D5 |

计划内打断 = U1+U12+U13(R0 批)→ U2/U3(R1 批)→ U5/U6(R5 批)→ U11+U-dirs(R6 批)≤ **5 次批次呈报**(原「≤4 次」按 D5 红方 P1-6 重算修正,U4/U7/U8 随相邻批次捎带)。

## 6. 验收与度量

- 六指标(M1 金丝雀误报率/M2 引文验证失败数/M3 deny 率/M4 收敛轮数/M5 注入体积/M6 P0 修复率)按 D5 §4 执行,`docs/knowledge/metrics.md` 单表,责任者=主控。
- 每轮 DONE 判据:P0 清零、P1 ≥90%、guardrails 全绿(241→含新增 KG 规则)、compose 测试全绿、金丝雀回归通过(screen 层)、账本记账含验证证据。
- 全部计划文档获批后先 commit 固定基线(红蓝双方引用同一 hash——D5 红方 P2-10)。

## 7. 文件索引

| 文件 | 角色 |
|---|---|
| `tasks/r5-plans/00-chain-coverage.md` | 主控管线覆盖盘点+发现(可选素材通道等) |
| `tasks/r5-plans/d{1-5}-*.plan.md` ×5 | 方向规划(细节权威,与本文冲突处以本文为准) |
| `tasks/r5-plans/d{1-5}-*.redteam.md` ×5 | 红方对抗审查(P0/P1/P2 清单+跨方向预警) |
| 本文 | 整合裁决+排程+契约+验收 |
