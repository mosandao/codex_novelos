# R5-D5 红方审查

> 审查对象：`tasks/r5-plans/d5-adversarial-system.plan.md`（D5 对抗审查体系编排与全链路演练设计文档）
> 红方：方向5红方 agent（本文件）。日期：2026-08-29。方法：仓库事实逐锚点核对（file:line）+ node:sqlite 只读实测 `data/novelos-v2.db` + 联网核实引用研究 + 对照 d1-d4 四份设计稿查跨方向接口。
> 定级：P0=阻断（规格不可实施/接口冲突必炸）；P1=须修（合并前必须解决）；P2=记录备查。
> 本文件即该设计文档的 G4 规格审产物（§2.4 要求「本文件自身在获批前也应过一次」——§8 自跑不满足异构红方要求，本审查补足该门）。

---

## 1. 事实核查表

| # | 计划声明 | 核查结果 | 证据 |
|---|---|---|---|
| 1 | slot_vocabulary 22 个槽（agent-recipes.json:4-27） | ✓ 属实（逐个数=22） | `config/agent-recipes.json:4-27` |
| 2 | 两条新配方「零新槽」（§3.1，§7.4 称已人工核对） | **部分**：vocabulary 层成立（9+2 个槽名全部 ∈ vocabulary），但 `craft_refs` **不在 SLOT_REGISTRY**（17 键无它），且 craft 卡注入机制是 manifest 的 `craft_refs` 独立字段而非 data_slot | `scripts/novelos-compose-prompt.mjs:1326-1344`（SLOT_REGISTRY）；`catalog/skills/writing/chapter-draft-generation/modules/manifest.json`（data_slots 无 craft_refs、craft_refs 为独立字段）；`scripts/test-guardrails.mjs:69`（G2a 要求 `slot in SLOT_REGISTRY`） |
| 3 | ASSET_DIRS 共 25 键、无 revision/redteam（§1.2 引 :52-78） | ✓ 属实（逐个数=25） | `scripts/novelos-compose-prompt.mjs:52-78` |
| 4 | 组装器原生支持 `--db`（§1.2 引 :28,1465-1506）——R6 副本隔离零代码改动 | ✓ 属实：CLI 解析有 `--db`，且 `new DatabaseSync(args.db)` 真消费该值 | `scripts/novelos-compose-prompt.mjs:28`、`:1506`、`:1537` |
| 5 | expansions/prose-revision 存在但未注册 | ✓ 属实（目录含 contract/metadata/prompt/provenance.yaml，**无 modules/manifest.json**） | `catalog/skills/expansions/prose-revision/` 目录实测 |
| 6 | novel-review SKILL 六处锚点（:36-43/:45-49/:57-58/:60-61/:63-72；落库=第 6 步） | ✓ 全部命中 | `.agents/skills/novel-review/SKILL.md:17`（第 6 步落库）、`:36`、`:45`、`:57`、`:60`、`:63` |
| 7 | prose-quality-review/prompt.md:18（数字阈值唯一权威源）与 :29（证据标准禁「多处/整体」） | ✓ 精确命中 | `catalog/skills/review/prose-quality-review/prompt.md:18`、`:29` |
| 8 | 指纹卡只有 5 个节标题（:5,15,29,38,51）、无稳定规则编号 | ✓ 精确命中；grep `FP-\|规则编号` 零命中 | `catalog/skills/craft/prose-anti-ai-fingerprint/prompt.md:5,15,29,38,51` |
| 9 | §1.3 DB 实测：projects=1/books=0/volumes=0/chapters=0/planning_assets=0/reviews=3/resources=181；reviews 均为 planning-cross-check 裸 profile 旧数据；唯一项目 setup v2 完整、规划链空白 | ✓ 除 creator_profiles 外全部复现（2026-08-29 只读实测）；R6「从 direction 起跑覆盖全链、无需另造项目」判断成立 | node:sqlite 只读查询：projects=1（`project:fdc0e83f-…`「诸天无限：从大运开始」，metadata_json 含 `setup_schema_version:2`）；reviews 3 条 subject_ref 均为 `planning-cross-check:*`、reviewer_profile 为裸字符串 |
| 10 | §1.3 creator_profiles=31（18 系统+用户签名若干） | **✗ 计数错**：实际 **30 = 26 system_archetype(active) + 4 user(active)**；「18 系统」无来源 | 同上只读查询 `GROUP BY ownership,status` |
| 11 | reviews 表已存在 metadata_json 列（§2 通用约定称「见 §1.3 reviews DDL 实测」） | ✓ 列存在（`TEXT NOT NULL DEFAULT '{}'`）；**但 §1.3 并无 DDL 展示——指针空指** | `sqlite_master` reviews DDL 实测 |
| 12 | （计划未提）生产库迁移止于 v18，**019 未应用，chapters 无 review_id 列** | ✓ 实测：schema_migrations 1-18；`PRAGMA table_info(chapters)` 无 review_id | `db/migrations/019_state_machine_links.sql`（文件头自注「生产库不由本仓库手工执行」）；`tasks/README.md:69`「生产库 019 迁移待用户择机执行」 |
| 13 | （计划未提）生产库 journal_mode=**wal**，-wal/-shm 文件在场，只读连接也触碰 -shm | ✓ 实测：`PRAGMA journal_mode`=wal；`data/novelos-v2.db-shm` mtime 随本次只读查询刷新 | 文件系统 + PRAGMA 实测 |
| 14 | §10.2「novelos-render-projection.mjs 若当前硬编码 DB 路径，R6 需 --db 直通（小改）」 | **✗ 过时**：该脚本**已支持** `--db`（参数化默认值，非硬编码） | `scripts/novelos-render-projection.mjs:832`（`db: { type:'string', default:'data/novelos-v2.db' }`）、`:841` |
| 15 | tasks/README.md:57-69 三路子代理对抗审查（23 条，WP1-WP8） | ✓ 属实 | `tasks/README.md:57-69` |
| 16 | RESEARCH.md 分母纪律 :43-55 / 判定门槛 :57-75 / 六次失误 :244-255 / :19 单模型癖好 / :227-242 模型间差异——引用忠实 | ✓ 忠实：三分母表、倍率+三条件（人类侧稳定/可定位/不违白名单）、「改规则前先抽样看 20 条命中再看频率」原文均在；G1「抽样 ≥20 条」与 M1 分母口径未误用 | `/Users/yiyi/Documents/refs/lieflat-less-ai-tone/RESEARCH.md` 逐节核对 |
| 17 | §11 来源 2 CALM：authority bias（伪造引用劫持评判）→G2；bandwagon→G3；refinement-aware→盲测不注入轮次 | **论文与三项偏差均真实存在**；bandwagon 结论**轻度外延**（见 P2-8） | arXiv:2410.02736（Ye et al., CALM，12 类偏差含 Authority/Bandwagon/Refinement-Aware；HTML 版核实：authority 实验用 GPT-4 生成伪引用附加到弱答案后成功翻转判决；bandwagon=注入「N% 的人认为某模型更好」的多数意见声明；refinement-aware=看到修订历史打分更高） |
| 18 | §11 来源 1 self-preference（arXiv:2410.21819）→异构厂商+匿名化 | ✓ 论文真实（Wataoka et al., NeurIPS 2024 Safe GenAI Workshop）；注意其结论本质是**困惑度/熟悉度**而非字面自识别（见 P2-10） | arXiv:2410.21819 摘要核实 |
| 19 | （环境事实）仓库当前非干净 | git status：`M tasks/README.md` + 未跟踪 `tasks/R5-knowledge-absorption.md`、`tasks/r5-plans/`——D1-D5 全部设计稿与 v1 计划均未提交，file:line 锚点尚无固定基线 | `git status --porcelain` 实测 |
| 20 | 门-轮矩阵（§2.7）与四方向执行轮次（D1=R1/D2=R2/D3=R3-R4/D4=R5） | ✓ 对得上：G2 上线 R2、G3 首测 R2、R3 盲测（有/无知识槽）、R4 演练（参照混入）、R5 豁免假阳性，与 v1 `:73` 每轮节奏及各轮 G5 描述一一对应，无发明新门 | `tasks/R5-knowledge-absorption.md:73`、`:98`、`:111`、`:145`、`:158` |

---

## 2. Findings

### P0-1 · G3 deny 留痕出现两套互不兼容的存储契约（D5 vs D2 正面冲突）

- **问题**：D5 §2.3/§3.5/§10.3/M3 规定预筛表态存 `reviews.metadata_json.prescreen`（含 `dispositions:[{candidate_id, rule_id, verdict, reason}]`），M3 采集 SQL 用 `json_extract(metadata_json,'$.prescreen.denied')`；D2（机器校验轮，同日产出）已单方面定为**零 schema 变更**方案：confirm=`findings[].code='fpr:<规则号>'`、deny=`code='fpr-deny:<规则号>'`+`severity:'note'`+理由，候选总数存 `chapters.metadata_json.prescreen.screen_counts`，并明确「deny 率告警（趋零/连续3章）**消费本采集点**，归方向5」（d2:467、d2:512-514）。
- **证据**：本计划 §2.3、§3.5、§4-M3、§10.3 vs `tasks/r5-plans/d2-machine-gates.plan.md:429-431`、`:467`、`:512-514`、`:518`。
- **后果**：若 D2 按 test 执行、D5 按 metrics 采集，M3 永远读空，G3 整门「只统计不处置」——恰是 D5 §8-3 自己定义的纸面化形态。
- **处置建议**：两稿必须二选一并双向回写。倾向：**过渡期采纳 D2 的零 schema 方案**（finding code 已存在、可 SQL、无 schema 动作），D5 的 M3 SQL 与 G3 统计口径改为 `fpr:/fpr-deny:` 计数；D5 §3.5 的顶层 `prescreen` 对象若保留，降级为「与方向4 合并轮的结构化升级项」并显式声明取代 D2 采集点的迁移语句（含历史 `fpr-deny:` 数据的换算口径）。禁止两套并行。

### P0-2 · R6 S4「接受（写 review_id）」依赖一个不存在的列——019 迁移无人落地、无裁决点

- **问题**：§5.2 S4 通过判据「3 章全部 accepted」、蓝方动作「接受（写 review_id）」，但生产库 `chapters` 表**没有 review_id 列**：schema_migrations 止于 v18，019 未应用；019 文件头自注「生产库不由本仓库手工执行；迁移只在测试内存库与未来真实运行时经门生效」——而该「门」（插件工具）已随 plugin/ 退役。drill 库是生产库的 `cp` 副本，同样无此列，S4 的接受 SQL 在演练库上直接报 no such column。U1-U10 无此项裁决，S1 冒烟清单（「确认项目/签名绑定完好」）也不查 schema 状态。
- **证据**：`PRAGMA table_info(chapters)`（无 review_id）；`db/migrations/019_state_machine_links.sql`；`tasks/README.md:69`；AGENTS.md「状态机约束」节（纪律已写、列未落）；d2/d4 计划 grep 均无 019/review_id 认领。
- **处置建议**：① 新增裁决点 U11「019 是否落生产库（或 drill 库单独 ALTER）」——注意 drill 库单独改列违反自家「演练期 schema 冻结/防副本漂移」原则，正解是先在生产库走备份+迁移再 cp；② S1 冒烟加 `PRAGMA table_info` 核对 chapters 列清单与 schema_migrations 版本；③ §9 风险表补「演练库 schema 基线=生产库实际应用版本，不是仓库 migrations 目录 HEAD」。

### P0-3 · 两条新配方的落地无主：委托对象拒绝承接，且时序自相矛盾

- **问题**：§3.1 说「ASSET_DIRS 注册键由方向2 落地」，但 D2 红线明写「**不动 composer（方向3）**……本方向不改 composer 任何代码」（d2:5、d2 §8），其 R0+R2 范围也不含注册；D3 的 composer 改动只覆盖 knowledge 槽，其盘点甚至写「新增槽不改此处（走 manifest 声明）」（d3:16）——**四个方向的计划里没有任何一方承接这两个注册键**。同时：D5 自己论证缺口①「R1 双模式修订目前无组装通道」，§8-4 还要求「R1 验收中检查主控行为切换（不再手工拼注入）」，即注册必须 R1 前生效；但 §6.1 依赖图把 composer 改动排在「R2 并行/R3§槽机制」窗口——**R1 需要的东西被排到了 R2-R3**。另外 guardrails G2c 要求每个 recipes 资产存在 `catalog/skills/<skill>/modules/manifest.json`（test-guardrails.mjs:75-80），prose-revision 现无 modules/、review/prose-blindtest 目录不存在——recipes 行若先行落库，护栏直接红；两处（新 skill 目录+manifest、ASSET_DIRS 键、recipes 行）必须同批同 commit，计划未写此约束。
- **证据**：本计划 §3.1、§6.1、§7.4、§8-4；`d2:5`；d2 §8「本方向不改 composer 任何代码」；`d3:16`；`scripts/test-guardrails.mjs:75-80`；`catalog/skills/expansions/prose-revision/`（无 modules/）。
- **处置建议**：① 改委托方向3 或 D5 自持（编排落点是 D5 的责任边界），并把该承接写进被委托方的计划（否则仍是纸面委托）；② §6.1 依赖图修正：prose-revision 注册是 **R1 前置**，与 knowledge 槽（R3）解耦为两个独立 composer 变更；③ §7 执行步骤加一条验收：「`--asset prose-revision` 与 `--asset prose-blindtest` 可组装出产物 + test-guardrails 全绿（manifest≡matrix 含新两资产）」，并注明 skill 目录/manifest/ASSET_DIRS/recipes 同 commit。

### P1-1 · prose-blindtest 草案把 `craft_refs` 当 data_slot——护栏必红，「零新槽」结论口径错误

- **问题**：§3.1 草案 `"slots": ["subject","craft_refs"]`。`craft_refs` 在 slot_vocabulary 里但**不在 SLOT_REGISTRY**，且无动态前缀豁免——guardrails G2a（`slot in SLOT_REGISTRY && in slot_vocabulary`）必失败。仓库先例（chapter-draft）的做法是：data_slots 不含 craft_refs，craft 卡走 manifest 的独立 `craft_refs` 字段逐字注入。
- **证据**：`scripts/novelos-compose-prompt.mjs:1326-1344`、`:1377-1385`（manifest.craft_refs 分支）；`scripts/test-guardrails.mjs:64-72`；`catalog/skills/writing/chapter-draft-generation/modules/manifest.json`。
- **处置建议**：草案改为 `"slots": ["subject"]` + manifest `craft_refs: [...]`；§7.4 的验证口径从「slots ⊆ slot_vocabulary」升级为「具名槽 ⊆ SLOT_REGISTRY、craft 走 manifest.craft_refs」（后者才是机器可查的真约束）。

### P1-2 · WAL 模式下「生产库 sha256 前后一致 = 零污染机器证明」不成立；`cp` 副本可能缺页

- **问题**：生产库 journal_mode=wal。写事务先进 `-wal` 文件，主库文件只在 checkpoint 后变化——**演练期间若有进程误写生产库，主库 sha256 可以保持不变**（数据躺在 -wal 里），「一致」给出假阴性证明；反之合法只读连接也会改 `-shm`（本次实测即刷新了 mtime），任何把 sidecar 计入的粗 hash 又会假阳性。另外 §5.1 的 `cp data/novelos-v2.db data/novelos-drill.db` 只复制主文件：若 -wal 有未 checkpoint 页（R5 轮 D4 迁移/新签名写入后完全可能），副本=陈旧甚至不一致的库。今日 -wal 恰为 0 字节，是「现在没事」而非「方案没事」。
- **证据**：`PRAGMA journal_mode` = wal；`data/novelos-v2.db-wal/-shm` 在场；SQLite WAL 语义（写先入 wal、checkpoint 才落主库）。
- **处置建议**：① cp 前对生产库执行 `PRAGMA wal_checkpoint(TRUNCATE)`（或用 `VACUUM INTO`/backup API 生成副本——零 Python 纪律下可 `node -e` 一句）；② 零污染证明改为「演练前后 `wal_checkpoint` 后主库 sha256 一致 **且** `-wal` 恒为 0 字节/内容 hash 一致」，并把「演练期间生产库只允许只读打开」写成硬纪律（任何脚本默认 `--db` 都是生产库路径，漏带参数即读错库——组装器默认值就是 `DB_PATH`）。

### P1-3 · §3.4 红方编排示例与自家三层表矛盾：红方示例模型与审查方撞厂

- **问题**：三层表写「审查（黑方）anthropic:claude-sonnet-4-6 / 红方 google:gemini-3-pro / deepseek:deepseek-v4」，同节 G4 编排示例却写红方任务书 `model: "anthropic:claude-sonnet-4-6"`（注释只说「与写作模型异构」）。示例恰好违反自己上面的表；且「至少两两异厂商」的 pairwise 范围（红方 vs 审查是否必须异厂）从未定义——若允许红方与审查同厂，「审查者也被审」的防共谋分层被削弱一半。
- **证据**：本计划 §3.4 两段对照；v1 `:69` 只要求「红方与写作方异构」。
- **处置建议**：改示例为 google/deepseek；明确 pairwise 矩阵（写作↔审查、写作↔红方必须异厂；红方↔审查给出明确取舍及理由）；与 §9 风险表「撞厂降级 P2」条款对齐（该条款说的是红方与审查方撞厂，正好被示例踩中）。

### P1-4 · 盲测对照组文体失配：金丝雀=人类论述文，AI 段=男频小说正文——判源可由题材而非指纹完成

- **问题**：§2.5 盲测协议「3 段 AI 生成文 + 3 段金丝雀文」，只做长度配对（±20%）与匿名化。金丝雀来自 `kb_corpus_articles`（nwriter 知识库文章，论述文），项目正文是男频网文小说。红方判源只需识别「这是不是小说」，即可 100% 命中——盲测测的是判文体不是判 AI，判源结论不能支撑「双向达标」。§2.1 自己承认金丝雀结构层结论要打折，§2.5 却把同一语料当「人类小说对照组」用，未打折。附带触发 §2.5-③（判源全对→复核难度→重抽）的死循环：重抽多少次都是全对。
- **证据**：`tasks/R5-knowledge-absorption.md:44`（金丝雀集=kb_corpus_articles）；d3:90（canary 原料=articles.jsonl 论述文）；本计划 §2.1、§2.5、§5.2-S4。
- **处置建议**：盲测对照组改用**人类写的叙事文**（男频网文语料需用户授权补采——v1 风险表已预留该渠道，可提前到 R0 裁决包），或至少取金丝雀中叙事性段落并在报告中对「判源结论」单列「文体泄漏折扣」；否则 R1/R6 的 G5 盲测判据（「AI 段指纹下降+人类段改动非零」中依赖判源的部分）降级为仅供参考。

### P1-5 · R1-R5 期间 G3/G5 的素材来源未定义：库内 chapters=0，deny 率首测与盲测 AI 段无成文取材通道

- **问题**：门-轮矩阵把 G3 首测排在 R2、G5 盲测排在 R1，但生产库 0 章节，v1 R2 的「首测 deny 率」与 D2 冒烟（「对库内真实章节草稿只读 SELECT 导出」——并不存在）都无真实小说正文可用；R1 盲测的「3 段 AI 生成文」由谁、用什么模型、经什么通道生成并留痕，计划只字未提（只有 R6 S4 定义了 AI 段来源）。deny 率「合理区间」在 R6 之前无任何真实数据校准，若 R6 才暴露预筛/审查失效，返工面覆盖已完成的 R1-R4。
- **证据**：§2.7 矩阵、§2.5、§5.2；DB chapters=0；d2:455。
- **处置建议**：在 §2 或 §7 增加「素材编备规程」：R1 起维护一份 `docs/knowledge/redteam/fixtures.md`，登记每轮 G3/G5 用的素材来源（临时生成段的模型 provider:model 留痕、金丝雀选段 ID），并明确 R2 首测允许用金丝雀改写段/人工构造段先行校准（标注「非真实章节数据」折扣）。

### P1-6 · U 清单查漏：U-dirs（R6 S2 方向选定）缺席总清单；v1 §7 的「personas 试点范围」未标注归属；「≤4 次打断」算术依赖未列项

- **问题**：① §5.2-S2 明确「呈报用户选定（演练 U-dirs）」且通过判据含「用户选定留痕」——这是一次计划内打断，但 §6.2 总清单（自称「预先声明，执行中不再逐次打断」）没有它；计入后计划内打断=包A+包B+U-dirs+U10 恰好 4 次，预算成立的前提恰是补上这个漏项。② v1 §7 预声明五裁决点中「R5 schema 变更**与 personas 试点范围**」，U6 只覆盖 schema 变更范围+备份时点，personas 试点范围（kb_author_personas 10-20 条试点认定）未入总清单也未标注「由 D4 呈报」——两计划都以为对方负责的风险形态。③ 019 迁移裁决缺失（见 P0-2）。
- **证据**：本计划 §5.2-S2、§6.2；`tasks/R5-knowledge-absorption.md:213`；d4:323（种子选择裁决在 D4，试点范围未见独立裁决点）。
- **处置建议**：§6.2 补三行：U-dirs（R6 现场、S2 方向选定）；U-personas（R5 前，标注呈报责任方=D4）；U11-019（见 P0-2）。并把「≤4 次」的重算过程写透明。

### P1-7 · G1 的「改规则前先抽样看 20 条」缺少对 R0 基线本身的适用声明；金丝雀集小样本下 M1 阈值单侧化已有预案但 R0 基线未过 G4

- **问题**（较轻，合并前澄清即可）：§2.1 触发时机写「R0 建基线时不判只测」——正确；但 R0 产出即 U1 呈报的基线数字本身没有先例可回归，15-20 篇小样本的分组稳定性（RESEARCH.md:57-75 的「人类侧各组相差不超 5 倍」条件）没有进 U1 呈报模板；§9 风险表只对「总量趋势」放宽，未要求呈报分组离散度。
- **证据**：§2.1、§9 风险 4；RESEARCH.md 判定门槛节。
- **处置建议**：U1 呈报包模板增加「每规则的人类侧分组区间（min-max）」，离散超 5 倍的条目自动标「仅 direction 佐证」。

### P2 清单（记录备查，不阻断）

| # | 问题 | 证据 | 建议 |
|---|---|---|---|
| P2-1 | §1.3 creator_profiles 计数错：写 31（18 系统），实测 30（26+4） | 核查表 #10 | 更正数字；非载荷事实，不影响 R6 设计 |
| P2-2 | §10.2 称 render-projection「若硬编码需 --db 小改」——实际已支持 `--db` | 核查表 #14 | 删除该条依赖，R6 直接用 |
| P2-3 | G3「趋零」无量化：硬触发「=0 且候选≥5」已量化，但「连续 3 章趋零」的趋零无阈值；v1 的 deny<50% 上界被静默丢弃（deny 率过高=预筛规则差，只剩处置③兜底、无告警线） | §2.3、§4-M3 vs v1 `:175` | 定义如「deny率<10% 计趋零」「>50% 触发预筛质量复核」，或显式声明放弃上界并给理由 |
| P2-4 | fingerprint CLI 旗标与 D2 不一致：D5 写 `--chapter <id> \| --file <path>`，D2 全文用 `--text-file <草稿> --json` | §10.2 vs d2:417、d2:455 | 以 D2（工具实现方）为准回改 §10.2 契约 |
| P2-5 | FP 编号稳定性/退役纪律缺失：D2 给预筛 L 号立了「ID 永不改义、不复用、只追加」（d2:80），D1 卡头草案与 D5 §10.1 对 craft 卡 FP 号都没立——而 G1 失败处置恰好会「降级/撤回」条目，撤回后编号是否复用无人定义，M1 按条目追踪与 G5 指认的历史连续性会断 | d1:135-137、本计划 §10.1 | §10.1 接口需求补两条：FP/T 编号发布后不改义不复用（对齐 D2 先例）；降级条目编号保留并标 retired |
| P2-6 | metrics.md 更新责任者未显式指定（各 M 分散暗示主控）；M5 在 R3 前无阈值无动作属「悬空指标」；M6 的 P0/P1 修复勾选由谁回写 redteam 文档未写 | §4 | 表尾加一行「责任者=主控，随每门执行记录同步追加；R6 收口按 §5.3-1 查完整性」 |
| P2-7 | §2 通用约定引「§1.3 reviews DDL 实测」——§1.3 只有计数无 DDL（列存在本身为真） | 核查表 #11 | 把 DDL 一行补进 §1.3 或改引用 |
| P2-8 | CALM bandwagon 引用轻度外延：CALM 的 bandwagon=「N% 的人认为 X 更好」的多数意见注入，非「供参考的机器候选清单锚定」。后者是合理类推（同属外注入信息影响评判），但作为「直接依据」 overstated | §2.3、§11 | 措辞改「bandwagon 同族的外注入锚定效应」或补引 distraction/anchoring 类证据；G3 的 deny 率监控本身设计成立 |
| P2-9 | self-preference 论文本质=困惑度/熟悉度偏好（作者自证非字面自识别）：异构厂商降低但不根除（同厂不同型号也可能互相低困惑度偏好），§2.5 的依赖可补一句局限 | arXiv:2410.21819 | §2.5 设计依据句补「（根因为熟悉度偏好，异构+匿名化仅缓解）」 |
| P2-10 | 仓库非干净：v1 计划与 d1-d5 全部未提交，锚点无固定基线；获批即基线 | 核查表 #19 | 用户批准前将 R5 计划族 commit 固定，红蓝双方引用同一 hash |
| P2-11 | G2 输入假设「该次审查组装时注入的上游原文清单」——novel-review SKILL 第 2 步仍允许「未注册审查」走手工注入路径，该路径无组装日志可查，G2 的「假通过」防线在未注册审查上缺输入 | `.agents/skills/novel-review/SKILL.md:13` | G2 规程注明：未注册审查的回执须主控附注入清单快照，否则该回执不得计入 M2 分母 |

---

## 3. 跨方向冲突预警

| 冲突点 | D5 立场 | 对方立场 | 状态 |
|---|---|---|---|
| **G3 deny 留痕存储**（最尖锐） | `reviews.metadata_json.prescreen`（dispositions 数组）+ M3 用 `json_extract('$.prescreen.denied')` | D2 `:429-431/:512`：`findings[].code` 的 `fpr:`/`fpr-deny:` + `chapters.metadata_json.prescreen.screen_counts`，零 schema 变更，并声明「告警消费归方向5」 | **正面冲突，必须裁决**（P0-1） |
| **预筛候选注入通道** | §10.3「建议不新开槽，复用 prose-review 数据区附带」 | D2 `:508`「建议槽名 `prescreen_candidates`，注册归方向3」 | 同题两答案，方向3 无所适从；且新槽名不在 slot_vocabulary，与 D5「零新槽」精神相抵（P1 关联） |
| **ASSET_DIRS 两新键归属** | 「由方向2 落地」 | D2 红线「不动 composer（方向3）、本方向不改 composer 任何代码」；D3 只做 knowledge 槽 | **无人承接**（P0-3） |
| **规则编号体系** | §10.1 向方向1 要「稳定规则 ID，建议 FP-<节>.<序>」 | D1 `:135-137` 已有 FP-x.y + T-n 卡头草案（「0. 编号、来源与豁免约定」）——接口已被满足一半；但两方都没写稳定性/退役纪律；D2 另有 L 号体系（`:80` 已立不改义不复用），**L↔FP 映射**只有 D2 `:49` 一句「R1 后与本脚本规则号对齐」，D5 的 G3 处置③（deny 理由成立→改卡）消费该映射却未列入接口需求 | 部分对齐；缺稳定性条款与映射归属（P2-5） |
| **code 字段命名空间** | 未提 | D1 `:281` 豁免落账 `code:"exempt:FP-x.y"`；D2 `:429` `code:"fpr:"/"fpr-deny:"`——三个前缀族同挤一个 `findings[].code`，无登记处 | 建议在 D5 §10（接口声明）加一张 code 前缀注册表（fpr:/fpr-deny:/exempt:），D5 是编排方、最合适持表 |
| **schema 合并轮（U6）** | Receipt prescreen 正式字段与 D4 的 R5 轮 schema 变更「合并一次执行」 | D4 计划通篇无 Receipt prescreen（其变更=creator-signature v3 + migration 031）；且 D4 的 031 编号悬空（仓库现止于 019，020-030 无人认领） | 单方承诺，合并大概率落空（关联 P0-1/P0-2：真正该合并的 019 反而没人管） |
| **盲测段来源** | R6 S4：本章 AI 段+金丝雀 | D3 `:443`：R3 盲测=「同章纲 --no-log 双跑（有/无 knowledge 槽）」 | 不冲突但素材池分叉——若 P1-4 采纳「人类叙事文对照组」，男频语料授权采集需提前到 R0/R1 裁决包，影响 D3 的 R3 盲测同样受益 |
| **CLI 契约** | §10.2 三脚本旗标/退出码 | D2 `:297`（fingerprint 成功恒 0）、`:417`（--text-file） | 退出码一致；旗标不一致（P2-4），以实现方为准 |
| **门-轮矩阵 vs 各方向轮次** | §2.7 | v1 `:73` 节奏、D1=R1/D2=R2/D3=R3-R4/D4=R5 | **核对一致，无冲突**（正面结论） |

---

## 4. 结论

**修改后放行。** 设计骨架健全：六门与 v1 一一对应无发明新门、门-轮矩阵与四方向轮次核对一致、SKILL/配方/组装器的 file:line 锚点绝大多数精确命中、R6 取材判断（唯一项目规划链空白→从 direction 起跑）经 DB 实测成立、外部引用（CALM 三偏差、self-preference）论文真实且核心结论未被误用、RESEARCH.md 分母纪律引用忠实。但存在三处 P0 级接口/落地冲突，合并进 v1 计划前必须完成：

**必改项（P0，缺一不可）：**

1. **统一 G3 留痕契约**（P0-1）：与 D2 二选一（建议过渡期采 D2 零 schema 方案），M3 采集 SQL、G3 规程、§3.5、§10.3 四处同步改写，双方计划互相回引。
2. **补 019 迁移裁决与 S1 检查**（P0-2）：新增 U11；S1 冒烟加 chapters 列与 schema_migrations 核对；§9 补「演练库 schema 基线=生产库实际版本」风险行。
3. **落实两条新配方的承接方与时序**（P0-3）：注册键改委托方向3 或 D5 自持并写入对方计划；依赖图把 prose-revision 注册提为 R1 前置；§7 加「两资产可组装+guardrails 全绿」验收行，注明 skill 目录/manifest/ASSET_DIRS/recipes 同 commit。

**强烈建议随批改（P1）：** prose-blindtest 槽位草案修正（craft_refs 走 manifest，P1-1）；WAL 下零污染证明与 cp 方案加固（checkpoint+三文件口径，P1-2）；§3.4 示例模型与 pairwise 异厂定义（P1-3）；盲测对照组文体失配（P1-4）；R1-R5 素材编备规程（P1-5）；U 清单补 U-dirs/U-personas（P1-6）。

P2 共 11 条均为低成本修正，建议一次性顺手清掉（尤其 P2-5 编号退役纪律——它是 G 门指认功能的前置，两份计划目前都没写）。
