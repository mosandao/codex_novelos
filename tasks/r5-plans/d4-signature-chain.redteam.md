# R5-D4 红方审查

> 审查对象：`tasks/r5-plans/d4-signature-chain.plan.md`（G4 规格审，异构红方）
> 审查日期：2026-08-29。核查手段：仓库 file:line 实读、生产库 `data/novelos-v2.db` node:sqlite 只读、MySQL `nwriter` 只读、外部引用联网核查（4/8 处抽验）。
> 结论速览：**修改后放行**。P0 ×3（fp: 规则号接口断裂、`data/stylecorp/` 未被 gitignore 覆盖、与 D3 种子双通道未协调），P1 ×6，P2 ×8。

---

## 1. 事实核查表（18 处，≥8 处要求）

| # | 计划声明 | 核查结果 | 判定 |
|---|---|---|---|
| 1 | creator-signature.schema.json :19 `enum [1,2]`、:7 根对象 `additionalProperties:false`、:18-41 无风格侧字段 | 实读全吻合（/Users/yiyi/Documents/codex_novelos/config/schemas/creator-signature.schema.json:7,19,18-41） | ✅ |
| 2 | prompt.md :92-113 七字段分工表（expression_preferences :107 笔触层）、:15-17 输入无语料、:156-206 输出、:141-154 自检十二项 | 全吻合（catalog/skills/onboarding/creator-signature-fusion/prompt.md:15-17,92-113,141-154,156-206）；输入节另有 :17 条件语法模块，计划未列但不影响结论 | ✅ |
| 3 | manifest :88-94 `data_slots=[kernel_full,archetype_roster,project_setup,persona_fingerprints]` | 吻合（modules/manifest.json:88-93，实际止于 93 行，偏差一行无伤） | ✅ |
| 4 | sql-reference :76-144 六表链、:124-130 内核名册（ownership='author_kernel'+active+最高 revision）、:141-144 三自查 | 全吻合（.agents/skills/novel-project/sql-reference.md:76-144） | ✅ |
| 5 | 018 :18-35 ownership CHECK 三枚举 + 表重建模板（建新表→INSERT SELECT→DROP→RENAME，foreign_keys=OFF） | 吻合（db/migrations/018_author_kernel_and_characters.sql:18-35）；creator_profile_versions（011:10-28）无 ownership 列，031 确实只需重建 creator_profiles 一张表 | ✅ |
| 6 | compose-prompt :52-56 ASSET_DIRS、:691-712 槽位注册表、:727+ slotKernelFull、:1333 槽位表 | 全吻合；**但 slotKernelFull（scripts/novelos-compose-prompt.mjs:727-750）对 select 模式只做「版本存在性检查」直读全文，并无 ownership/status/hash 四查**——四查是主控纪律层（AGENTS.md），组装器层「同构」声明有出入（见 F15） | ⚠️ |
| 7 | render-projection :482-573 签名渲染防御式（字段缺失跳过不崩） | 吻合（scripts/novelos-render-projection.mjs:482-573，`sig[field] ?? []` 全防御式；style_dna 为 object 不进七字段循环，不会被误渲染） | ✅ |
| 8 | test-guardrails :75-83 守卫 manifest≡recipes | 吻合（scripts/test-guardrails.mjs:74-88，G2b/G2c） | ✅ |
| 9 | MySQL：122 条/103 作者；q 分布 10×9、9×52、8×58、7×3（q≥9 共 61） | 实测全中（COUNT=122、DISTINCT author_name=103；GROUP BY quality_score 逐条吻合） | ✅ |
| 10 | MySQL 字段均值 persona_prompt 127.3 / sentence_style 21.2 / signature_techniques 35.2 / narrative_drive 41.4 | 实测 AVG(CHAR_LENGTH) 四值精确吻合 | ✅ |
| 11 | 格式不统一：id=2 signature_techniques 为 JSON 数组、id=199 为「逗号串」；narrative_drive 部分带 score 信封 | id=2 确为 JSON 数组 + `{"score":10,"description":…}` 信封；**id=199 实为顿号串**（「序列晋升、魔药调配、扮演法…」），计划写「逗号串」措辞不准——归一化须同时拆逗号/顿号 | ⚠️ |
| 12 | q≥9 名单与女频「Priest/海宴」 | 名单主体吻合（金庸/古龙/猫腻/耳根/辰东/忘语/紫金陈×2/雷米/三天两觉/当年明月/吹牛者/黑色火种/会说话的肘子/蝴蝶蓝×2/萧鼎/海宴 q9 均验证在库）；**Priest q=9 存在但 author_name 实为「␣Priest」（前导空格，id=200）**——又一归一化证据 | ⚠️ |
| 13 | 重复项「id=2/84 同为刘慈欣×三体2；耳根×2、烽火×2、天蚕土豆×2、天下霸唱×2」 | 方向正确但严重轻描：实测同作者多行 **17 组**（爱潜水的乌贼×3、辰东×3 等）；「刘慈欣」族实际 **5 种名字变体 6 条**（刘慈欣/刘慈欣风格×2/刘慈欣（三体1风格）/刘慈欣（三体2风格）/刘慈欣·硬科幻风格）——按 author_name 字符串去重则 id=2 与 id=84 不会相认；爱潜水的乌贼《诡秘之主》同书 8/10 分两条、忘语《凡人修仙传》同书 q9 两条 | ⚠️ |
| 14 | writing-dna 六层表 :41-52、L1 :109-133、L2 :137-164、6.1 :283-308、6.2 :310-319、6.3 :321-325 | 全部行号内容吻合（/Users/yiyi/Documents/refs/writing-dna-skill/SKILL.md）；「:325 蒸馏产物>去AI味规则」原文确认。**计划未提的差异**：原版要求语料「至少 20 篇」，D4 A 级放宽为「≥5 篇」且无论证（见 F13） | ⚠️ |
| 15 | `.gitignore :6-14 已覆盖 data/*.db`（隐含 stylecorp 被覆盖） | `data/*.db` 等条目属实，**但 .gitignore 全文无 `data/stylecorp/`**（仅 data/exports/、data/**/*.db 等）——A/B 级语料是 .txt/.md 文本文件，不被任何现有规则覆盖（见 F2，P0） | ❌ |
| 16 | migration 编号 031；表重建引用「§5」 | 现有迁移止于 019（020-030 空号未解释）；**「§5」为悬空引用**——§5 是对抗门设计，全文无 031 SQL 草案（见 F4，P1）；另 `db/migrations/schema.sql:167-168` ownership 枚举需在 031 后重新导出，计划影响面清单漏列 | ❌ |
| 17 | 生产库现状（计划隐含内核库/签名链在用） | 实测 creator_profiles **30 行（26 system_archetype + 4 user），author_kernel 零行**——内核库与 v3 签名链在生产从未走过，冒烟步骤 8「select 内核」需先建测试内核（计划未列前置） | ⚠️ |
| 18 | 外部引用 8 处 | 抽验 4 处：Sapkota NAACL 2015 ✅（N15-1010，「词缀+标点类 n-gram 贡献几乎全部判别力」吻合）；自动化学报 2021（c200654，句法感知优于字符 n-gram）✅；**Kestemont 2014 标题引错**（实为 *From Black Magic to Theory?*，非 Serious Science）；**NAACL 2025 SRW 作者+标题双错**（2025.naacl-srw.41 实际为 Mukherjee/Ojha/McCrae/Dušek，*…Are There Any Reliable Metrics?*，非「Bommasani et al. …Predictors?」；URL 指对了论文） | ⚠️ |

补充：chapter-draft prompt.md:3 与 prose-quality-review prompt.md:7 的 style_refs 现状描述吻合；agent-recipes.json fusion 条目 slots 与 manifest 一致吻合；project-create-request.schema.json setup `additionalProperties:false`（:20）+ author_kernel select 段（:41-115）吻合。

---

## 2. Findings

### P0（放行阻断）

**F1｜fp: 规则号接口与 D2 全线断裂——豁免查表键不可用**
- 问题：measured_features.feature 的 pattern `^(fp:[a-z0-9-]+|style:[a-z0-9-]+)$`（计划 §3.1）与 D2 计划的规则号体系对不上。D2（tasks/r5-plans/d2-machine-gates.plan.md:66,80,417,429）已冻结契约：finding code = **`fpr:<RULE_ID>`**，规则号为 **`L01`/`L04` 式大写字母+两位数字**（:86 规则表），并明文「规则号不可变：发布后 ID 永不改义、不复用」。三重不兼容：前缀（fp: vs fpr:）、大小写字符类（`[a-z0-9-]+` 匹配不了 `L01`）、命名风格（D4 示例 `fp:dash-density` 语义名 vs D2 编码 `L04`）。
- 证据：D2 计划 :429「该 finding 的 `code` 写 `fpr:<规则号>`（如 `fpr:L01`）」；D4 §3.1 pattern 与 §3.4「查 `fp:N`」。
- 处置建议：三选一并在两份计划同步——① D4 pattern 改 `^(fpr:[A-Za-z0-9]+|style:[a-z0-9-]+)$` 直接对齐 D2 编码（推荐，D2 契约已冻结）；② 与 D2 协商在 R2 输出中给每条规则加 `fp_aliases` 语义名映射表（改 D2，成本高）；③ 弃用 fp: 前缀、measured_features 只收 style: 前缀（豁免通道降级）。§8 对 R2 的接口声明须重写。另注意：当前 scripts/ 无 fingerprint 脚本（R0-R2 未执行），该接口是「对着尚不存在的东西」设计，须在 D4 计划里显式声明对 D2 的依赖与联调点。

**F2｜`data/stylecorp/` 不被 .gitignore 覆盖——人类语料将明文进 git，违反版权红线**
- 问题：计划 §3.2a/§3.3/§7 多处声称「A/B 级语料落 `data/stylecorp/<project-id>/`（gitignore）」「全程 gitignore」，但 .gitignore 现有规则只覆盖 `data/*.db`、`data/**/*.db`、`data/exports/` 等，**文本文件（.md/.txt）零覆盖**；执行步骤 §4.2 的 git 改动清单（schema/prompt/模块/manifest/recipes/渲染器/向导段）也没有「更新 .gitignore」这一动作。
- 证据：`grep -rn stylecorp .gitignore scripts/` 零命中。
- 处置建议：§4 步骤 2 增补「.gitignore 加 `data/stylecorp/`」，并在 §1.5 红线节把该动作列为语料落地的前置条件；顺带建议 `data/canary/`（R0 金丝雀语料落点）同类核查转交 D2/D3。

**F3｜与 D3 的种子数据双通道未协调，且「不整表搬运」红线在 D3 侧已被击穿而 D4 无表态**
- 问题：D3 计划（tasks/r5-plans/d3-knowledge-pipeline.plan.md:87,193）已定「kb_author_personas（122）→ `config/knowledge/staging/author-personas.json`，q∈[8,10] → **119 条**（仅导出不接槽，预留 R5 轮 D4 消费）」——config/knowledge/ 是入 git 目录，119/122 = 97% 全量导出。D4 §3.5 却设计为 `mysql -B` 直连导入 12-16 条进 DB。两个通道并存：同一数据两个权威副本（git JSON vs DB），且 D4 的「试点 <15% 不整表搬运」口径在 D3 的 97% staging 面前形同虚设。
- 证据：D3 计划 :87「q∈[8,10] → 119」、:193「author-personas.json # 119（D4 预留，不接任何槽）」；D4 §3.5 转换资源形态整节只字未提 D3 staging。
- 处置建议：D4 计划显式二选一并写入 §3.5——① 从 D3 staging JSON 取数（单源，但要求 D3 把 staging 挪出 git 或降为 data/ 本地、或明确 119 条入 git 的版权裁决先过用户）；② 维持 MySQL 直连、并要求 D3 删除 personas 的 staging 导出项。无论哪种，属用户预声明裁决点（R5 总计划 §7「personas 试点范围」）应把「数据通道 + 119 条是否入 git」并入呈报。

### P1（修复后放行）

**F4｜migration 031 草案缺失 + 悬空引用 + schema.sql 漏联动**
- 问题：影响面表写「`db/migrations/031_*.sql`｜ownership 枚举 + 'style_seed'（表重建，**§5**）」，但 §5 是「对抗门设计」，**全文没有 031 的 SQL 草案**——红方无法审一个不存在的重建方案（列清单、索引重建、INSERT SELECT 顺序）。且 `db/migrations/schema.sql` 文件头明文「下次 schema 变更后仍须从生产库重新导出本文件」，其 :167-168 的 ownership CHECK 是 D3 等测试夹具的建库基线——031 后不重新导出，夹具库与生产结构漂移，后续所有测试基线错位。
- 证据：db/migrations/schema.sql:1-7,167-168；D4 全文无 schema.sql 字样。
- 处置建议：补 031 SQL 草案进计划（照 018 模板：CREATE new → INSERT SELECT 七列 → DROP → RENAME → 重建 idx_creator_profiles_ownership），修正「§5」引用；影响面表与 §4 步骤 5 增「从生产库重新导出 db/migrations/schema.sql」。现有风险面尚可控（实测生产库 creator_profiles 仅 30 行），但步骤不可省。

**F5｜author_name 归一化缺口：「同作者同书去重 / 每作者 ≤2」按字符串执行必失真**
- 问题：实测脏数据远超计划描述——「刘慈欣」5 种名字变体 6 条、「 Priest」带前导空格（id=200，若按名字清洗漏掉它，女频必取判据直接落空）、爱潜水的乌贼《诡秘之主》同书 8/10 分两条、忘语《凡人修仙传》同书 q9 两条；「103 位作者」含别名水分。归一化蒸馏节（§3.5）只处理了 JSON 数组/逗号串/score 信封三种**字段内格式**，没有 author_name 的**跨行别名归并**逻辑。
- 处置建议：导入脚本增 author_name 预处理（trim + 别名归并表——`刘慈欣（三体2风格）`/`刘慈欣风格`/`刘慈欣·硬科幻风格` → 刘慈欣），归并表进 conversion_notes；无法机械归并的呈报用户裁决。「每作者 ≤2」与「10 分全取」冲突时明确去重优先。

**F6｜style_refs_samples 建议体量与 D3 注入预算哲学正面冲突，无预算不足降级路径**
- 问题：D3 实测 chapter-draft 固定注入层 24711B、其 knowledge 槽预算论证锚定「4096B = 16% 增量，一屏可审」（d3 plan :48,357）；D4 建议样本 5×600-1000 字 + 摘要 800 字 ≈ **15-16KB（≈65% 增量）**，是 D3 预算哲学的 4 倍。方向3 裁定硬上限时必然砍，而选篇五判据只覆盖「人类语料不足」的情形，没有「预算砍到 3 篇时怎么选」的降级路径——判据与体量建议不可兼得时计划内部无仲裁。
- 处置建议：§3.3 增预算降级序（如 5→3 篇时保 ≥2 篇人类语料 + 场景类型优先级），并把「4500 字 + 800 字」改为区间（如 2400-4500 字）呈报方向3；预算数值并入 R5 总计划预声明裁决点（对齐 R3 注入上限的先例）。

**F7｜主控修正指令未执行：direction/strategy 的 persona 消费方接口缺失**
- 问题：00-chain-coverage.md 修正指令 2 明确「D4：签名链的 measured_features 豁免，direction/strategy 的 persona 消费条款是消费方——接口要对齐 persona 四用法的现有形态」。D4 §8 接口声明只覆盖方向3/方向1/R2/向导四方，**没有 direction/strategy**。而 slotPersonaFull（compose-prompt.mjs:714-725）直读签名 JSON 全文注入——v3 签名生效后 style_dna + measured_features 会**自动溢出**到一切消费 persona 的资产（direction「persona 四层消费」prompt.md:17、strategy「persona 四用法 + metadata.persona_usages」prompt.md:23-30），这些方法论没有任何消费/对账条款：strategy 的「目光→揭层节奏」与 style_dna.structure_preferences（节奏蓄放）存在双源重叠，冲突裁决顺序未定义。
- 处置建议：§8 增「对规划链（D5/R4 范畴）」接口声明：style_dna 在 direction/strategy 的消费边界（参照素材、无对账义务、与 persona 四用法的关系）、或显式声明「v3 签名经 persona_full 槽全文注入即已覆盖、无需新槽」并论证；至少把该溢出写进影响面清单。

**F8｜B 级授权强度不足：一句话声明、无凭证、无用户裁决点**
- 问题：§3.2a「B authorized_text：用户明确声明授权的他人文本（授权范围一句话存 corpus_basis.notes）」——授权完全自报，refs 里的「授权标识」是任意字符串；风险表对「B 级授权不实」的预案只有「corpus_basis.refs 强制授权标识」。对比之下，种子选择与 mismatch 都是用户裁决点，唯独授权声明不是——这正是「纸面化裁决门」的变体（声明即放行）。
- 处置建议：B 级语料启用列为用户裁决点（向导确认约束时一并问：授权来源、范围、是否本人持有版权），裁决记录入派生 resource 的 user_input_snapshot；至少要求 notes 含可核验凭证（链接/书证标识），主控抽查。

**F9｜style: 前缀特征无机器核对通道，豁免强度不分层**
- 问题：fp:（应为 fpr:）条目可对预筛 density 机械比对；style: 条目（sentence-length/lexical-richness 等）无任何测量工具落地（计划自认「本仓无运行时统计引擎」），「出区间即不豁免」对 style: 条目退化为 reviewer 纯语义判断——且档位值（「俭省」）与数值区间混在同一 value 字段，判定粒度不一致。滥用面在 style: 侧残留。
- 处置建议：§3.4 分层声明豁免强度（fpr: 机器可核=强豁免；style: 仅语义核对=弱豁免，reviewer 引用时须附人工抽样依据）；或 style: 条目降级为「风格参照」不参与豁免通道，只进写作侧。

### P2（择期修复）

**F10｜外部引用两处硬伤**：Kestemont 2014 标题实为 *From Black Magic to Theory?*；2025.naacl-srw.41 实际作者 Mukherjee/Ojha/McCrae/Dušek（arXiv 2502.04718），副题 *Are There Any Reliable Metrics?*——计划写「Bommasani et al. …Predictors?」作者与标题双错（URL 恰好指对论文）。引用错误本身是「纸面化引用」样本，与本仓对抗立场相悖，须改正。Sapkota 与自动化学报两处核验无误。
**F11｜source_ref 不在 measured_features.items.required**：验收判据 4「逐条有 source 可溯源（抽查 100%）」与 schema 不强制矛盾——source='user_corpus' 而 source_ref 缺失时溯源链断。建议 required 增 source_ref，或声明 library_persona/degraded_default 可免。
**F12｜tier=D 置空约束无机器强制**：只写在 description 与自检 13。JSON Schema 可表达（`if corpus_basis.tier=D then measured_features maxItems 0`），建议补进 allOf——这正是 D4 自己批判过的「约束只写描述不进结构」。
**F13｜A 级语料「≥5 篇」对 writing-dna 原版「至少 20 篇」的降标无论证**：区间可信度随样本量衰减。建议：5 篇语料强制更宽区间或 corpus_basis.notes 声明小样本折扣；或分级（≥5 可用、≥15 可信区间收窄）。
**F14｜渲染增补「应做」与验收「必须」不一致**：影响面表标「应做（否则人类视图风格侧不可见）」，验收判据 2 却硬要求「投影渲染出风格 DNA 段」。统一为必须——单渲染器纪律下投影是唯一人类视图，风格侧不渲染即黑箱。
**F15｜「同构」表述与实现偏差**：slotKernelFull 组装器层仅查版本存在性，四查纪律在主控层；style_seed 槽按 §8.1 四查实现是「更严」而非「同构」。不破坏既有内核 select（向导段不扩 ✓），但文档应如实改述，避免后人按同构假设省略四查。
**F16｜lexicon_summary 与词表唯一源的边界未闭合**：种子卡有「零词表职能」红线复述，A/B 级自备语料蒸馏出的 lexicon_summary（口头禅/禁用词倾向）没有对 genre_pack/world_lexicon 的对账义务与冲突裁决顺序。建议在 style-corpus-present 模块补一句：lexicon 条目与题材词表冲突时词表优先、冲突呈报。
**F17｜杂项**：migration 031 从 019 跳号未解释（020-030 预留说明一句话即可）；冒烟步骤 8「select 内核」前置缺失（生产库 author_kernel 零行，须先建测试内核）；id=199 是顿号串非逗号串；§1.4 同作者多行例子列举不全（实际 17 组）。

---

## 3. 跨方向冲突预警

| 冲突 | 对端 | 性质 | 处置建议 |
|---|---|---|---|
| 规则号契约 `fpr:L01` vs `fp:[a-z0-9-]+` | D1（豁免消费措辞）/D2（预筛脚本） | **P0 接口断裂**（F1）——D1 的 finding code 也用 `fpr:` 前缀（d2 plan :429 转述 D1 侧），D4 是三方接口中唯一的异类 | 整合轮指定单一权威命名空间；D4 pattern 改对齐 `fpr:` + 大写字符类 |
| 种子数据通道：D3 staging 119 条入 git vs D4 MySQL 直连 12-16 条 | D3 | **P0 双权威副本 + 版权口径冲突**（F3） | 整合轮裁决数据通道与 staging 是否入 git；并入用户裁决点 |
| 注入预算：D3 固定层 24711B、knowledge 槽 4KB/16% 增量哲学 vs D4 样本槽建议 ~16KB/65% 增量 | D3（style_refs_samples 槽机制与硬上限归属方） | P1 哲学冲突（F6） | D4 给区间化建议 + 降级序；预算数值走用户裁决；方向3 硬上限落地时 G4 复审 |
| persona_full 槽全文注入使 style_dna 溢出到 direction/strategy/review | D5（R6 演练规划段）/R4 侧规划 prompt | P1 消费方无条款（F7，主控修正指令 2） | D4 §8 补规划链接口；D5 的 R6 检查点加「style_dna 未被当对账源」红方任务（同 00 文件发现二的参照纪律） |
| D5 schema 合并轮次 | D5 | P2 时序：D4 的 creator-signature v3、project-create v3 增段与 D2/D3 的零 schema 承诺并存，若 D5 另有 schema 合并，须以 D4 的 v3 草案为基避免二次返工；migration 编号段（020-030 预留）需统一分配表 | 整合轮出编号分配与合并顺序图 |
| 金丝雀豁免回归 | D2（canary 脚本归属） | P2：D4 §3.4 的「豁免特征在人类分布内抽样验证」依赖 `novelos-canary.mjs`（尚不存在），验证脚本职责应写进 D2 接口而非 D4 单方面假设 | D4 §8 对 R2 接口补 canary 抽样验证需求 |

---

## 4. 结论

**修改后放行。** 计划整体质量高：file:line 盘点基本诚实（18 处核查 12 处全中、4 处方向正确但程度失实、2 处实质不符）、MySQL 实数四组全对、writing-dna L1-L6 吸收裁剪理由成立（L3 选题归规划层、L6 无排版落点、6.3 总豁免改逐特征豁免的改造是正确的对抗设计）、v1/v2 不迁移在组装器/渲染器两侧验证为防御式消费不炸、mismatch 裁决红线沿用到位。但存在三条放行阻断：

**必改项（P0，100%）**：
1. fp: 规则号接口对齐 D2 的 `fpr:<L编号>` 契约（F1）——改 pattern、改 §3.4 查表键、重写 §8 对 R2 接口。
2. `.gitignore` 增 `data/stylecorp/` 进执行步骤（F2）。
3. 种子数据通道与 D3 staging 的二选一裁决 + 119 条入 git 的版权口径呈报用户（F3）。

**P1 ≥90%**：F4（补 031 草案 + schema.sql 再导出）、F5（author_name 归并）、F6（预算区间化与降级序）、F7（规划链接口）、F8（B 级授权裁决点）、F9（豁免强度分层）。P2 择期，F10 引用勘误建议随本轮顺手修。
