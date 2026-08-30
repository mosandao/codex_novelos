# R8 · 缓行修正案执行轮（A8/A5/A10/A9 + A6 裁决门）任务书 v1

> 状态：**执行收口（2026-08-30）：T0-T4/T6 全部完成，七套终值全绿（guardrails 409 / fingerprint 49 / verify 15 / render 48 / gate 70 / canary PASS / compose 17✓+11 环境性=基线一致）；执行记账见 `tasks/README.md` R8 条目。三个未决门留用户：① 022 落生产库（T2 裁决门，独立「确认」后执行）；② T3 试点报告用户抽检 ≥10 段；③ T5 A6 三问裁决。**
> 来源：`docs/novelos-adversarial-cross-exam.md` §5 缓行项 A8（M7 依从性记账）/A5（TBD 物化）/A10（漏报侧试点）/A9（蒸馏扩域）；A6（多视角审查）=文末裁决门，**不获批不执行**。2026-08-29 用户已认可执行顺序：A8+A5 → A10 → A9 → A6 单独裁决。
> 纪律前提：零 Python（Node 22+，node:sqlite/node:crypto，零 npm）；生产库任何写入前先复制 `data/novelos-v2.db` 备份；金丝雀 rule_table 全程不动（canary `--compare` 必须零回归，A10 是「用尺子量」不是「改尺子」）；metrics 追加行不覆盖；单渲染器红线不动；不建 DB 指标表不上仪表盘（M 系过度工程红线维持）。

## 0. 目标与验收总则

清偿对抗审查四项缓行修正案：**per-model 依从性零记账（P1-3/P2-7）→ M7；升级裁决不可恢复不可见（P4-5）→ adjudications 表+门互锁+注入槽；金丝雀漏报侧零基线（P4-3）→ 一次性试点；知识层三域缺席（P3-1）→ platform/commercial/compliance 蒸馏卡**。

**总 DONE 判据**（全部满足才可记账 DONE，缺一即 BLOCKED）：
1. 七套测试全绿且不低于 R7 终值基线：guardrails 379+ / fingerprint 49 / verify-review-evidence 15 / render 48 / canary `--compare` PASS / **test-gate 58+新增** / compose 17✓+11 环境性（口径一致）。
2. 生产路径实测：gate 新子命令对生产库只读冒烟 PASS 且 `PRAGMA data_version` 前后一致；migration 022 仅在副本库验证，**生产库应用=独立裁决门**（照 021 先例）。
3. 口径同步：sql-reference.md / 相关 SKILL.md / AGENTS.md 涉及新通道与新槽的表述全部更新（grep 验证无残留旧口径）。
4. `tasks/README.md` 记账 + `docs/knowledge/metrics.md` 追加行（M7 建档 + A10 试点行）。

## T0 · 预检（半小时，无写入）

- [ ] 复制备份：`cp data/novelos-v2.db data/novelos-v2.db.bak-r8-$(date +%Y%m%d%H%M%S)`。
- [ ] 七套基线快照：guardrails / fingerprint / verify / render / canary / gate / compose，记录通过数（应为 379/49/15/48/PASS/58/17✓+11）。
- [ ] git 基线：工作区干净。
- **验证**：基线与 tasks 账本 R7-T6 终值一致；不一致先停下呈报。

## T1 · A8 M7 依从性记账（半天，纯文档+SQL 模板，零库写入零脚本）

- [ ] `docs/knowledge/metrics.md` 开 **M7 模型依从性**节（列结构沿用，首行=建档行）：三指标定义——① per-model FATAL 率（verify-review-evidence 三路 FATAL + commit-review 门拦，分母=该模型回执落库尝试数）；② per-model 平均审查轮次（同 subject 收敛所需 review 数，自 reviews 聚合）；③ per-model deny 率（prescreen 候选 deny/候选总数，自 chapters.metadata_json.prescreen 聚合，M3 分母口径复用）。建档行如实记「生产库 reviews=0 无历史数据，采集触发=首个真实项目章节流」。
- [ ] `.agents/skills/novel-project/sql-reference.md` 增「M7 对账查询」节：三条一次性只读 SQL（reviews 按 reviewer_profile 前缀聚合轮次与 verdict；prescreen 按 metadata_json json_each 聚合 confirm/deny）。
- [ ] 判读纪律落 metrics 节首：**先记录后判读；低于阈值只呈报用户裁决，不自动从档位除名**（自动除名=门耦合指标，过度工程）。
- **验证**：SQL 在 /tmp 夹具库（造 2-3 行 reviews/prescreen 假数据）跑通；guardrails 不涉（纯 md）无回归。

## T2 · A5 TBD 物化（1-2 天；含 migration 022 与独立裁决门）

**设计**：升级用户裁决（3 轮未收敛/同因复发/mismatch）时，主控经 gate 落一条 adjudication 行——「卡住的 subject + 各轮 blocking 摘要」成为库内权威事实；未裁决（open）期间**门封状态推进**、**下游注入可见**。

- [ ] 新迁移 `db/migrations/022_adjudications.sql`：表 `adjudications(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, subject_type TEXT NOT NULL, subject_ref TEXT NOT NULL, reason TEXT NOT NULL, rounds_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')), resolution TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, resolved_at TEXT)`（rounds_json=各轮 blocking 摘要数组；存量不回填照 019/021 先例）。schema.sql 照 021 先例同步再导出（27 表独立建库验证）。
- [ ] `novelos-gate.mjs` 新子命令 ×2（dry-run 默认 / --commit / 生产库 --allow-production，全部照既有约定）：
  - `open-adjudication`：登记 TBD（subject 存在性反查 + open 幂等：同 subject 已 open 即拒绝重复开单，GateFail 指引先裁决）；
  - `resolve-adjudication`：用户裁决后落 resolution + 翻 resolved + resolved_at。
- [ ] **门互锁**（本条的牙齿，堵「地基未定还在盖楼」）：`lock-asset` / `accept-chapter` 遇 subject 存在 open adjudication → GateFail「先裁决后推进」；`commit-review` **不拦**（裁决期间补审查是合法输入）。`propagate-stale` 不拦（标记下游恰是裁决影响面的一部分）。
- [ ] **注入可见**：composer `SLOT_REGISTRY` 新槽 `open_adjudications`（项目内 open 行渲染为警示节：subject+reason+轮次摘要，置于 craft 卡之前）；先接三处 manifest——chapter-draft / prose-review / chapter-plan（data_slots 只许增长，G2b 语义兼容）；首接清单记入本任务书执行记录，其余资产按需追加不扩批。
- [ ] 测试：`test-gate.mjs` 增 ≥8 例（open 后 lock/accept 双阻断、resolve 后放行、重复开单 GateFail、rounds_json 留痕、CLI 生产卫兵、dry-run 零写入、无 open 行零影响、注入槽两态渲染）。
- [ ] 口径：SKILL.md（novel-review 升级路径句 + novel-planning 章纲句）与 AGENTS.md 工作流第 3 步「升级用户裁决」处增句不删句——升级须过 `open-adjudication`，裁决后过 `resolve-adjudication`。
- **验证**：/tmp 副本库应用 022 → 开单/阻断/裁决/放行全流程实测；compose 冒烟有/无 open 行两态 diff 仅警示节；行数对账零损失；canary PASS。
- **裁决门**：022 落**生产库**前单独呈报（备份名+影响面+回滚 SQL），用户点头才执行；未点头则 T2 记「代码 DONE、生产应用 BLOCKED(用户裁决)」不阻塞 T3/T4。

## T3 · A10 金丝雀漏报侧试点（1 天，一次性实验，零生产写入，rule_table 零接触）

**口径先立**：漏报 ground truth 无机器来源——规则表之外的新变种 AI 味只能人工标注。试点=小样人工基线，只报事实不判级。

- [ ] **语料**：fixture 库组装标准 chapter-draft 注入产物（T2 后口径，含语态槽），交写作 sub agent（强创意模型，多模型分工纪律）新生成 **≥2 章、每章 ≥4000 字**，落 `/tmp/r8-missrate/corpus/`；另以 R1 盲测 A 组合成 AI 味段作参照组（已知高密度，预期高命中——用于验证「该抓的抓得住」）。
- [ ] **流程**：全量语料过 `novelos-prose-fingerprint.mjs --text-file`（screen 层）→ 对**未命中段落**逐段人工初标（主控：残留 AI 味二元 + 理由，只报事实）→ 用户抽检 ≥10 段复核初标质量。
- [ ] **指标**：漏报率=初标阳性段/未命中段总数（按章与规则维度并列）；参照组命中率单列。`docs/knowledge/metrics.md` 追加行（M1 侧翼，标注「M1b 漏报试点（一次性，人工 ground truth）」）。
- [ ] **产出**：`docs/knowledge/redteam/missrate-pilot.md`（语料来源/标注协议/逐段标注留痕/数字/折扣声明——AI 自评初标 + 小样）；结尾给「是否升格常设基线」的呈报建议，**升格与否=用户裁决，本轮不自动升格**。
- **验证**：canary `--compare` PASS（尺子未动自证）；fingerprint 49 无回归；生产库零接触（全程 /tmp）。

## T4 · A9 蒸馏扩域（2-3 天，内容生产型）

- [ ] **预检盘点（半天，缺源如实呈报）**：对照已导 16 张 kb 表盘点三域源——commercial 佐证=`kb_cool_point_patterns`（爽点）+`kb_book_summaries`/`kb_story_genres`（平台调性侧写）；platform 同前两者；compliance 大概率**无原始源**。红线：biz_* 42 张已裁决排除（运行时业务数据非知识源，`novelos-import-knowledge.mjs` 头部声明）**不得回捞**；缺源域走「自著卡」路径——`source_filter` 标 `authored (R8, 无库内源)`，不冒充蒸馏，KG1 结构契约照旧。盘点结论先落任务书执行记录再动笔。
- [ ] **三卡落盘**：`config/knowledge/distilled.{platform,commercial,compliance}.json`（结构照 R3 契约：entries[] 必需字段 + placement；id `kg-<domain>-NNN`；单条 ≤512B / 槽 ≤4096B；零书名零例文引用红线沿用）。蒸馏 sub agent 产候选、主控自查落盘（零库写入，文件即产物）。
- [ ] **接线**：prose-review 与 chapter-draft manifest 按需增 `knowledge:<domain>` 槽（G2b 只许增长）；KG1 自动发现新域文件无需改白名单；`config/catalog-manifest.json` 刷新。
- [ ] 内容边界：compliance 卡=平台红线/敏感改写的**方法论**（自查清单式），不含任何具体平台条款抄录；commercial 卡=密度/钩子/继续率的判读框架，不虚构数据。
- **验证**：guardrails 全绿（KG1 对三新域逐条）+ compose 冒烟（新槽渲染 ≤4096B、`--without-slot` 可禁）+ canary PASS。
- **明确不做**：genre-packs 生成/版本/过期管道（P3-4 另案呈报）；16 表之外新增导入；蒸馏源扩到 biz_*。

## T5 · A6 多视角审查 —— 裁决门（**不获批不执行**）

设计骨架留档（批准后扩入 R8 尾段或另立 R9）：review 场景并行 2-3 视角 sub agent（结构连续性 / 人物声音 / 读者冷读），各自 fresh context、统一 findings schema（沿用 `fpr:` 编号 + G2 引文验证，零新协议），主控合并去重后走既有 commit-review 门；review 维度新增 reader-pull（翻页欲/认知负荷/继续率）。

**决策点三问**（批准前须用户逐条裁决）：
1. 是否接受每次审查 sub agent 调用 ×2-3 的成本结构变化；
2. reader-pull 维度进 blocking 还是先 warning 观察一个项目周期（建议后者，照 Claremont 先例）；
3. 视角模型是否强制异构厂商（防共谋纪律延伸，建议结构视角至少一家异构）。

## T6 · 收口（半天）

- [ ] 全量七套重跑记录终值（不低于 T0 基线）。
- [ ] `tasks/README.md` R8 记账（DONE 判据四条逐一勾验；022 生产应用状态如实记）；`docs/knowledge/metrics.md` 追加 M7 建档行 + M1b 试点行。
- [ ] `docs/novelos-adversarial-cross-exam.md` §5 标注 A8/A5/A10/A9 执行状态与 commit hash；A6 标「裁决门（设计骨架见 R8-T5）」。

## 回滚预案

| 阶段 | 回滚方式 |
|---|---|
| T1 | git revert 单提交；纯 md 零库接触 |
| T2 | 代码/文档 revert；022 未落生产=零影响；已落生产则 `data/novelos-v2.db.bak-r8-*` 整库还原（adjudications 无外部消费者） |
| T3 | `/tmp/r8-missrate/` 删除即可 + md 产物 revert；rule_table 零接触（canary 自证） |
| T4 | 删三张 distilled.*.json + manifest/recipes revert + catalog-manifest 刷新 revert |

## 工作量与顺序

总计约 5-7 个工作日；顺序刚性 T0→T1→T2→T3→T4→T6（T2 生产应用与 T5 裁决门不阻塞后续，可后置）。T1 完成即独立交付（M7 建档）；T2 是本任务重心（唯一动 schema 的阶段，开工时先出 022 DDL + gate 两子命令接口签名供过目再填实现）。
