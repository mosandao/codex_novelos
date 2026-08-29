# D5 · 对抗审查体系编排与全链路演练（设计文档）

> R5 知识吸收计划「方向5规划员」产出。上游：`tasks/R5-knowledge-absorption.md`（v1 总计划，六道门骨架在其 §2）。本文件把 G1-G6 从「机制一句话」细化为**操作规程**，给出红蓝编排落点、度量体系、R6 演练剧本与轮间依赖图。
> 边界重申：工具实现归方向2、判级语义归方向1、槽机制归方向3、schema 变更归方向4。本文件只定义**接口需求与规程**，不动任何 schema 与脚本。

---

## 1. 现状盘点（file:line 锚点）

### 1.1 对抗纪律已有地基

| 现状 | 锚点 | 对本设计的意义 |
|---|---|---|
| 六道门 G1-G6 一句话定义 | `tasks/R5-knowledge-absorption.md:58-68` | 本文件逐门细化的骨架 |
| 红蓝分工（红方指认规则编号、指不出降 note；异构厂商） | 同上 `:69` | G4/G5 执行者约束 |
| 每轮节奏 G4→实施→G5→G1 回归→修复轮(≤3)→记账 | 同上 `:73` | 门与轮次的绑定关系 |
| 审查-修复循环 + warning 必修 | `.agents/skills/novel-review/SKILL.md:36-43` | G6 的宿主循环 |
| 循环边界（3 轮上限/同因复发直接升级） | 同上 `:45-49` | G6 已有 90%，只差豁免援引入呈报清单 |
| 生成侧异议（辩护回合） | 同上 `:57-58` | 红蓝对抗的既有回合制 |
| 横向回执（多候选并列呈报） | 同上 `:60-61` | R6 direction 阶段复用 |
| 豁免通道（defer_to_downstream / accepted_risk） | 同上 `:63-72` | 指纹豁免必须走同款显式留痕 |
| reviewer_profile 机器身份前缀 `model:<provider:model>` | `.agents/skills/novel-project/sql-reference.md:203`、`config/schemas/review-receipt-candidate.schema.json:87-91` | 异构厂商模型的留痕格式已定 |
| Receipt 证据标准（禁"多处/整体"模糊描述） | `catalog/skills/review/prose-quality-review/prompt.md:29` | G2 的语义前置条件已存在，缺机器验证 |
| 数字阈值唯一权威源 = 注入 craft 卡 | 同上 `:18` | G1 回归对象的定义域 |
| 2026-08-25 三路子代理对抗审查实战（23 条 P0/P1/P2，WP1-WP8） | `tasks/README.md:57-69` | G4 组织方式的母本，直接沿用 |

### 1.2 配方矩阵与组装器现状

- `config/agent-recipes.json:4-27` slot_vocabulary（22 个槽）、`:28-33` divergence 三档、`:34-39` decision_scope 四档——**新增配方只能用既有槽名**（本设计验证过，两条新配方零新槽）。
- `chapter_draft` 配方（`config/agent-recipes.json:369-389`）与 `prose-quality-review` 配方（`:390-409`）是写作/审查两侧的落点。
- `catalog/skills/expansions/prose-revision/` 存在但**未注册进 ASSET_DIRS**（`scripts/novelos-compose-prompt.mjs:52-78` 共 25 键，无 revision / redteam）——R1 双模式修订目前无组装通道，是编排缺口 ①。
- 组装器原生支持 `--db <路径>`（`scripts/novelos-compose-prompt.mjs:28,1465-1506`）——**R6 演练库隔离零代码改动即可实现**。
- 指纹卡 `catalog/skills/craft/prose-anti-ai-fingerprint/prompt.md` 只有 5 个节标题（`:5,15,29,38,51`），**无稳定规则编号体系**——红方「指认规则编号」与预筛候选回填都依赖它，是编排缺口 ②（语义归方向1，此处立为接口需求）。

### 1.3 数据库取材（2026-08-29 只读实测）

```
projects=1  books=0  volumes=0  chapters=0  planning_assets=0
reviews=3（均为 planning-cross-check 遗留回执，reviewer_profile 为裸字符串——旧数据）
resources=181  creator_profiles=31（18 系统 + 用户签名若干）
```

唯一项目 `project:fdc0e83f-3cb8-4b7e-8b6d-84e9ea1db589`「诸天无限：从大运开始」：男频·番茄·免费算法·超长篇，setup v2 快照完整，**规划链与章节完全空白**。结论：R6 演练从 direction 起跑即可覆盖八级规划全链，无需另造最小项目；但演练数据必须隔离（见 §5.1）。

### 1.4 方法论母本（refs/lieflat-less-ai-tone/RESEARCH.md）

- 分母三选（`:43-55`）→ G1 度量设计：误报率分母 = 同类元素总数（每千字/每百段/占同类比例），不得跨类混算。
- 判定门槛（`:57-75`：倍率 + 人类侧稳定 + 触发可定位 + 改法不违白名单）→ 新规则收录判据。
- 六次测量失误（`:244-255`）→ **「改规则前先抽样看 20 条命中，再看频率」**写进 G1 操作规程。
- 单模型癖好误读为共性（`:19`）与模型间数量级差异（`:227-242`）→ 异构厂商红方/审查的实证依据。

---

## 2. G1-G6 六门操作规程

> 通用约定：所有门的执行记录统一落 `docs/knowledge/redteam/`（新建目录，git 内）与 `docs/knowledge/metrics.md`（§4）；**六门全部不动数据库 schema**，G2/G3 的过渡存储用 `reviews.metadata_json`（表已存在该列，见 §1.3 reviews DDL 实测）。

### 2.1 G1 · 金丝雀回归门

| 项 | 规程 |
|---|---|
| **触发时机** | 任何影响指纹判级语义/阈值/rubric 措辞的变更**合并前最后一步**（R1 craft 卡、R3/R4 例文与参照、R5 豁免措辞）；R0 建基线时不判只测 |
| **执行者** | 脚本 `scripts/novelos-canary.mjs`（方向2 交付）+ 主控执行与判读 |
| **输入** | `data/canary/*.md`（人类语料金丝雀集，gitignore，R0 建成 15-20 篇）+ 当前生效的指纹规则集（craft 卡 + 预筛正则） |
| **输出** | 追加式报告 `docs/knowledge/canary-baseline.md`：每条规则 × 分母口径 × 误报计数/误报率；与基线差值列 |
| **失败处置** | ① 新增/收紧条目**单项误报 >0** → 该条目降级 `note` 或撤回（回滚该条，不动整批）；② 总误报率高于基线 → 整批变更回滚重设计；③ 误报率下降（R1「不作为判级理由」表预期效果）→ 记录通过。**判读前必做**：对新命中抽样 ≥20 条人工过目（RESEARCH.md:255 操作要求，防宽正则假命中） |
| **记录位置** | `docs/knowledge/canary-baseline.md`（明细）+ `docs/knowledge/metrics.md`（每轮汇总行，§4 指标 M1） |

**编排要点**：金丝雀是女频短篇、项目是男频长篇——语言层结论可用，结构层结论在报告中显式打折扣标注（v1 计划 §6 风险 1 的落实位）。

### 2.2 G2 · 引文机器验证门

| 项 | 规程 |
|---|---|
| **触发时机** | **每张 Review Receipt 落库前**（prose-review 与 planning-*-review 全覆盖；R2 交付脚本后启用，R6 全程开） |
| **执行者** | 脚本 `scripts/novelos-verify-review-evidence.mjs`（方向2 交付）+ 主控执行 |
| **输入** | Receipt JSON（findings 的 excerpt/evidence_refs）+ 被审对象正文（resource content）+ 该次审查组装时注入的上游原文清单（防止「引文命中了上游却没注入给审查者」的假通过） |
| **输出** | 验证结论：每条 finding 的引文是否在被审正文或注入上下文中**归一化字符串命中**（空白/直弯引号/省略号变体归一）；不命中清单 |
| **失败处置** | ① 任一 finding 引文不命中 → **整张 Receipt 作废打回**审查 agent 重出（不是修复循环——证据无效与正文缺陷是两回事，重出次数计入该 reviewer 的 G2 失败计数）；② 同一 reviewer 连续 2 张作废 → 更换审查模型并记入 `docs/knowledge/redteam/g2-log.md`（疑似编造证据倾向）；③ 脚本自身误报（引文确在但归一化不命中）→ 主控人工复核通道，确认后修脚本不罚 reviewer |
| **记录位置** | `docs/knowledge/redteam/g2-log.md`（每次作废/复核一行）+ `metrics.md` 指标 M2 |

**设计依据**：CALM 框架实测「伪造引用（authority bias）能成功劫持评判模型的判断」（§11 来源 2）——引文必须机器验证，不能信任模型自证。Receipt 证据标准已在 `prose-quality-review/prompt.md:29` 有语义约束，G2 把它变成机器门。

### 2.3 G3 · deny 率监控门

| 项 | 规程 |
|---|---|
| **触发时机** | R2 起：每章 prose-review 组装时注入预筛候选清单（标注「仅供证伪，须逐条 confirm/deny」）；回执落库后统计 |
| **执行者** | 审查 sub agent（逐条表态）+ 主控（统计与告警判定） |
| **输入** | 预筛候选清单（规则号/位置/原文片段/计数，`novelos-prose-fingerprint.mjs` 输出，只报事实不判级） |
| **输出** | Receipt 内每条候选的 `confirm / deny + 理由`（存储见接口声明 §10.3：过渡用 `reviews.metadata_json.prescreen`，正式字段与方向4 合并轮）；`metrics.md` 每章一行 deny 率 |
| **失败处置** | ① deny 率 = 0 且候选数 ≥5 → 告警：主控抽 3 条候选人工判（真候选还是误候选）；② 连续 3 章趋零 → **升级用户裁决**（U7：预筛规则或审查 agent 哪个失效）；③ deny 理由成立（规则误报）→ 转规则修订提案，走 R1 通道改卡，改后过 G1 |
| **记录位置** | `reviews.metadata_json`（逐条表态）+ `docs/knowledge/metrics.md`（M3） |

**设计依据**：CALM 的 bandwagon/锚定效应——给评判模型「供参考」的机器候选会系统性拉高确认率，必须强制逐条表态 + 监控 deny 率才有证伪力（§11 来源 2）。deny 不是失败信号，**deny 率趋零才是失败信号**。

### 2.4 G4 · 红方规格审门

| 项 | 规程 |
|---|---|
| **触发时机** | 每轮（R0-R6）改动清单成文后、**实施前**；本文件自身在获批前也应过一次（§8） |
| **执行者** | 红方 sub agent 1-3 路，**异构厂商模型**（编排示例见 §3.4），主控汇总 |
| **输入** | ① 规格全文（本轮计划节选/设计文档）；② 受影响面清单（改哪些文件、哪些配方、哪些 SKILL）；③ 固定三问模板：**体裁错配**（论述文结论套小说场景？女频金丝雀结论套男频项目？）、**上下文预算**（新增注入撑不撑爆组装体积？）、**双源漂移/纸面化**（有没有第二个权威源？有没有「仅警告即放行」的口子？） |
| **输出** | `docs/knowledge/redteam/r{N}-spec.md`：P0（阻断，规格不可实施）/ P1（须修，≥90% 修复才 DONE）/ P2（记录备查）findings，每条带定位与建议 |
| **失败处置** | P0 存在 → 修改规格重审（同因复发直接升级用户，沿用 G6 逻辑）；P1 修复率 <90% → 该轮不得记 DONE |
| **记录位置** | `docs/knowledge/redteam/r{N}-spec.md` + `metrics.md`（M6）；修复结论回写 `tasks/README.md` R5 节账本 |

**组织方式**：沿用 2026-08-25 三路切法（题材信息流 / 流程间上下文 / 组织与产出质量，`tasks/README.md:57`），按轮次裁剪——R1/R3/R5 重点前两路，R4 加「参照与 Canon 权威关系」专项，R6 剧本审加「演练成本与收敛判据可操作性」。

### 2.5 G5 · 红方产物审门

| 项 | 规程 |
|---|---|
| **触发时机** | 每轮落地后（R1 起盲测；R3/R4 各自专项；R6 终审） |
| **执行者** | 红方 sub agent（异构厂商模型，§3.4） |
| **输入** | **盲测协议**（R1/R6）：3 段 AI 生成文 + 3 段金丝雀文，**随机顺序、匿名标签、长度配对**（±20% 字数内，防 verbosity bias）+ 注入 craft 卡全文（判级唯一权威源）；**专项协议**（R3/R4）：成品 + 规格对照（实现偏离找差） |
| **输出** | `docs/knowledge/redteam/r{N}-artifact.md`：① 判源结论（哪段 AI/人类 + 置信度）；② 每条指纹 finding **指认规则编号**，指认不出自动降 `note`（防红方发明规则，v1 `:69` 纪律）；③ P0/P1/P2 |
| **失败处置** | ① 修订后 AI 段指纹未降 → 修订模式违规，打回重修；② 修订后人类段（金丝雀）改动非零或超最小改动 → 双模式边界失守，打回并复核 R1 判据；③ 红方判源全对或全错 → 盲测校准问题，复核段落难度后重抽；④ 连续两轮识破匿名标签 → 盲测协议本身修订（段落来源特征泄漏） |
| **记录位置** | `docs/knowledge/redteam/r{N}-artifact.md` + `metrics.md`（M6） |

**设计依据**：LLM-as-judge 的 position bias（配对顺序影响判断）用随机化+可复核排序记录缓解；verbosity bias 用长度配对；self-preference 用异构厂商 + 匿名化（§11 来源 1/2/3）。

### 2.6 G6 · 收敛纪律门

| 项 | 规程 |
|---|---|
| **触发时机** | 审查-修复循环每轮重审前（主控查上轮回执做同因判定） |
| **执行者** | 主控（既有纪律的执行者，无需新增角色） |
| **输入** | 同 subject 的历史回执序列（reviews 表按 subject_ref 查） |
| **输出** | 收敛判定：继续循环 / 升级用户（附各轮 blocking 摘要） |
| **失败处置** | ① 3 轮未收敛 → 升级（既有）；② 同因复发 → 直接升级（既有）；③ **新增**：「指纹豁免援引」列入须呈报分歧类型——审查方或修订方援引签名豁免对抗指纹 finding 时，必须呈报用户（豁免是否成立 = 艺术取舍裁决，等价 accepted_risk 通道 `novel-review/SKILL.md:69-72` 的用户确认要求） |
| **记录位置** | 升级事件入 `tasks/README.md` R5 节账本 + `metrics.md`（M4 收敛轮数） |

### 2.7 门-轮矩阵（哪轮开哪些门）

| 轮 | G1 | G2 | G3 | G4 | G5 | G6 |
|---|---|---|---|---|---|---|
| R0 | 建基线 | — | — | ✓（审本计划） | — | — |
| R1 | ✓ | — | — | ✓ | ✓ 盲测 | ✓ |
| R2 | ✓ | ✓ 上线 | ✓ 首测 | ✓ | ✓（假 Receipt 用例） | ✓ |
| R3 | ✓ | ✓ | ✓ | ✓ | ✓ 盲测（有/无知识槽） | ✓ |
| R4 | ✓ | ✓ | ✓ | ✓ | ✓ 演练（参照混入路径） | ✓ |
| R5 | ✓ | ✓ | ✓ | ✓ | ✓（豁免假阳性） | ✓ |
| R6 | ✓ | ✓ 全程 | ✓ 每章 | ✓（审剧本） | ✓ 终审 | ✓ |

---

## 3. 红蓝编排落点

### 3.1 agent-recipes.json 新增配方（JSON 草案）

两条新配方追加进 `assets` 数组（**全部使用既有槽名，slot_vocabulary 零新增**；ASSET_DIRS 注册键由方向2 落地，此处为契约）：

```json
{
  "asset": "prose-revision",
  "composer_key": "prose-revision",
  "skill": "expansions/prose-revision",
  "slots": [
    "subject",
    "kernel_full",
    "persona_full",
    "persona_gate",
    "project_setup",
    "canon_minimal",
    "world_lexicon",
    "character_essence",
    "review_feedback"
  ],
  "divergence": "constrained",
  "decision_scope": "execute",
  "output": "修订正文（--payload 指定双模式 mode=fingerprint-clean|texture-inject；指纹清除=白名单最小改动+未命中句逐字保留+语言层信息守恒；质感注入=Canon 守恒不加事实；按 review_feedback 中 findings 的规则编号定点处理）",
  "failure": "模式判据不明或 payload 缺 mode → 组装 fail()（沿用 WP1 静默降级硬失败先例）；修复未命中 findings 编号 → 主控打回；禁全文重写（超阈值 diff 视为重写打回）"
},
{
  "asset": "prose-blindtest",
  "composer_key": "prose-blindtest",
  "slots": ["subject", "craft_refs"],
  "skill": "review/prose-blindtest",
  "divergence": null,
  "decision_scope": "judge",
  "output": "盲测报告（判源判定+置信度+指纹 findings 逐条指认规则编号；指认不出自动降 note）",
  "failure": "段落配对被识破匿名标签 → 重抽对；连续两轮识破 → 盲测协议修订升级主控"
}
```

设计说明：

- `prose-revision` 补编排缺口 ①（§1.2）：R1 双模式修订目前无注册资产，主控只能手工拼注入——违反「已注册资产一律用组装器」精神。mode 参数走 `--payload`（与 kernel-fusion 的 request_type 同模式，composer 已有 payload 域先例 `scripts/novelos-compose-prompt.mjs:50-51`）。
- `prose-blindtest` 是 G5 的组装通道：红方判级依据必须与正式审查同源（craft_refs 逐字注入，唯一权威源纪律），否则红方与审查方各说各话，finding 无法互校。
- `redteam-spec-review`（G4）**不注册**：规格是文件不是库资产，无槽可解析，主控直接贴规格全文给红方 sub agent 即可——注册反而制造伪权威源。此边界写明，防过度工程。

### 3.2 .agents/skills/novel-review/SKILL.md 增补行（措辞草案）

工作流第 6 步（落库模板）之前插入一步（R2 后生效）：

```markdown
6. 落库前过 G2 引文验证：`node scripts/novelos-verify-review-evidence.mjs
   --receipt <回执.json> --subject <被审资产ID>`——任一 finding 引文归一化不命中
   即整张回执作废重出（证据无效≠正文缺陷）；连续两张作废更换审查模型并记
   docs/knowledge/redteam/g2-log.md。预筛候选清单随组装注入时，须逐条
   confirm/deny 并给理由（G3），表态随回执落 metadata_json.prescreen。
```

「循环边界」节（现 `:45-49`）追加一行：

```markdown
- 指纹豁免援引列为须呈报分歧类型（G6）：援引签名豁免对抗指纹 finding 时，
  须呈报用户确认豁免是否成立，未获确认不得豁免（等价 accepted_risk 通道）。
```

### 3.3 .agents/skills/novel-writing/SKILL.md 增补行（措辞草案）

第 1 步（组装命令）之后追加（R1/R2 后生效）：

```markdown
1a. 修复重试经修订资产组装：`node scripts/novelos-compose-prompt.mjs
    --asset prose-revision --project <id> --payload '{"mode":"fingerprint-clean"}'
    --review-feedback <上轮回执.json> --round <N>`——指纹清除模式未命中句逐字
    保留、按 findings 规则编号定点改，禁顺便润色与全文重写（R1 双模式纪律）。
1b. 落库 draft 前跑预筛自查：`node scripts/novelos-prose-fingerprint.mjs
    --chapter <chapter:xxx>`——候选仅自查参考，落库不因候选存在而阻断（判级归
    审查方）。
```

### 3.4 红方异构厂商模型编排示例（provider:model 格式）

三层防共谋（至少两两异厂商，最优三家互异）：

```
写作（蓝方）     zhipu:glm-5.3            （主会话同厂强创意模型）
审查（黑方）     anthropic:claude-sonnet-4-6   （AGENTS.md 既有纪律：异构厂商直审）
红方（对抗）     google:gemini-3-pro / deepseek:deepseek-v4
```

主控编排红方 sub agent 时的指定方式（三家 harness 的 per-agent provider/model 覆盖，AGENTS.md「多模型分工」节）：

```
红方任务书（G4 规格审）编排片段：
  subagent:
    model: "anthropic:claude-sonnet-4-6"        # 与写作模型异构厂商
    prompt: <规格全文> + <三问模板> + <P0/P1/P2 输出契约>
    留痕: 产出文档头部写 reviewer 身份 "model:anthropic:claude-sonnet-4-6"
盲测（G5）额外约束: model 与被测修订 agent 不同厂（self-preference 防线，
                    refs RESEARCH.md:19 单模型癖好不可当共性）
备选池: 至少备两家异构模型，配额/不可用时切换并留痕（§9 风险 2）
```

### 3.5 Receipt 留痕字段需求（接口给方向4，合并 schema 轮）

现状 `config/schemas/review-receipt-candidate.schema.json:6` `additionalProperties:false`，findings 项（`:45-86`）无预筛表态字段。G3 需要：

- **顶层可选对象 `prescreen`**：`{ run_id, candidates_total, confirmed, denied, dispositions: [{candidate_id, rule_id, verdict: "confirm"|"deny", reason}] }`。
- **过渡方案（零 schema 变更，R2 起立即可用）**：同构 JSON 写 `reviews.metadata_json.prescreen`（列已存在）——统计 SQL 用 `json_extract(metadata_json,'$.prescreen.denied')`。正式 schema 字段与方向4 的 R5 轮 schema 变更**合并为一次**（先备份 DB，红线），避免两次动 schema 两轮备份。
- G2 验证状态留痕：`metadata_json.evidence_verified: {tool, verified_at, result}`（回执通过验证的机器痕迹，终审可查）。

---

## 4. 度量体系

**存储形式：`docs/knowledge/metrics.md` 单张 Markdown 表**（追加行，不建 DB 表、不上脚本仪表盘——过度工程红线）。列结构：`日期 | 轮次/章 | 指标 | 值 | 阈值判定 | 处置动作 | 留痕链接`。

| # | 指标 | 采集点 | 采集方式 | 告警阈值 | 处置 |
|---|---|---|---|---|---|
| M1 | 金丝雀误报率（按规则条目） | 每次判级语义变更后 | `novelos-canary.mjs` 输出 → 主控抄录追加行（分母按 RESEARCH.md:43-55 三分母口径） | 新增条目单项 >0；总量 > 基线 | 条目降级/撤回；整批回滚（G1） |
| M2 | 引文验证失败数 | 每张 Receipt 落库前 | `novelos-verify-review-evidence.mjs` 退出码 + 报告 | >0 | Receipt 作废打回；同 reviewer 连 2 次 → 换模型（G2） |
| M3 | deny 率 | 每章审查回执后 | `node -e` 一句 SQL 统计 metadata_json.prescreen（R2 后） | =0 且候选 ≥5；连续 3 章趋零 | 抽 3 条人工判；连 3 章升级用户 U7（G3） |
| M4 | 收敛轮数 | 每次审查循环退出时 | 主控数 reviews 表同 subject_ref 回执数 | 单 subject >3 轮；同因复发 | 升级用户（G6，既有纪律） |
| M5 | 注入体积 | 每次组装产物生成时 | 组装日志字节数（compose 已有日志目录）对照硬编码上限 | 每场景条数/总字节超上限 | 组装 fail()（防上下文爆炸，R3 设计前置） |
| M6 | 红方 finding 修复率 | 每轮 G4/G5 后 | redteam 文档勾选状态人工汇总 | P0 未 100%；P1 <90% | 该轮不得记 DONE（账本纪律） |

口径纪律（来自 RESEARCH.md 教训，逐条落实）：

1. M1 的分母必须同类元素（问句占比的分母是问句总数不是千字）；跨口径比较无效。
2. M3 的分母是**预筛候选数**不是 finding 数（deny 的对象是机器候选）。
3. 所有指标先记录后判读，禁止先看数字再挑口径（六次测量失误的共同根因）。

---

## 5. R6 全链路演练剧本

### 5.1 取材与库隔离（建议方案）

- **底本**：现有唯一项目「诸天无限：从大运开始」（setup v2 完整、规划链空白），从 direction 起跑天然覆盖八级规划 → 写作 → 连续性全程。
- **隔离方案（推荐）**：演练开始时 `cp data/novelos-v2.db data/novelos-drill.db`，全程 `--db data/novelos-drill.db`（组装器原生支持，§1.2）+ 主控直写也连 drill 库；演练前后各算一次生产库文件 sha256，**两值一致 = 零污染机器证明**。演练库 gitignore（data/ 已含）。
- **裁决点 U2**：用户认可副本方案，或指定直接在生产项目跑（若选后者，演练章节只走到 draft+回执、不走 accepted，降低污染面）。
- **演练前冻结**：演练期间生产库不做 schema 变更（防副本漂移，§9 风险 1）。

### 5.2 阶段检查点与红方任务书

| 阶段 | 蓝方（生成/主控）动作 | 红方任务书（输入 → 产出） | 通过判据 |
|---|---|---|---|
| **S0 剧本审** | 冻结剧本 | G4：本剧本 + 六门规程 → P0/P1/P2 | P0=0 后开跑 |
| **S1 立项冒烟** | 确认 drill 库内项目/签名绑定完好（SELECT 复核，不重跑向导） | 拿六表签名链落库 SQL 事务边界 → 找回滚不全/缺 review 关联路径 | 红方 P0=0 |
| **S2 direction** | 组装 2-3 候选 → 逐候选审查 → 横向回执汇总呈报用户选定（演练 U-dirs） | 输入=候选全文+setup → 找体裁错配（男频力量轴串味）/表里失联/假多样性 | blocking 清零；用户选定留痕 |
| **S3 八级规划**（architecture→…→chapter_plan） | 逐级：蓝方组装起草 → 专审 → G2 验证 → 修复循环（G6）→ 锁定（先 supersede 后 lock） | 抽查 2 级（建议 world + chapter_plan）：输入=锁定资产+上游 → 找上游矛盾被静默调和、参照素材混入 locked（R4 防线） | 每级回执 approved 且 G2 通过 |
| **S4 写作×3 章** | 每章全门：组装 → 预筛自查 → draft 落库 → 异构审查（G2+G3）→ 修订循环（prose-revision 双模式）→ 接受（写 review_id） | 第 2 章后盲测（G5）：输入=3 段本章 AI 文 + 3 段金丝雀（随机匿名等长）→ 判源 + 指纹 findings 指认规则编号 | 3 章全部 accepted；盲测双向达标；M2=0；M3 在区间 |
| **S5 连续性收尾** | 提取候选 → continuity-review → 晋升六账本 + 人物状态迁移 → 注册表对账 | 输入=对账报告+账本抽样 → 找漏项/推测写成事实/无溯源条目 | 对账零漂移（有漂移处理完才收口） |
| **S6 终审收口** | 汇总指标 | G5 终审：输入=全链路产物投影（`novelos-render-projection.mjs --db drill` 若支持，否则 SELECT 导出）→ 系统性缺陷 P0/P1/P2 | 见 5.3 收敛判据 |

### 5.3 收敛判据（全部满足才收口）

1. 六指标（M1-M6）全部在 §4 阈值区间内，metrics.md 有完整记录链。
2. 全链路无未呈报的裁决绕过（每次升级/豁免都有账本或回执留痕）。
3. G5 终审 P0=0；P1 修复率 ≥90%；遗留项全部转 TODO/BLOCKED 入账本。
4. 生产库 sha256 演练前后一致（隔离证明）。
5. `tasks/README.md` R5 节各条 DONE 均有验证证据链接。

### 5.4 收口报告结构（docs/knowledge/redteam/r6-final.md）

1. 演练范围与库快照（drill 库来源 hash、起止时间、模型分工清单含 provider:model）
2. 阶段-门执行矩阵（S0-S6 × G1-G6 实际执行与结果）
3. 指标终值表（M1-M6 + 趋势）
4. 红方终审 findings 与修复状态（P0/P1/P2 逐条）
5. 遗留问题清单（转 TODO/BLOCKED，含责任人方向）
6. 生产库完整性证明（sha256 前后值）
7. 体系裁决建议（哪些门/阈值需在 R5 收口后常态化、哪些一次性退役）

### 5.5 演练数据处置

- drill 库：保留至收口报告获用户认可后删除（或存档改名 `novelos-drill-{date}.db`）；**绝不导回生产库**。
- 度量与 findings：git 内文档（docs/knowledge/），永久留档。
- 演练产出的规则修订（G3 deny 理由反哺、G5 发现的判级漏洞）：走 R1 通道进 catalog，不直接带演练文风。

---

## 6. 轮间依赖图与用户裁决点总清单

### 6.1 依赖图（→ 依赖；⇢ 可并行窗口）

```
R0 基线 ──→ R1 语言层 ──→ R2 机器校验 ──→ R3 写作知识 ──→ R4 规划知识 ──→ R5 签名轮 ──→ R6 演练
              │               │
              │               ├──⇢ R2§G2（引文验证脚本）可与 R1 并行开发：
              │               │    只依赖 Receipt 格式，不依赖 craft 卡语义
              │               └──⇢ R3§槽机制（方向2/3 composer 改动）可与 R2 并行：
              │                    代码面零冲突（新脚本 vs composer 内改），验收合并做
              └──⇢ R1§rubric 措辞与 R0§金丝雀选样可同批呈报（同一裁决包 U1+U3）
R4 ⇢ R5：文件面不冲突（planning 参照 vs onboarding schema），但共享 G4 红方预算
        且 R5 涉 DB 备份窗口——默认串行，仅在红方配额富余时并行
R6 依赖全部前轮（度量链与双模式修订链必须先通）
```

保守主线 = 串行（v1 `:73` 纪律：前轮验收不过不进下轮）；并行窗口仅作进度弹性，**验收边界不跨越**（并行开发、串行验收）。

### 6.2 用户裁决点总清单（预先声明，执行中不再逐次打断）

| # | 时机 | 内容 | 呈报形式 |
|---|---|---|---|
| U1 | R0 后 | 金丝雀基线数字 + 选样认可（误报率数字与 15-20 篇选样） | 批次包 A（U1+U2+U3） |
| U2 | R0 后 | 演练库隔离方案认可（drill 副本 vs 生产直跑） | 同上 |
| U3 | R1 前 | 双模式边界确认（指纹清除/质感注入判据措辞） | 同上 |
| U4 | R3 前 | knowledge 槽注入上限数值（每场景条数/总字节） | 批次包 B（U4+U5+U6） |
| U5 | R4 前 | 规划参照只进 candidate 的口径确认 | 同上 |
| U6 | R5 前 | Receipt prescreen 字段 + creator-signature schema 变更范围（与方向4 合并轮；含 DB 备份时点） | 同上 |
| U7 | R2 起现场 | G3 deny 率连续 3 章趋零（预筛或审查哪侧失效） | 现场触发 |
| U8 | 任意轮现场 | G6：3 轮未收敛 / 同因复发 / **指纹豁免援引分歧** | 现场触发（附各轮回执摘要） |
| U9 | R1/R5 现场 | accepted_risk 艺术风险豁免确认（既有纪律，不新增） | 现场触发 |
| U10 | R6 后 | 收口遗留问题定级 + drill 库删除/存档 | 收口报告随附 |

批次包 A/B 一次性呈报（各一次打断），U7-U9 仅触发时打断，U10 随收口报告——全程预期打断 ≤4 次 + 现场触发。

---

## 7. 执行步骤（本计划落地顺序与验证）

1. **本文档获用户批准**（与 D1-D4 方案对齐后并入 v1 计划作为 §2/§3 的细化附件）。
2. R0 启动时：建 `docs/knowledge/redteam/`、`docs/knowledge/metrics.md` 骨架（表头）。
3. 各轮按 §2.7 门-轮矩阵执行；每轮账本记 `tasks/README.md` R5 节，G4/G5 产物按 `r{N}-spec.md` / `r{N}-artifact.md` 命名。
4. **验证方式**：
   - 本文档 §3.1 JSON 草案：落地时 `node scripts/test-guardrails.mjs` 的 manifest≡matrix 校验自然覆盖（新增资产会进矩阵），slots ⊆ slot_vocabulary 已人工核对通过；
   - 六门规程与 v1 计划 `:58-68` 的门编号/机制一一对应（无发明新门）；
   - R6 收口按 §5.3 五判据逐条验证。
5. 修订记录：本文档改动过 G4 自审（§8）后版本号 +1 留档。

---

## 8. 对抗门自检（本设计文档自跑 G4 三问）

1. **体裁错配**：金丝雀（女频短篇论述文语料）结论用于男频长篇小说——已在 G1 编排要点显式打折（语言层可用/结构层记录折扣），盲测段等长配对防文体泄漏。残余风险：金丝雀误报率达标 ≠ 男频正文不误伤，靠 G3 deny 率 + R6 三章实跑兜底。
2. **上下文预算**：G5 盲测注入 craft 卡 + 6 段文本；G3 预筛候选注入正文审查上下文——候选清单可能很长，已在 M5 设上限并要求预筛输出只报事实不判级（压缩体积）；预筛候选超限时的截断策略（按规则严重度截断还是分批审查）**留给 R2 G4 规格审裁决**，本文不预定。
3. **双源漂移/纸面化**：① 盲测判级源 = craft 卡注入（与正式审查同源），无第二权威源；② G3 若只统计不处置即纸面化——已设「趋零→抽检→连续 3 章→升级用户」处置链；③ G2 复核通道可能被滥用为「人工放行」后门——已限定只修脚本不罚 reviewer，复核事件留痕 g2-log；④ prose-revision 注册后，手工拼修订注入成为违规路径，须在 R1 验收中检查主控行为切换。
4. **循环依赖检查**：红方指认规则编号 → 依赖方向1 的规则编号体系（编排缺口 ②）——已列为 R1 验收前置项：**编号体系未落地则 G5 盲测与 G3 回填均不可启动**（R1 验收清单需加此条）。

---

## 9. 风险与回滚

| 风险 | 预案 / 回滚 |
|---|---|
| 演练库副本与生产库 schema 漂移（演练中生产侧变更） | 演练期冻结 schema 变更；若必须变更 → 重 cp 重跑受影响阶段；drill 库可随时删除重建 |
| 红方异构模型配额不足/不可用 | 备选池 ≥2 家（§3.4）；切换留痕；单门延误不阻断其他门（G4/G5 可延后补审，账本标 BLOCKED） |
| G2 归一化误报（引文确在但不命中） | 人工复核通道修脚本；误报计数入 g2-log，连续误报 >3 → 脚本缺陷修复优先级提升 |
| 金丝雀集小（15-20 篇）统计不稳 | 阈值只对「新增条目单项 >0」硬性；总量比较仅看趋势不设硬阈值；男频语料后续补采（用户授权） |
| 红方与审查方模型撞厂（配额挤压下妥协） | 撞厂时红方产出降级为 P2 参考，不得出 P0 阻断（防共谋纪律不妥协） |
| 盲测段落来源泄漏（匿名失效） | §2.5 失败处置 ④：连续两轮识破 → 协议修订；段落来源记录在 redteam 文档供复核 |
| 六门全部回滚 | 门独立：recipes 摘两条新配方、SKILL 摘增补行、metrics/redteam 文档删除即净；**生产库零改动**（G1-G5 不动 schema，G6 只用既有表）——最坏情况回滚成本 = 文档删除 + git revert |

---

## 10. 接口声明（对其他方向）

### 10.1 对方向1（判级语义）

- **规则编号体系**：指纹 craft 卡需稳定规则 ID（建议 `FP-<节>.<序>` 形态，如 FP-1.3），供红方指认、预筛候选回填、修订定点三处消费。**R1 验收前置项**。
- 「不作为判级理由」反向边界表、双模式判据（指纹清除/质感注入的可操作边界）——本设计 G5 盲测的通过标准消费其定义。

### 10.2 对方向2（工具实现）

三个脚本的 CLI 契约（退出码语义：验证通过 0 / 失败非零 / 参数错误 2）：

```
novelos-canary.mjs                      --canary <dir> [--rules <craft卡版本>] → 明细 JSON + md 报告
novelos-prose-fingerprint.mjs           --chapter <chapter:xxx> | --file <path> → 候选清单 JSON
                                        （规则号/位置/原文片段/计数；对话行过滤；同类元素分母）
novelos-verify-review-evidence.mjs      --receipt <json> --subject <id> [--db <path>] → 逐 finding 命中表
```

- composer ASSET_DIRS 增 `prose-revision`、`prose-blindtest` 两键（§3.1 契约）。
- `novelos-render-projection.mjs` 若当前硬编码 DB 路径，R6 需 `--db` 直通（小改，随方向2 排期）。

### 10.3 对方向3（槽机制）与方向4（schema）

- 槽：knowledge 槽上限参数化（M5 采集需要可读上限值）；预筛候选注入通道——**建议不新开槽**，复用 prose-review 组装的数据区附带（候选清单是审查输入不是方法论），具体形态方向3 裁决，本设计只要求「候选随组装注入且标注仅供证伪」。
- schema：Receipt 顶层 `prescreen` 可选对象 + findings 无需改动（§3.5 字段定义）；与 R5 轮 creator-signature schema 变更**合并一次执行**（先备份 DB）。

---

## 11. 来源引用（联网补全）

1. **LLM-as-judge 偏差与缓解**：[A Survey on LLM-as-a-Judge](https://www.sciencedirect.com/science/article/pii/S2666675825004564)（Gu et al., 2026，位置/自增强偏差分类与缓解综述）；[Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge（CALM）](https://llm-judge-bias.github.io/) / [arXiv:2410.02736](https://arxiv.org/html/2410.02736v1)——12 类偏差量化，其中 **authority bias（伪造引用劫持评判）→ G2 机器验证**、**bandwagon（机器候选锚定）→ G3 逐条表态+deny 率**、**refinement-aware（知道修订历史改变评分）→ 盲测不注入轮次信息** 的直接依据；[Self-Preference Bias in LLM-as-a-Judge](https://arxiv.org/html/2410.21819v1)（自偏好 → 异构厂商+匿名化）；[A Systematic Study of Position Bias](https://aclanthology.org/2025.ijcnlp-long.18/)（swap consistency → 盲测随机排序+可复核记录）。
2. **Rubric/评分标准设计**：[Brown University Sheridan Center – Designing Grading Rubrics](https://sheridan.brown.edu/resources/course-design/feedback-student-learning/grading-criteria-rubrics/designing-grading)（criteria + 表现等级 + 评分策略三要素 → 检查清单结构）；[NC State – Rubric Best Practices](https://teaching-resources.delta.ncsu.edu/rubric_best-practices-examples-templates/)（analytic rubric 逐项反馈 → 逐门逐项过）；[ERICAe – Inter-Rater Reliability](https://ericae.net/inter-rater-reliability-in-performance-assessments/)（校准集 = 金丝雀基线的等价物——审查者先在金丝雀上「校准」误报率）。
3. **红队方法论**：[Anthropic – Challenges in Red Teaming AI Systems](https://www.anthropic.com/news/challenges-in-red-teaming-ai-systems)（临时无标准化探测的问题 → G4 固定三问模板；多样性价值 → 多路红方；红蓝循环 → 门-轮矩阵；method 匹配风险等级 → P0/P1/P2 分级处置）；[OpenAI – Approach to External Red Teaming](https://arxiv.org/html/2503.16431v1)（外部红队纳入风险评估流程 → 红方作为轮次验收门而非事后抽查）；[CSET – AI Red-Teaming Design: Threat Models and Tools](https://cset.georgetown.edu/article/ai-red-teaming-design-threat-models-and-tools/)（威胁模型先行 → 每门「防什么」列）。

方法论母本：`/Users/yiyi/Documents/refs/lieflat-less-ai-tone/RESEARCH.md`（分母纪律 `:43-55`、判定门槛 `:57-75`、六次测量失误 `:244-255`）——G1/M1 口径设计与「抽样 20 条再看频率」操作要求的直接来源。
