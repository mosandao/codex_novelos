# NovelOS 对抗性交叉审查 · 四方起诉与裁判裁决

> 日期：2026-08-29。立场与方法：应用户要求**抛弃「我方正确」默认**，对 NovelOS 现行设计做有罪推定。四个起诉方 sub agent 分别从 agent 架构、prompt/上下文工程、材料资产、审查/对抗机制四个维度起诉，弹药取自 `/tmp/novel-skills-survey/` 13 个外部仓库（背景见 `docs/novel-skills-cross-analysis.md`）；主控任裁判，对致命指控做了逐条事实抽验（标注〔已验〕处均为裁判亲自 grep/读文件核实）。四份起诉书原文见附录，本文件未提交；**全部修正案均为呈报项，须用户裁决后方可执行**。

## 1. 裁决总表

| # | 维度 | 指控 | 裁决 | 抽验 |
|---|---|---|---|---|
| P1-1 | 架构 | 「主控=唯一落库人」：一章 6 次脚本+4 事务全过主控，全文上下文往返两趟 | **成立** | — |
| P1-2 | 架构 | 主控四职合一（编排+预筛+核验+对账），过程角色零分离 | 部分成立 | composer 已程序化是有效辩护；G2 归属应明示 |
| P1-3 | 架构 | 「模型无关 ABI」无依从性度量支撑 | **成立** | — |
| P1-4 | 架构 | 八级依赖链对单本书是官僚主义 | 待定 | 链不砍、lite 档要加 |
| P1-5 | 架构 | 机器门降级为主控自查：JS 写门建成、验证、又随插件拆除 | **成立** | 〔已验〕tasks/README.md L13-23 三件套 159/159 绿；L94 随插件整体退役 |
| P1-6 | 架构 | 「SQLite 权威库不可倒退」应降级为规模取舍 | 待定 | 事务原子性真实；检索/diff 成本也真实 |
| P2-1 | prompt | 69KB 组装产物是「搬运」不是「工程」 | 部分成立 | craft 层成立；canon_minimal/knowledge 槽已是 LOD 雏形，对数据槽驳回 |
| P2-2 | prompt | 槽截断「静默丢知识」 | **被驳回** | 截断有脚注透明化+组装日志 hash 可审计 |
| P2-2b | prompt | 预算纪律只管机器卡（≤2560B）放过最大消耗源（27KB 人工 fingerprint 卡） | **成立** | — |
| P2-3 | prompt | 被动注入剥夺运行时按需补读 | 待定 | 拉取入口确已腐坏（见 P2-5）；但 writeCompositionLog 审计面反超挑战者 |
| P2-4 | prompt | 注入顺序工程缺位：无语态槽、无按人物加权 | **成立** | — |
| P2-5 | prompt | 防漂移守护被自己拆除：config 引用的守护测试已删，按需 Read 指向腐坏路径 | **成立** | 〔已验〕config/agent-recipes.json:3 引用 tests/test_recipe_matrix.py（tests/ 仅剩 35 个 .pyc 尸体）；writing/chapter-draft-generation/prompt.md:37 指向 catalog/skills/craft/scene-dialogue——craft/ 下无此目录（卡实际在 catalog/skills/writing/ 下，指针写错） |
| P2-6 | prompt | 27KB 静态反AI卡是最低效方案 | 部分成立 | 校准强度反超挑战者（驳回「最低效」）；常驻固定税+零反自我说服心理学成立 |
| P2-7 | prompt | 无模型能力门控（同一 69KB 注入任何模型） | **成立** | — |
| P3-1 | 材料 | 知识资产名不副实 | 部分成立 | 原始库 5.7MB/16 卡不薄；蒸馏仅 3 域、商业合规为零属实 |
| P3-2 | 材料 | SQLite 存非结构化材料是错配引擎 | 部分成立 | 投影可再生路线驳回（与本仓同源）；正文 BLOB+LIKE 检索欠账成立 |
| P3-3 | 材料 | 六账本有账无流水、无收支预算 | **成立** | 〔已验〕db/migrations/schema.sql:200-211 narrative_promises 仅 status 三态+source_chapter_id，无 resolution 章位、无事件表 |
| P3-4 | 材料 | genre-packs「唯一源」实为无更新管道的冻结 | **成立** | 30 题材仅 4 字段 vs webnovel-writer 37 题材方法论模板 |
| P3-5 | 材料 | 结构 schema 强、内容 schema 弱 | 部分成立 | world 契约层 dimension_costs 自辩成功；volume_settings spec 自由串属实 |
| P3-6 | 材料 | planning_assets 对一人一书过度设计 | 部分成立 | 资产 8 : 章节 0 失衡属实；单机定位可辩护 |
| P3-7 | 材料 | 数据完整性押在模型自查上 | **成立** | 与 P1-5 同源 |
| P4-1 | 对抗 | G2 默认配置放行「空 findings+approved」橡皮图章回执 | **成立** | 〔已验〕verify 脚本 L347-353：空回执仅 advisory，--strict 才 FATAL；SKILL.md:24 标准命令无 --strict，全仓 grep 无强制 |
| P4-2 | 对抗 | 防共谋=字符串礼仪：reviewer_profile 无 pattern 校验，WARN 执行器随插件退役 | **成立** | schema L87-91 仅 minLength:1 |
| P4-3 | 对抗 | 金丝雀只测误报，AI 味漏报率零基线 | **成立** | D2 红方 F6 自认「假阴性没有任何门」 |
| P4-4 | 对抗 | 「只报事实不判级」把判级推给人还先塞噪声 | 部分成立 | U1 方案 A 重分层方向正确；脚本侧仍不判级 |
| P4-5 | 对抗 | 升级用户=流程挂起，非可恢复状态（无 TBD 产物、下游无感知） | **成立** | — |
| P4-6 | 对抗 | 审查缺「读者」与「钱」维度 | **成立** | 被告上轮自认在案 |
| P4-7 | 对抗 | 单审查者一次产出全维度，无多视角对抗、无降级自证 | **成立** | — |
| P4-8 | 对抗 | 时序攻击：事后验证 vs 事前门禁 | **被驳回** | 被告是双层防线（锁定计划+受控注入+组装 fail() 在前，G2 终验在后）；写前门是「避免浪费」优化非正确性缺口 |

计分：成立 12（其中 5 处经裁判抽验证实）、部分成立 6、被驳回 3、待定 3。

## 2. 被击穿的七处（成立项合并归类）

**一、招牌机制的默认配置有洞（P4-1，〔已验〕，最危险）。** G2 引文验证的「空查回执防线」（红方 F7）被实现为 `--strict` 下的 FATAL，而 SKILL.md、AGENTS.md 全仓没有任何地方传 `--strict`——即标准流程下「零 findings + approved」的橡皮图章回执 exit 0 落库。「13 仓无等价物的最大差异化资产」其拦截能力取决于一个没人传的开关。脚本注释表明这是 R2 轮的有意任务口径，但口径从未收口为默认。

**二、机器强制层被拆除且无替代（P1-5/P2-5/P3-7，〔已验〕）。** R2 已建成并验证 JS 写门三件套+状态机门+七件资产校验器（159/159 测试绿，`docs/r2-js-gate-spec.md` 在案），随插件退役一并删除后，校验、席位对账、词表级联、状态机封跳审全部降级为「主控自查」。拆除本身是用户裁决（纪律显式），但攻击点在于：**纪律替代层的机器性从未补回**，且伴随三处行为证据——config/agent-recipes.json 仍引用已删除的守护测试、tests/ 只剩 35 个 .pyc 尸体、写作主干的按需 Read 指向腐坏路径（卡片在 `catalog/skills/writing/` 下而 prompt 写的是 `catalog/skills/craft/`）。dreampowers tested_model.md 已实证弱模型多约束并行依从性 15/100——「自查即赌命」有量化依据。

**三、账本只有余额没有流水（P3-3，〔已验〕）。** narrative_promises 仅三态+来源章，无 resolution 章位、无事件追加表；relationship_states/arc_states UPSERT 整体覆盖历史即焚；全库无收支门禁。dreampowers 一伏笔一文件的事件流（foreshadow/progress/twist/climax/resolution）+Claremont 系数（active−resolved>2 预警）证明「流水+预算」是长篇可审计性的最低配置。300 章后断线伏笔在 NovelOS 不可审计——直接击穿「连续性最强」卖点。

**四、对抗结构缺失（P4-2/P4-7）。** 防共谋的全部机器痕迹是 reviewer_profile 字符串前缀（schema 仅 minLength:1 无 pattern），唯一会为其缺席发 WARN 的执行器随插件退役；审查是单 sub agent 一次产出全维度，无并行多视角、无 fresh-context 分离、无降级自证。oh-story（三视角并行+统一 Findings Schema+降级逐字报告）与 creative-writing（critic/editor/reader-sim/character-sim 各自 fresh context+只读沙箱）证明：**结构对抗防的是「同分布宽容」，身份标签防不了**。

**五、评估体系单侧化（P4-3/P4-6）。** 金丝雀只测误报侧，漏报侧零基线（自家红方 F6 承认「假阴性没有任何门」）；审查维度无读者冷读（翻页欲/认知负荷/继续率）与商业达标（平台调性/爽点密度）。特征规则抓不住规则表之外的新变种 AI 味，而结果侧检验（dreampowers dp-review-reader 四维冷读）恰是本仓空白。

**六、上下文工程缺「顺序」与「门控」（P2-4/P2-7/P1-3/P2-7b）。** composer 有体积预算（M5）无顺序工程：17 槽无一注入上章定稿语态、promise_ledger 按 rowid 固定 LIMIT 无按本章人物加权——上轮调研已立案的「动笔前最后读正文语态」至今无对应槽。同时 69KB 产物无差别注入任何模型，per-model 依从性零记账，「廉价模型跑 constrained 档塌方」无任何报警。

**七、知识资产「名实差」（P3-1/P3-4）。** 原始库 5.7MB 不薄，薄的是可用层：23 张 kb 表只蒸馏 3 域，平台密度/合规改写/数据漏斗/继续率全部缺席；genre-packs 30 题材×4 字段无生成/版本/过期管道，「唯一源」实为冻结（对照 webnovel-writer 37 个题材×阶段方法论模板）。

## 3. 被驳回项（NovelOS 站得住，记录在案防止翻案）

1. **时序攻击**（P4-8）：被告防线本就是双层的（写前：锁定计划+受控注入+组装 fail()；写后：G2 终验），挑战者的写前门是「避免浪费修复轮次」的优化，不是正确性缺口。
2. **「槽截断静默丢知识」**（P2-2）：截断有节尾脚注透明化弃置数，组装日志 content_hash 可审计——比 dreampowers 全内联（tested_model 实测弱模型崩坏）与 oh-story「自觉读到 EOF」的审计性都强。
3. **「27KB 静态卡最低效」**（P2-6 的前半）：43 条机器预筛+人类语料金丝雀基线+confirm/deny 证伪协议，校准强度远超挑战者的模型自评指数（aidetect 无任何人类基线）。成立的只有成本结构部分（常驻固定税+零反自我说服条目）。

## 4. 待定项（价值取舍，须用户裁决）

- **八级依赖链**（P1-4）：对 300 章一致性是真实投资，但缺 lite 快档——链不砍、档要加（denova 双档证明零冲突）。
- **SQLite 红线降级**（P1-6/P3-2）：多表事务与对账 join 是真实优势（六账本对账吃 join）；正文 BLOB+LIKE 检索与不可 diff 是真实成本。结论：红线降格为「规模取舍」，检索层（FTS5）可作独立增量，不必动存储引擎。
- **运行时拉取 vs 被动注入**（P2-3）：拉取入口该修（P2-5 已立案），但把披露整体改为运行时自主拉取会以审计面倒退为代价——折中：保留机器组装为主，修复按需 Read 指针为辅。

## 5. 修正案清单（按性价比排序）

> **执行状态（2026-08-29 R7 收口）**：A1 ✅ / A2 ✅ / A3 ✅（021 生产库应用=独立裁决门待批）/ A4 ✅ / A7 ✅——执行详情见 `tasks/README.md` R7 条目；A5/A6/A8/A9/A10 缓行呈报中。
> **执行状态（2026-08-30 R8 收口）**：A8 ✅（`25135ee` M7 建档）/ A5 ✅（`2e90051` 022+门互锁+注入槽；**022 生产库应用 2026-08-30 用户裁决「确认」后执行完毕**——备份 `bak-r8-022-20260830180138`，单事务 022+版本登记 22，26→27 表零损失，integrity ok/FK 违例 0，与 schema.sql v22 逐列一致）/ A10 ✅（`fd24ecb` 漏报试点阳性 1.18%，**用户抽检待做**，报告 `docs/knowledge/redteam/missrate-pilot.md`）/ A9 ✅（`cf1f391` platform/commercial/compliance 三卡+接线）——执行详情见 `tasks/README.md` R8 条目；**A6=裁决门**（设计骨架+三决策问见 `tasks/R8-deferred-amendments.md` T5，未获批不执行）。
> **执行状态（2026-08-30 A6 补记）**：A6 ✅——用户指令「T3 A6」批准按建议口径执行：三视角简卡+prose-review 接线（多视角 `--without-slot` 单卡注入/单审查者三卡自检）+SKILL.md 多视角编排节（fresh context 三 sub agent、≥2 家 provider、结构视角不得与写作者同 provider、READER-* severity 上限 warning 观察一个项目周期、合并单回执走既有 commit-review 门+G2 零新协议）。关闭 P4-7/P4-6（观察期条目：reader-pull 升 blocking 与否据实后议）。

- **A1｜一行堵最大洞**：`novelos-verify-review-evidence.mjs` 把 `empty_findings_approved` 从 --strict-only 升为默认 FATAL（或 SKILL.md:24 标准命令加 `--strict` 并在 AGENTS.md 固化），留 `--allow-empty` 显式豁免。成本一行，直接关闭 P4-1。
- **A2｜复活机器门（harness 中立 CLI 形态）**：`scripts/novelos-gate.mjs`（lock-asset/accept-chapter/commit-review/propagate-stale/validate-asset），语义规格直接考古 `docs/r2-js-gate-spec.md` 与 gate/*.ts 移植成品（159 用例可当移植验收集）；reviewer_profile 加 `^(model|agent):` pattern 校验一并收进门内。关闭 P1-5/P3-7/P4-2。
- **A3｜账本补流水**：`promise_events` 追加表（promise_key/chapter_id/event_type/anchor+hash）+每章收口算 Claremont 收支门禁；relationship/arc 状态保留版本历史。关闭 P3-3。
- **A4｜语态槽+加权**：SLOT_REGISTRY 增「上章定稿结尾 500-800 字」槽置于自检节前；promise_ledger/canon_minimal 按本章出场人物与活跃弧线加权排序。关闭 P2-4。
- **A5｜TBD 物化**：升级用户裁决时落盘 TBD 产物（subject 标记+各轮 blocking 摘要），下游注入可见。关闭 P4-5。〔R8-T2 ✅ `2e90051`：022 adjudications+gate open/resolve-adjudication+lock/accept 门互锁+open_adjudications 注入槽；022 生产应用=独立裁决门待批〕
- **A6｜多视角审查**：review 场景并行 2-3 个视角 sub agent（结构/人物声音/读者冷读），统一 findings schema 后主控合并；review 维度新增 reader-pull。关闭 P4-7/P4-6。〔R8-T5 ✅ 2026-08-30 用户批准按建议口径执行：三视角简卡+编排协议落地（SKILL.md 多视角节+craft 三卡），READER-* 先 warning 观察；详见 tasks/README.md A6 条目〕
- **A7｜防漂移三小件**：修 chapter-draft prompt.md:37 指针（craft/→writing/）；agent-recipes.json:3 引用改口径；catalog/skills+config 建 sha256 manifest lint（参照 oh-story manifest v2）。关闭 P2-5。〔R7-T2 ✅〕
- **A8｜依从性记账**：per-model FATAL 率/审查轮次/deny 率进 metrics M 系（M7）。关闭 P1-3/P2-7。〔R8-T1 ✅ `25135ee`：M7 三指标建档+判读纪律（只呈报不自动除名）+对账 SQL；数据自首个真实项目章节流起采〕
- **A9｜蒸馏扩域**：platform/commercial/compliance 三张蒸馏卡（P3 已列，本轮由 P3 升格为成立项）。缓解 P3-1/P3-4。〔R8-T4 ✅ `cf1f391`：platform/commercial 各 14 条（kb 源蒸馏+溯源）+compliance 10 条（自著，无源如实声明）；双 manifest 接线；genre-packs 生成管道不在本条范围〕
- **A10｜漏报侧试点**：抽 AI 生成对照语料做金丝雀漏报率首测（小样即可），决定是否升级为常设基线。缓解 P4-3。〔R8-T3 ✅ `fd24ecb`：标准管线 2 章+R1 A 组对照；句层零命中、初标阳性 1.18%（残留=表外变体三类）；用户抽检 12 段包回执无异议（2026-08-30）——**1.18% 转正为可引用基线**；升格常设基线与否=用户另行裁决〕

**裁判驳回存档（不得采用的挑战者路线）**：运行时自主拉取全面化（审计倒退）、单文件全内联（依从性实证崩坏）、弃 SQLite 改文件提交链（六账本 join 成本真实，存储引擎不动、检索层增量即可）。

## 附录：四份起诉书原文

### 起诉方一号 · agent 架构

**一、单写者纪律 ≠ 主控当写者。**〔指控〕AGENTS.md「sub agent 不持有数据库访问手段，只返回候选文本，所有持久化由主控完成」——一章至少 6 次脚本+4 次事务全过主控，章节全文在主控上下文往返两趟。〔证据〕webnovel-writer `docs/architecture/overview.md` 定 Data Agent 为唯一写者，落库由 `chapter-commit` 驱动 projection writers，正文由 data-agent 自读不过主控之手。〔思想实验〕新增 data-writer sub agent，主控只递章节 ID 与候选路径。〔裁决〕成立：单写者是对的，但单写者可以是程序或专职 agent。

**二、主控四职合一。**〔证据〕creative-writing-skills `agents/` 12 个独立 agent；webnovel-writer 主+context/reviewer/data 三 subagent。〔裁决〕部分成立：composer 已卸载大头，但「审查证据核验由谁跑」应明确归属。

**三、「模型无关 ABI」是无度量支撑的幻觉。**〔证据〕dreampowers `tested_model.md`：Sonnet 4.6「多约束并行」15 分（Opus 4.6=100），同一 ABI 下依从性差 6 倍+；被告调研自认无依从性度量。〔裁决〕成立：per-model 通过率应记账，低于阈值自动从档位除名。

**四、八级依赖链官僚主义。**〔证据〕denova novel-lite/standard 双档、chinese-novelist 三级 JSON 状态机照跑长篇。〔裁决〕待定：链不砍、档必须加。

**五、把机器门降级为主控自查——最危险的行为证据。**〔证据〕tasks/README.md R2：JS 写门三件套建成并验证 DONE（159/159 绿），随插件一并拆除；webnovel-writer PreToolUse hooks 硬拦直写；oh-story reference-tool 路径逃逸直接 throw。〔裁决〕成立：辩护（hooks 是 Claude Code 专属）挡不住 harness 中立的 CLI 门——chinese-longnovel 脚本契约证明 CLI 门可跨 harness。长跑中纪律必然漏。

**六、攻击红线「SQLite 权威库」。**〔证据〕chinese-longnovel 纯文件提交链+CAS+sha256 状态回证达到等价完整性，免费获得 diff/git 历史与人可读。〔裁决〕待定：红线应降级为规模取舍。

最危险一击=第五条（强制降级为自律有行为证据）；最该立即采纳=以 harness 中立 CLI 复活写门。

### 起诉方二号 · prompt/上下文工程

**攻一：69KB 一次性注入是搬运不是工程。** compose() L584-620 单文本拼接、craft 卡逐字全量（L1558-1568）；M5 实测 fingerprint 27,172B/craft 五卡 43,836B/产物 69,433B。〔裁决〕部分成立：craft 层成立；canon_minimal（LIMIT 12/30/5 近端）与 knowledge 槽已是 LOD 雏形，对数据槽驳回。

**攻二：截断静默丢知识。**〔证据〕dreampowers 单文件 928 行+tested_model 依从性崩坏量化。〔裁决〕被驳回：节尾脚注透明化+content_hash 可审计。反揭一桩：KG1 的 2560B 上限只管机器卡（test-guardrails.mjs L98），26,720B 人工 fingerprint 卡全量豁免——预算纪律方向倒置。

**攻三：被动注入剥夺按需补读。** chapter-draft prompt.md 末节指名的 `catalog/skills/craft/scene-dialogue`、`scene-fight-craft` 目录不存在（ls 实证）。〔裁决〕待定：补读入口腐坏属实；但 writeCompositionLog（L1601-1637）把「模型实际看到什么」做成可回查事实，审计反超；真缺口在 knowledgeRetrieve 字面匹配的检索精度。

**攻四：注入顺序工程缺位。** 17 槽无一注入上章语态；promise_ledger 按 rowid 固定 LIMIT；U 型排布把生成点前最后位置留给自检清单。〔证据〕webnovel-writer context_ranker recency+钩子加权。〔裁决〕成立。

**攻五：防漂移守护被自己拆除。** config/agent-recipes.json 描述明言由 tests/test_recipe_matrix.py 校验，该文件已在零 Python 提交删除（仅剩 .pyc）。〔裁决〕成立但限缩：guardrails 271 项/KG1/canary rule_table_hash 守护密度仍高于全部挑战者；但 config 引用的守护已删而引用未改+两张幽灵卡，防漂移叙事破口确凿。

**攻六：27KB 静态反AI卡最贵方案。**〔裁决〕被驳回一半（校准强度反超 aidetect 自评指数）；成立一半：常驻固定税+防自我说服的 prompt 心理学为零（dreampowers 危险信号对照表 L135-152）。

**攻七：无模型能力门控。** 同一 69,433B 注入任何模型，配方矩阵管「加载什么」不管「谁在消费」。〔裁决〕成立。

最危险一击=攻五；最该立即采纳=语态槽（SLOT_REGISTRY 增上章定稿结尾槽、置于自检前）。

### 起诉方三号 · 材料/知识/数据资产

**攻一【知识资产名不副实】** config/knowledge 恰 3 张蒸馏卡（112 条）+15 persona；data/knowledge 16 张 kb_*.json 约 5.7MB 但 gitignored、23 张 kb 表仅蒸馏 3 域，平台密度/合规改写/数据漏斗缺席。〔裁决〕部分成立：原始资产不薄，可用知识确薄。

**攻二【SQLite 错配引擎】** 正文 CAST BLOB 存 resources；novel-memory 检索仅 LIKE；novels/ 投影 gitignored。〔证据〕Claude-Code-Novel-Writer 手稿唯一真源+派生可再生。〔裁决〕部分成立：投影可再生路线驳回（与本仓同源）；检索/协作成本真实。

**攻三【六账本有账无流水】** schema.sql:200-211 无 resolution 章位无事件表；relationship/arc UPSERT 历史即焚；无收支门禁；唯一亮点每行 source_content_hash 溯源。〔证据〕dreampowers 事件流+Claremont（dp-set-outline SKILL.md L447-460）；chinese-longnovel source_anchor+sha256 事实锁。〔裁决〕成立。

**攻四【genre-packs 冻结】** 30 题材×4 字段仅 20KB，无生成/版本/过期机制。〔证据〕webnovel-writer 37 题材模板。〔裁决〕成立。

**攻五【内容 schema 弱】** world 契约 dimension_costs 代价轴自辩成功；但 volume_settings 条目 spec 自由字符串。〔证据〕Distilled 新设定 7 字段。〔裁决〕部分成立。

**攻六【planning_assets 过度】** 8 类资产×4 态 vs R5 自认唯一项目规划链空白、chapters=0——全副武装打空场。〔裁决〕部分成立：单机定位可辩护。

**攻七【完整性押在自查上】** 九个门工具全退役，运行时零机器强制。〔裁决〕成立。

最危险一击=攻三；最该立即采纳=promise_events+Claremont 门禁（一张追加表+一处收口计算）。

### 起诉方四号 · 审查/对抗机制

**攻一：G2 验证的是「引文存在」不是「审查没放水」，且默认放行空查回执。**〔已验〕脚本 L347-353：空 findings+approved 仅 advisory，--strict 才 FATAL；SKILL.md:24 标准命令无 --strict。〔裁决〕成立：橡皮图章检测开关是 opt-in。

**攻二：防共谋降级成字符串礼仪。** schema L87-91 仅 type:string minLength:1；modelRoleWarnings()（WP4）随插件退役删除；M2 只对引文验证失败计数不放水计数。〔证据〕creative-writing critic 只读沙箱；denova SubAgent 只审不改。〔裁决〕成立（被高估）：前缀有留痕价值，「拒绝落库」无机器执行。

**攻三：金丝雀只测误报，漏报率零基线。**〔已验〕canary-baseline.md:5 口径自认；D2 红方 F6 原文「假阴性没有任何门」；M3 deny 率 43.5% 为合成夹具。〔证据〕dreampowers dp-review-reader 四维冷读测读者侧结果。〔裁决〕成立。

**攻四：「只报事实不判级」把判级推给人还先塞噪声。** 金丝雀证明 L03 破折号 0.92/千字全是人类正常标点。〔证据〕chinese-webnovel aidetect 机器给分+扣分定位到句。〔裁决〕部分成立：U1 方案 A 重分层方向正确，脚本侧仍不判级。

**攻五：升级用户是流程挂起，不是可恢复状态。**〔证据〕dreampowers TBD 文件+[TBD] 标记随摘要流入下游；tianming 待决议进体检矩阵。〔裁决〕成立。

**攻六：审查维度缺「读者」与「钱」。**〔裁决〕成立（被告自认在案）。

**攻七：单审查者一次产出全维度。**〔证据〕oh-story full spawn 4 agent+统一 Findings Schema+降级逐字自证。〔裁决〕成立。

**攻八：时序指控。**〔裁决〕被驳回：被告是双层防线，写前门是优化非正确性缺口。

最危险一击=攻一；最该立即采纳=TBD 机制（升级物化为持久产物+下游可见）。
