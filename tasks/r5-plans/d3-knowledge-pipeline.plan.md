# D3 · 知识蒸馏与组装器接入（可执行设计）

> ⚠ **R0 执行偏差记录（2026-08-29）**——导入层已执行（`scripts/novelos-import-knowledge.mjs`），以下为实际执行与本文的差异（未列者仍以本文为准）：
> 1. **落盘路径与文件名**（裁-5/P0-3）：原始导出层由 `config/knowledge/*.json`（入 git）改为 **`data/knowledge/<table>.json`**（gitignore，文件名=源表名）；`config/knowledge/` 仅留蒸馏产物（后续轮次）。
> 2. **不导表扩至 7 张**：`kb_author_personas`（裁-5：D4 于 R5 轮走 MySQL 直连 12-16 条试点，staging 导出取消，author_name 归并预处理随之移交 D4）、`kb_corpus_articles/excerpts`（裁-4：由金丝雀选样执行员按 D2 装载器格式 `data/canary/g{N}/*.md` 直连导出，本文 §8.1 的 jsonl 交付取消）+ 本文既定的 worldbuilding_priority / reusable_templates / memes / imported_files。23 张 kb_* 表全部在脚本 TABLE_DISPOSITIONS 注册表逐条登记。
> 3. **quality 口径**（裁-6/P0-2）：SQL 侧原始 `BETWEEN 8 AND 10` 过滤（techniques 1310 实数确认）；normScore 不参与过滤，条目仅保留 `norm_score` 排序辅助字段。
> 4. **dup_key 排序**（P1-8）：字面 `category, dup_key, id` 在实测数据上无法保证同 key 相邻（同 dup_key 条目 category 实测发散，如 id 6/258/435 分属世界观融入/信息差运用/叙事技法），改为 **`dup_key, category, id`** 兑现「同 key 相邻」意图；连接符 `::`。
> 5. **scene_maps 死引用**：不自动剔除（避免丢数据），`--verify` 双口径报告（源表死引用 1 个、quality 过滤外失联 74 个），剔除决策留蒸馏层。
> 6. **字段名保持源列名**（不采用 §3.2 短名 schema 草案）；溯源三件套每条必备（`kb:<域>:<orig_id>` / orig_id / book_source / exported_at）；`--canary-only` flag 未做（tags.json 随 kb_corpus_tags 双落 `data/canary/tags.json`，articles/excerpts 已不在本管道）。
> 7. **幂等口径**：`exported_at` 为 UTC 日期粒度——同库状态同日重跑字节一致（已验证 diff 为空）；跨日重跑仅该字段变化。
> 8. **biz_\***：红队快照 41 张，2026-08-29 实测 **42 张**，已全量显式排除（脚本头注释逐一登记）。
> 9. **验证证据**：`--all` 16 表导出成功；`--verify` 全绿（运行时 COUNT 对账，不写死数字）；幂等 diff 为空；独立 SQL COUNT 双源对账一致；83 条 parse_error 均为源库坏 JSON（数组元素间缺英文逗号），按「保真 + `_parse_error` 标记」处置。

> 状态：`TODO`（设计文档，待 G4 红方规格审 + 用户裁决后执行）
> 负责范围：R0 导入管道（kb_* → config/knowledge/ + data/canary/）· R3 写作层 knowledge 槽 · R4 规划层参照投递 · 蒸馏流程与注入预算
> 边界：既有 fingerprint 卡修改归 D1；craft 卡**内容蒸馏**归本文；onboarding/签名归 D4；门规程（G1/G2/G3 运行时）归 D5；本计划不修改任何其他仓库文件（仅本文件）
> 上游输入：`tasks/R5-knowledge-absorption.md`（v1 总计划）+ `tasks/r5-plans/00-chain-coverage.md`（主控修正指令：D3 须论证「可选素材 Read 注入」vs「composer 槽」取舍——见 §3.6/§5）

---

## 1. 现状盘点（file:line 实测）

### 1.1 组装器 `scripts/novelos-compose-prompt.mjs`（1610 行）

| 结构 | 位置 | 新增槽需联动的事实 |
|---|---|---|
| `ASSET_DIRS` 注册表 | L52-78 | 资产→skill 目录映射；新增槽不改此处（走 manifest 声明） |
| `validateManifestStruct` | L301-347 | L306 `knownRoot = ['modules','data_slots','divergence','decision_scope','craft_refs']`（manifest 根字段封闭集）；L328 槽名 pattern `^[a-z_]+(-[a-z_]+)*(:[a-z_]+)?$`——**`knowledge:techniques` 这类带冒号槽名天然合法，无需改 schema** |
| `loadManifest` / `selectModules` | L484-492 / L495-503 | manifest 读取 + when 条件路由 |
| `compose`（U 型拼装） | L556-592 | L562-565 输入数据区拼装（`### 标题\n正文` 分节）；条件模块贴近生成点（U 尾） |
| `buildContextDirection` | L644-653 | context = `{setup, has_kernel}`；`setup.channel` / `setup.genre_profile`（键形如 `男频|玄幻`，值含 genre-packs 四字段）是 knowledge 检索的确定性依据 |
| `slotUpstream` | L824-847 | locked 上游资产查询模式（`planning_assets` 按 `asset_type+status='locked'` 取最高 revision）——`knowledge:techniques` 复用此查询取 chapter_plan 作场景匹配源 |
| `slotGenrePack` / `slotWorldLexicon` | L900-910 / L912-943 | 槽节返回格式范本：`[标题, 正文]` 二元组；缺位时显式声明而非静默 |
| `SLOT_REGISTRY` | L1326-1344 | 具名槽注册表（17 个）；带冒号的动态槽不走此表 |
| `resolveSlots` | L1347-1388 | **前缀分发**：L1354 `upstream:` / L1358 `upstream-reviews:` / L1362 `canon_minimal` / L1366 `review_feedback` → L1371 查 `SLOT_REGISTRY` → L1377-1386 `craft_refs`（craft 卡 prompt.md 逐字全量注入；引用不存在即 L1383 fail） |
| `writeCompositionLog` | L1418-1454 | 每次组装落 `data/compositions/`（gitignore）+ `index.jsonl`（记 data_slots/modules/content_hash）——knowledge 槽自动被留痕，无需额外记账 |
| CLI `main` | L1533-1586 | 无需新 flag：knowledge 槽全部从 `--project` 派生 |

### 1.2 配方矩阵 `config/agent-recipes.json`

- `slot_vocabulary` L4-27（22 项，含 `upstream:<asset_type>`）——新槽家族须登记。
- 相关条目：`direction` L72-85（4 槽）、`world_contract` L209-223（5 槽）、`chapter_plan` L331-348（8 槽）、`chapter_draft` L370-389（10 槽）。
- **`craft_refs` 不在矩阵中**（只在 manifest，如 chapter-draft manifest L48-53）——craft 卡增补是 manifest-only 改动，不触发 G2b。

### 1.3 manifest 实例

- `catalog/skills/writing/chapter-draft-generation/modules/manifest.json`（manifest v2 实例）：4 条件模块（channel/kernel 维度，when 走 `setup.channel`/`has_kernel`）+ `data_slots`（10 槽，L36-47）+ `craft_refs`（4 卡，L48-53）+ `divergence: constrained` / `decision_scope: execute`。
- `catalog/skills/planning/story-direction/modules/manifest.json`：8 条件模块，`data_slots` 4 槽；`world-contract`：5 槽；`chapter-plan-execution-card`：8 槽（均无 craft_refs）。
- schema：`config/schemas/compose-manifest.schema.json`——`data_slots` pattern 与 `validateManifestStruct` 一致（`^[a-z_]+(-[a-z_]+)*(:[a-z_]+)?$`）；`craft_refs` pattern `^[a-z][a-z0-9-]*$`。

### 1.4 测试基线

- `scripts/test-guardrails.mjs`（93 行）：G1 词表单源 L29-47；**G2a 槽注册** L64-72（非动态槽须同时在 `SLOT_REGISTRY` 与 `slot_vocabulary`；动态前缀白名单 `DYNAMIC_PREFIXES` L59 = `['upstream:', 'upstream-reviews:', 'canon_minimal', 'review_feedback']`）；**G2b manifest≡matrix** L74-88（槽集合**全等**——`deepEqual(sorted slots)`，不是只增）；G2c skill 目录存在 L75-79。实测当前 **241 passed / 0 failed**（`node scripts/test-guardrails.mjs`）。
- `scripts/test-compose-prompt.mjs`（243 行）：CLI 冒烟（①a-①d 组装产物结构断言：主干标题/输入数据区标记/尾部自检节；②③ 错误路径）+ when 路由单测（④a-④g）。新增槽须补：knowledge 检索纯函数单测 + 产物体积断言。

### 1.5 craft / expansions 现有全景

- `catalog/skills/craft/` 9 卡，**全部扁平 prompt.md、无 modules/、经 craft_refs 全量注入**（字节数实测）：prose-format-hardrules 8090、prose-anti-ai-fingerprint 5697（D1 管）、prose-webnovel-accessibility 4098、compliance-place-guard 2586、worldview-lexicon 1730、shuangwen-techniques 1007、dash-ellipsis-guide 477、mobile-formatting 411、**scene-pacing 仅 388（节奏蒸馏的自然扩充点）**。
- chapter-draft 固定注入层实测 = 主干 5096 + 4 卡 19615 = **24711B**——注入预算以此为对照基线。
- `catalog/skills/expansions/` 11 件（scenario-atlas/universe-atlas 带 clusters/ 簇文件）——「可选素材 Read 注入」通道的现有载体（00-chain-coverage 发现一）。

### 1.6 MySQL nwriter 实测（2026-08-29 只读抽样，n=各表 1-2 条全字段）

- `kb_writing_techniques`：**3017 行**（information_schema 估算 2749 为近似；R5 计划表 3017 为真值）、91 个 category（命名脏：`对话技巧/对话/对白/潜台词` 分裂、`节奏控制/节奏/喜剧节奏` 分裂）。
- **quality_score 双刻度**：2884 行落 0-10，**133 行落 11-100**（如 `写作总结` 类均值 87、`语言风格` 均值 30.75——另一批 0-100 打分）。直接 `q>=8` 会混入异刻度行；`q BETWEEN 8 AND 10` = **1310 行**。
- 首批三类实数（q∈[8,10]）：对话类（对话技巧 58 + 对话 + 对白 + 潜台词）**65 条**；节奏类（节奏控制 125 + 喜剧节奏 23 + 节奏）**151 条**；开篇技法 **46 条**——合计 **262 条**。
- 近重复实测：id 7 与 id 68 同书同技法双版本（`对话驱动叙事` 两种表述）——蒸馏层必须去重合并（covers 多 id）。
- 例文体量：`example_text` 均值 69 字 / 最大 334 字——例文天然短，一行标注可行；`description` 均值 111 字。
- `kb_technique_scene_maps` 15 行：`applicable_techniques` 是 id 的 JSON 数组（需引用存在性校验）；`priority_order` 为 1..N 序列（**无信息量，丢弃**）；`combination_guides` 全 NULL、`book_examples` 全 `[]`（丢弃）。
- 文本列内 JSON 实测形态：`applicable_scenes`/`application_rules`（techniques，字符串数组）、`key_techniques`/`reusable_frameworks`（book_summaries）、`core_rules`（world_settings）、`formula`（cool_points）、`arc_config`/`turning_points`（plot_frameworks，**对象数组**）、`internal_structure`（scene_blueprints，对象数组）；`power_system`（world_settings）是**JSON 对象**。
- 各表 q∈[8,10] 计数：book_summaries 66/79、world_settings 276/474、dialogue_patterns 252/269、scene_blueprints 240/326、cool_point_patterns 519/546、plot_frameworks 164/267、emotional_arc_patterns 181/193、character_archetypes 445/506、economic 23/156、social 51/229、faction 87/304、author_personas 119/122、story_genres 52/52（字段仅 genre_name/definition/example_titles，无 quality 脏数据）。
- 语料：`kb_corpus_articles` 123（article_id/title/tags/char_count/source_url/quality_tier/quality_score/status）、`kb_corpus_excerpts` 436（excerpt_id/article_id/excerpt_type/tags/para 范围/text/quality_score）。
- 其余：`kb_worldbuilding_modules` 28（genre/module_name/badge/design_questions/design_prompt）、`kb_worldbuilding_priority` 91（排序表）、`kb_reusable_templates` 362、`kb_memes` 3、`kb_imported_files` 261。
- 生产库 `data/novelos-v2.db`：1 项目、**0 条 planning_assets**——槽测试需构造夹具库（composer `--db` 指向临时库，脚本已支持）。

---

## 2. 表 → 目标映射（27 张 kb_* 全处置）

| 来源表（行数） | 目标 | 筛选/清洗 | 消费方 |
|---|---|---|---|
| kb_writing_techniques（3017） | `config/knowledge/techniques.json` | q 归一后 ∈[8,10] → **1310 行**；category 经映射表归一 | R3 槽 + 蒸馏源 |
| kb_technique_scene_maps（15） | `config/knowledge/scene-maps.json` | 死 id 引用剔除；丢 priority_order/空列 | R3 槽检索辅助 |
| kb_dialogue_patterns（269） | `config/knowledge/planning/dialogues.json` | q∈[8,10] → 252 | chapter_plan 参照（R4） |
| kb_scene_blueprints（326） | `config/knowledge/planning/scenes.json` | → 240 | chapter_plan / volume_outline 参照 |
| kb_cool_point_patterns（546） | `config/knowledge/planning/cool-points.json` | → 519 | strategy / volume_outline 参照 |
| kb_emotional_arc_patterns（193） | `config/knowledge/planning/emotional-arcs.json` | → 181 | story_arc 参照 |
| kb_plot_frameworks（267） | `config/knowledge/planning/plot-frameworks.json` | → 164 | architecture / story_arc 参照 |
| kb_book_summaries（79） | `config/knowledge/planning/book-summaries.json` | → 66 | direction / architecture 参照 |
| kb_story_genres（52） | `config/knowledge/planning/genres.json` | 全量 52 | direction 题材缺位兜底 |
| kb_world_settings（474） | `config/knowledge/planning/world-settings.json` | → 276（kind=world） | world 参照 |
| kb_economic_systems（156） | `config/knowledge/planning/world-settings.json` | → 23（kind=economic） | world 参照（同文件合并读取） |
| kb_social_systems（229） | 同上 | → 51（kind=social） | world 参照 |
| kb_faction_designs（304） | 同上 | → 87（kind=faction） | world 参照 |
| kb_worldbuilding_modules（28） | `config/knowledge/planning/world-modules.json` | 全量 | world 参照（后批接槽） |
| kb_worldbuilding_priority（91） | **不导** | 排序元数据，信息已被 modules 覆盖 | — |
| kb_character_archetypes（506） | `config/knowledge/planning/archetypes.json` | q∈[8,10] → 445 | character 原型参照（R4 后批） |
| kb_author_personas（122） | `config/knowledge/staging/author-personas.json` | q∈[8,10] → 119 | **预留 R5 轮**（D4 消费；仅导出不接槽） |
| kb_reusable_templates（362） | **暂不导**（R5 计划既定） | 观察槽实际消耗后再定 | — |
| kb_memes（3）/ kb_imported_files（261） | **不导** | 垃圾/源文件登记 | — |
| kb_corpus_articles（123） | `data/canary/articles.jsonl`（gitignore） | 全量导出（含 quality_tier/tags）——**S 级选样 15-20 篇归 D1**，本管道只供原料 | D1 金丝雀 |
| kb_corpus_excerpts（436） | `data/canary/excerpts.jsonl`（gitignore） | 全量按 article_id 关联导出 | D1 金丝雀 |
| （导入层元数据） | `config/knowledge/provenance.json` + `category-map.json` + `distilled.json` | 见 §3.1/§3.2 | 溯源/互斥登记 |

**quality_score 筛选放导入层还是蒸馏层——结论：导入层做刻度归一 + 量化过滤，蒸馏层保留内容否决权。** 理由：①导入层确定性可重复，过滤规则写进 `provenance.json` 可审计可回放；②蒸馏是 LLM 高成本动作，先廉价裁剪（3017→1310，-57%）再蒸馏省编排开销；③git 不背死数据；④内容质量判断（空洞描述、同质化）导入层做不了也不该做——蒸馏 agent 逐条 `dropped`（附理由），两层职责正交。**归一规则**：`q > 10 → Math.round(q/10)`（133 行 0-100 刻度行归一后再过滤；原始值保留在 `orig_quality_score`，归一动作记入 provenance `scale_notes`）。

---

## 3. 改动清单（代码骨架 + JSON schema 草案）

### 3.1 `scripts/novelos-import-knowledge.mjs`（新建，一次性 + 可重复工具，零 Python）

```
用法：
  node scripts/novelos-import-knowledge.mjs [--knowledge-only|--canary-only]
       [--mysql-host 127.0.0.1] [--mysql-user root] [--mysql-db nwriter] [--verify]
凭据：密码经 MYSQL_PWD 环境变量传入（用户 profile 注入），不进 argv、不进代码、不进日志。
产物：config/knowledge/*.json（入 git）+ data/canary/*.jsonl（gitignore）。
```

核心骨架（仅 node: 标准库 + node:child_process）：

```js
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';

// ── 表规格：声明式，一表一条 ──────────────────────────────────
const TABLE_SPECS = [
  {
    table: 'kb_writing_techniques',
    file: 'techniques.json',
    columns: ['id', 'technique_name', 'category', 'sub_category', 'description',
              'book_source', 'applicable_scenes', 'application_rules',
              'example_context', 'example_text', 'prerequisites',
              'difficulty_level', 'effectiveness_score', 'anti_patterns', 'quality_score'],
    jsonColumns: ['applicable_scenes', 'application_rules'],  // text 里的 JSON 数组
    filter: (r) => normScore(r.quality_score) >= 8,
    idPrefix: 'kb:tech',
  },
  // world 四表共用 file 'planning/world-settings.json'，以 kind 字段区分；
  // plot_frameworks/scene_blueprints 另有 jsonObjColumns（对象数组）；其余同构。
];

function normScore(q) { const n = Number(q); return n > 10 ? Math.round(n / 10) : n; }

// ── 导出：mysql -B -e → TSV（显式列清单，禁 SELECT *） ───────────
function exportTsv(opts, sql) {
  const r = spawnSync('mysql',
    ['-h', opts.host, '-u', opts.user, '-B', '-e', sql],
    { env: { ...process.env }, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  // MYSQL_PWD 由调用环境提供；r.status!==0 即抛错（stderr 全文进错误）
  return r.stdout;
}

// ── TSV 解析：mysql -B 转义反转义 ──────────────────────────────
function parseTsv(tsv) { /* 首行表头；\N → null；\\t \\n \\\\ 反转义；返回对象数组 */ }

// ── JSON 列清洗：解析失败降级保底，不丢行不中断 ──────────────────
function cleanJsonCol(v, col, rowId, warnings) {
  if (v == null || v === '') return [];
  try { const p = JSON.parse(v); return Array.isArray(p) ? p : [String(p)]; }
  catch { warnings.push(`${rowId}::${col} 非法 JSON，降级为原文`); return [String(v)]; }
}
```

**字段清洗规则汇总**：

| 规则 | 内容 |
|---|---|
| JSON-in-text | 声明列先 `JSON.parse`（数组列/对象数组列/对象列分类处理）；失败降级为 `{col}_text: 原串` 并计 warning |
| 空值 | 核心方法论字段双空丢行（techniques：description 与 application_rules **双空**；book_summaries：core_appeal 空），计数入 provenance `dropped_rows` |
| 死引用 | scene-maps 的 applicable_techniques 引用 id ∉ techniques ids → 剔除该 id；剔空后整条丢 |
| 无信息量列 | scene-maps `priority_order`（1..N 序列）、全 NULL/`[]` 列（combination_guides/book_examples）不导 |
| 双刻度 | normScore + `orig_quality_score` 保真 |
| category 脏名 | 导出原值 + `category_norm`（经 `category-map.json` 查表；未命中归 `其他` 并计 warning 待人工补表） |
| 幂等 | 重跑覆盖 config/knowledge/*.json；**`distilled.json` 若存在则保留并校验其 kb id 仍在新导出集**（漂移即报错，防蒸馏登记失联） |
| canary | articles/excerpts 两 jsonl 全量；`--canary-only` 供 D1 独立重跑 |
| --verify | 行数对账（导出行数 vs `SELECT COUNT`）+ 死引用检查 + JSON 解析 warning 清单；全绿 exit 0 |

`.gitignore` 追加一行 `data/canary/`（执行期改动；本计划阶段只列清单）。

### 3.2 `config/knowledge/` 数据 schema

```
config/knowledge/
├── provenance.json          # 导入批次元数据（时间/来源库/各表行数对账/过滤与归一规则/warnings）
├── category-map.json        # 91 脏类 → 12 规范类（对话/节奏/开篇/悬念/爽点/虐点/人物/结构/设定/情感/战斗/其他…可增补）
├── distilled.json           # kb id → 蒸馏落点登记（槽与卡互斥依据）
├── scene-words.json         # 槽检索用场景关键词表（对话：对话/交谈/谈判/质问/对峙…）
├── techniques.json          # 1310 条（R3 槽 + 蒸馏源）
├── scene-maps.json          # 15 条场景→技巧索引
├── planning/
│   ├── book-summaries.json  # 66   ← direction/architecture 参照
│   ├── genres.json          # 52   ← direction 题材兜底
│   ├── world-settings.json  # 276+23+51+87（kind 四值合并）
│   ├── world-modules.json   # 28
│   ├── plot-frameworks.json # 164
│   ├── cool-points.json     # 519
│   ├── emotional-arcs.json  # 181
│   ├── archetypes.json      # 445
│   ├── scenes.json          # 240  ← chapter_plan 参照
│   └── dialogues.json       # 252  ← chapter_plan 参照
└── staging/
    └── author-personas.json # 119（D4 预留，不接任何槽）
```

**techniques.json 条目 schema 草案**（planning 各文件同构，字段按表裁剪）：

```json
{
  "meta": {
    "source_table": "kb_writing_techniques",
    "exported_at": "2026-08-29T…",
    "filter": "normScore(quality_score)>=8",
    "scale_notes": "q>10 按 q/10 归一；orig_quality_score 保真",
    "source_rows": 3017, "exported_rows": 1310,
    "dropped_rows": { "q_filter": 1707, "empty_core": 0 }
  },
  "items": [
    {
      "id": "kb:tech:7",
      "orig_id": 7,
      "name": "对话驱动叙事（聊天群模式）",
      "category": "对话技巧",
      "category_norm": "对话",
      "scenes": ["都市", "群像", "轻松向", "修真", "科幻"],
      "rules": ["每个角色必须有独特说话方式…", "…"],
      "description": "…",
      "prerequisites": "…",
      "anti_patterns": "所有角色说话方式相同、群聊代替所有叙事…",
      "example": { "context": "…", "text": "三浪：…", "non_canonical": true },
      "q": 9, "effectiveness": 9, "difficulty": 3,
      "book_source": "修真聊天群",
      "dup_key": "修真聊天群|对话驱动叙事"
    }
  ]
}
```

**溯源三件套（全文件统一契约）**：`id`（稳定 `kb:<域>:<orig_id>`，槽输出引用它）/ `orig_id` / `book_source`（真实书名——**只留在 config/knowledge 与蒸馏 provenance，注入正文节不渲染书名/角色名**，防拆解腔渗入）。

**例文标注机制**：所有 `example*` 字段包成 `{text, context, non_canonical: true}`；渲染端（槽/蒸馏 prompt）见 `non_canonical` 必附「例（非成稿标准，防拆解腔——只看机制，不看措辞，禁止仿写句式）」——机器可查，guardrails 校验注入文本含该标（G3b，§3.4）。

`distilled.json` 草案：`{"kb:tech:7": "craft:scene-dialogue", "kb:tech:68": "craft:scene-dialogue"}`——id 7/68 同技双版本互覆合并登记。

### 3.3 蒸馏流程设计

**执行者**：主控编排 sub agent（角色 `knowledge-distiller`，隔离上下文）；**sub agent 只返回候选文本，主控校验信封后落盘**（沿用「sub agent 不持有持久化手段」纪律——此处持久化 = 写 catalog/config 文件 + git）。模型分工按 AGENTS.md：蒸馏属方法论写作，默认写作级模型，主控可按批指定。

**批大小：20 条/批。** 依据：输入 ≈ 20 × 700B ≈ 14KB（≈4-5k tokens），输出信封 ≈ 20 × 250B ≈ 5KB——对齐 Anthropic「sub agent 探索数万 token、返回 1,000-2,000 token 蒸馏摘要」量级带（§9 来源 1）。首批 262 条 → **14 批**（并行 3-4 批/波，约 4 波）。

**首批输入筛选（SQL 实数）**：

```sql
SELECT COUNT(*) FROM kb_writing_techniques
WHERE quality_score BETWEEN 8 AND 10
  AND (category IN ('对话技巧','对话','对白','潜台词')      -- 65
    OR category IN ('节奏控制','节奏','喜剧节奏')           -- 151
    OR category = '开篇技法');                             -- 46   合计 262
```

近重复（id 7/68 型）估计再折 10-20%（蒸馏 `covers` 合并），有效条目 210-235 → 公理化产出 **30-45 条**（多对一收敛）。

**输出目标**：

| 批 | 落点 | 形态 | 字节预算 |
|---|---|---|---|
| 对话 65 | **新 craft 卡** `catalog/skills/craft/scene-dialogue/`（prompt.md + metadata.yaml + provenance.yaml） | trigger/formula/anti_pattern 公理化 | ≤2560 |
| 节奏 151 | **扩充** `craft/scene-pacing/prompt.md`（388B → ~2.5KB；非 fingerprint 卡，内容蒸馏归 D3） | 同上 | 卡总 ≤2560 |
| 开篇 46 | **新 craft 卡** `craft/chapter-opening/` | 同上 | ≤2560 |

三卡经 chapter-draft manifest `craft_refs` 追加（manifest-only，不触 G2b；craft_refs 是全量注入，故卡必须公理化而非罗列——**超 2560B 即回炉合并**）。

**蒸馏 prompt 要点**（主控拼装注入文本时执行）：

1. 保三类结构：`trigger`（何时用——源自 applicable_scenes + description）/ `formula`（步骤化——源自 application_rules）/ `anti_pattern`（禁止形态——源自 anti_patterns）。
2. **例文降权**：每条至多一句例文且必附 non_canonical 标注；禁整段例文、禁连续两句仿写示例。
3. **去重合并**：同 `dup_key`/同书同技合并为一条，`covers` 登记全部 kb id。
4. **书源隔离**：方法论正文不出现书名/角色名（入 provenance.yaml）。
5. 否决权：空洞/同质/与现有卡重复的条目放 `dropped[]`（附一句理由），不硬凑。
6. 输出信封（主控校验通过才落盘）：

```json
{
  "card": "scene-dialogue",
  "entries": [{ "covers": ["kb:tech:7", "kb:tech:68"], "trigger": "…",
                "formula": ["…"], "anti_pattern": "…", "example": "…" }],
  "dropped": [{ "id": "kb:tech:123", "reason": "与 e3 同质" }]
}
```

7. 信封解析失败/超预算 ≤3 轮重试 → 升级用户（G6 沿用）；失败批次零落盘。

### 3.4 composer knowledge 槽实现方案

**改动定位（全部在 `scripts/novelos-compose-prompt.mjs`，向后兼容——无 `knowledge:` 槽声明则零行为变化）**：

1. **新常量 `KNOWLEDGE_DOMAINS` + `KNOWLEDGE_BUDGET`**（置于 `SLOT_REGISTRY` L1326 之前）：

```js
// knowledge:<domain> 域注册表——文件、检索器、预算三件套。域集封闭，guardrails G3 校验。
export const KNOWLEDGE_BUDGET = {          // 硬编码防上下文爆炸（R5 度量项采集点）
  techniques:            { maxEntries: 5, maxGroups: 2, entryBytes: 512, totalBytes: 4096 },
  scenes:                { maxEntries: 4, maxGroups: 1, entryBytes: 640, totalBytes: 3072 },
  'reference-direction': { maxEntries: 3, maxGroups: 1, entryBytes: 768, totalBytes: 2560 },
  'reference-world':     { maxEntries: 3, maxGroups: 1, entryBytes: 768, totalBytes: 2560 },
};
export const KNOWLEDGE_DOMAINS = {
  techniques:            { retriever: retrieveTechniquesByScene },   // techniques.json + scene-maps.json
  scenes:                { retriever: retrieveScenesByPlan },        // planning/scenes.json + dialogues.json
  'reference-direction': { retriever: retrieveDirectionRefs },       // planning/book-summaries.json + genres.json
  'reference-world':     { retriever: retrieveWorldRefs },           // planning/world-settings.json（四 kind）
};
```

2. **`resolveSlots` L1362 后插前缀分支**（仿 `upstream:` L1354 模式）：

```js
if (slot.startsWith('knowledge:')) {
  sections.push(...resolveKnowledge(db, slot.slice('knowledge:'.length), projectId, context));
  continue;
}
```

3. **新函数 `resolveKnowledge(domain, db, projectId, context)`**：域未注册即 `fail`；读域文件 → 调域检索器 → 预算裁剪 → 返回 `[标题, 正文]`。标题固定含「外部知识（非 Canon——方法论参照，不得作为锁定/对账依据）」。
4. **检索器：纯关键词确定性打分，零嵌入零依赖**。`retrieveTechniquesByScene`：①复用 `slotUpstream` L824 同款 SQL 取 locked chapter_plan 正文（缺 locked → 返回显式缺位节，**不 fail**——knowledge 是增益非权威，与 upstream 硬停语义有意不同）；②`scene-words.json` 词表对章纲正文计数 → top 场景组（≤ maxGroups）；③组内 `scene-maps` 命中 id ∩ techniques 条目，按（关键词命中数 → q → effectiveness）排序；④**剔除 `distilled.json` 已登记 id**（卡与槽互斥，防同知识双通道重复注入）。
5. **降级策略（超限依次执行，节尾透明化）**：①逐条先删 example 行（例文最低优先）；②按分数升序删条；③仍超限保 top-3 并截断 anti_pattern 之后内容；④节尾固定一行 `（预算 4096B：命中 7 条，降级弃 2 条 [kb:tech:xx,…]；例文已省略 N 处）`——组装产物 diff 可审计（R5 度量表「knowledge 槽注入体积」采集点）。

**manifest 声明方式**（槽名已合 schema pattern，manifest **无需新键**——`data_slots` 数组直接加字符串）：

- `chapter-draft-generation/modules/manifest.json`：`data_slots` 追加 `"knowledge:techniques"`；`craft_refs` 追加 `"scene-dialogue"`、`"chapter-opening"`。
- `chapter-plan-execution-card/modules/manifest.json`：`data_slots` 追加 `"knowledge:scenes"`。
- `story-direction/modules/manifest.json`：追加 `"knowledge:reference-direction"`；`world-contract/modules/manifest.json`：追加 `"knowledge:reference-world"`。

**recipes 条目改动**（G2b 全等要求 matrix 与 manifest 同步）：

```jsonc
// chapter_draft（L370-389）slots 追加："knowledge:techniques"
// chapter_plan（L331-348）slots 追加："knowledge:scenes"
// direction（L72-85）slots 追加："knowledge:reference-direction"
// world_contract（L209-223）slots 追加："knowledge:reference-world"
// slot_vocabulary（L4-27）追加："knowledge:<domain>"
// 各 *-review 条目：一律不加——审查侧结构性隔离（§3.6）
```

**test-compose-prompt.mjs 联动**（新增 ⑦ 组）：

- ⑦a `retrieveKnowledge` 纯函数单测：关键词打分 / 预算裁剪（构造超限夹具断言节字节数 ≤ totalBytes）/ 降级脚注出现 / distilled 登记 id 被剔除 / 未注册域 fail / 缺 locked chapter_plan 返回缺位节而非报错。
- ⑦b CLI 冒烟（`--db` 夹具库预置 locked chapter_plan）：chapter-draft 组装 exit=0、含「外部知识（非 Canon」节、节字节 ≤4096、含「非成稿标准」标。

**test-guardrails.mjs 联动**：

- L59 `DYNAMIC_PREFIXES` 追加 `'knowledge:'`（G2a 豁免通用注册检查，改走更强专项检查）。
- **新增 G3 组（knowledge 专项，比 G2a 更强）**：
  - G3a 域合法：recipes + manifests 中出现的每个 `knowledge:<x>` ∈ `KNOWLEDGE_DOMAINS`；
  - G3b 域文件存在、条目必备溯源三件套（id/orig_id/book_source）与 `example.non_canonical`；
  - G3c **词表单源红线延伸**：`config/knowledge/**.json` 不得含 genre-packs 四字段键名（`power_currency_candidates`/`typical_dilemmas`/`reader_expectations`/`taboos`）——kb 知识永不自建词表；
  - G3d **审查侧隔离**：`asset` 以 `-review` 结尾的 recipes 条目 slots 不得含 `knowledge:` 槽——参照永不进审查注入；
  - G3e 预算存在性：`KNOWLEDGE_BUDGET` 键集 ⊇ `KNOWLEDGE_DOMAINS` 键集且 totalBytes ≤ 4096。

**注入预算值与依据（呈报用户裁决——R5 计划预声明裁决点「R3 注入上限数值」）**：

| 参数 | 建议值 | 依据 |
|---|---|---|
| techniques 每场景 top-N | **5** | top-k 实践常用 k=3（来源 6）；技巧是公式型小条目，+2 余量；Liu U 形曲线（来源 3）：条目越多中段越被忽略，>5 边际为负 |
| 每次组装场景组上限 | **2** | 章纲场景词命中通常集中 1-2 类；>2 多半是章纲涣散，多注无益 |
| 单条 entryBytes | **512**（≈170 汉字 ≈110-170 tokens） | 块粒度研究（来源 5）：事实型利用以 64-128 token 小块最优，512B UTF-8 落在该带 |
| techniques totalBytes | **4096**（≈1365 汉字 ≈900-1400 tokens） | ①Anthropic「最小高信号 token 集」+ sub agent 蒸馏摘要 1,000-2,000 tokens 带（来源 1）——贴下带留余量；②对照 chapter-draft 固定层实测 24711B，4KB 为 16% 增量，组装产物 diff 一屏可审；③OpenAI 指南：每请求数据靠后、仅注入预选资源（来源 2）——预算小才配「预选」 |
| planning 参照 totalBytes | **2560**（3 条 × ≤768B） | planning 主干实测 16KB 且条目为书级宏观信息（core_appeal 一行一条），密度高于技巧条目；上游层 expansive 档更须防素材发散 |
| scenes 域 totalBytes | **3072**（4 × 640B） | 章纲参照只取 internal_structure 骨架行；blueprint 步骤表比技巧条长但条数更少 |

### 3.5 注入位置与形态

knowledge 节经 `resolveSlots` 返回 → 落入 `compose` L562-565 **输入数据区**（U 型中部；条件模块仍在尾部贴近生成点）——与 OpenAI「Identity→Instructions→Examples→Context、每请求数据靠后」一致（来源 2），与仓库 U 型设计（高信号约束贴尾）一致。节形态：

```
### 场景技巧（knowledge:techniques——外部方法论参照，非 Canon；例文均非成稿标准）
[kb:tech:312] 沉默式情感高潮｜触发：情感高潮对话｜公式：询问(简短)→承认挣扎→停顿→选择→环境呼应｜反模式：高潮处长篇抒情
（例·非成稿标准，防拆解腔——只看机制，禁仿句式）「我挣扎过。」「我输了。」
…
（预算 4096B：命中 7 条，降级弃 2 条 [kb:tech:xx,…]；例文已省略 N 处）
```

### 3.6 规划层参照投递——两个完整样例（不动 prompt.md 主干）

**样例 A：direction × kb_book_summaries/core_appeal**

- 注入形态：`knowledge:reference-direction` 槽（manifest data_slots 声明，recipes slots 同步）。检索键 = `context.setup.genre_profile`（键形 `男频|玄幻`，与 slotGenrePack L900-910 同源）——取 `|` 后题材段（如 `玄幻`）匹配 `book_summaries.genre` 与 `genres.json.genre_name`，q 降序 top-3；无 genre_profile 时 genres.json 同名兜底，仍无则显式缺位节。渲染每本一行：`书名甲（玄幻·260 万字·单元剧+主线推进）｜core_appeal：…｜key_techniques 前 3`。
- 节头固定声明：**「外部参照·非 Canon·无对账义务（00-chain-coverage 发现二防线）——借鉴须在候选正文前置 metadata 注 `reference_ids: [kb:book:1,…]`；词表唯一源是 genre-packs，本节不含词表」**。
- 与 genre-packs 红线隔离：渲染字段白名单 = `structure_type/core_appeal/key_techniques/reusable_frameworks`（机制与魅力描述），**禁渲染名词列表型字段**；G3c 机器校验 config/knowledge 无词表键名。
- 审查方识别「参照非 Canon」：①结构性隔离——direction-review 的 slots **不加**此槽（G3d 机器校验），审查方注入中根本不存在参照，参照不可能成为其判级依据；②候选若逐字搬运参照措辞、或出现 genre_pack 与 world_lexicon 都没有的专名 → 审查方按「非 Canon 溯源」判 blocking（候选 metadata 的 reference_ids 供反查越界借鉴）。

**样例 B：world × kb_world_settings**

- 注入形态：`knowledge:reference-world` 槽。检索键 = setup.genre_profile 题材段 × `world_type`/`kind` 关键词（economic/social/faction 同文件 kind 合并检索），q 降序 top-3。渲染白名单 = `core_rules`（机制）/`entry_point`/`anti_patterns`——**只出机制与反模式，不出 special_elements/immersive_details 里的名词密度段**；节头声明同上并加一句「本节不含词表——词表唯一源 genre-packs，任何专名入正文前须过 genre_pack/world_lexicon 对账」。
- 审查方识别：world-contract-review 不注入此槽（G3d）；其判级锚定 genre_pack + upstream（已有槽）；候选出现参照特有专名而无词表对账 = blocking——**词表单源红线的运行时落点**。
- **双通道取舍论证（G4 红方必审项，回应主控指令）**：静态书级参照**不走**「可选素材 Read 注入」通道，理由——Read 通道①无预算控制（agent 可 Read 任意大文件）；②不留组装痕（index.jsonl 只记槽与模块，Read 不入账，「这次生成看到了什么」不可回查）；③注入与否取决于 agent 自由裁量，不可复现不可测试；④绕过 distilled 互斥与降级策略。**并用分工**：composer 槽 = 确定性、可预算、可留痕的参照投递主通道；expansions「可选素材」保留为 agent 主动深挖通道（本计划不动 expansions，**不向其投递 kb 蒸馏物**，避免同知识双载体漂移）。

---

## 4. 执行步骤（每步验证命令）

| # | 步骤 | 产出 | 验证 |
|---|---|---|---|
| 0 | 本计划 G4 红方规格审 + 用户裁决（R3 上限数值、首批蒸馏范围） | `docs/knowledge/redteam/r3-d3-spec.md` | P0 清零 |
| 1 | 导入脚本 + `.gitignore` 追加 `data/canary/` | `scripts/novelos-import-knowledge.mjs` + `config/knowledge/*` + `data/canary/*` | `export MYSQL_PWD=… && node scripts/novelos-import-knowledge.mjs --verify`（行数对账全绿：techniques 3017→1310、死引用 0、JSON warning 清单呈报）；重跑二次 `git diff config/knowledge` 为零（幂等）；`git check-ignore data/canary/articles.jsonl` 命中 |
| 2 | guardrails G3 组先行（红线先于功能） | test-guardrails.mjs 增 G3a-e + DYNAMIC_PREFIXES 加 `knowledge:` | `node scripts/test-guardrails.mjs`（241 + 新增全 PASS） |
| 3 | composer 槽实现 + 四 manifest + recipes 同步 | compose-prompt.mjs（KNOWLEDGE_DOMAINS/BUDGET/resolveKnowledge/前缀分支） | `node scripts/test-compose-prompt.mjs`（含 ⑦ 组）；`node scripts/novelos-compose-prompt.mjs --asset chapter-draft --project <fixture> --db <fixture.db> --no-log | grep -c '非 Canon'` ≥1；`… | awk '/场景技巧/,0' | wc -c` ≤ 4096 + 节头余量 |
| 4 | 首批蒸馏（对话 65 / 节奏 151 / 开篇 46，14 批） | `craft/scene-dialogue/`、`craft/chapter-opening/` 新卡 + scene-pacing 扩充 + `distilled.json` + 各卡 provenance.yaml | 每批信封过校验；`wc -c` 三卡各 ≤2560；`node scripts/test-guardrails.mjs` 绿（craft 引用存在性另由 resolveSlots L1383 运行时保证）；G5 盲测（§5） |
| 5 | 规划参照槽样例（direction/world）落地 | §3.6 两样例 | 夹具项目 direction 组装含参照节 ≤2560B；world 同；G3d 绿（review 侧无 knowledge 槽） |
| 6 | 回归 + 记账 | R5 账本 | `node scripts/test-guardrails.mjs && node scripts/test-compose-prompt.mjs && node scripts/test-render-projection.mjs` 全绿；通过数较 241 只增不减；`tasks/README.md` 记账 |

每步独立 commit（导入 / 护栏 / 槽 / 蒸馏 / 参照五个 commit），回滚 = revert 对应 commit。

---

## 5. 对抗门设计（本计划专属）

| 门 | 内容 |
|---|---|
| **G4 规格审**（步骤 0） | 三专项：①双通道取舍（§3.6 论证是否成立——红方可反驳并主张调整并用比例）；②注入预算（数值依据是否充分、降级顺序是否丢高信号内容）；③拆解腔（例文降权与书源隔离是否可操作）。产出 P0/P1/P2，P0 清零才进步骤 1 |
| **G5 产物审-盲测**（步骤 4 后） | 同一章纲组装两版（有/无 knowledge:techniques 槽），异构厂商红方盲判：①哪版正文更差（技巧名词/公式化句式渗入正文 = 槽有害证据）；②「例文非成稿标准」是否真防住仿写；③组装产物 diff 确认注入体积 ≤ 预算且降级脚注如实 |
| **G5 产物审-参照混入演练**（步骤 5 后，呼应 D5 指令） | 假想项目跑 direction + world 起草：红方找「参照混入 locked 资产」路径——检查候选 metadata reference_ids 声明完整性、审查方（无参照注入）是否把参照专名当 blocking 抓住 |
| **G2/G3 机器门** | §3.4 G3a-e 常驻 CI；review 侧隔离（G3d）与词表键名红线（G3c）每次必过 |
| **金丝雀（G1）** | 本计划不触 fingerprint 规则，无金丝雀回归义务；guardrails 241 只增不减 |

---

## 6. 验收判据

1. `node scripts/novelos-import-knowledge.mjs --verify` 可重复运行，行数对账表（§4 步 1 实数）全绿；`config/knowledge/` 入 git、`data/canary/` 被 ignore（`git status` / `git check-ignore` 验证）。
2. `node scripts/test-guardrails.mjs` 全 PASS（≥241 + G3 新增）；`node scripts/test-compose-prompt.mjs` 全 PASS。
3. 四个 knowledge 槽组装产物（夹具项目）：节存在、字节 ≤ 对应 totalBytes、含非 Canon 声明与（有例文时）非成稿标准标、降级脚注如实。
4. 盲测无「技巧名词渗入正文」red team finding；参照混入演练零未呈报绕过。
5. 蒸馏三卡总计 ≤7.5KB，经 craft_refs 注入后 chapter-draft 组装仍可 diff 审计；`distilled.json` 与槽输出零交集（单测断言）。

## 7. 风险与回滚

| 风险 | 预案/回滚 |
|---|---|
| 注入撑爆上下文 | 预算硬编码 + 降级 + diff 审查；超限 revert 槽 commit（manifest/recipes 摘槽即失效；composer 改动向后兼容——无 knowledge: 声明零行为变化） |
| 拆解腔渗入正文 | 例文 non_canonical 标注 + 盲测门 + 书名/角色名不进注入正文；出问题 revert 蒸馏卡 commit（槽与卡解耦，卡撤槽照常） |
| kb 知识变第二词表源 | G3c 键名红线 + 渲染字段白名单 + review 侧隔离（G3d）；违规 guardrails FAIL 挡合并 |
| 双通道漂移（槽 vs expansions） | kb 蒸馏物**只**落 config/knowledge + craft，禁投 expansions；G4 复核 |
| distiller 信封解析失败 | ≤3 轮重试 → 升级用户（G6）；失败批次零落盘（主控校验后才写） |
| scene-maps 死引用 / JSON 脏数据 | 导入层 --verify 拦截；解析失败降级保底不丢行 |
| 误触生产库 | 全程零 novelos-v2.db 写入；MySQL 只读访问，密码走 env |
| 蒸馏质量塌方 | dropped 率与合并率入 provenance；首批 G5 盲测不过即回滚三卡 |

## 8. 接口声明（对外契约）

1. **对 D1（金丝雀）**：`data/canary/articles.jsonl`（123 篇全量，含 quality_tier/quality_score/tags/source_url）+ `excerpts.jsonl`（436 段，article_id 关联）就位；S 级选样 15-20 篇的标准由 D1 制定；`node scripts/novelos-import-knowledge.mjs --canary-only` 可独立重跑。
2. **对 D4（签名链）**：`knowledge:<domain>` 槽家族与 `KNOWLEDGE_BUDGET` 框架可复用为 style_refs 原文样本槽（建议域名 `style-samples`：同预算/降级/留痕机制，语料仅限用户自有/授权文本）；`config/knowledge/staging/author-personas.json`（119 条）为 R5 轮 persona select 库原料，接槽前不得被任何 manifest 引用（G3a 会拦）。
3. **对 D5（门规程/R6 演练）**：①「同场景有/无槽两版」用 `--no-log` 双跑同章纲即得盲测对；②注入体积度量点 = 组装产物 diff + `data/compositions/index.jsonl` 的 data_slots 字段；③候选 metadata 的 reference_ids 声明是 R6 红方「参照混入 locked」检查点的输入。
4. **对所有方向**：`config/knowledge/` 溯源三件套（id/orig_id/book_source）与 `example.non_canonical` 是全仓统一契约，后续任何消费（含 R5 轮 personas）不得绕过。

## 9. 来源引用

1. Anthropic Engineering — *Effective context engineering for AI agents*：「最小高信号 token 集 / attention budget / sub agent 探索数万 token 而返回 1,000-2,000 token 蒸馏摘要 / just-in-time retrieval」。https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
2. OpenAI — *Prompt engineering guide*：Identity→Instructions→Examples→Context 顺序、每请求数据靠后、XML 界定参照文档、仅注入预选资源（RAG 形态）、few-shot 求多样。https://developers.openai.com/api/docs/guides/prompt-engineering
3. Liu et al. 2023/2024 — *Lost in the Middle*（TACL 2024）：U 形位置曲线，相关信息在长上下文中部显著劣化——top-N 克制与「数据区不淹没尾部约束」的依据。https://arxiv.org/abs/2307.03172
4. Anthropic — *Agent Skills / progressive disclosure*：Level 1 元数据约 100 tokens、按需加载 Level 2/3——「恒定方法论进卡、场景触发进槽」的分层依据。https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview · https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
5. arXiv 2505.21700 — *Rethinking Chunk Size for Long-Document RAG*：事实型问答以 64-128 token 小块最优——单条 512B（≈110-170 tokens）预算依据。https://arxiv.org/html/2505.21700v2
6. knowledged.to — *Top-K in RAG Search*：k=3 是常见默认且该参数沉默地决定 RAG 性能——top-5 上限的对照锚点。https://knowledged.to/notes/ml/top-k-in-rag-search/
