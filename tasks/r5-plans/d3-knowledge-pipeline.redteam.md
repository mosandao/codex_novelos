# R5-D3 红方审查

> 审查对象：`tasks/r5-plans/d3-knowledge-pipeline.plan.md`（2026-08-29 规格）
> 审查方式：file:line 逐处比对 · MySQL nwriter 只读复算（2026-08-29）· guardrails/compose 测试实跑 · 外部引用联网核查
> 结论速览：**修改后放行**——3 项 P0（表数与漏表、quality 过滤口径自相矛盾、原始拆解数据入 git 撞 v1 版权红线），6 项 P1（三个跨方向接口错位、modules 替代方案未评估、跨批去重缺失、蒸馏体积估算失实、craft 卡例文标注无机器校验）。

---

## 1. 事实核查表

| # | 计划声称（位置） | 核查结果 | 判定 |
|---|---|---|---|
| 1 | composer 1610 行；`ASSET_DIRS` L52-78；`validateManifestStruct` L301-347（L306 knownRoot、L328 槽名 pattern）；`loadManifest`/`selectModules` L484-492/L495-503；`compose` L556-592（L562-565 数据区）；`buildContextDirection` L644-653；`slotUpstream` L824-847；`slotGenrePack`/`slotWorldLexicon` L900-910/L912-943；`SLOT_REGISTRY` L1326-1344（17 槽）；`resolveSlots` L1347-1388（L1354/L1358/L1362/L1366 前缀分支、L1383 craft fail）；`writeCompositionLog` L1418-1454；`main` L1533-1586（§1.1） | 逐处比对源码全部吻合；`knowledge:techniques`、`knowledge:reference-direction` 实测匹配 pattern `^[a-z_]+(-[a-z_]+)*(:[a-z_]+)?$`，「零 schema 改动」成立 | ✅ 属实 |
| 2 | guardrails「实测当前 241 passed / 0 failed」；G1 L29-47、DYNAMIC_PREFIXES L59、G2a L64-72、G2b L74-88 deepEqual(sorted)；test-compose 243 行（§1.4） | 实跑 `node scripts/test-guardrails.mjs` = **241 passed / 0 failed**；`node scripts/test-compose-prompt.mjs` = **19 passed**；行号与结构断言全部吻合 | ✅ 属实 |
| 3 | agent-recipes：slot_vocabulary L4-27（22 项）；direction L72-85（4 槽）、world_contract L209-223（5 槽）、chapter_plan L331-348（8 槽）、chapter_draft L370-389（10 槽）；craft_refs 不在 assets slots（§1.2） | 逐行核对全部吻合；craft_refs 确实不在任何 entry.slots（只在 slot_vocabulary 词表与 manifest 根字段），「manifest-only 增补不触发 G2b」成立 | ✅ 属实 |
| 4 | craft 九卡字节（8090/5697/4098/2586/1730/1007/477/411/388）；chapter-draft 固定层 5096+19615=24711B；expansions 11 件；chapter-draft manifest 4 模块/10 槽/4 craft_refs（§1.3/§1.5） | `wc -c` 实测全部一致（四卡 = hardrules+fingerprint+accessibility+worldview-lexicon = 19615）；manifest 实读吻合 | ✅ 属实 |
| 5 | MySQL：techniques 3017 行；2884 行 0-10 + 133 行 11-100；`q BETWEEN 8 AND 10` = 1310；对话 65（58+…）/节奏 151（125+23+…）/开篇 46；id 7/68 同书同技双版本（§1.6/§3.3） | 逐项复算全部一致 | ✅ 属实 |
| 6 | 「q 归一后 ∈[8,10] → 1310 行」（§2 映射表、§3.2 meta `exported_rows: 1310`） | **不成立**：133 行 0-100 刻度实测全部落在 75-93（MIN=75），`normScore>=8` 过滤器实际导出 **1443 行**（1310+133）。1310 只是「原始 BETWEEN 8 AND 10」口径。同因：首批三类按归一口径应为 **对话 79/节奏 170/开篇 48 = 297 条**，非 262（§3.3 SQL 用的是原始口径） | ❌ 口径矛盾 |
| 7 | 「27 张 kb_* 全处置」（§2 标题）；「91 个 category」；「语言风格 均值 30.75」；例文「均值 69 字/最大 334 字」；description 均值 111 字（§1.6） | information_schema 实数 **23 张** kb_ 表，计划映射列 **22 张**；**`kb_corpus_tags`（28 行，thematic 标签字典+keyword_patterns）完全未处置**。`COUNT(DISTINCT category)`=**90**；语言风格高刻度行均值 **81.30**（10 行，75-87），30.75 无从得出；example_text 非空均值 **98 字**、最大 **619 字**；description 均值 **105 字** | ❌ 数字失实+漏表 |
| 8 | 各表 q∈[8,10]/总数：book_summaries 66/79、dialogue 252/269、cool_points 519/546、plot 164/267、archetypes 445/506、world_settings 276/474、reusable_templates 362（§1.6/§2） | q 过滤值全部吻合 ✅；但**总数 6 处失实**：dialogue 实 303（称 269）、cool_points 实 580（称 546）、plot 实 286（称 267）、archetypes 实 579（称 506）、world_settings 实 500（称 474）、reusable 实 397（称 362）——库仍在增长，快照已过时（emotional_arcs/scene_blueprints/economic/social/faction/personas/genres/corpus/worldbuilding 系列均吻合） | ⚠️ 部分失实 |
| 9 | 生产库 1 项目、0 planning_assets，槽测试需夹具库，composer 支持 `--db`（§1.6） | node:sqlite 实查 projects=1、planning_assets=0；`--db` flag 在 parseCliArgs L1506 确认 | ✅ 属实 |
| 10 | 来源 1（Anthropic）：「sub agent 探索数万 token、返回 1,000-2,000 token 蒸馏摘要」「最小高信号 token 集」 | 原文确认："returns only a condensed, distilled summary of its work (often 1,000-2,000 tokens)"、"find the smallest set of high-signal tokens"。批大小 20 条/批的量级带引用成立 | ✅ 属实 |
| 11 | 来源 2（OpenAI 指南）：Identity→Instructions→Examples→Context、每请求数据靠后、XML 界定、仅注入预选资源（§3.5/§9） | 原文确认 context "usually best positioned near the end of your prompt"、XML delineation、RAG 预选资源均在 | ✅ 属实（注：knowledge 节实际落 U 型中部数据区而非尾部，属宽松对应，见 P2-14） |
| 12 | 来源 5（arXiv 2505.21700）：「事实型问答以 64-128 token 小块最优」→ 512B/条依据 | 摘要确认"smaller chunks (64-128 tokens) are optimal for datasets with concise, fact-based answers" | ✅ 引用属实（适用性折扣见 P2-14） |
| 13 | planning 主干实测 16KB（§3.4 预算表） | story-direction 16182B、world-contract 16728B | ✅ 属实 |
| 14 | `.gitignore` 需追加 `data/canary/`（§3.1） | 现无该条目（有 `data/compositions/`）；config/knowledge、data/canary 目录均不存在（未执行，与状态 TODO 一致） | ✅ 属实 |

**小结**：仓库侧 file:line 引用（约 30 处）与测试基线全部属实，D3 的现状盘点功课扎实；失血点集中在 **MySQL 数字层**（口径矛盾 1 处、快照过时 6 处、编造样例数字 1 处）与**表清单完整性**（23≠27、漏 corpus_tags）。

---

## 2. Findings

### P0（必改，阻断执行）

**P0-1 「27 张 kb_* 全处置」不成立，`kb_corpus_tags` 漏处置**
- 问题：§2 标题声称 27 张全处置，实测库里只有 **23 张** kb_ 表，映射表实际列 22 张。**`kb_corpus_tags`（28 行：tag_name/tag_type/description/keyword_patterns）零处置**——它不在「导出」也不在「不导」清单。该表正是 v1 R0「金丝雀按标签覆盖频道轴」选样的**标签字典本体**（thematic 标签 + 关键词模式），D1/D2 的选样与分组逻辑直接依赖它。另与 v1 总计划「kb_* 31 表」相差 8 张且无任何消解说明（31 同样失实，实测 23）。
- 证据：§2 表格 vs `information_schema.tables WHERE table_name LIKE 'kb\_%'` 实测 23 行；`SELECT * FROM kb_corpus_tags LIMIT 5` 见系统/攻略、弹幕/评论等标签。
- 处置建议：①表清单改为实测 23 张并逐一消解（corpus_tags 建议导出 `data/canary/tags.json` 与 articles 一并入 D1 原料，或至少记「不导+理由」）；②在 §1.6 补一句「v1 计划 31 表为误计」的勘误，防后续轮次再引用失真数字。

**P0-2 quality 过滤口径自相矛盾：1310 与过滤器产出 1443 不一致，首批 262 应为 297**
- 问题：§1.6/§3.3 的 SQL 用**原始值** `BETWEEN 8 AND 10`（1310/262），而 §2 映射表与 §3.1 `TABLE_SPECS.filter = normScore(quality_score) >= 8`、§3.2 meta `exported_rows: 1310` 用**归一口径**。实测 133 行 0-100 刻度全部在 75-93，归一后全部 ≥8——过滤器实际导出 **1443 行**。执行时 `--verify` 行数对账（§4 步 1「techniques 3017→1310」）必然 FAIL；蒸馏首批若以导出文件 techniques.json 为源（应当如此，蒸馏不应再连 MySQL），对话/节奏/开篇实得 **79/170/48 = 297 条**（0-100 刻度行里对话技巧 14、节奏控制 15、喜剧节奏 4、开篇技法 2 会混入），批次应为 15 批而非 14 批。
- 证据：`CASE WHEN quality_score>10 THEN ROUND(quality_score/10) ELSE quality_score END >= 8` 实测 1443；分类归一计数实测 79/170/48。
- 处置建议：二选一并全文统一——(a) 导入层过滤改为原始 `BETWEEN 8 AND 10`（normScore 仅用于排序辅助，高刻度行整体排除：它们是另一套打分体系，87 分≈8.7 与 8 分并不同质）；(b) 维持 normScore>=8，把 1310/262/14 批全部改为 1443/297/15 批。红方倾向 (a)：0-100 刻度是「另一批打分」（§1.6 自己的发现），混入蒸馏源反而增加同质化噪声。

**P0-3 原始拆解数据入 git 违反 v1 版权红线，且计划未讨论该冲突**
- 问题：`config/knowledge/techniques.json`（1310 条）等导出文件含 **book_source 真实书名 + example_text 原文例句（均值 98 字、最大 619 字）+ description 拆书文本**，计划令其「入 git」。v1 §1.3 红线：「真实网书拆解与人类语料**只落本地 data/（gitignore），不进公开目录**……**蒸馏后**的方法论表述可进 catalog」；v1 R0 虽写「config/knowledge/*.json（蒸馏方法论层，入 git）」，但其授权对象是蒸馏产物，D3 把导入层做成了**未蒸馏原始数据入 git**，超出 v1 R0 授权并直接撞 §1.3。计划通篇未识别此冲突——属「裁决点漏报」（红队 F2 纸面化教训同型：约束存在但流程没接上）。
- 证据：v1 `tasks/R5-knowledge-absorption.md` §1.3 版权边界 vs 本计划 §3.1「产物：config/knowledge/*.json（入 git）」+ §3.2 条目 schema 含 example.text 原文与 book_source。
- 处置建议：呈报用户裁决，二选一：(a) 原始导出层落 `data/knowledge/`（gitignore，同 canary 待遇），`config/knowledge/` 只留 distilled.json/category-map/scene-words 等纯方法论产物；(b) 用户明确豁免（私有仓、拆解表述版权风险自担）并记入裁决记录。默认应走 (a)——互斥校验与幂等设计不依赖 git 承载数据。

### P1（应改）

**P1-4 与 D2 的 canary 文件形态错位：jsonl vs md 分组目录**
- 问题：D3 交付 `data/canary/articles.jsonl`+`excerpts.jsonl`；D2 计划（§3.2）的 `novelos-canary.mjs` 装载器是「`--dir`（默认 data/canary）**递归收集 \*.md**；分组 = 顶级子目录匿名化为 g1/g2」。jsonl 会被装载器静默忽略 → 金丝雀集为空 → D2 设计的「空目录友好报错 exit 2」。两侧都以为对方铺好了路。
- 证据：D3 §3.1/§8.1 vs `tasks/r5-plans/d2-machine-gates.plan.md` L53、L301-334。
- 处置建议：D3 增补一步「S 级选样导出为 md 分组目录」的产物契约（如 `data/canary/g1/*.md` + `_meta/` 放元数据），或与 D2 约定装载器读 jsonl——写进 §8.1 接口声明，不能只写「就位」。

**P1-5 与 D4 的 style 槽接口三重错位**
- 问题：①槽名——D3 §8.2 建议 `knowledge:style-samples`（挂 KNOWLEDGE_DOMAINS 家族）；D4 §3.3 建议独立槽名 `style_refs_samples`。②数据位置——D3 的 G3b 契约要求域文件在 `config/knowledge/` 且条目必备溯源三件套（id/orig_id/**book_source**）；D4 要求语料「不进任何公开产物、`data/stylecorp/` 全程 gitignore」。③保护圈——D4 的无前缀槽名恰好**绕开** G3a（域注册校验）与 G3d（review 侧隔离）的全部保护。「框架可复用」的声明没有验证过任一前提。
- 证据：D3 §8.2 vs `tasks/r5-plans/d4-signature-chain.plan.md` L277、L394（「机制、检索与硬上限归方向3」）。
- 处置建议：G4 整合轮定契约：若走 `knowledge:` 前缀家族，须为 stylecorp 域显式豁免 G3b 的路径/book_source 断言（用户语料无书源、不入 git）；若走独立槽名，G3a/G3d 需扩展覆盖。两方向计划文本同步改一处。

**P1-6 对 D5 的盲测对生产方式失实：`--no-log` 关不掉槽**
- 问题：D3 §8.3 声称「同场景有/无槽两版用 `--no-log` 双跑同章纲即得盲测对」。`--no-log` 只关组装日志（main L1578），**不改变槽注入**——槽由 manifest data_slots 声明，composer 无单槽禁用 flag。D5 的 R3 盲测门（「有/无知识槽」）依赖此机制，实际拿不到对照组。
- 证据：`novelos-compose-prompt.mjs` L1502（--no-log 仅置布尔）+ L1353（槽遍历 manifest 声明）。
- 处置建议：补一个最小机制——如 `--without-slot <name>` 可重复 flag（或夹具库配双 manifest 切换），并在 §8.3 修正声明；该 flag 本身也要进 test-compose 用例。

**P1-7 「双通道取舍」论证不完整：modules 条件模块这条更简通道未评估**
- 问题：主控指令（00-chain-coverage §3.1）要求论证 Read 注入 vs composer 槽。D3 §3.6 用四理由（无预算/不留痕/不可复现/绕互斥）论证不走 Read 通道——这部分成立。但 **reference-direction / reference-world 两域是纯静态检索**（genre_profile 键 → top-3 预组合，无运行时状态），完全可走**既有 manifest modules + when 路由**（`selectModules` L495 已支持 field/not_null 路由；`writeCompositionLog` L1443 已记 modules id——留痕现成；G2b 只对 data_slots，modules 增补不触全等校验）——零 composer 代码改动，回归风险远低于新槽家族。D3 只在「槽 vs Read」二选一里论证，漏了第三方案，「并用分工」的结论下得太快。真正需要运行时检索（依赖 locked chapter_plan 场景词计数 + distilled 互斥）的只有 techniques/scenes 两域。
- 证据：composer L495-503（selectModules when 路由）、L1418-1454（modules 已入组装日志）vs D3 §3.4/§3.6。
- 处置建议：G4 裁决注入通道矩阵：静态参照（direction/world）评估改走 modules 预组合（导入时按 genre 预计算模块文件），动态检索（techniques/scenes）保留新槽。若维持四槽方案，须在计划中写明否决 modules 方案的理由（如：参照集会随导出更新而变，modules 预组合会产生大量生成文件入 git——这本身就是一个真实权衡，但现在是空白）。

**P1-8 蒸馏跨批去重机制缺失，dup_key 生成逻辑无实现落点**
- 问题：id 7/68 型近重复合并依赖「同 dup_key 合并为一条、covers 登记全部 id」，但 ①`TABLE_SPECS` 骨架没有 dup_key 计算（书名规范化+技法名归一的逻辑不存在，schema 草案里却是现成字段）；②14 批并行 3-4 波，**并行批之间互不可见**——近重复若被切进不同批，各自独立产出条目，covers 漏登、卡内重复，「互斥登记」从源头失真。distilled.json 是蒸馏全部完成后才落盘，无法做批间协调。
- 证据：§3.3 批大小/输出信封设计 vs TABLE_SPECS L117-131 无 dup_key。
- 处置建议：导入层显式实现 dup_key（book_source + 技法名归一），导出时按 category+dup_key 排序聚类，保证同 key 条目同批；蒸馏 prompt 补「本批内 dup_key 聚簇必须合并」的硬约束。

**P1-9 蒸馏产出体积估算与条目数不匹配；「16% 增量」漏算三卡自身**
- 问题：①30-45 条公理化条目分三卡各 ≤2560B ≈ 单条 70 汉字——trigger+formula（数组）+anti_pattern+例文四件装不下，实际条数上限约 8-12 条/卡，或必然超预算回炉，计划未给「合并到多少条算失败」的下限；②预算依据表以「4KB 为固定层 16% 增量」论证克制，但 craft_refs 是**全量注入**，三卡 +7.5KB 使固定层 24711→~32.2KB（+30%），该增量只字未提；③例文实测最大 **619 字**（计划称 334），均值 98（计划称 69），「一行标注可行」与「512B/条预算」的相容性被高估。
- 证据：§3.3 输出目标表、§3.4 预算表 vs MySQL CHAR_LENGTH 实测。
- 处置建议：预算论证补「槽 4KB + 卡 7.5KB 合计对固定层的总增量」一列；蒸馏验收增「单卡条目数下限（如 ≥6 条）」防过度抽象化（空洞化是另一种质量塌方）；例文策略改为「至多半句」并在骨架里明确截断规则。

**P1-10 craft 卡例文的「非成稿标准」标注是纯声明层，无机器校验**
- 问题：§3.2 声称「guardrails 校验注入文本含该标（G3b）」，但 G3b 实际定义是校验 **config/knowledge 域文件**的 schema（三件套 + example.non_canonical），不扫 craft 卡 prompt.md，也不跑组装。蒸馏产出的三卡经 craft_refs 逐字注入 Writer——卡内例文是否带标，完全取决于蒸馏 agent 自觉（prompt 要点 2）。恰好「Writer 真的看得到标注吗」这条链路在卡路径上断掉。
- 证据：§3.2 标注机制 vs §3.4 G3b 定义（「域文件存在、条目必备……」）；composer L1377-1386 craft 注入无任何内容检查。
- 处置建议：guardrails 增一条轻校验：`catalog/skills/craft/scene-dialogue|chapter-opening|scene-pacing/prompt.md` 内每个例文标记（如「（例」起至句终）必须同段含「非成稿标准」字样（正则可查，与 G1 同级成本）；或蒸馏信封校验器（主控侧）加同规则。

### P2（建议）

**P2-11 快照数字漂移与编造样例**：6 处表总数已过时（库仍在增长，见核查表 #8）；「91 category」实为 90；「语言风格均值 30.75」实为 81.30（该数字疑似臆造——同类目实测分布 75-87，30.75 无从得出）；example/description 均值偏差。`--verify` 用运行时 COUNT 对账的设计是对的，但计划文本应标注「快照时点 2026-08-29，总数以运行时对账为准」，且 30.75 这类支撑「双刻度」论证的具体数字应更正（双刻度本身真实存在）。

**P2-12 G 编号撞名**：D3 新增 guardrails「G3a-e」与六道门体系（v1 §2 / D5 细化）的「G3 deny 率监控」同名异义；既有 guardrails G1（词表单源）与六道门 G1（金丝雀回归）也已撞名。建议 D3 改用 `KG1-KG5`（knowledge guard）前缀，redteam 报告与 metrics 账本引用时强制消歧，防 R5 账本里「G3 FAIL」语义歧义。

**P2-13 KNOWLEDGE_DOMAINS 初始化纪律未写明**：§3.4 骨架在模块顶层定义域注册表并绑定检索器。若任一检索器/域文件读取发生在模块加载期（而非 resolveKnowledge 调用链内），`config/knowledge/` 不存在时**所有现存资产的组装都会崩**——直接击穿「无 knowledge: 槽声明则零行为变化」承诺。骨架应显式注明惰性读取（文件 open 全部下沉到 resolveKnowledge 内）。

**P2-14 依据链的适用性与来源等级**：①2505.21700 的 64-128 token 结论来自**嵌入检索**管线且明确依赖嵌入模型选型（Snowflake/Stella 结论有别），D3 检索器零嵌入，类比适用有折扣，建议标注；②knowledged.to（k=3）是博客级来源，无实验支撑，只可作「对照锚点」不宜作依据（计划已如此措辞，建议再降格为脚注）；③OpenAI「每请求数据靠后」与 knowledge 节实际落点（U 型中部数据区、尾部是静态条件模块）是宽松对应，宜如实标注「与仓库 U 型设计一致的自主取舍」。4096/2560/3072 数值本身有依据链且有四步降级路径，方向可接受。

**P2-15 渲染白名单未进代码骨架；G3c 只防键名**：§3.6 的字段白名单（禁渲染名词列表型字段）只存在于文字样例，KNOWLEDGE_DOMAINS 域注册表骨架没有 fields/render 配置位；G3c 键名黑名单挡不住「键名不同、值仍是词表型名词列表」的数据形态。建议域对象加 `renderFields: [...]` 声明并由 ⑦a 断言。

**P2-16 biz_\* 41 张未声明排除边界**：nwriter 另有 41 张 biz_\* 表（novels/chapters/worldviews/power_systems 等，应用运行时数据）。不处置是合理的，但计划应补一句显式排除声明（「biz_\* 为 nwriter 应用运行时业务数据，非知识源」），防后续轮次把 `biz_worldviews`/`biz_power_systems` 这类与 kb 语义相近的表误当第二知识源开挖。

**P2-17 杂项**：①`resolveKnowledge(domain, db, …)` 签名与调用处 `resolveKnowledge(db, slot.slice(…), …)` 参数顺序不一致（笔误）；②distilled.json 互斥只覆盖 techniques 域，planning 参照（cool-points 519 条等）未来若蒸馏进 expansions/craft 无对应互斥设计，宜在 §3.2 预留 domain 维度；③§4 步 4 验证引「resolveSlots L1383 运行时保证 craft 存在性」属实（L1383 确为 fail 点）✅。

---

## 3. 跨方向冲突预警

| 对端 | 冲突点 | 状态 |
|---|---|---|
| **D1（金丝雀）** | ①`tasks/r5-plans/` 无 d1 计划文件——D3 §8.1 对 D1 的交付承诺与「S 级选样标准由 D1 制定」**无对端确认**，接口悬空；②canary 原料缺 `kb_corpus_tags`（P0-1），按标签覆盖选样将无字典可用；③quality_tier/tags 字段在 articles 表已确认存在 ✅ | **未对齐**（D1 缺位） |
| **D2（canary 脚本）** | 文件形态错位：D3 产 jsonl，D2 装载器收 `*.md` 顶级子目录（P1-4）；另 D2 已把「R0 canary 脚本」划入自己范围，D3 §5 说「本计划无金丝雀回归义务」——分工一致 ✅ | **错位，须改** |
| **D4（签名链）** | style 槽名（knowledge:style-samples vs style_refs_samples）、数据位置（config/knowledge 入 git vs data/stylecorp gitignore）、溯源契约（book_source 必备 vs 不进公开产物）三重错位；无前缀槽名绕开 G3 保护圈（P1-5）。author-personas.json 预留 staging/ 不接槽的隔离设计与 D4「R5 轮试点」时序一致 ✅ | **错位，须改** |
| **D5（门规程）** | ①盲测「有/无槽两版」生产机制缺失（P1-6）；②guardrails-G3 与六门-G3 撞名（P2-12）；③度量采集点（组装产物 diff + index.jsonl data_slots 字段）与 writeCompositionLog L1444 实况吻合 ✅；④R4 参照混入演练剧本与 D5 L142 互认 ✅ | **部分错位** |
| **v1 总计划** | kb 表数（31 vs 实测 23）、「config/knowledge=蒸馏方法论层入 git」与 D3「原始导出入 git」的授权范围冲突（P0-3） | **须勘误+裁决** |

---

## 4. 结论

**修改后放行。** D3 的现状盘点（composer/recipes/manifest/test 的 file:line 与基线数字）质量很高，方案主体（导入层确定性过滤 + 蒸馏层否决权、槽前缀零 schema 改动、G3 专项护栏、降级脚注）方向正确、可实施。但存在三处阻断级问题与六处应改问题，P0 清零前不得进步骤 1。

**必改项清单（P0）**：
1. 表清单重整：27→23 实数，补 `kb_corpus_tags` 处置（P0-1）；
2. 统一 quality 过滤口径（1310/262/14 批 vs 1443/297/15 批二选一，全文+验收数字+SQL 同步改）（P0-2）；
3. `config/knowledge` 入 git 与 v1 版权红线的冲突呈报用户裁决，默认改落 `data/knowledge/` gitignore（P0-3）。

**应改项（P1，建议随 P0 一并改后再进 G4 复核）**：canary 文件形态契约（对 D2）、style 槽三方契约（对 D4）、盲测对照机制（对 D5）、modules 替代方案论证（回应主控指令的完整性）、dup_key 分批去重、蒸馏体积/条目数估算更正、craft 卡例文标注机器校验。

**放行后须保持的优点**（红方确认，勿在修改中丢失）：`--verify` 运行时对账而非写死数字、四步降级脚注的透明化、G3c/G3d 的机器红线、review 侧结构性隔离、sub agent 零持久化纪律、五 commit 分步回滚设计。
