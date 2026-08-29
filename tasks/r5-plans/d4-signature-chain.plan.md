# D4 · 立项签名链增强设计文档（R5 立项签名轮 · 方向4）

> 状态：`TODO`（设计稿，待 G4 红方规格审 + 用户裁决后执行）
> 上位计划：`tasks/R5-knowledge-absorption.md` §3 R5 轮（149-160 行）与 §1.2/§1.3 吸收表
> 本文件职责边界：onboarding 两条链的方法论改造、creator-signature schema 变更草案、kb_author_personas 试点、style_refs 样本槽的**内容需求**（槽机制归方向3）、逐特征豁免的**资产化数据形态**（审查侧消费措辞归方向1）。

---

## 1. 现状盘点（file:line 实读）

### 1.1 方法论现状：签名链只有「怎么想」，没有「怎么写」

- `catalog/skills/onboarding/creator-signature-fusion/prompt.md`
  - :92-113「第二步：落规」七字段分工表中，**表达层仅 `expression_preferences` 一个字段**（笔触层 2-4 条，:107）——「他喜欢什么笔触」的主观声明，没有任何机器可测的语言特征（词频/句长/标点习惯）与结构偏好（开头钩子/场景切换/章尾收束）的系统蒸馏。
  - :15-17 输入节：`kernel_full` / 原型清单 / `project_setup` / `existing_persona_fingerprints` 四类输入——**没有语料输入**，风格侧无米下锅。
  - :156-206 输出 JSON：`signature` = persona + 七字段，无风格侧产物。
  - :141-154 自检十二项全部针对「人」与「规」，无风格侧条款。
- `modules/manifest.json` :88-94：`data_slots = [kernel_full, archetype_roster, project_setup, persona_fingerprints]`——组装器槽位层面同样无语料/种子槽。
- 对照 `writing-dna-skill`（`/Users/yiyi/Documents/refs/writing-dna-skill/SKILL.md`）：
  - :41-52 六层表：L1 表层语言（词频/句长/标点/修辞，脚本统计）· L2 文章结构 · L3 选题 · L4 素材 · L5 认知框架 · L6 视觉；
  - :109-133 L1 分析项：高频名词/动词/副词、平均句长、短句（≤15字）占比、长句（≥50字）占比、破折号 vs 括号比、引号场景；
  - :137-164 L2 结构骨架（hook 类型 → 转折 → 正文结构 → 结尾处理）；
  - :283-308「写作前重读纪律」：先读全部蒸馏产物、再读 5 篇与本次**体裁题材最接近**的 raw 原文（选篇四判据：meta 匹配 → 超取最近 → 不足同体裁补齐 → 缺 meta 按文件名判断），目的是校准「分层产物描述不出来的语感」；
  - :310-319 优先级：用户指令 > L2 结构 > L1/L6 > L3-L5；
  - :321-325 冲突裁决：「蒸馏产物与去 AI 味规则冲突时，以蒸馏产物为准」——**原样引入即总豁免后门**，须改造为逐特征豁免（R5 总计划 :37 已定）。

**差距结论**：现有签名 v2 ≈ writing-dna 的 L3-L5 中的「认知/视角」半边（且由内核 psychology + 七字段以更强的「人格化」方式覆盖）；L1/L2 完全缺失；L6 不适用（网文平台无自定义排版）。

### 1.2 schema 与落库链现状

- `config/schemas/creator-signature.schema.json`：:19 `schema_version enum [1,2]`；:18-41 `properties` 无任何风格侧字段，且根对象 `additionalProperties:false`（:7）——**新增字段必须显式进 properties，否则 v3 签名被自查拒收**。
- `config/schemas/project-create-request.schema.json`：:41-110 `setup.author_kernel {mode: select|create}`，select 需 `kernel_version_id + subject_hash`；setup `additionalProperties:false`（:17-34）——**无签名种子 select 段**。
- `.agents/skills/novel-project/sql-reference.md` :76-144「作者签名链」：六表单事务（resources×2 → creator_profiles → creator_profile_versions → projects → project_creator_bindings）；:141-144 落库前三自查（schema 校验 / 无逐字复制 / parent 一致）。**签名 JSON 存 resources BLOB——schema 扩展不触发表结构**。
- :124-130 内核名册：`ownership='author_kernel'` + `status='active'` + 每 profile 最高 revision——种子库 select 反查应与该纪律同构。
- `db/migrations/012_system_archetypes.sql`:1 与 `db/migrations/018_author_kernel_and_characters.sql`:18-35：`creator_profiles.ownership` 带 `CHECK (ownership IN ('system_archetype','user','author_kernel'))`——**新增种子库 ownership 枚举需要表重建 migration**（018 即模板：建新表 → INSERT SELECT → DROP → RENAME，`foreign_keys=OFF` 执行）。

### 1.3 组装与渲染联动点

- `scripts/novelos-compose-prompt.mjs`：:52-56 `ASSET_DIRS` 注册表（fusion = creator-signature-fusion 目录）；:691-712 槽位注册表 + `slotProjectSetup`（payload.setup 原样注入）；:727+ `slotKernelFull`；:1333 槽位表。fusion payload 先过 project-create-request schema 校验（:693-694 注释）——**扩 setup 段必须三联动：schema + manifest.data_slots + `config/agent-recipes.json`**，`scripts/test-guardrails.mjs` :75-83 守卫 manifest≡recipes 一致性，漏一即挂。
- `scripts/novelos-render-projection.mjs` :482-573：签名投影渲染（persona narrative/五维/特质/主题/矛盾/声音/盲区 :494-538 + 七字段 :539-542 + 派生溯源 :543-561）。渲染是防御式（字段缺失跳过不崩），但**新增 style_dna 不加渲染段 = 人类视图中风格侧不可见**，需联动增补。
- `catalog/skills/writing/chapter-draft-generation/prompt.md`:3 与 `catalog/skills/review/prose-quality-review/prompt.md`:7：`style_refs` 现状 = Creator Profile revision/hash 一行 + Direction ref——「重读纪律」的落点即此处扩容。

### 1.4 kb_author_personas 实测（MySQL 只读，2026-08-29）

- 结构：15 列全 text（id/author_name/book_source/narrative_drive/emotional_style/structure_preference/world_building_style/character_style/sentence_style/dialogue_style/signature_techniques/strengths/weaknesses/persona_prompt/quality_score）。
- 规模：122 条 / 103 位作者。`quality_score` 分布：**10 分×9、9 分×52、8 分×58、7 分×3**（q≥9 共 61 条）。
- 字段长度（均值）：`persona_prompt` 127.3 字、`sentence_style` 21.2 字、`signature_techniques` 35.2 字、`narrative_drive` 41.4 字——**高度浓缩卡片，非长文**。
- 格式不统一：部分行 `signature_techniques` 是 JSON 数组（id=2 刘慈欣：`["双线/多线叙事","时间跳跃叙事",…]`），部分是逗号串（id=199 爱潜水的乌贼）；`narrative_drive` 部分带 `{"score":10,"description":…}` 信封。转换时须归一化。
- 内容质量（id=2 抽读）：`sentence_style`「冷峻理性科学报告式……几乎不用感叹号和排比句」、`weaknesses`「不擅长亲密关系描写/女性角色缺乏独立人格」——**风格侧描述与 cannot_write 种子质量可用**；但无生平、无 trait、无声音样本、无测量数值，**不能直接当签名，只能当种子**。
- 题材/频道覆盖（q≥9 名单）：科幻（刘慈欣×3 形态）、仙侠（辰东/耳根/萧鼎/忘语）、历史武侠（猫腻/烽火戏诸侯/金庸/月关）、武侠经典（古龙/黄易）、都市诡异（爱潜水的乌贼/黑色火种/会说话的肘子）、游戏电竞（蝴蝶蓝×2）、悬疑（紫金陈×2/雷米/三天两觉）、**女频向偏弱但有（Priest/海宴）**、历史科普（当年明月）、群像参考（吹牛者·临高启明）。
- 重复项：id=2 与 id=84 同为刘慈欣×《三体2》（84 是「风格分身」重制卡）；同作者多行（耳根×2、烽火×2、天蚕土豆×2、天下霸唱×2）。

### 1.5 红线继承（来自 AGENTS.md 与 R5 总计划）

- schema 变更前备份 `data/novelos-v2.db`；resources.content 经 BLOB 写入并同步 `content_hash`（node:crypto）；ID 格式 `类型:uuid`；多表单事务。
- 蒸馏不整表搬运；真实网书拆解只落本地 `data/`（`.gitignore` :6-14 已覆盖 `data/*.db`）。
- mismatch 必须用户裁决后才落库（红队 F2 纸面化教训）；「指纹豁免援引」为 G6 须呈报分歧类型。

---

## 2. 吸收映射（writing-dna L1-L6 + kb personas → 本仓签名链）

| writing-dna 层 | 本仓落点 | 判定与理由 |
|---|---|---|
| L1 表层语言（词频/句长/标点/修辞） | **新增 `style_dna.lexicon_summary / syntax_patterns / punctuation_habits` + `measured_features`** | 现有签名零覆盖；且是逐特征豁免的唯一可信依据 |
| L2 文章结构（hook/正文/收束） | **新增 `style_dna.structure_preferences`（网文化）** | 网文场景化为：章首钩子形态/场景切换手法/章尾收束与钩子留法/节奏蓄放——不是公众号文章结构 |
| L3 选题逻辑 | **不收** | 立项选题由 direction/strategy/题材 pack 管（规划层资产），签名管「怎么写」不管「写什么题」；收了会造成签名与规划层职责双源 |
| L4 素材策略 | **不重复收** | 跨书层已由内核 `knowledge_ecology`（domain/depth/verification）覆盖；本书题材层由 `recurring_attention` + genre_profile 承接 |
| L5 认知框架 | **不重复收** | 七字段（价值/因果/底线）+ 内核 psychology 八维已以更强的人格化形式覆盖——现有已覆盖部分不重复（任务边界约定） |
| L6 视觉风格 | **裁剪** | 网文平台正文是纯文本流，无自定义排版/配图位；6.3 中排版类清理（加粗密度/标题层级）无落点 |
| 6.1 写作前重读纪律（全部产物 + 5 篇 raw） | **映射为 style_refs 样本槽内容需求**（§3.3；槽机制归方向3） | 「蒸馏产物是压缩结论，语感只在原文里」——章级组装注入 style_dna 摘要 + 5 篇样本 |
| 6.2 优先级（用户指令 > L2 > L1 > L3-L5） | **改造收**：章纲/执行卡（用户侧约束）> 结构偏好 > 语言特征 > 七字段价值层 | 与现有「narrative_principles 主原则仲裁」不冲突：价值层管立场，结构语言层管形态，冲突类型不同 |
| 6.3 冲突裁决「蒸馏产物 > 去 AI 味规则」 | **改造收：逐特征豁免**（`measured_features` 资产化） | 原样引入 = 总豁免后门；豁免必须指认特征条目 + 声明区间 + 有 source，禁整体援引（R1 侧措辞归方向1，数据形态归本文 §3.4） |
| kb_author_personas 122 条 | **select 模式风格种子库试点 12-16 条**（§3.5） | 与内核库同构的第二个 select 源；卡片是「表达层种子」不是 parent |

**外部 stylometry 特征 → measured_features 候选清单**（引用见 §9）：

| 外部特征族 | 来源 | measured_features 候选 | 本仓操作化 |
|---|---|---|---|
| 功能词/最高频词频率分布（MFW，Delta 系 100-5000 词） | Kestemont 2014；Evert 2019 | `style:hf-lexicon-profile` | 方向性摘要（高频虚词倾向/意象域），不做全向量——本仓无运行时统计引擎，声明给 R2 预筛脚本核对 |
| 句长分布（均值/短句占比/长句占比） | StyloMetrix 2025；writing-dna L1 | `style:sentence-length`、`style:short-sentence-ratio`、`style:long-sentence-ratio` | 每千字归一区间（如「短句占比 35-50%」） |
| 标点类字符 n-gram（判别力几乎全部来源之一） | Sapkota et al. 2015 | `fp:<规则号>` 逐条对接（破折号/省略号/感叹号/顿号罗列密度） | 与 R2 `novelos-prose-fingerprint.mjs` 的规则编号空间对齐——豁免查表键 |
| 词汇丰富度（type-token ratio） | StyloMetrix 2025 | `style:lexical-richness` | 定性档（俭省/中等/繁富）+ 千字新词率锚点 |
| 句法 n-gram（中文语境句法特征优于字符 n-gram） | 自动化学报综述 2021 | `style:syntax-patterns` | 句首模式/从句习惯/对话引导句式（定性，落在 syntax_patterns 文本里） |
| 风格强度/内容守恒/自然度三轴评估 | NAACL 2025 SRW；Fast Forward Labs 2022 | **评估轴而非特征**：风格强度→特征命中率；内容守恒→Canon 守恒（R1 已有）；自然度→指纹误报（G1） | 三轴恰好由 D1（语言对抗）+D4（签名）分工拼成「像这个作者」的判定：像=特征命中且不违 Canon 且不露 AI 痕迹 |

---

## 3. 改动清单（schema 草案 + prompt 增补草案）

### 3.1 creator-signature.schema.json 变更草案（v3 增量，向后兼容）

**版本策略**：`schema_version enum [1,2] → [1,2,3]`。v3 = v2 + 风格侧（`style_dna` 必填、`measured_features` 可选数组）；**存量 v1/v2 签名不迁移、不复验、继续合法**（旧版本签名字段可空 = 新字段对 v1/v2 签名直接缺省，读侧全部防御式）。签名存 resources BLOB，**此 schema 变更零 SQL migration**；唯一需要 migration 的是种子库 ownership 枚举（§3.5）。

新增 properties 片段（插到 `properties` 内，`negative_constraints` 之后）：

```json
"style_dna": {
  "type": "object",
  "additionalProperties": false,
  "required": ["corpus_basis", "lexicon_summary", "syntax_patterns", "punctuation_habits", "structure_preferences"],
  "properties": {
    "corpus_basis": {
      "type": "object",
      "additionalProperties": false,
      "required": ["tier"],
      "properties": {
        "tier": {"enum": ["A_user_corpus", "B_authorized", "C_library_seed", "D_degraded"],
                 "description": "A=用户自有语料；B=授权文本；C=库内种子卡（无语料）；D=全降级（内核+题材语法推导，无测量依据，豁免不可用）"},
        "refs": {"type": "array", "maxItems": 20, "items": {"type": "string", "maxLength": 200},
                 "description": "依据锚点：resource:stylecorpus:xxx / kb persona id / 授权声明标识；tier=D 时为空数组"},
        "notes": {"type": "string", "maxLength": 500, "description": "tier 组合与降级理由（A+C 之类）；tier=D 必填降级声明"}
      }
    },
    "lexicon_summary":   {"$ref": "#/$defs/non_empty_text_list", "description": "高频意象域/词汇色彩/口头禅与禁用词倾向（2-4 条，带体温）"},
    "syntax_patterns":   {"$ref": "#/$defs/non_empty_text_list", "description": "句长节奏/短句长句配比习惯/句首与从句模式（2-4 条）"},
    "punctuation_habits": {"$ref": "#/$defs/non_empty_text_list", "description": "破折号/省略号/感叹号/顿号罗列等标点习惯（2-4 条，每条可被预筛规则核对）"},
    "structure_preferences": {"$ref": "#/$defs/non_empty_text_list", "description": "网文化结构偏好：章首钩子形态/场景切换/章尾收束/节奏蓄放（2-4 条）"}
  }
},
"measured_features": {
  "type": "array",
  "maxItems": 24,
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["feature", "metric", "value", "source"],
    "properties": {
      "feature": {"type": "string", "pattern": "^(fp:[a-z0-9-]+|style:[a-z0-9-]+)$",
                  "description": "fp:=R2 预筛指纹规则号（豁免查表键）；style:=风格侧测量特征（§2 候选清单）"},
      "metric": {"type": "string", "minLength": 2, "maxLength": 120, "description": "度量定义（如：每千字破折号数）"},
      "value":  {"type": "string", "minLength": 1, "maxLength": 200, "description": "声明区间或档位（如 3-6）——豁免按区间比对，出区间即不豁免"},
      "source": {"enum": ["user_corpus", "authorized_text", "library_persona", "degraded_default"]},
      "source_ref": {"type": "string", "minLength": 1, "maxLength": 200, "description": "溯源：resource:stylecorpus:xxx / personaseed id / 授权标识"}
    }
  },
  "description": "逐特征豁免依据：tier=D 时必须为空数组或缺省——无测量依据即无豁免"
}
```

`allOf` 追加（v3 才强制风格侧；v1/v2 不动）：

```json
{"if": {"properties": {"schema_version": {"const": 3}}},
 "then": {"required": ["persona", "style_dna"]}}
```

**受影响面清单**：

| 受影响点 | 联动内容 | 必要性 |
|---|---|---|
| `resources` 表 | 无表结构变化（签名 JSON 内容扩展） | — |
| `config/schemas/creator-signature.schema.json` | 本节草案 | 必须 |
| `scripts/novelos-render-projection.mjs` :482-573 | persona 段后增「风格 DNA」渲染段（corpus_basis tier + 四列表 + measured_features 表格：feature/metric/value/source） | 应做（否则人类视图风格侧不可见；防御式渲染不崩，但 --verify 投影对不上设计意图） |
| v3 向导 select 反查 | `project-create-request.schema.json` 新增可选 `setup.style_seed` 段（§3.5）；**内核 select 段不扩** | 必须（种子接入） |
| `novelos-compose-prompt.mjs` | fusion 域新增 `style_seed` 槽 resolver（payload 反查种子卡全文）；manifest.data_slots 增 `style_seed`；`agent-recipes.json` fusion slots 同步——**三联动，test-guardrails :75-83 守卫** | 必须 |
| 审查侧（D1/rubric） | 消费 `measured_features` 的措辞与判定流（本文只定义数据形态，§3.4） | 方向1 |
| 章级组装（writing） | style_refs 样本槽内容需求（§3.3），槽机制实现归方向3 | 方向3 |
| `db/migrations/031_*.sql` | ownership 枚举 + `'style_seed'`（表重建，§5） | 仅试点落库需要 |

### 3.2 creator-signature-fusion 方法论改造（prompt.md 增补草案）

**改造原则**：不动「第一步立人 / 第二步落规」主干（它们是 L3-L5 的人格化实现，已被验证）；新增「第三步量体」与配套输入、自检、条件模块。以下为增补段落草案（实施时按此合并进 `prompt.md`）：

**（a）输入节增补**（插在 `existing_persona_fingerprints` 条目后）：

```markdown
- `style_corpus`（风格语料包，按来源分级，优先级固定 A>B>C>D，可组合）：
  - A `user_corpus`：用户自有历史作品 ≥5 篇（每篇 ≥1000 字），存 `data/stylecorp/<project-id>/`
    （gitignore）。最佳依据——这是本人真实写法，豁免与蒸馏的首选源。
  - B `authorized_text`：用户明确声明授权的他人文本（授权范围一句话存 corpus_basis.notes）。
    只蒸馏写法，原文观点/事实/专有名词禁入签名与正文。
  - C `library_seed`：库内风格种子卡（style_seed 载荷）——无语料时的降级参照，只有浓缩描述
    无原文，measured_features 只能引用卡内声明值并标 source='library_persona'。
  - D 全降级：无语料无种子。style_dna 从内核 psychology 注意偏向 + 生平五维 + 题材 pack 语法
    习惯**保守推导**；measured_features 必须为空；corpus_basis.tier='D_degraded' 且 notes 写明
    「本签名无测量依据，指纹豁免不可用」。禁止假装有语料。
- `style_seed`（可选）：向导 select 的库内种子卡全文（v3 载荷 setup.style_seed 反查注入）。
  语义：**表达层风格参照，不是 parent**——parent 永远是内核版本。种子卡用于校准 style_dna
  与 expression_preferences 的方向；其 narrative_drive/structure_preference/sentence_style/
  dialogue_style 是参照素材；weaknesses 是 cannot_write 的候选种子（须重长成 persona 语气，
  禁逐字搬运）。种子与内核 emotional_stance/aesthetic_commitments 或本书表里基调根本相斥时
  （如冷峻卡 × 甜宠表层），在 parent_rationale 报 mismatch——主控呈报用户裁决后才落库，
  禁止静默硬融、禁止仅警告放行。
```

**（b）新增「第三步：量体（风格侧蒸馏——语言与结构）」**（插在「第二步：落规」之后、「用户输入处理」之前）：

```markdown
## 第三步：量体（风格侧蒸馏——语言与结构）

七字段回答「他怎么想」，style_dna 回答「他写出来什么样」——偏好声明（expression_preferences）
不等于写作事实；事实必须从语料或种子量出来。本步产物过 schema v3 的 style_dna +
measured_features。

### 3.1 语料分级与降级（先判 tier 再动手）
按 style_corpus 输入判定 corpus_basis.tier（A>B>C>D，组合时主源在前）。
tier=D 时：三、四小节照做但全部标注「推导缺省」，measured_features 留空——降级不是省略，
是显式声明「无依据即无豁免」。

### 3.2 L1 语言 DNA（词/句/标点）
- lexicon_summary：高频意象域与词汇色彩（他从哪个词库里取词）、口头禅、倾向禁用的词类。
  从 A/B 语料中归纳；C 种子取 sentence_style 的词汇面。
- syntax_patterns：句长节奏（短句连击后接长句？平均句长偏长/偏短？）、句首模式、从句习惯、
  对话引导句式。
- punctuation_habits：破折号/省略号/感叹号/顿号罗列的使用习惯——**每条写成可被指纹规则
  核对的形态**（「感叹号每千字 ≤1，只在情绪顶点」优于「少用感叹号」）。

### 3.3 L2 结构偏好（网文化，非文章结构）
structure_preferences 写**章节级**模式：章首钩子形态（场景直入/悬念前置/对话开场）、
场景切换手法（硬切/过渡物/视角移交）、章尾收束与钩子留法、节奏蓄放（蓄几章放一章？）。
种子卡的 structure_preference 是直接素材，但须按本书规模/平台重校。

### 3.4 measured_features 产出纪律（逐特征豁免的依据）
- 每条 feature 对齐规则号空间：`fp:<R2 预筛规则号>`（豁免查表键）或 `style:<特征名>`（§2 候选清单）。
- 数值一律**区间或档位**（「3-6」/「俭省」），一律每千字归一——点值不可信，区间可核对。
- source 如实分级；tier=D 时本数组必须为空。
- 只量写法不量内容：任何具体情节/观点/专有名词禁入（复刻的是写法，不是内容）。

### 3.5 与七字段的边界
expression_preferences 管「他喜欢什么笔触」（主观偏好），style_dna 管「他实际写出什么样」
（可测事实）；同一条表述两边都成立 = 违反单字段纪律，按其性质归位。
```

**（c）输出 JSON 增补**（`signature` 对象内，`negative_constraints` 之后）：

```json
"style_dna": {
  "corpus_basis": {"tier": "A_user_corpus", "refs": ["resource:stylecorpus:xxx"], "notes": "…"},
  "lexicon_summary": ["…"],
  "syntax_patterns": ["…"],
  "punctuation_habits": ["…"],
  "structure_preferences": ["…"]
},
"measured_features": [
  {"feature": "fp:dash-density", "metric": "每千字破折号数", "value": "3-6",
   "source": "user_corpus", "source_ref": "resource:stylecorpus:xxx"}
]
```

**（d）自检增补三项**（原十二项 → 十五项）：

```markdown
13. **风格侧可执行**：style_dna 四列表条条具体（抽检 punctuation_habits 每条都能被指纹
    规则或人工核对）；tier 与 refs 一致；tier=D 时 measured_features 为空且 notes 有降级声明。
14. **豁免有据**：measured_features 每条有 metric/value/source/source_ref，value 是区间或
    档位；无「整体风格豁免」式条目。
15. **语料卫生**：签名中零具体情节/观点/专有名词搬运；B 级语料的授权声明已入 notes。
```

**（e）新增条件模块**（`modules/` 新建两文件，manifest 注册）：

- `style-corpus-present.md`（`when: {field: setup.style_corpus, not_null: true}`）：tier 组合判定细则、A/B 级语料的重读纪律（蒸馏前通读全部语料再动手——L1 统计不能替代通读）、种子与语料冲突时语料优先。
- `style-corpus-absent.md`（`when: {field: setup.style_corpus, is_null: true}`）：降级推导路径（内核 attention_bias → 注意落点 → 句法倾向的推导链要写进 corpus_basis.notes）、measured_features 置空纪律、下游告知义务（该签名禁用指纹豁免）。

同时 `modules/manifest.json` `data_slots` 增 `style_seed`（与 `style_corpus` 经 project_setup 载荷透传不同，style_seed 需库内反查全文，故单列槽位）；`config/agent-recipes.json` fusion 资产 slots 同步（否则 guardrails 挂）。

### 3.3 「写作前重读 + 5 篇原文」纪律 → 章级组装映射（style_refs 样本槽内容需求，接口给方向3）

**判据（writing-dna 6.1 四条 → 网文化五条）**：

1. 场景类型匹配优先：按本章执行卡的主场景类型（对话密集/打斗/过渡/情绪高点的哪一类）在语料中选同类片段；
2. **人类语料下限：5 篇中 ≥3 篇必须来自人类风格语料（A/B 级），≤2 篇可来自本项目已接受章节**——后者保连续性，前者防「AI 模仿自己输出」的自我强化漂移（对抗设计：纯自我模仿是风格漂移的最短路径）；
3. 时间最近优先：匹配项超过 5 篇取时间最近（近期更代表当前风格；项目内章节即「最近」）；
4. 不足补齐：同类不足时用同体裁不同场景类型的人类语料补齐到 5 篇；
5. 全降级（tier=D/语料为空）：不注入样本，仅 style_dna 摘要 + voice_samples——**禁止拿种子卡描述冒充原文样本**。

**注入内容与体量需求**（上限数值由方向3 裁定，以下为内容需求建议）：

| 组成 | 内容 | 建议体量 |
|---|---|---|
| style_dna 摘要 | 四列表全文 + corpus_basis 一行 | ≤800 字 |
| 5 篇样本 | 每篇取与本章场景类型最接近的**连续片段**（非摘句拼盘——呼吸感在连续段落里） | 每篇 600-1000 字，合计 ≤4500 字 |
| 选篇说明 | 一行：每篇为何入选（场景类型 + 时间） | ≤100 字 |
| 豁免清单 | measured_features 原文（供写作侧自查与审查侧核对） | 原文长度 |

槽名建议 `style_refs_samples`，注册于 chapter-draft-generation 的 manifest（机制、检索与硬上限归方向3）。注入语料仅限 A/B 级用户语料，**不进任何公开产物**；`data/stylecorp/` 全程 gitignore。

### 3.4 逐特征豁免资产化接口（数据形态定义；消费措辞归方向1）

- **数据形态**：§3.1 的 `measured_features` 数组即资产本体，随签名 v3 存 resources BLOB，经 `subject_hash` 与绑定链追溯（审查回执 `subject_hash` 对齐正文，豁免核对对齐签名版本）。
- **查表键**：`feature` 的 `fp:` 前缀 = R2 预筛脚本 `novelos-prose-fingerprint.mjs` 的规则编号；`style:` 前缀 = 风格侧特征（§2 候选清单），供 rubric 语义比对。
- **D1 rubric 消费方式（判定流，措辞细节归方向1）**：预筛 finding（规则号 N）到达 → reviewer 在绑定签名的 measured_features 中查 `fp:N` → 命中且 finding 的实测值落在声明区间内 → 豁免成立（finding 降 note/dismiss，**须引用条目原文**，R1 已定）；未命中或出区间 → 豁免不成立。tier=D 签名查表必空 → 豁免通道整体关闭。
- **与金丝雀校准（G1）的关系**：豁免条目是「规则 × 签名」的豁免，不是规则的删除——**指纹规则本身在金丝雀集上的误报率不受签名影响**；新增豁免特征（如某签名声明高频破折号）须抽样验证该特征在金丝雀人类语料中非罕见（在人类分布内），否则该豁免条目是把 AI 特征合法化，撤回并记录。豁免清单变更列入 G1 回归触发事件。
- **与 G6 的关系**：豁免援引分歧（reviewer 认为出区间、writer 认为在区间）= 须呈报的分歧类型（R5 总计划 :67 已列），3 轮未收敛升级用户。

### 3.5 kb_author_personas 试点方案

**选样标准（SQL 实数支撑）**：q≥9 共 61 条（10×9 + 9×52）；试点取 **12-16 条**，判据四条：

1. `quality_score >= 9`（10 分全取、9 分择优）；
2. 同作者同书去重（id=2/84 刘慈欣×三体2 取信息密度高者；同作者多书可留多卡但试点每作者 ≤2）；
3. 题材轴覆盖：科幻（刘慈欣）、仙侠（辰东/耳根）、历史武侠（猫腻/烽火戏诸侯）、武侠经典（金庸/古龙）、都市诡异（爱潜水的乌贼）、游戏电竞（蝴蝶蓝）、悬疑（紫金陈或雷米）、**女频（Priest 或海宴——必取一条，防种子库全男频**）、历史向（当年明月）、群像参考（吹牛者）；
4. `weaknesses` 非空且具体（cannot_write 种子质量门槛；纯「节奏慢」类泛词降权）。

**转换资源形态**（一次性 JS 脚本 `scripts/novelos-import-style-seeds.mjs`，Node 22+，`mysql -B` TSV → 蒸馏 → node:sqlite 事务直写）：

- 每卡 → `resources`（id `resource:styleseed:<uuid>`，content 为归一化 JSON 的 BLOB，content_hash 同步）→ `creator_profiles`（display_name=`<作者>·<书名>风格卡`，**ownership='style_seed'**，status='active'）→ `creator_profile_versions`（revision=1，双资源链第二 resource 存转换溯源：原表字段快照 + 归一化说明 + 转换时间）。
- 归一化蒸馏：JSON 数组/逗号串统一拆数组；`narrative_drive` 剥 score 信封；`persona_prompt` 保留为 `seed_prompt` 字段（**只注入融合 agent，禁入写作侧**——防拆解腔渗入正文）；每卡附 `conversion_notes` 声明合并了哪些源字段。
- **ownership 同构性**：内核库 `ownership='author_kernel'`（深层根），分身 `ownership='user'`，种子库 `ownership='style_seed'`（表达层参照）——三者共用 creator_profiles 全套版本链机制，语义由 ownership 区分；select 反查纪律同构：**版本存在 + ownership='style_seed' + status='active' + subject_hash 相符**。
- 版权边界：卡片是拆解方法论非原文，落本地 DB（gitignore 已覆盖），不进 catalog/config 公开目录，不整表搬运（试点 12-16 条 < 122 条全量的 15%）。

**向导接入点**：`project-create-request.schema.json` 的 `setup` 新增**可选段**（缺省 mode='none'，完全向后兼容）：

```json
"style_seed": {
  "type": "object",
  "additionalProperties": false,
  "required": ["mode"],
  "properties": {
    "mode": {"enum": ["none", "persona_select"]},
    "seed_version_id": {"type": "string", "pattern": "^creator-profile-version:[a-z0-9][a-z0-9-]*(:[0-9]+)?$"},
    "seed_subject_hash": {"$ref": "#/$defs/hash"},
    "seed_display_name": {"type": "string", "maxLength": 60}
  },
  "allOf": [{"if": {"properties": {"mode": {"const": "persona_select"}}},
             "then": {"required": ["seed_version_id", "seed_subject_hash"]}}]
}
```

组装时 `style_seed` 槽反查种子卡全文注入融合 agent（§3.2a）。

**mismatch 裁决红线沿用**：种子卡 `emotional_style/sentence_style` × 内核 `emotional_stance/aesthetic_commitments` × 本书 `emotional_surface/emotional_core` 三方任一根本相斥（冷峻卡×甜宠书、翻译腔卡×原教旨热血）→ 融合 agent 在 `parent_rationale.style_seed_check` 小节报 mismatch + 调和建议（换卡/调 tier/去种子）→ **主控呈报用户裁决后才落库**——仅警告即放行 = 纸面化（F2 教训直接沿用）。种子选择本身（哪张卡）也是用户裁决点（向导确认约束时一并问）。

---

## 4. 执行步骤（含验证）

1. **备份 DB**（红线，先于一切）：`cp data/novelos-v2.db "data/novelos-v2.db.bak.r5d4-$(date +%Y%m%d-%H%M%S)"`，核对备份文件字节数一致。
2. **git 文件改动**（可独立 commit，先于 DB 动作）：schema v3 草案（§3.1）→ prompt.md 增补 + 两条件模块 + manifest（§3.2e）→ `agent-recipes.json` 同步 → 渲染器增补（§3.1 影响面表）→ project-create-request 增 `style_seed` 段（§3.5）。
3. **静态验证**：`node scripts/test-guardrails.mjs`（manifest≡recipes + 词表单源，241 项不退化）；`node scripts/test-compose-prompt.mjs`；用旧 v2 签名样本对 schema 重跑校验（**向后兼容验证：旧签名必须仍合法**）。
4. **migration 031 副本验证**：`cp data/novelos-v2.db data/tmp-verify.db` → 在副本跑 031（§5 草案）→ 行数比对（creator_profiles 前后行数不变）+ 抽查 ownership 值无丢失 → 通过后才动生产库。
5. **生产库 migration 031**（备份已在手）。
6. **试点导入**：`scripts/novelos-import-style-seeds.mjs` 按选样标准导 12-16 卡（先在副本演练一轮，核对归一化输出后人审，再上生产库）；导入后跑内核名册同款 SQL 验证种子名册可查。
7. **G4 红方规格审**（§5）：P0 修复 100%、P1 ≥90%，≤3 轮。
8. **冒烟演练**：测试项目走完 v3 向导（select 内核 + select 种子 + 假 A 级语料 5 篇）→ 融合产出 v3 签名 → schema 自查 → 六表落库（sql-reference 模板）→ 投影 `--verify` 渲染含风格 DNA 段 → 组装产物 diff 确认 style_seed/style_corpus 注入生效且体量受控。
9. **G5 产物审**（§5）：金丝雀豁免假阳性测试 + 滥用用例 + 降级链冒烟。
10. **记账**：`tasks/README.md` R5 节按条目记 `IN PROGRESS`→`DONE`（附验证证据：guardrails 输出、冒烟投影路径、种子名册 SQL 结果）。

---

## 5. 对抗门设计（G4/G5/G1 本轮专项）

- **G4 规格审焦点**（异构模型红方审本计划）：
  1. schema 影响面完整性：三联动（schema/manifest/recipes）+ 渲染器 + 向导段是否有漏网消费方（重点 grep 全仓 `creator-signature` 引用）；
  2. 豁免防滥用：区间比对（出区间不豁免）、tier=D 通道关闭、feature 前缀约束是否堵死「整体豁免」路径；
  3. 语料权属分级：B 级必须有授权声明；种子卡不进写作侧注入；
  4. 体裁错配：网文化 L2（章首/章尾/切换）是否真的可操作，有无残留公众号文章结构残留；
  5. 双源漂移：种子卡 vs genre-packs（种子不作词表，红线复述进 prompt 模块）。
- **G5 产物审焦点**：
  1. **豁免假阳性**：拿金丝雀人类语料段构造「签名声明 vs 实测」用例——声明「感叹号每千字 ≤1」的豁免用在感叹号每千字 8 次的稿上必须不生效；
  2. **滥用用例**：诱导整体豁免（「这位作者整体风格如此」）必须被 reviewer 拒（引用原文条款缺失即拒）；
  3. **降级链**：无语料无种子项目全程可走通，且 measured_features 为空、豁免通道关闭；
  4. **漂移用例**：样本槽连续 10 章全用项目自身章节（违反 ≥3/5 人类语料下限）应被组装侧拒绝或告警（该约束写进方向3 的接口需求）；
  5. mismatch 用例：冷峻种子 × 甜宠 setup 必须产生 parent_rationale 上报而非静默落库。
- **G1 金丝雀回归**：豁免清单建立/变更后重跑 `novelos-canary.mjs`——规则误报率不得高于基线（豁免不修改规则本体，理论上无影响；验证「豁免特征在人类分布内」的抽样另记）。

---

## 6. 验收判据

1. schema v3 自查通过；**存量 v1/v2 签名重校验仍合法**（向后兼容证明）。
2. 新签名落库链路冒烟通过：六表单事务、风格侧字段完整、投影渲染出「风格 DNA」段。
3. 试点种子 12-16 卡入库：名册 SQL 可查、ownership='style_seed'、归一化后人审零结构错误。
4. measured_features 逐条有 source 可溯源（冒烟签名抽查 100%）。
5. 豁免判定演练：命中区间豁免生效、出区间不生效、tier=D 通道关闭，三例各有 Receipt 证据。
6. `test-guardrails.mjs` 全绿（含新 SLOT_REGISTRY 一致性）；`test-compose-prompt.mjs` 全绿。
7. 金丝雀误报率 ≤ 基线。
8. G4 P0 清零、G5 findings 修复率达 R5 总计划 §4 阈值。

---

## 7. 风险与回滚（含 DB 备份）

| 风险 | 预案 |
|---|---|
| migration 031 表重建损数据（生产库） | 事前备份（§4.1）；副本先行（§4.4）；行数+ownership 抽查比对；异常即停 |
| 豁免被滥用于放行 AI 痕迹 | 逐特征+区间+引用原文（R1 措辞配合）；tier=D 关闭通道；G6 呈报 |
| 样本槽撑爆章级上下文 | 体量上限（建议 4500 字样本 + 800 字摘要，硬上限由方向3 落地并写死） |
| 自我模仿漂移（样本全用项目章节） | ≥3/5 人类语料下限写进选篇判据与方向3 接口 |
| 种子卡拆解腔渗入正文 | seed_prompt 只进融合 agent；卡片标「参照卡非成稿标准」 |
| 种子与 genre-packs 双源漂移 | 种子零词表职能；词表唯一源红线复述进 style-corpus-present 模块 |
| 版权越界（B 级授权不实） | corpus_basis.refs 强制授权标识；语料只落 data/（gitignore）；不进公开产物 |
| schema v3 兼容性破坏旧链 | v1/v2 不迁移不复验；读侧全防御式；重校验用例进 §6.1 |

**回滚步骤**（按层）：git 层 `git revert` schema/catalog/recipes/渲染器/向导段（步骤 2 的 commit 独立，revert 干净）；DB 层恢复备份 `cp data/novelos-v2.db.bak.r5d4-<ts> data/novelos-v2.db`（覆盖前二次确认）；种子数据可单独 DELETE（按 ownership='style_seed' 反查 id 集，resources/versions/profiles 逆序删，先备份）；组装槽位 revert 后 guardrails 自动回到旧一致性。

---

## 8. 接口声明（对外契约）

- **对方向3（槽机制）**：
  1. fusion 域新增 `style_seed` 槽：输入 = payload.setup.style_seed，resolver 反查种子卡全文（version + ownership='style_seed' + status='active' + subject_hash 四查），输出 `[标题, 卡片 JSON 全文]`；
  2. writing 域建议新增 `style_refs_samples` 槽：内容需求 = §3.3 表（style_dna 摘要 ≤800 字 + 5 篇人类语料为主的连续片段每篇 600-1000 字 + 选篇说明 + measured_features 原文）；选篇五判据与 ≥3/5 人类语料下限是**内容侧硬约束**，槽机制侧需提供拒给/告警钩子；
  3. `style_corpus` 经 project_setup 载荷透传（不单列槽），A/B 级语料文件落 `data/stylecorp/<project-id>/`（gitignore），读取时机与去重归方向3。
- **对方向1（审查 rubric）**：`measured_features` 消费协议 = §3.4 判定流（feature 查表键 `fp:` 对齐 R2 规则号、区间比对、出区间不豁免、引用原文、tier=D 关闭）；豁免降级语义（finding → note/dismiss）与 reviewer 措辞由方向1 落地，数据形态以 §3.1 schema 片段为唯一权威。
- **对 R2（预筛脚本）**：`novelos-prose-fingerprint.mjs` 输出的候选清单每条须携带**规则号**（`fp:<id>` 命名空间），供豁免查表与 D1 引用；规则号的新增/变更须同步本文 §2 候选清单的映射表。
- **对向导/主控**：`setup.style_seed` 为可选段（缺省 none）；mismatch（种子×内核×基调）与种子选择均为用户裁决点；落库仍走 sql-reference「作者签名链」六表模板零改动（仅签名 JSON 内容扩展）。

---

## 9. 来源引用（外部，检索于 2026-08-29）

**stylometry 特征体系**：
1. [Kestemont, *Function Words in Authorship Attribution: From Black Magic to Serious Science*, 2014](https://aclanthology.org/W14-0908.pdf) —— 功能词是作者身份最判别性特征（内容词随题材漂移，功能词是习惯）。
2. [Evert, *Statistical Significance in Literary Authorship Attribution*, 2019](https://purl.stefan.evert/PUB/Evert2019_Manchester_slides.pdf) —— Burrows' Delta 以 100-5000 最高频词的标准化频率向量度量风格距离（「签名 = 频率分布」而非单词表）；另见 [Programming Historian: Introduction to Stylometry with Python](https://programminghistorian.org/en/lessons/introduction-to-stylometry-with-python)（Delta 的 fitting/距离两步实操）。
3. [Sapkota et al., *Not All Character N-grams Are Created Equal*, NAACL 2015](http://ccc.inaoep.mx/~mmontesg/publicaciones/2015/CharacterNgramsForCrossDomainAuthorshipAttribution-NAACL15.pdf) —— 词缀类与**标点类** n-gram 贡献了字符 n-gram 几乎全部判别力（标点习惯入 measured_features 的依据）。
4. [作者识别研究综述，自动化学报 2021](https://www.aas.net.cn/cn/article/doi/10.16383/j.aas.c200654?viewType=HTML) —— 中文语境句法 n-gram 优于字符 n-gram（syntax_patterns 的依据）。
5. [Przystalski et al., *Stylometry Recognizes Human and LLM-Generated Texts*, 2025](https://www.sciencedirect.com/science/article/pii/S0957417425026181) —— StyloMetrix 特征集（功能词类型/句长/词汇丰富度 TTR）同时用于作者判别与人机区分（与本仓「签名 × 去 AI 味」双用途同构）。

**风格迁移评估方法（如何判定「像这个作者」）**：
6. [Bommasani et al., *Evaluating Text Style Transfer Evaluation: Are There Any Reliable Predictors?*, NAACL 2025 SRW](https://aclanthology.org/2025.naacl-srw.41/) —— 风格迁移评估三轴：style transfer accuracy / content preservation / naturalness，人工评估仍是金标准。
7. [Fast Forward Labs, *Automated Metrics for Evaluating Text Style Transfer*, 2022](https://blog.fastforwardlabs.com/2022/07/11/automated-metrics-for-evaluating-text-style-transfer.html) —— style classifier 测「风格强度」的评估器用法（映射：特征命中率 = 风格强度的可核对代理）。
8. [Lipani et al., *Meta-Evaluation of Style and Attribute Transfer Metrics*, 2025](https://arxiv.org/html/2502.15022v3) —— content preservation 度量的元评估（映射：Canon 守恒轴由 R1 双模式承担，与本文三轴拼合）。

**外部特征 → measured_features 映射汇总**：见 §2 表（MFW→hf-lexicon-profile；句长分布→sentence-length/short-ratio/long-ratio；标点 n-gram→fp 规则号逐条；TTR→lexical-richness；句法 n-gram→syntax-patterns；三轴评估→验收判定框架）。
