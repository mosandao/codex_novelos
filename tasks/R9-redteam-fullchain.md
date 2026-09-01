# R9 · 全链路红队评估报告（机器层 + 方法论层）

> 日期：2026-08-31 · 执行：主控编排 11 个攻击/情报 sub agent + 主控交叉复核
> 纪律：所有写库实验在 `/tmp` 副本库完成；生产库 `data/novelos-v2.db` 仅两次零写入探针（前后 md5 一致 `6334a4e8…`）；`/Users/yiyi/github/novelos` 全程零接触。
> 范围（用户裁定）：**机器层**（A 创建链 / B 状态机与DB / C+E 章节循环与编排接线 / D 基础设施脚本 / F 联网情报）+ **方法论层**（G 内核 / H 方向与词表 / I 世界与人物 / J 弧卷章与写作执行 / K 审查与连续性 / L 联网基准）。
> 明确排除（用户指令）：数据生命周期与灾备、编排运行时与经济性、供应链与知识源、合规与法律细节、人机裁决协议层、仓内自一致性层、长程规模与多项目层、审计可观测层。

---

## 0. 总体结论

原始 findings 106 条（机器层 49 + 方法论层 57），合并同根因后 **64 条**（阻断 1 / 高 25 / 中 27 / 低 11）。三条根因线贯穿全链：

1. **机器层根因——插件退役后的「纪律化回退」**：R2 时代的 ajv 校验门、六表事务门、mismatch 阻断随 `plugin/` 删除；R7 复活的 gate.mjs 只覆盖 8 个子命令；schema 27 表零 TRIGGER。结果是：**全部状态机约束（锁定须回执/接受须留痕/裁决互锁/stale 传播）只剩 gate 单层防线，任何裸 SQL 直写全部绕过**（M2/M7/M8/M11）。回执验证链可整体自证（M5）。
2. **方法论层根因——「理论与执行断层」**：方法论资产本体质量高（正面基线 20+ 条），但存在系统性断裂：理论卡不在 ASSET_DIRS 永不注入（P26）、审查配方槽饥饿——要求审 X 却不注入 X（P33）、三套字段体系（内核/签名/style_seed）名义焊接结构断裂（P5）、scene 类型不进条件路由（P24）。
3. **两线交汇的最危险点——canon 投毒闭环**（M3+M4）：DB 内容零围栏注入写作与审查两端 + 提取端无过滤 + 审查按 Canon 对照反打不服从章 = 一次污染永久驻留且自增强。外部研究佐证：间接注入成功率 54.2%（Unicode）、OWASP LLM01/08 直接命中、异构厂商≠防共谋（Apple：错误强相关）。

---

## 1. 阻断级（1 条）

### RT-B1 · select 模式内核反查零强制，style_seed 卡可冒充作者内核直达六表落库
- **证据**：`scripts/novelos-compose-prompt.mjs:472-475`（select 只查 kernel_version_id/subject_hash 存在+格式）；`slotKernelFull` :771-775 仅 `WHERE v.id=?` 存在性查询，不查 ownership/status/hash 相符。
- **复现（/tmp 副本）**：payload `kernel_version_id` 指向 style_seed 版本 + `subject_hash:"sha256:000…0"`（与真实 hash 不符）→ `--asset fusion` exit 0，注入文本 239 行「作者内核（第一因的根）」标题下出现 `"seed_kind":"style_seed"`——MySQL 导入人格卡全文被当作内核注入派生 agent，分身从伪内核派生并可落六表。
- **关联**：P5（style_seed 是第三套断裂字段体系）、M2（创建链无任何机器门兜底）。
- **修复**：composer 对 mode=select 加库内三查（ownership='author_kernel' AND status='active' AND hash 相符），fail 即拒；同时收进 gate 新 create-project 子命令。

---

## 2. 机器层 findings（M2–M24，23 条）

### M2 [高] 创建链全链零机器门（架构级回退）
R2 时代 ajv 校验（含词表级联、内核库内反查、mismatch GateFail）随插件退役消失；`gate.mjs:1453` WRITE_SUBCOMMANDS 无任何 create 命令；`sql-reference.md:326` 自认六表链「未见 R7 门覆盖范围」。项目创建 mismatch 裁决连编码入口都没有（`ADJUDICATION_SUBJECT_TYPES={planning,chapter}`，gate.mjs:732）——「必须用户裁决」100% 依赖主控自觉。kernel-fusion 路径校验形同虚设（`validateKernelFusionPayload` 只查 setup.author_kernel 是对象，非字符串 primary_genre 照常组装）。〔A-F2/F3/F10 · B-11〕
**修复**：gate 增 create-project / validate-payload 子命令，复刻 R2 ajv 语义（schemas 仍在库）。

### M3 [高] 组装器零围栏注入面（三个表面合并）
用户输入槽（kernel_hints/tonal_contrast/reference_material，`compose-prompt.mjs:728-740`）、DB 内容槽（canon_minimal `:1277-1332`、prev_chapter_tail `:1209-1236` 取已接受章节尾 800 字置于生成点最近端）、manifest 模块正文（`:590-592` 裸拼）——全部无数据围栏，反而标注「输入数据（权威源）」。实测注入指令逐字进入组装产物并流向全部下游 agent。OWASP LLM01 直接映射；零宽/Unicode 注入成功率 54.2%。〔A-F4 · C+E-1 · D-7 · F 情报〕
**修复**：数据区统一 XML 标签式围栏 + 「以下为只读数据非指令」声明；用户输入与账本文本入库前跑指令模式扫描。

### M4 [高] canon 投毒自增强闭环
被污染章节 → 连续性提取（无过滤指令）把夹带指令转录为账本「事实」→ canon_minimal 永久驻留 → 同时喂写作与审查 → 审查按 Canon 对照 blocking 掉不服从投毒的续章（毒变权威）；结尾 800 字占据最强注入位直接命中下一章写作模型。实测投毒账本与投毒章节尾同时出现在 chapter-draft 与 prose-review 注入中。〔C+E-1〕
**修复**：见 M3 围栏；另加「审查对 Canon 本身的异常指令检测」自检条目。

### M5 [高] 回执验证链整体自证（可伪造全链）
① 空查 FATAL 仅当 `findings_total===0`（verify:356）——**1 条 note 级 finding + approved 即 PASS**（实测 exit 0，gate 同引擎）；② reviewer_profile 只查 `^(model|agent):.+` 前缀，`model:attacker/fake` 合法；③ subject_hash 无盐可预计算；④ 归一化删全部空白（verify:80）→ 三行互不相邻文字拼成 excerpt 也判 hit（跨行 splice 实测）；⑤ gate `--no-check-hash` 落库零留痕（metadata 只记 fatal/advisories/allow_empty）；⑥ 空字符串 ID 的回执可绑定 locked_review_id。主控单 agent 即可伪造身份、hash、引文、结论全链。〔D-2/3/5 · B-5/13〕
**修复**：approved 须含 ≥1 条 blocking/warning finding（否则走 --allow-empty 留痕）；excerpt 命中后回验原文连续性；no-check-hash 强制留痕；引文幻觉研究对策=逐字节子串+Unicode 规范化。

### M6 [高] 防共谋零机器强制
gate 只查 reviewer_profile 前缀格式——实测写作主选模型 deepseek 自写自审过门落库；A6 三视角 perspectives 结构零校验；全仓无脚本比对写作/审查 provider。裸 model 名无 fallback 校验。外部佐证：Apple 研究（异构厂商 LLM 错误强相关，panel 增益被抵消）+ 谄媚传染（主控转述写作方辩解带偏审查者，58.19% 多轮出现）。〔C+E-5 · F 情报〕
**修复**：commit-review 校验 reviewer provider ∉ 本项目写作端记录，冲突即 GateFail；perspectives 三身份与注入卡一一对应校验。

### M7 [高] 状态机纸面化族（零 TRIGGER 的直接后果）
`locked_review_id`（schema.sql:270）与 `chapters.review_id`（:94）均为可空列无 CHECK/TRIGGER：免审锁定、免审接受、已接受章节降级直改、改 content_resource_id 全部成功（/tmp 实测）；rejected 回执甚至空串 ID 可绑定 locked_review_id；019 注释自认「由门工具强制」=gate-only。裁决互锁（assertNoOpenAdjudication 仅 lockAsset:618/acceptChapter:668 调用）直写 SQL 完全绕过——open 裁决期间照常锁定成功。全库 27 表零 TRIGGER 零 VIEW（sqlite_master 查证）。〔B-1/2/3/5〕
**修复**：补 4 个 TRIGGER：locked⇒review_id NOT NULL 且 verdict='approved' 且 subject_ref 匹配；accepted⇒review_id NOT NULL；accepted 行 UPDATE 前置拦截；adjudication open 期锁 lock/accept 写入。

### M8 [高] stale 传播断链 + 双语义漂移
`planning_asset_dependencies` INSERT 只存在于 SKILL 与 sql-reference（主控纪律）；缺边时 gate `propagate-stale --commit` 静默 `marked:0` exit 0；实验库 chapter_plan 零依赖边照常入库（跳步无约束）。sql-reference 手工 stale 模板只标**直接**下游一层，gate BFS（gate.mjs:173-193）才递归——两套语义已漂移。〔B-4〕
**修复**：lock 时 TRIGGER 强制 chapter_plan 须有全部上游 locked 边；gate 增「无边告警」；手工模板改为 BFS 版或标注差异。

### M9 [高] 生产库守卫词法比对绕过（gate + import-personas 同病）
`isProduction = path.resolve(dbPath) === path.resolve(DEFAULT_DB)`（gate.mjs:1487-1491；import-personas.mjs:344 同）——纯字符串比对不解析 symlink 不比 inode。实测：symlink 指向生产库 → `--commit` 无 `--allow-production` 按写模式打开（exit 1 GateFail 来自命令本身，守卫未触发）；大小写变体（stat 同 inode）同病；副本上证实可实际写入。〔B-6 · D-1 · A-F11〕
**修复**：`fs.realpathSync` + statSync dev/ino 比对；非 regular file 一律拒绝。

### M10 [中] 升级机制无锚点族
reviews 表无 round 列；`--round` 可选仅进 index.jsonl（实测 8 条中 7 条 `review_round:null`——常态缺失）；open-adjudication 的 --rounds 手工填报无计数来源；「同因复发」无 issue_key（三视角 code 是流水号 STRUCT-<n> 跨轮不可匹配）；3 轮阈值零实证（M4/M4b 从未采集，R6 演练已关闭）。无限打转不触发裁决是常态而非攻击。〔C+E-3 · K-4/5〕
**修复**：findings 增 issue_key（规则号/受控分类号）；gate 按同 subject reviews 行数在 ≥3 时互锁；首个真实项目补采轮次数据回看阈值。

### M11 [中] 裁决互锁半封闭——「预制品」架空裁决
互锁只封 lock/accept（gate.mjs:710-713 注释明示 commit-review 不拦）；章节草稿写入本就不经门。裁决 open 期间可继续产新 revision、落新 approved 回执，resolve 后立即 accept。〔C+E-4〕
**修复**：resolve 后强制该 subject 重审一次；open 期间 commit-review 至少 warning 留痕。

### M12 [中] composer manifest `modules[].file` 路径穿越
`compose-prompt.mjs:324` 仅查字符串非空；`:527/:577` `path.join(skillDir,'modules',file)` 直读——`../../../../…/secret.txt` 过结构校验，任意文件内容作为模块正文注入（实测）。对照组 craft_refs 有 `^[a-z][a-z0-9-]*$`（:345），modules 没有。〔D-8〕
**修复**：modules.file 加 `^[a-z0-9._-]+\.md$` 且禁 `..`。

### M13 [中] 指纹预筛对抗逃逸 + 流转零保证
① 未闭合引号把整段掩没（prose-fingerprint.mjs:263-266 + :407 对话抑制）→ L01 从 1 降 0，仅 advisory 无阻断；② `──`(U+2500) 替 `——` 躲 L03；③ measure 档措辞（「表面上…实际上」）永不进候选清单；④ 预筛候选→审查注入的衔接纯手工（prose-review 配方/manifest 均无 prescreen 槽；fingerprint 零 DB 依赖不写 metadata_json.prescreen）——漏附=静默逃逸，门与验证器均不校验。〔D-6 · C+E-2〕
**修复**：mask_ratio 超阈值输出显式降级警告并强制随审查注入；fingerprint 增 `--update-chapter` 写 prescreen；prose-review manifest 增 prescreen 槽由组装器自动注入。

### M14 [中] gate 信任 resources.content_hash 列值不重算
loadSubject（gate.mjs:503-517）直接取列值，commitReview/bindReviewGuard 均比列值从不 `sha256(content)` 重算。resources 由主控直写，列值与 content 脱钩时 hash 绑定失效。〔D-4〕
**修复**：门内重算并要求一致，不一致 GateFail。

### M15 [中] 投影验证与删除风险
`--verify` 是目录内自洽校验（render:822-849 仅遍历 manifest.files 比本地 sha）——同改 manifest 即通过、多余文件不检出、无 DB 回比、无独立 verify 入口；同名无 manifest 目录静默 `rm -rf`（:396-412 归属校验仅当 manifest 存在且可解析）；gate/compose 对不存在 --db 建 0 字节库文件（读用途留副作用）；`--flag=a=b=c` 静默截断（compose:1745-1747 split limit 丢余段）。〔D-9/10/11/12〕
**修复**：verify 增 DB 快照回比+目录扫描+独立入口；无主目录删除前要求确认；读路径 readOnly+写路径先 stat；flag 用首个 indexOf 切分。

### M16 [低] 双版本机制漂移
`PRAGMA user_version=0` vs schema_migrations=22；user_version 零读者、无迁移 runner（002-022 全人肉）。当前无直接攻击面，未来引入 runner 会误判基线。〔B-10〕
### M17 [低] CLI/第三方工具 FK 默认 OFF
sqlite3 CLI 下插幽灵 project_id 成功、删父留孤（实测）。AGENTS.md 明文允许「人类用任意 SQLite 工具打开」，node:sqlite 默认 ON 只保护 scripts/ 路径。**修复**：AGENTS.md 声明 CLI 须手动 `PRAGMA foreign_keys=ON` + 周期性孤儿检测脚本。〔B-7〕
### M18 [低] `类型:uuid` ID 格式零 CHECK
`'EVIL; DROP TABLE projects--'` 与空串均可作主键（实测）；gate.mjs:501/509 的前缀解析可被畸形 ID 扰乱。**修复**：各表 id 加 `CHECK (id GLOB '<type>:*')`。〔B-8〕
### M19 [低] open_adjudications 注入槽单消费者
唯一消费点 composer:1239-1273；render-projection 与 novel-memory/novel-writing SKILL 零命中——裁决 open 期间人类看投影无警示、不经组装器的写作上下文对未决裁决无感知。〔B-9〕
### M20 [低] `VACUUM INTO '${drill}'` 字符串拼接进 SQL（drill-prepare.mjs:65，本地工具低危）。〔B-12〕
### M21 [低] schema 信封洞族：kernel-candidate `{"foo":"bar"}` 过信封（minProperties:1）；derivation 信封 signature 段无 additionalProperties:false 且不 $ref；**v3 签名不强制 persona/cannot_write**（schema:44-52 只对 v2 强制，sql-reference 自查清单同样只写 v2）；词表级联零结构编码（primary_genre 仅 1-30 字符）；表里互斥纯纪律（surface=core=「爽」通过）。〔A-F5/6/7/8〕
### M22 [低] 六表模板 content_hash 纸面化：模板展示占位符、计算在注释、手工路径无落库后复验工具（import-personas 有抽查，主控路径没有）。当前库 30 行实测全对。〔A-F9〕
### M23 [低] knowledge 槽缺文件=静默零注入（compose:1448/1523 设计如此）——静默删 compliance 蒸馏文件后合规知识零注入无痕。〔C+E-11〕
### M24 [低] 测试盲区矩阵：gate 无 symlink/大小写/no-check-hash/note-only 例；verify 无 splice 反例/伪造身份例；fingerprint 无「命中被掩没」对抗样本；render 无同改 manifest/无主目录例；compose 无穿越例。〔D-13〕

---

## 3. 方法论层 findings（P1–P40，40 条）

### 内核与分身（G 组）

**P1 [高] 八维 MECE 破产**：emotion_processing（K:38「幽默化」）与 defense_compensation（K:41「用玩笑回避脆弱」）同种防御两维认领；core_needs 与 attachment_pattern 互相侵入；价值排序在 identity（value_axioms/emotional_stance）与 psychology（moral_intuition）两层三处安家——签名层有 2.2 分工表硬边界（S:102-110「同一约束只许住一个字段」），内核层没有对应机制。〔G-F1〕
**P2 [高] 内核零跨段/跨维一致性检测**：schema 硬保五段齐全（这点好），但交付自检（K:97-104）全是存在性检查——「identity 冷峻 + aesthetic 甜腻」可同时通过 schema 与自检；根节点矛盾无衰减传播每个分身。签名层有「基调兼容」检查（S:191），内核层没有。〔G-F2〕
**P3 [高] 「内核=第一因」与「风格=盲区总和」内部互斥**：K:7 宣称「知识边界不变」，S:8 宣称「风格恰恰是盲区的总和」且盲区来自 per-book 虚构生平（S:90/37 阶层圈子库存）——方法论认定风格之根是人生库存，却把根节点设计成没有人生库存的东西。跨书声音一致性实际无人认领。〔G-F4〕
**P4 [高] 四归因零程序零量化**：express/slot/setting/kernel 四句话定义（K:56-57），无判定树、无正反例、无多因裁决规则，由持有内核的同 agent 自评无独立复核——唯一能触发根节点重写的机制，误归因即根节点漂移且 growth_log 不留推理。〔G-F3〕
**P5 [高] style_seed 15 卡=第三套断裂体系 + 数据治理失守**：15 卡全部 18 字段旧结构，既不对齐内核（identity/psychology）也不对齐签名 v3（七字段+style_dna+measured_features）；tier C 承诺「measured_features 引用种子卡声明值」但卡内是叙述句非区间/档位，schema 强制区间——**从这些卡根本产不出一条合法 measured_feature**（结构性不可满足）；quality_score 全 9-10 零方差、8/15 narrative_drive_score=null、二手蒸馏无凭证要求、按书拆卡（三体1/2）反证「跨书不变」公理。〔G-F7/F8 · 关联 RT-B1〕
**P6 [中] 盲区只收材料向**：「写不了群像/多线 POV/大场面」的手法盲区两头没家；绕开固定四招（侧写/借他人之口/留白/转喻）高频使用成跨书可识别系统腔；审查发现「实际写不了 X」无回流更新 cannot_write 的路径。〔G-F6〕
**P7 [中] voice 框架缺位**：tone（语气/态度）、幽默与反讽、叙事距离/POV 纪律全链无字段——种子卡有（三体1「叙述者语气像科学报告」恰属 tone 层）而目标 schema 没有，再证 P5 断裂。〔G-F9〕
**P8 [低] personality→prose 决定论无证据强度声明**：人格与书面语言仅弱-中相关（Moreno et al. 2021）；tier D 用户全链零风格实测（D 级强制 measured_features 为空）——「心理画像+虚构生平+零测量」直跳成文。〔G-F10〕

### 方向/架构/战略与词表（H 组）

**P9 [高] direction 差异化只「对内」不「对市场」**：比较表（prompt:116）只比自家候选；book_soul 十三字段无对标/竞品/差异声明；仓库现成的 scenario-atlas（26 题材 260 桥段带代表作）只给 World 当镜子。书内唯一性≠市场差异性——「玄幻+系统流」换个组织措辞照样同质化。编辑/市场视角在三视角审查中也缺位（L-6）。〔H-1 · L〕
**P10 [高] genre-packs 均质模板撑不起「唯一词表源」**：全 30 包 4/2/3/3 条同构（power/dilemmas/expectations/taboos），361 条目平均 **11.6 字/条**（最短 3 字「作者藏牌」）；跨包重复 12 条；全向包≈男频压缩版（现实 5/12 重合）；且零运行期消费者（运行时只有 test-guardrails G1 读它查结构）——direction 的 central_contradiction「从候选池变形」实际每题材只有 2 个起点。〔H-2/H-8〕
**P11 [高] 平台工业常数全缺**：番茄 10 万字完读率及格线（脑洞≥15%/传统≥10%）、章长 2050-2300、晋江顺 V 七八万字、上架存稿 20 章、首日吸量等硬指标无一处进入方法论；platform 模块止步 direction/architecture/strategy 三层，卷/章（卡点排布的执行层）无 platform 条件模块；「前3章定生死/前10章兑现/首收前30%」三处数字互不引用无出处。外部数据信号（成绩/弃文预警）零回流接口。〔H-3/H-9 · J-5 · L-1/L-3〕
**P12 [中] 画像生成与商业包装无人认领**：reader_profile 仅由 setup 回传，贫信息时只「声明消费受限」无生成方法；书名/简介/标签/封面（签约第一道审核对象）在八类规划资产中零对应。〔H-5 · L-1〕
**P13 [中] 表里揭示排期在下游蒸发**：direction 强制「写明在哪里反、何时揭」（:60），strategy 七行消费表与 book_soul 均无 tonal_reveal_schedule 字段接住——只传递了标签化反差声明，中段渐渗/终局揭底无人排期。〔H-6〕
**P14 [中] 题材阶段形态只映射 5/30**：「玄幻=境界突破弧…都市=里程碑弧」五值枚举，武侠/历史/军事/轻小说等 20+ 题材现场自造且 packs 不携带 stage_form。〔H-7〕

### 世界与人物（I 组）

**P15 [高] 日常民生维度完全缺失**：吃穿住行/物价/疾病医疗/节庆在主件+8 扩展件中零要求（对照 Wandering Words/SFWA checklist 为核心小格）；网文日常章高频，Writer 现场发明→连续性漂移无基准可审。〔I-1 · L-2〕
**P16 [高] 力量体系无最低产出下限**：dimension_costs minItems:1 是唯一数字门；等级阶梯/每能力硬限制全在自愿触发的扩展件——Sanderson 第二律（Limitations>Powers）恰是行业核心却不在主干；升级流也可只写 1 条代价过审。〔I-2〕
**P17 [高] 席位 power_tier 硬套所有题材**：seats 必填 power_tier（schema:18），女频方法论明言力量只是「筹码不是结算轴」（channel-female.md:7）——都市言情/纯现实为过 minItems 被迫编造力量档位。〔I-3〕
**P18 [高] 长篇支撑判据薄且单向**：喂料储备仅 terminal_mode=open 强制，closed 超长篇无储备要求；卷数权威在 story_arc 而 world 无法对账「储备量 vs 卷数」——百万字中期喂料枯竭只能事后补。〔I-4〕
**P19 [中] 席位自标自证 + 关系位无格**：world 自标主要席位、character 只对账标注（漏标无人查）；一人多席无限制；「正妻/宠妾/白月光」类命运关系位只能挤进 org/duty 自由文本。〔I-5/6〕
**P20 [中] 题材裁剪是散点分档非矩阵**：仅经济/人文/历史三格分档，力量/地理/民生无——两头漏：都市文被迫答力量体系、玄幻文可漏答地理通行逻辑。〔I-7〕
**P21 [中] 4 件薄方法卡与 atlas 职责重叠**：world-rule-system(15行)/world-social-power(8行)/world-growth-resource(8行) ≈ universe-atlas 对应节，仙侠项目 use_when 全命中无优先级仲裁。〔I-8〕
**P22 [中] 升级曲线与卷纲无强制锚点**：人物↔world 有门（越阶=blocking）但 world 境界阶梯×卷次无对账；消费时序表无「境界×卷次」样例。〔I-9〕
**P23 [低] 宗教/语言文字/种族/地理低格**：宗教仅「一个禁忌」擦边（对照 175 问模板标准维度）；地理无「何时必须立档」判据。〔I-10/11 · L-2〕

### 弧/卷/章与写作执行（J 组）

**P24 [高] scene 类型不进条件路由**：全部 manifest 的 when 只有 channel/platform/genre_profile/has_kernel；craft_refs 固定 5 张，scene-fight-craft/scene-dialogue 仅「按需 Read」+ use_when 描述；审查端 manifest 也无两张场景卡——最高频场景的技法注入与审查对表全靠 writer 自觉。〔J-1〕
**P25 [高] scene-fight-craft 全文 7 行**：唯一硬规则「每轮改变距离/资源/伤势/信息/心理优势其一」；空间锚点、单挑/一对多/群战分型、标志事件、短长句节奏、伤害一致性（连续性接口）全缺——战斗占玄幻三四成正文。〔J-2〕
**P26 [高] 承诺-兑现理论错层族**：DB promise_events 五态（plant/progress/twist/resolve/break）vs 方法论只覆盖三态（种收台账 plant/payoff/close，twist 无登记时机、断言式 vs 悬念式无分类学）；story-expectation-design（期待+意外/释放阶梯）与 story-causal-structure、story-pov-tone-contract 均不在 ASSET_DIRS——理论卡与执行层物理隔离，弧/卷/章组装永不注入；promise_events 分录表未被任何注入槽消费（021 注释自称解决「300 章断线伏笔不可审计」，审查视角仍看不到事件流）。Sanderson 理论对照再缺四点：场景级微承诺三层嵌套、基调承诺（tone promise）、兑付规模校准、twist「重释不背叛」的读者公平性规则。〔J-3 · K-9 · L-4〕
**P27 [中] 「高潮」无操作定义 + 兑付过载**：卷纲高潮门三硬判据可判但 climax 本身自由心证（不可逆点？多流汇合？）；小兑现无章距上限；伏笔忌单点集中引爆无分布约束。〔J-4 · L-3〕
**P28 [中] 盲区绕开无正例教学**：硬禁令+四技法一行公式，零好坏对照例句（对照 pov-tone-contract 有例句）；sub agent 拿到一行公式，绕开质量靠运气。〔J-6〕
**P29 [中] 爽文卡过薄 + 三处频率口径自相冲突**：shuangwen-techniques 全文 11 行且 :7「不套固定章数公式」直接推翻 scene-pacing「小爽3-5/中爽10-20/大爽50-100」与 coolpoint-cadence 四档阶梯——三处两套口径；打脸三拍只在章纲参照不在正文卡；mobile-formatting 7 行无阈值而 hardrules 135 行量化（排版双标）。〔J-7〕
**P30 [中] 行业技法缺**：黄金三章的章级分工与信息配比（前500字主角/前1000字困境/5%世界观+70%代入+25%悬念）、章中钩（每800-1200字微钩）、伏笔回收窗（短线10章/长线30万字、行为伏笔需暴露2-3次、回收分散）。〔J-8 · L〕
**P31 [中] 章纲无场景级字数分配**：场景序列无 word_share/三拍职责字段——2-4 场的实际重心由 Writer 现场决定，章纲对节奏的约束力漏气；防「梗概化」仅一句「不要写正文」。〔J-9〕
**P32 [低] scene-dialogue 与 dialogue-techniques 重叠（两套数字口径）+ POV 场景级切换纪律缺位（多视角书章内/场内禁切无规则）。〔J-10/11〕

### 审查与连续性（K 组）

**P33 [高] 审查上下文饥饿族（prompt 假设 vs 组装 ABI 断裂）**：① cross-consistency-review 要求审「人物契约×世界契约」三组交叉，配方 slots（recipes:475-484）却只有 direction/architecture/strategy——**被审的两份契约不在注入内，只能对想象审一致=随机通过**；② entity-authority-review 与 planning-quality-review 仅 subject 槽，要求对照的注册表/roster/微档案/快照/正文全不在注入内（「变更溯源」=幻觉检索）；③ prose-review 要审「声音趋同」但只给 5 章标题+摘要（无 prev_chapter_tail 槽）；要核「世界规则/时间位置」但只有词表无规则条文；要核 book_soul 忠实度但 book_soul 未注入（全产物仅出现 1 次=判分指令本身）。注意：guardrails G2 只查 recipes↔manifest 全等——接线自洽但查不出「该有而没有」的槽。〔K-1/2/7/8 · C+E-9〕
**P34 [高] 六账本漂移矩阵四类无覆盖**：候选类型仅六类；**故事时间（无章→时间锚点账本）、数值（身高/收入/战力，characters 无属性建模）、地理（无位置账本）、离屏时间+物件持有**四类结构性盲区；facts 仅近 12 条滚动窗——慢变量（伤势恢复/道具）滚出即系统性不可见；AI 长文研究佐证：地理/时间属「长程错误」需分型检测、错误在长输出尾部聚集（位置偏置无防护）。配角关系网（几十角色靠记忆=公认后期崩点）无账本。〔K-3 · C+E-6 · L-3/5〕
**P35 [中] 审查标准 vibes 占比 25-40%**：planning rubric 内部双态——编号条目极硬（死亡四问/退场七型/≤30万字/±2 beats），遗留条目纯形容词（「清晰鲜明」「是否合理」「阶梯递进」）；prose 语义层 ~20 项中 5-6 项 vibes。LLM 审查者对 vibes 条目只能语感抽样放行=系统性通过通道。另缺编辑侧 line-level 清单（对话标签/show-telling/场景目的性/重复裁剪）与动机-行动一致性链核查。〔K-10 · L-6〕
**P36 [中] 三视角卡 severity 用 `suggestion` 与主 schema（blocking/warning/note/strength）冲突**——落库归 note 还是弃置无规则。〔K-11〕
**P37 [中] entity-authority 只查授权存在性不定义优先序**——正文 1.85m vs 契约 1.78m 谁赢无裁决链（「以较新为准」一句藏在 novel-memory SKILL）。〔K-12〕
**P38 [中] 读者知识状态半盲区**：角色 knows/not-knows 只在规划层，正文审查无 per-character 知识清单注入——「角色说漏嘴」类漂移无对照数据。〔K-13〕
**P39 [中] prose-blindtest 无样本量与显著性设计**：未规定段对数 n（n=3 全对概率 1/8）、无判源准确率阈值、单 judge 无一致性度量、对照源身份未声明。〔K-6〕
**P40 [低] 兜底审查最弱管最广（「口号级=warning」无判据）+ continuity-review 唯一无判级条目 + 盲测超配对处置不完整。〔K-14/15/16〕

---

## 4. 正面基线（防止一面倒，修复时不要误伤）

1. **DB 真约束在位**：同 scope 单 locked 唯一索引、单 open 裁决唯一索引、sha256 CHECK、status/asset_type CHECK、node:sqlite v22.22.1 FK 默认 ON、gate 事务边界（BEGIN IMMEDIATE+ROLLBACK，中途 FK 失败整体回滚实测无半写）。库内 15 张 personas 卡全量复验干净（30/30 hash 重算 OK、无孤儿）。
2. **不可绕过项实测**：`--asset` 白名单拒绝路径穿越；lock/accept 对不存在 ID 显式 GateFail 非静默；投影文件名 sanitizeFilename+_withinRoot 双防。
3. **guardrails 409 全绿**：recipes↔ASSET_DIRS↔catalog-manifest（360 文件 sha256）三方一致——WP3 防线真实有效（盲区在「该有而没有」的槽，见 P33）。
4. **方法论资产本体质量高**：种收双账闭环+volume 双对账、78 部书 519 条拆解的数据驱动 coolpoint-cadence、章级三拍（分级→执行→结算）、反百科原则+消费时序表、代价两轴+book_soul if/then 机器锁、规则六角色、universe-atlas 显式吸收 Sanderson 三律、planning 九件 rubric 实质差异化非模板换标题、指纹判级反滥用设计（fpr 编号+不作为表+基线折扣）、提取端五条可教边界、反模板工程（危险结构清单+70% 滚动去重）、五段式 schema 硬保证、tier 诚实纪律（D 级强制空 measured_features 有 allOf 机器约束）。

---

## 5. 修复路线图（ROI 排序）

**P0 批次（立即，全是小改动大收益）**
1. RT-B1：composer select 三查 + gate create-project 子命令（M2 一并收口）
2. M9：realpath+inode 守卫（gate 与 import-personas 两处）
3. M5：note-only approved 拦截 + no-check-hash 留痕 + excerpt 连续性回验
4. M12：modules.file 白名单正则
5. M7：四个状态机 TRIGGER（023 迁移）

**P1 批次（高危收口）**
6. M3/M4：数据围栏 + 提取端指令扫描 + 审查对 Canon 异常指令自检
7. M6：reviewer provider ∉ 写作端校验
8. M8：锁定强制依赖边 + gate 无边告警
9. M10：issue_key + round 列 + 同 subject ≥3 互锁
10. P33：配方补槽一族（cross-consistency 补 character/world、entity/planning-quality 补上下文、prose-review 补 prev_chapter_tail/book_soul/世界规则摘要）——多为 agent-recipes.json 单文件改动
11. P24：scene_type 进执行卡与路由
12. P26：expectation-design/causal/pov-tone 注册进 ASSET_DIRS + twist 登记时机收编

**P2 批次（方法论内容建设，需蒸馏/调研）——前置知识调研已完成，见 §7**
13. P10/P11：genre-packs 分级扩容（taboos≥6 三分类/dilemmas≥4/stage_form 键）+ platform-constants.json 单源收敛（三模块引用）——§7.2 已备底料（起点官方十禁/毒点分类/平台常数表）
14. P15/P16/P17/P20：world 民生最小集 + 力量体系按题材下限 + power_tier 条件化 + 题材×维度投入矩阵
15. P1/P2/P5：内核 identity×psychology 分工表 + 交叉一致性自检 + 种子卡 v3 映射表
16. P9/P12：book_soul 增 market_position（对标+差异声明）+ 画像推导节 + commercial-package 资产
17. P25/P29/P30/P31：战斗卡扩为分型技法卡 + 爽文卡收编三拍与统一口径 + 行业技法三条 + 场景字数分配

**P3 批次（低优先与卫生）**
18. 死引用清理（KD:10 校验门已退役、SKILL `--asset continuity-quality-review` 不存在）
19. M16-M24、P36-P40 逐项
20. M24 测试盲区补例（symlink/splice/note-only/对抗样本/同改 manifest）

---

## 6. 附：证据索引

- 机器层实验库：/tmp/rt-b.db、/tmp/rt-c.db、/tmp/rt-d.db（副本，实验后已清理或保留于 /tmp）
- 关键 PoC 命令留存：RT-B1（伪内核 payload+fusion 组装）、M5（note-only 回执 verify PASS）、M9（symlink+--commit 越守卫）、M12（file 穿越）、M7（免审锁定/降级直改/裁决期锁定）
- 外部来源：OWASP LLM Top 10 2025、EchoLeak、Unicode 注入研究（54.2%）、Apple correlated LLM panels、SycEval、Sanderson 三律/2025 讲座、番茄/晋江/七猫编辑公开标准、ConStory-Bench、Moreno et al. 2021——URL 见各组报告原文

---

## 7. 知识补充增补轮（2026-08-31 → 09-01 · GitHub skill 库调研 + 联网行业知识）

> 目的：为 §5 P2 批次（「方法论内容建设，需蒸馏/调研」）补齐前置知识。手段：GitHub 小说写作 skill 库深挖（用户授权）+ 联网检索。方法：主线程 WebFetch/WebSearch 直采（sub agent 通道两次 TLS 故障后改为主控直采）。

### 7.1 GitHub 小说 skill 库调研（4 库，逐库对照 NovelOS 缺口）

**① zenstory-ai/oh-story-claudecode**（网文 skill 包，约 3.2k 星；[repo](https://github.com/zenstory-ai/oh-story-claudecode) · [skillsllm 镜像](https://skillsllm.com/skill/oh-story-claudecode)）
- **拆文维度**（对 P10/E——genre-packs 与拆书能力）：长篇拆文=「黄金三章、爽点设计、节奏分析」，输出「五维评分+爽点密度+可借鉴套路」，文风分析覆盖「句长/标点/对话潜台词/情绪节奏+原文锚点」，故事线「框架识别+4 剧情+2 故事线」；短篇拆文有「54 个情节节点（原文引用+情绪标记 −9~+9）」「爆点 6 维」「共鸣 9 层」「POV/对话/信息差/物件钩子等 11 项写作手法」。
- **story-deslop 去AI味原则**（对 M13）：「blocking 只限确定性句式/标点问题，其他提示按读感判断」——与 NovelOS screen/measure 分层**同构**，佐证现有设计；「朱雀等外部检测只作自测参考，不替代人工读感」；自曝教训 v0.7.5「清掉过度累加的限制指令，其中一条把普通的『他说』判成违规」——**指纹规则过密会误伤**，与 M1b 折扣纪律互证。
- **流程缺环**（对新环节建议）：扫榜→拆文→商业化写作三步；NovelOS 八级链**没有「拆书学习/扫榜选题」环节**（kb 表有数据但无工作流），oh-story 的 `/story-import` 逆向导入后续写也值得对照。
- **上下文管理**（对 canon 预算）：「上下文状态分层管理」；v0.7.6「每次会话固定加载文本再降两成（开书 −30%、回炉 −41%）」。

**② danjdewhurst/story-skills**（端到端小说 agent skill；[repo](https://github.com/danjdewhurst/story-skills)）
- **物件/知识状态持久化**（直接补 P34 四类盲区中的两格）：「Scene records and continuity state make **character knowledge, object ownership**, and setup/payoff tracking durable」——artifacts 带 `status: destroyed` 字段；角色死后出场强制移入 mentions 字段。NovelOS 六账本正缺 object ownership 与 per-character knowledge 两本。
- **机器可查的连续性契约**（对 gate 思路）：CLI「treats contradictions like a compiler treats type errors」——可检出「payoff 先于 setup」「未引爆的 Chekhov 枪」「问题在引入前被解决」「引用缺失章节」。与 M7/M8 的 TRIGGER 修复方向同构：**承诺时序可机器判定**。
- **结构**：双向引用注册表（relationships bidirectionally maintained）、timeline.md、questions//promises/ 子目录——对照 NovelOS promise_events 表（有表无事件流消费，见 P26）。

**③ haowjy/creative-writing-skills**（13 skill 写作系统；[repo](https://github.com/haowjy/creative-writing-skills)）
- **voice 从实测语料来**（对 P5/P7 修复方向）：`style-creator` agent「Analyzes prose samples to produce **style reference files** for the project's voice」+ 周期性「voice check」——与 NovelOS `measured_features`（fpr: 契约）设计同路，印证「种子卡叙述句必须档位化/实测化」的修复；llm-writing skill「Intentional language discipline: **catches unchosen LLM defaults**」——指纹规则扩表（F-5/F-6 登记）的外部参照。
- **kb/issues 持久问题追踪**（对 M10）：issue 跨轮追踪有独立目录——NovelOS「同因复发」无 issue_key 的修复可借鉴其结构。
- **写作五模式**：fresh draft / revision / bridge / alternate take / line polish——NovelOS prose-revision 双模式可对照扩「bridge（衔接章）/line polish（润色）」两档。

**④ wfcz10086/AI-automatically-generates-novels**（AI 长文工具，数百家工作室在用；[repo](https://github.com/wfcz10086/AI-automatically-generates-novels)）
- **分阶段评分菜单**（对 P35 vibes 条目修复）：大纲层评分维度「深化冲突/增加伏笔/强化感情线」、正文层「改写视角/去除说教/润色升华」——可作为 planning-review/prose-review 的 checklist 候选条目来源；「AI 根据自我评分实现迭代（设定分数和迭代次数）」——对照 M10 升级阈值机制。
- **组织方式**：按阶段分层（大纲→章节→内容）非按题材；「多套小说提示词库管理」+变量系统（`${background}/${characters}/${relationships}/${plot}/${style}`）——与 NovelOS 配方矩阵同构，佐证 recipes 设计是主流做法。
- **拆书反哺**：拆书结果入知识库「被引用组装到提示词中」——NovelOS R5 knowledge 槽已实现同路线（场景词检索 top-5×2），验证方向正确。

**库调研小结**：NovelOS 在「配方矩阵/指纹分层/knowledge 槽/measured_features」四点上与头部开源做法同构或更细；真正缺的是 ①拆书/扫榜工作流环节 ②物件持有与角色知识两本账 ③承诺时序的机器检查 ④voice 实测参照文件闭环 ⑤issue_key 跨轮追踪。

### 7.2 行业知识补充（taboos/毒点/平台常数）

**起点创作学院官方「十项通用禁忌」**（[原文](https://write.qq.com/portal/content/21467782608087801)——全类型 taboos 扩容的官方底料，直接回应 P10「taboos≥6」）：
① 亲友背叛（尤其女主，**假背叛同样致命**）② 女主失贞（含潜在女性角色）③ 主角单方面受辱（可有骨气地败，不能耻辱地败）④ 出人意料的挫折（暗算顺利却突然失败）⑤ 大乱斗（无等级标准=体系崩坏）⑥ 多主角（破坏代入感；群穿例外）⑦ 恶搞（破坏真实感）⑧ 恶趣味（作者私愿分心）⑨ 不舍弃该舍弃的创意 ⑩ 突破道德底线（如拿空难写穿越）。**题材特化实证**：竞技题材主角挫折禁忌「视情况而定」——禁忌并非全类型均质，印证 P10「题材×禁忌矩阵」修复方向与「模板填空」批判。趋势句：「读者平均年龄进一步降低→更简单的剧情、更明快的节奏、悲剧承受度更低」。

**毒点体系其他来源**（taboos 三分类的「读者雷点」层素材）：十大毒点（绿帽/主角弱智/圣母/降智等，[搜狐](https://www.sohu.com/a/234316624_100113218)）；逆苍天四大雷区（「主角的女人不能出轨」等代入感逻辑，[中国作家网](https://www.chinawriter.com.cn/n1/2016/0704/c404024-28522220.html)）；女频特化=「双洁/排雷」文化已成言情普遍避雷要求（[三联](https://www.lifeweek.com.cn/article/176377)、[36氪](https://m.36kr.com/p/1834408295801345)）——女频包 taboos 须含双洁声明位；毒点分类明细（[知乎](https://zhuanlan.zhihu.com/p/8669295463)，反爬 403 未逐条取回，条目框架以起点官方十禁+上述两源为准）。

**平台工业常数**（L 组 §6 已给，此处归拢为 platform-constants 草稿表数值——来源见 L 组 URL）：番茄章长 2050-2300 字/日更 6000/10 万字完读率及格线（脑洞≥15%、传统≥10%）/首日吸量 400+/4-7 天二波给量/8 万字验证期+3 周首秀期/上架前存稿 20 章；晋江顺 V 约七八万字/入 V 收藏线（言情 300、耽美 500）/前三章定生死；通用：开篇黄金 500 字、章中微钩 800-1200 字（J 组 P30）。

**题材 stage_form 草稿表**（补 P14「只映射 5/30」；标注=草稿，落库前须编辑复核；既有 5 式沿用 strategy prompt：玄幻=境界突破弧/悬疑=案件升级弧/竞技=赛季弧/无限流=副本难度弧/都市=事业里程碑弧）：

| 题材 | stage_form 草稿 | 依据类型 |
|---|---|---|
| 仙侠 | 凡人起步→宗门修行→金丹元婴→界域扩展→飞升/天道 | 境界弧变体（oh-story 拆文+惯例） |
| 武侠 | 入门学艺→江湖历练→门派恩怨→武功大成→武林大局 | 师徒成长弧 |
| 历史 | 穿越落地→立足（军政/商业）→势力割据→天下棋局→定鼎 | 事业里程碑弧变体 |
| 军事 | 入伍/参战→小队历练→战役升级→战略层面→终战 | 赛季弧变体 |
| 游戏 | 入游/重生→新手期红利→职业化/公会→巅峰赛事→版本更迭 | 赛季+副本混合弧 |
| 科幻 | 异变/发现→生存危机→技术突破→文明冲突→终局选择 | 危机升级弧 |
| 现实 | 困境→首次反击→事业/关系双线→中产危机→和解/超越 | 里程碑+情感双弧 |
| 轻小说 | 日常引入→设定揭示→关系网→事件连作→主题收束 | 单元+主线混合弧 |
| 古代言情 | 入府/嫁入→宅斗立足→身份揭秘→家族/朝堂卷入→位份终局 | 关系+地位双弧 |
| 现代言情 | 相遇→误会/契约→确认关系→外部阻力（家世/事业）→婚姻终局 | 关系弧 |
| 幻想言情 | 觉醒/入界→能力成长→身份之谜→两界冲突→牺牲/团圆 | 境界+关系混合弧 |

### 7.3 外部知识 → 修复项映射总表

| 修复项 | 来源（§7.x） | 可落地动作 |
|---|---|---|
| P10 taboos 扩容 | 7.2 起点十禁+毒点源 | 30 包 taboos≥6：官方十禁作全类型底料+题材特化条目+女频双洁位 |
| P14 stage_form | 7.2 草稿表 | genre-packs 增 stage_form 键（编辑复核后） |
| P11 平台常数 | 7.2 常数表 | platform-constants.json 建档，三模块改引用 |
| P34 物件/知识盲区 | 7.1② story-skills | 六账本扩 possession+knowledge 两类 candidate 或 characters.state_json 字段 |
| P26 承诺时序机检 | 7.1② payoff-before-setup | gate 增 promise 时序校验（resolve 须有 plant 前置） |
| P5/P7 voice 字段 | 7.1③ style-creator | 种子卡 v3 映射+voice 实测参照文件闭环 |
| M13 指纹误伤 | 7.1① deslop 教训 | 规则扩表时保留「普通他说不判违规」回归样例 |
| M10 issue_key | 7.1③ kb/issues | findings 增 issue_key+跨轮追踪结构 |
| P35 vibes 条目 | 7.1④ 评分菜单 | review checklist 候选条目（深化冲突/增加伏笔等） |
| 流程缺环（新） | 7.1① 扫榜/拆文 | 评估增「拆书学习」skill 与 kb 复用工作流（NovelOS 现无） |

### 7.4 调研完成度声明

已备齐：P10/P11/P14 的知识前置（官方禁忌+常数+stage_form 草稿）、P34/P26 的结构参照、P5/P7 的实现路径印证。仍缺（执行 P2 时补）：①stage_form 需编辑复核定稿；②各平台 2026 算法细节持续跟踪（完读率阈值随运营调整）；③知乎毒点明细逐条取回（403，可换镜像）；④女频各细分题材（现言/古言/幻言）雷点需晋江站内证据加固。

---

## 8. 修复执行记录（2026-09-01 · §5 路线图落地状态）

> 详细记账见 `tasks/README.md` R9 节。七套终验全绿：guardrails **508** / compose **30** / gate **75** / verify **15** / fingerprint **49** / render **48** / canary PASS（基线 409/28/70/15/49/48/PASS；增量=本轮新增用例与 G1 扩容检查）。生产库零写入实证（开工=收工 md5 `6334a4e8…`）。

| §5 项 | 状态 | 落点 |
|---|---|---|
| P0-1 RT-B1+M2 | ✅ 完成 | composer `verifyKernelBinding`（select 三查，分发层防 without-slot 绕过）+ gate `validate-payload` 子命令 |
| P0-2 M9 | ✅ 完成 | gate `isSameFileAs`（realpath+dev/ino）+ import-personas 同款 |
| P0-3 M5 | ✅ 完成 | note-only=空查 FATAL / 空白 run 折叠反 splice / `check_hash` 留痕 |
| P0-4 M12 | ✅ 完成 | `modules.file` 白名单（附12 负例测试） |
| P0-5 M7 | ✅ 代码+副本攻防双验 | 023 五 TRIGGER + schema.sql v23；**落生产库待用户「确认」**（备份 `.bak-r9-20260901081029` 已备） |
| P1-6 M3/M4 | ✅ 完成 | `<<<DATA-BEGIN/END>>>` 围栏 + 提取端自检第 5 条 + 审查 `[canon-injection]` |
| P1-7 M6 | ✅ 完成 | `--writer-profile` 同模型 GateFail + `--allow-same-provider` 留痕（S24/S25） |
| P1-8 M8 | ✅ 完成 | lock/propagate 无边 WARN + sql-reference 递归 CTE 模板 |
| P1-9 M10 | ✅ 完成 | `assertReviewRoundBudget` ≥3 升级门（S26）+ `issue_key` schema/prompt |
| P1-10 P33 | ✅ 完成 | 四卡补槽（recipes+manifest 成对，G2/G3 绿） |
| P1-11 P24 | ✅ 完成 | scene_type 条件路由 + 执行卡字段 + review 补 dialogue-techniques |
| P1-12 P26 | ✅ 完成 | craft 解析扩展 expansions/ + twist 登记纪律 + promise_events 入槽 |
| P2-13 P10/P11/P14 | ✅ 完成 | genre-packs 30 包扩容（stage_form/taboos 三分类等，G1 +90 项检查）+ platform-constants.json |
| P2-14 P15/P16/P17/P20 | ✅ 完成 | world 民生最小集/维度矩阵/力量下限 + seats anyOf 条件必填（gate 零改动验证） |
| P2-15 P1/P2/P5 | ✅ 完成 | 内核分工表 + 交叉一致性自检 + tier C 档位化映射 |
| P2-16 P9/P12 | ✅ 完成 | book_soul `market_position` 入 required + 画像推导节 |
| P2-17 P25/P29/P30/P31 | ✅ 完成 | 战斗卡分型五节 + 爽文口径统一 + 三条行业技法 + word_share |
| P3-18 死引用 | ✅ 完成 | kernel-derive 改主控自查程序（含 sympathies 比对区）；SKILL `--asset continuity-review` 键名修正 |
| P3-19 M 系列 | ◐ 部分 | M17（CLI FK 提醒入 AGENTS.md）/M23（knowledge 降级可见化）完成；**M15 投影 DB 回比、M16 双版本机制、M19 裁决投影可见性留待后续轮次** |
| P3-20 测试盲区 | ◐ 部分 | 附12 穿越负例 + 归一化 splice 反例完成；gate symlink CLI 级例/render 同改 manifest 例留待后续 |

**023 已落生产库**（用户裁决「确认」2026-09-01，照 021/022 先例）：预检→备份 `.bak-r9-023-20260901094218`→单事务应用+版本登记 23→验证全绿（5 触发器在位/版本链 22→23/数据零损失/integrity ok/fk 0）→只读冒烟过（validate-payload exit 0、RT-B1 仍拒 exit 1）。**R9 全部关闭，无未决门。**
