# R2 规格文档：项目创建写路径校验门的 TypeScript 等价重实现规格

> 依据 `legacy-python/scripts/novelos_create_project.py`（854 行，v3 管线）逐行提炼。
> 目标：读者不接触任何 Python 代码，即可用 **ajv + node:sqlite + node:crypto** 在插件 host 中写出行为等价的 JS 门。
> 行为等价判定标准：**每个输入产生相同的 FAIL/WARN 判定与相同的阻断决策**；错误消息文本按本文模板复刻（措辞可微调，但必须包含模板中标注的关键数据片段）；退出码语义必须一致。
> 红线（AGENTS.md）：mismatch 仅警告即放行 = 纸面化；**任何 FAIL 必须阻断**。本文所有标注 FAIL 的步骤在 JS 门中必须使本次请求整体失败且零写入。
> **状态（2026-08-24）**：本规格已实现于 plugin/dsh-novelos-viewer/src/gate/（vitest 55 用例全绿）；文中提到的 legacy-python 源文件已整体删除，保留为历史推导依据。

---

## 0. 消费资产清单（权威来源，语言无关）

| 资产 | 用途 |
|---|---|
| `config/schemas/project-create-request.schema.json` | 入口结构校验（E0） |
| `config/schemas/kernel-candidate.schema.json` | 内核候选信封校验（K0） |
| `config/schemas/author-kernel.schema.json` | 内核深层结构校验（K1） |
| `config/schemas/creator-derivation-candidate.schema.json` | 分身候选信封校验（G0） |
| `config/schemas/creator-signature.schema.json` | 分身签名深层校验（G1） |
| `plugin/client/project-wizard-data.js` | 词表级联唯一权威（`window.NOVELOS_WIZARD_DATA` 单对象赋值） |
| `data/novelos-v2.db` | 权威库（反查 + 落库）；空库基线可由 `db/migrations/schema.sql`（schema v18 终态导出）重建 |
| `db/migrations/schema.sql` | 表结构权威（本文 §8 引用其约束） |

五个 schema 均 `$schema: https://json-schema.org/draft/2020-12/schema`，自包含（`$ref` 仅指向自身 `#/$defs/*`，**无跨文件引用**）。schemas 目录其余 13 个文件本门不消费。

---

## 1. 入口契约

### 1.1 输入 JSON：`novelos.project.create.v3`

顶层结构（`additionalProperties: false`，`required: ["request_type","setup"]`）：

```
request_type: "novelos.project.create.v3"        // const，其他值直接结构 FAIL
setup: {
  title: string(1..120)                           // 项目名
  author_kernel: {                                // 内核分支（§6 详述）
    mode: "select" | "create"                     // ★ 分叉点
    kernel_hints?: {                              // maxProperties 6，键固定：
      taste_anchors | people_and_scenes | hard_nos |
      obsessions | core_questions | knowledge_domains
    }                                             // 每个 = line_list（string(1..200)，≤20 条）
    kernel_version_id?: ^creator-profile-version:[a-z0-9][a-z0-9-]*(:[0-9]+)?$
    subject_hash?:   ^sha256:[0-9a-f]{64}$
    display_name?:   string(1..60)
  }                                               // additionalProperties:false；required:[mode,kernel_hints]
                                                  // if mode==select then required:[kernel_version_id,subject_hash]
  channel: "男频"|"女频"|"全向"
  platform: string(1..20)
  platform_traits: null | {model?,patience?,reader_profile?}  // 三键均 string(1..)，additionalProperties:false
  scale: "短篇（30万字以下）"|"中篇（30-100万字）"|"长篇（100-300万字）"|"超长篇（300万字以上）"
  primary_genre: string(1..30)
  secondary_directions: string(1..30)[], ≤16 条, uniqueItems
  emotional_surface: string(1..30)[], 1..2 条, uniqueItems
  emotional_core: string(1..30)
  tonal_contrast: null | string(≤300)
  aesthetic_styles: string(1..30)[], 1..2 条, uniqueItems
  genre_profile: object | null                    // 内容不限，由 E11 快照比对管
  reference_material: null | string(≤10000)
}                                                 // setup.additionalProperties:false，14 个键全部 required
```

### 1.2 CLI 契约（对应 defineTool 参数面）

Python 门是单脚本多旗标，JS 门应拆成等价工具或一个工具多模式。旗标→语义映射：

| 旗标 | 语义 |
|---|---|
| `--payload <file>` | 向导 v3 JSON（入口校验必经） |
| `--kernel-candidate <file>` | 内核融合候选（`novelos.kernel.candidate.v1` 信封） |
| `--kernel-revise <file>` | 独立内核修订载荷（`novelos.kernel.revise.v1` 信封，替代 `--payload`，二者至少给一，否则用法错误） |
| `--emit-payload <path>` | 建核成功后把缝合 select 形态 payload 写盘（可选产物） |
| `--candidate <file>` | 分身融合候选信封（须与 select 形态 `--payload` 同用） |
| `--dry-run` | 只校验不落库 |
| `--db <path>` | 库路径，默认 `<repo>/data/novelos-v2.db` |

### 1.3 管线分叉点（main 流程）

```
db 不存在 -------------------------------------------> 打印 "数据库不存在: {path}"，exit 2
payload 读失败(JSON/OSError) ------------------------> "payload 读取失败: {exc}"，exit 2
--kernel-revise 给定 --------------------------------> 载荷=revise 信封，跳过入口门，直达内核阶段(K)
否则 --payload --------------------------------------> 入口门(E)：FAIL 即 exit 1；WARN 仅打印
[--kernel-candidate] --------------------------------> 候选容错解析(kind=kernel) → 内核门(K) → FAIL exit 1
                                                       ├─ --dry-run → 打印内核 hash，exit 0（不再往下）
                                                       └─ 落库 persist_kernel → 若 payload.setup.author_kernel.mode=="create"
                                                            自动缝合 payload 为 select 形态(+可选写 --emit-payload)
                                                            └─ 无 --candidate → exit 0
[--candidate] --------------------------------------> 守卫：payload 为 create 形态 → FAIL 打印 + exit 1；
                                                       无 payload 或 kernel_revise 模式 → 用法错误 exit 2
                                                     → 候选容错解析(kind=persona) → 分身门(G) → FAIL exit 1
                                                       → mismatch 标记扫描(仅打印) → [--dry-run → 打印 sig hash，exit 0]
                                                       → 落库 persist（六表单事务） → exit 0
--kernel-revise 且无 --kernel-candidate -------------> 打印提示，exit 0
仅 --payload（无 candidate/kernel-candidate）--------> "入口校验完成…" 提示，exit 0
```

关键守卫：**分身阶段强制 select 形态**。`payload.setup.author_kernel.mode == "create"` 时携带 `--candidate` 直接 FAIL（exit 1），错误文本：

> `FAIL payload 为 create 模式：--candidate 需要 select 形态 payload。建核时加 --emit-payload 产出 bound payload 再用；或把 --kernel-candidate 与 --candidate 放在同一次调用（建核后自动缝合）。`

### 1.4 候选容错解析（parse_candidate_text，两种 kind 共用）

对候选原文（LLM 输出）做**只做安全修复**的解析，顺序：

1. `strip()` 后直接 `JSON.parse`；成功 → 返回，notes=[]。
2. 若以 ```` ``` ```` 开头：剔除所有以 ```` ``` ```` 开头的行后再 parse；成功 → notes 记 `去除 Markdown 代码围栏`。
3. 否则做**字符串感知的括号配平扫描**（跟踪 `in_str`/转义 `esc`；栈收集未闭合 `{[`/`]}`）：栈非空则按逆序补 `}`/`]` 后再 parse；解析成功且**形状校验**通过 → notes 记 `补齐尾部未闭合括号 '{closer}'（结构修复不改动内容）`。
4. 全部失败 → 抛出致命错误（Python 为 `SystemExit(str)` → stderr + **exit 1**），文本固定：

> `候选 JSON 解析失败或字段错位：按协议要求融合智能体重新输出，禁止主控手工改写候选内容（去围栏/尾部补括号等结构性修复除外）。`

形状校验（防「中段缺括号但能 parse」的字段错位）：
- `kind="persona"`：对象含 `parent_version_id` 与 `signature` 两键，`signature` 是对象且含 `sympathies`。
- `kind="kernel"`：对象含 `mode`、`display_name`、`kernel` 三键，`kernel` 是对象且含 `identity`。

notes 每条打印为 `NOTE 候选解析修复: {note}`（内核阶段前缀为 `NOTE 内核候选解析修复: `）。**NOTE 不是 WARN 也不是 FAIL，不影响退出码。**

---

## 2. 判定策略与输出协议

- **FAIL**：追加到 errors，最终统一打印（每行前缀 `FAIL `），随后打印汇总行并以 **exit 1** 结束，**不发生任何写库**。
- **WARN**：即时打印（前缀 `WARN `），只提示不阻断。
- **NOTE**：候选解析修复说明，前缀 `NOTE `。
- 各门汇总行（精确模板）：
  - 入口：`入口校验失败（{n} FAIL / {m} WARN），拒绝继续。` / `入口校验通过（0 FAIL / {m} WARN）。`
  - 内核：`内核校验门失败（{n} FAIL），拒绝落库。` / `内核校验门通过（信封 + author-kernel 深层 + 基底反查）。`
  - 分身：`校验门失败（{n} FAIL），拒绝落库。` / `校验门通过（信封 + 签名 v2 + parent 反查 + 逐字复制 + 条数）。`

### 退出码全表（魔法值）

| 码 | 含义 | 触发点 |
|---|---|---|
| 0 | 成功/干跑/仅入口校验完成/revise 无候选提示 | 各通过分支与 `--dry-run` 分支 |
| 1 | 任一门 FAIL、create 形态带 `--candidate`、候选解析致命失败（SystemExit）、落库守卫 SystemExit、未捕获异常 | §1.3 各分支 |
| 2 | 库文件不存在、payload 读失败、argparse 用法错误（缺参/非法组合） | `parser.error` 一律 exit 2 |

注意：Python `SystemExit("msg")` = stderr 打印 + exit 1（不是 2）。JS 门用 `throw` + 统一顶层捕获映射到相同码。

---

## 3. jsonschema 的使用方式（Python 现状 → ajv 映射）

- 调用形态：`jsonschema.validate(instance, schema)`（函数内延迟 import；venv 版本 **jsonschema 4.26.0**）。
- **Draft 版本**：由各 schema 的 `$schema` 关键字自动选择 → `Draft202012Validator`。ajv 侧须用 `ajv/dist/2020`（Ajv2020 实例），不能用默认 draft-07 实例。
- **format 断言**：未传 `format_checker` → format 关键字仅为注解（本组 schema 也根本没用 `format`）。ajv 默认同样不校验未知 format，无需配置。
- **自定义 format/keyword**：无。未注册任何自定义类型、keyword 或 codec。
- **错误报告**：`jsonschema.validate` **首错即抛**（不做全量收集）。错误定位取 `exc.absolute_path` 以 `/` 连接；根级错误显示 `<root>`。ajv 默认也是首错即停（不开 `allErrors`），语义一致；消息措辞不同属可接受漂移（判定与定位必须一致）。
- schema 特性使用面（ajv 全部原生支持）：`const`、`enum`、`type`（含 `["object","null"]` 联合）、`additionalProperties:false`、`required`、`allOf`+`if`+`then`（条件必填）、`pattern`（ECMA 正则、**部分匹配**语义）、`minLength/maxLength`、`minItems/maxItems/uniqueItems`、`minProperties/maxProperties`、内部 `$ref`+`$defs`。
- `uniqueItems` 按**深度相等**判重（对象/数组也可比）。ajv 同语义。
- 建议 ajv 配置 `strict: false`（消除对 `if/then` 组合的严格告警），校验结果须归一化为 `{path, keyword, message}`。

---

## 4. 入口门步骤全清单（validate_request）

顺序执行；除 E0 外**全部累加**（某步 FAIL 不中断后续步骤，最后一次性汇总）。数据源缩写：`W = window.NOVELOS_WIZARD_DATA`。

| # | 步骤 | 数据来源 | FAIL/WARN | 错误消息模板（{x} 为插值） |
|---|---|---|---|---|
| E0 | 整体 JSON Schema 校验 | `config/schemas/project-create-request.schema.json` | **FAIL（唯一早退点）**：命中即返回，E1–E13 全部跳过 | `结构校验 FAIL [{path}]: {message}`；path=`absolute_path` 以 `/` 连接，根为 `<root>` |
| E1 | `setup.platform ∈ W.channels[setup.channel].platforms` | W.channels | FAIL | `platform={platform!r} 不属于 {ch} 平台列表 {platforms数组}` |
| E2 | `setup.platform_traits === W.platform_traits[platform]`（深比较，键序无关；**词表查不到该平台时整步跳过**） | W.platform_traits | FAIL | `platform_traits 与词表快照不一致（伪造或数据旧版）` |
| E3 | `setup.scale ∈ SCALES`（四档常量，与 schema enum 冗余互为防线） | 脚本常量 SCALES | FAIL | `scale={scale!r} 非四档之一` |
| E4 | `setup.primary_genre ∈ genres[channel]`（兼容 list 或 dict-keys 两种历史形态） | W.genres | FAIL | `primary_genre={g!r} 不在 {ch} 题材库` |
| E5 | `secondary_directions ⊆ W.secondary_directions[ch][primary_genre]`（越界项集合） | W.secondary_directions | **WARN** | `secondary_directions 超出词表（[{超出项}]）——自由发挥或词表需更新` |
| E6 | `emotional_surface 每项 ∈ {t.value → t.pole} 映射` | W.tone_pools[ch] | FAIL | `emotional_surface 不在 {ch} 基调池: [{bad}]` |
| E7 | surface 各项 pole 不同时含 `light` 与 `dark` | 同上（pole 来自 E6 命中项） | FAIL | `emotional_surface 同层 light+dark 互斥: [[值,pole],…]` |
| E8 | `emotional_core ∈ 同一 pool` | W.tone_pools[ch] | FAIL | `emotional_core={c!r} 不在 {ch} 基调池` |
| E9 | `emotional_core ∉ emotional_surface` | — | FAIL | `emotional_core 与 surface 重复` |
| E10 | `aesthetic_styles 每项 ∈ W.aesthetic_styles`（**全局表，不分频道**） | W.aesthetic_styles | FAIL | `aesthetic_styles 超出词表: [{bad_aes}]` |
| E11a | `genre_profile==null && W.genre_profiles[ch+"|"+primary_genre] 存在` | W.genre_profiles（键格式 `"频道|题材"`） | **WARN** | `genre_profile=null 但词表已有该题材包，快照漏带` |
| E11b | `genre_profile!=null && 深比较 != 词表包` | 同上 | FAIL | `genre_profile 与词表快照不一致` |
| E12 | `author_kernel.mode=="select"` → 库内反查链（§6） | DB | FAIL×4 / WARN×2 | 见 §6 |
| E13 | `author_kernel.mode=="create"` → 近重复建核提示 + 孤儿内核提示（§7.3） | DB | WARN×N | 见 §7.3 |

大小写/trim 规则：**全部精确匹配**——不做 lowercase、不做 trim、不做全半角归一。CJK 字面量（含全角括号的四档 scale、`男频|玄幻` 复合键）必须字节级一致。唯一 trim 发生在 §7.3 的相似度计算内部（不回写、不用于存储）。

---

## 5. content_hash 精确算法

```python
def content_hash(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
```

- 输入：**JSON 字符串**（不是原始请求字节），序列化参数 `json.dumps(obj, ensure_ascii=False, indent=2)`。
- 编码：UTF-8 字节流；输出 `sha256:` + 64 位小写 hex（总长 71，与 DB CHECK 约束一致）。
- 序列化格式要点（= Python `indent=2` 风格）：键后 `": "`、项间 `,`+换行、2 空格缩进层级、空容器 `{}`/`[]` 不换行、非 ASCII 原样输出。JS 等价物为 `JSON.stringify(obj, null, 2)`，**但存在漂移点，见 §11 R1**。
- 三处使用，哈希对象各不相同：
  1. **内核资源**：`content_hash(kernel_json)`，其中 `kernel_json = dumps(candidate.kernel, indent=2)`；该 hash 同时作为 `creator_profile_versions.subject_hash`。
  2. **签名资源**：`content_hash(sig_json)`，`sig_json = dumps(candidate.signature, indent=2)`；同时作为新 profile_version 的 `subject_hash` 与 binding 的 `subject_hash`。
  3. **派生资源**（kernel 与 project 两处）：`content_hash(deriv_json)`，`deriv_json = dumps(deriv, indent=2)`；仅入 `resources.content_hash`，不入 subject_hash。
- **不变量：写入 `resources.content` 的字节必须与哈希前像字节完全相同**（Python 经 `CAST(? AS BLOB)` 存 UTF-8 串）。JS 侧：先 `const s = JSON.stringify(sig, null, 2)` → `const h = 'sha256:' + createHash('sha256').update(s,'utf8').digest('hex')` → `db` 绑定时 `Buffer.from(s,'utf8')`。绝不允许「算 hash 用一份序列化、入库用另一份」。

---

## 6. 内核库内反查逻辑

### 6.1 反查 SQL（lookup_kernel_version，三处共用：E12 / K2 基底 / G2 parent / persist 守卫）

```sql
SELECT v.id, v.revision, v.subject_hash, v.profile_id,
       p.display_name, p.status, p.ownership,
       CAST(r.content AS TEXT) AS kernel_json
FROM creator_profile_versions v
JOIN creator_profiles p ON p.id = v.profile_id
JOIN resources r ON r.id = v.content_resource_id
WHERE v.id = ?
```

读回 `kernel_json` 后 `JSON.parse` 取 `.identity`（逐字复制比对面）与 `.growth_log`（revise 追加检查）。node:sqlite 读 BLOB 得 `Uint8Array`，需 `Buffer.from(x).toString('utf8')` 再 parse。

### 6.2 E12：mode=select 入口反查链（顺序固定，全部累加）

设 `ak = setup.author_kernel`，`row = lookup(ak.kernel_version_id)`：

| # | 条件 | 级别 | 消息模板 |
|---|---|---|---|
| E12.1 | `row == null` | FAIL | `kernel_version_id={id!r} 库中不存在`（后续 5 步跳过，E13 不执行） |
| E12.2 | `row.ownership != 'author_kernel'` | FAIL | `kernel_version_id 指向 ownership={o!r} 的版本——只能绑定 author_kernel 内核` |
| E12.3 | `row.status != 'active'` | FAIL | `内核 profile status={s!r}，非 active` |
| E12.4 | `row.subject_hash != ak.subject_hash` | FAIL | `内核 subject_hash 与库内反查不符` |
| E12.5 | `ak.display_name 存在 && != row.display_name` | **WARN** | `内核 display_name 与库不符（库内 {name!r}）` |
| E12.6 | `SELECT MAX(revision) FROM creator_profile_versions WHERE profile_id=row.profile_id` 结果 `newest > row.revision` | **WARN** | `绑定的内核版本非最新（绑定 r{n}，最新 r{m}）——确认是沿用旧版还是改绑新版` |

### 6.3 G2–G7：分身候选门的 parent 反查

前置：payload 必为 select 形态（§1.3 守卫）。`ak = payload.setup.author_kernel`，`row = lookup(ak.kernel_version_id)`：

| # | 条件 | 级别 | 消息模板 |
|---|---|---|---|
| G2 | `row == null` | FAIL | `parent 内核版本库中不存在: {id!r}`；**G3–G9 全部跳过**（含条数检查！） |
| G3 | `candidate.parent_version_id !== ak.kernel_version_id` | FAIL | `parent_version_id 与 payload 绑定的内核版本不符` |
| G4 | `candidate.parent_subject_hash !== row.subject_hash` | FAIL | `parent_subject_hash 与内核库内反查不符` |
| G5 | `candidate.display_name === row.display_name` | FAIL | `display_name 逐字复制内核名——分身须凝聚为本书人格名` |
| G6 | 提取 `identity` 中四列表字段 → `parent_lists`：`core_questions` / `value_axioms` / `aesthetic_commitments` / `creative_axioms`（缺失字段取 `[]`） | （数据准备） | — |
| G7a | `sig.kernel_origin != null && kernel_origin.kernel_version_id !== ak.kernel_version_id` | FAIL | `kernel_origin.kernel_version_id 与绑定内核不符` |
| G7b | `… && kernel_origin.kernel_subject_hash !== row.subject_hash` | FAIL | `kernel_origin.kernel_subject_hash 与内核反查不符` |

**mismatch 处理现状（重要）**：以上全部为硬 FAIL，立即阻断——不存在「mismatch 仅警告放行」路径。唯一的软性出口是 §7.4 的 parent_rationale 标记扫描，它发生在门**通过之后**，且 Python 现状只是打印（见 §7.4 的政策注记）。

### 6.4 K2：revise 基底反查（内核门内）

`base_row = lookup(candidate.base_version)`：

| 条件 | 级别 | 消息模板 |
|---|---|---|
| 不存在 | FAIL | `base_version={bv!r} 库中不存在` |
| `ownership != 'author_kernel'` | FAIL | `base_version 指向非 author_kernel 版本——内核只能修订内核` |
| 新 `kernel.identity.display_name != 基底 identity.display_name` | FAIL | `revise 的 identity.display_name 与基底不一致——修订是演化不是重写` |
| `len(new.growth_log) <= len(base.growth_log)` | FAIL | `revise 的 growth_log 未追加新条目——每次修订必须带本次归因` |

---

## 7. 词表级联与其余专项检查

### 7.1 字段 → 词表对照总表

| payload 字段 | 词表（W.*） | 匹配规则 | 级别 |
|---|---|---|---|
| platform | `channels[channel].platforms` | 精确、成员 | FAIL |
| platform_traits | `platform_traits[platform]` 整体快照 | 深比较（键序无关） | FAIL（词表无此平台则跳过） |
| scale | 常量 SCALES 四档 | 精确 | FAIL |
| primary_genre | `genres[channel]` | 精确 | FAIL |
| secondary_directions（逐项） | `secondary_directions[channel][primary_genre]` | 精确 | **WARN**（越界项列出） |
| emotional_surface（逐项） | `tone_pools[channel][].value` | 精确 | FAIL |
| emotional_surface 极性组合 | 同上 `[].pole` | light/dark 不同共存 | FAIL |
| emotional_core | `tone_pools[channel][].value` | 精确 + 与 surface 不重复 | FAIL×2 |
| aesthetic_styles（逐项） | `aesthetic_styles`（全局） | 精确 | FAIL |
| genre_profile | `genre_profiles["{channel}|{primary_genre}"]` | null 漏带 WARN；非 null 快照深比较 | WARN/FAIL |

tone_pools 元素形如 `{"value":"轻松欢乐","pole":"light"}`；pole ∈ `light|dark|neutral`。genre_profile 包内容形如 `{power_currency_candidates, typical_dilemmas, reader_expectations, taboos}`（比对整体深比较，不逐键）。`style_recommendations` 键**不被门消费**（仅 UI 推荐）。

### 7.2 逐字复制检查（G8/G9，防分身偷懒复制内核）

- 比对面：签名七字段 `SIGNATURE_FIELDS = (sympathies, distrusts, recurring_attention, narrative_principles, forbidden_conveniences, expression_preferences, negative_constraints)` × 内核四列表字段（G6 所列）。
- 规则：签名某字段的某一项 `item` 若与任一父列表任一元素**字符串完全相等**（区分大小写、不 trim、不做子串匹配）→ FAIL：`逐字复制父值 [{field}]: {item前30字符}…`（截断后接省略号 U+2026）。
- 条数：七字段各自长度须满足 `2 ≤ n ≤ 4`，否则 FAIL：`{field} 条数 {n} 超出 2-4`。
- **作用域陷阱**：G8/G9 都在 `parent_lists` 非空（即 G2 反查命中）时才执行；row 缺失时只剩 G2 一条 FAIL。

### 7.3 mode=create 的建核防重（全为 WARN）

1. **近重复素材**（Jaccard 相似度）：新 `kernel_hints` 六字段展平为行集（仅取 list 值，`String(x).trim()`，去空行，Set 去重）。对照既有内核：查询

```sql
SELECT p.display_name, CAST(r.content AS TEXT) AS deriv_json
FROM creator_profiles p
JOIN creator_profile_versions v ON v.profile_id = p.id
JOIN resources r ON r.id = v.derivation_resource_id
WHERE p.ownership = 'author_kernel'
```

  对每行的 `deriv_json.user_input_snapshot.author_kernel.kernel_hints` 同样展平为旧行集；`overlap = |new∩old| / |new∪old|`（并集为 0 则跳过该行）；每个 display_name 取多版本中的最大 overlap；`overlap ≥ 0.8` 即产出 WARN（按名称排序）：
  `内核素材与既有内核「{name}」高度重合（相似度 {score:.2f}）——若非有意另立人格，应改为 select 该内核`
  （score 格式化保留两位小数。）派生资源解析失败（坏 JSON）静默跳过；查询抛 OperationalError（表不存在等）整体跳过。

2. **孤儿内核**：`ownership='author_kernel'` 且其任何 version 都未被 `project_creator_bindings.kernel_version_id` 引用的 profile 名单 → 单条 WARN：
  `库中存在未被任何项目绑定的内核（{名A}、{名B}）——若为此前失败尝试的孤儿，确认后另行清理，勿重复建核`

3. **重名硬闸在内核门 K3**（不是入口门）：`SELECT COUNT(*) FROM creator_profiles WHERE ownership='author_kernel' AND display_name=?` 非 0 → FAIL `display_name 与既有内核重名——内核是跨书根，必须可区分`。

### 7.4 parent_rationale 错配标记扫描（政策敏感点）

门通过后、落库前：

```python
MISMATCH_MARKERS = ("错配警告", "mismatch", "根本冲突", "根本相斥", "调和建议")
if any(m in rationale for m in MISMATCH_MARKERS):
    print("\n!! parent_rationale 含错配警告字样——按协议必须把冲突与调和建议呈报用户裁决，未获裁决不得落库。")
```

Python 现状：**仅打印，不改退出码、不阻断**（协议层要求主控呈报用户裁决）。JS 重实现必须显式抉择：要么原样复刻（打印 + 交由上层编排阻断），要么按红线升级为 FAIL 阻断。无论哪种，标记检测本身（五词子串包含，区分大小写）必须实现并在结果中上报，不允许静默吞掉。

---

## 8. 事务边界与写入（BEGIN IMMEDIATE 单事务）

两个持久化函数各自独立开连接、独立事务。共同设置：`PRAGMA foreign_keys = ON` → `BEGIN IMMEDIATE` → 写入 → `COMMIT`；任何异常 `ROLLBACK` 后重抛；`finally CLOSE`。

### 8.1 persist_kernel（内核落库事务）

写入顺序（FK 依赖决定）：

1. `resources` ← 内核资源：`(id=f"resource:{uuid4()}", media_type='application/json', content=CAST(kernel_json AS BLOB), content_hash=kernel_hash)`
2. `resources` ← 派生资源：content=CAST(deriv_json AS BLOB)，hash=`content_hash(deriv_json)`
3. 分支：
   - **revise**：`creator_profile_versions` 新行 `(id=f"creator-profile-version:{uuid4()}", profile_id=基底.profile_id, revision=COALESCE(MAX(revision),0)+1（限该 profile）, content_resource_id=内核资源id, subject_hash=kernel_hash, parent_version_id=candidate.base_version, derivation_resource_id=派生资源id)`；随后 `UPDATE creator_profiles SET version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=profile_id`
   - **create**：`creator_profiles` 新行 `(id=f"creator-profile:{uuid4()}", display_name=candidate.display_name, ownership='author_kernel')`；`creator_profile_versions` 新行 `(revision=1, parent_version_id=NULL, …同上)`
4. COMMIT。返回 `{kernel_profile, kernel_version, resource_kernel, resource_deriv, subject_hash}`。

内核 deriv_json 结构：

```json
{
  "mode": "create|revise",
  "rationale": "<candidate.rationale>",
  "user_input_snapshot": {                       // 有 --payload 且 setup 为对象时：
    "author_kernel": { "<setup.author_kernel 原样>" },
    "setup": { "<setup 去掉 author_kernel 外的全部键>" }
  },
  // 或 revise 信封（novelos.kernel.revise.v1，无 setup）时：
  // "user_input_snapshot": { "kernel_revise": { "base_version": …, "kernel_hints": … } }
  "base_version": "<仅 revise 分支追加此键>"
}
```

revise 附带提示（COMMIT 后、非阻断）：查询仍绑定该 profile 旧版本的 projects（`project_creator_bindings JOIN creator_profile_versions ON b.kernel_version_id=v.id WHERE v.profile_id=? AND b.kernel_version_id != ?`），有则打印 `{n} 个项目仍绑定该内核旧版本（{ids}）——按裁决制由用户决定跟随新版重派生还是锁定当前分身`。

### 8.2 persist（项目六表单事务）

前置守卫（事务内第一件事）：重新反查 `ak.kernel_version_id`，`row==None || row.ownership!='author_kernel'` → 抛 `绑定的内核版本无效: {id!r}（落库前校验门应已拦截）`（exit 1，连接关闭隐式回滚）。

写入顺序（严格；FK 全 RESTRICT，父行必须先行）：

| # | 表 | 行内容 |
|---|---|---|
| 1 | `resources` | 签名资源：`resource:{uuid4()}`，`application/json`，CAST(sig_json AS BLOB)，hash=sig_hash |
| 2 | `resources` | 派生资源：`resource:{uuid4()}`，hash=content_hash(deriv_json) |
| 3 | `creator_profiles` | `creator-profile:{uuid4()}`，display_name=candidate.display_name，**ownership='user'**（status/version 走列默认 active/1） |
| 4 | `creator_profile_versions` | `creator-profile-version:{uuid4()}`，profile_id=第3步，revision=**1**，content_resource_id=签名资源id，subject_hash=sig_hash，parent_version_id=candidate.parent_version_id（=内核版本），derivation_resource_id=派生资源id |
| 5 | `projects` | `project:{uuid4()}`，name=setup.title，description=模板（下），version=1，metadata_json=meta 紧凑串（下） |
| 6 | `project_creator_bindings` | project_id=第5步，profile_id/profile_version_id=第3/4步，profile_revision=1，subject_hash=sig_hash，binding_mode=**'kernel_derive'**，kernel_version_id=ak.kernel_version_id |

description 模板：`f"{channel}·{primary_genre} | {platform}·{(platform_traits or {}).get('model','')} | {scale}"`（platform_traits 为 null 时 model 段取空串）。

项目 deriv_json 结构（indent=2 资源）：

```json
{
  "parent_version_id": "<ak.kernel_version_id>",
  "parent_display_name": "<反查所得>",
  "parent_subject_hash": "<反查所得>",
  "auxiliary_archetypes": [],
  "rationale": "<candidate.parent_rationale>",
  "user_input_snapshot": {
    "author_kernel": { "<ak 去掉 kernel_hints 后原样>" },
    "setup": { "<setup 去掉 author_kernel 后原样>" }
  }
}
```

### 8.3 表结构要点（摘自 db/migrations/schema.sql v18 终态，JS 门依赖的约束）

- `resources`：`content BLOB NOT NULL`；`UNIQUE(content_hash, media_type)`；`content_hash` CHECK（`sha256:` 前缀 + 总长 71 + body 全 hex）。
- `creator_profiles`：`status CHECK IN ('active','archived') DEFAULT 'active'`；`version INTEGER DEFAULT 1 CHECK(>0)`；`ownership CHECK IN ('system_archetype','user','author_kernel') DEFAULT 'user'`。
- `creator_profile_versions`：`revision CHECK(>0)`，`UNIQUE(profile_id,revision)`；subject_hash 同款 CHECK；四个 FK 全 `ON DELETE RESTRICT`（parent_version_id 自引用）。
- `projects`：`metadata_json TEXT NOT NULL DEFAULT '{}'`；`version DEFAULT 1`。
- `project_creator_bindings`：`project_id PRIMARY KEY`；`binding_mode CHECK IN ('reuse','derive','create','kernel_derive')`；`kernel_version_id` 可空 FK RESTRICT；部分索引 `idx_project_creator_bindings_kernel … WHERE kernel_version_id IS NOT NULL`。
- 时间戳列 `DEFAULT CURRENT_TIMESTAMP`（SQLite UTC `YYYY-MM-DD HH:MM:SS`）——node:sqlite 引擎同源行为，无需应用侧填充。

### 8.4 缝合（_stitch_bound_payload，create 建核后的机械回填）

deep-copy 原 payload 后仅替换 `setup.author_kernel` 为：

```json
{
  "mode": "select",
  "kernel_version_id": "<persist_kernel 返回的 kernel_version>",
  "subject_hash": "<返回的 subject_hash>",
  "kernel_hints": "<原 ak.kernel_hints，缺省 {}>",
  "display_name": "<仅当原 ak.display_name 是 string 时携带>"
}
```

缝合版经 `--emit-payload` 写盘（`dumps(indent=2)`）并同时替换内存 payload，使单次调用即可直连分身阶段；两段式重跑与单次调用的落库快照保证一致。

---

## 9. setup 快照（projects.metadata_json）结构

```json
{"setup_schema_version": 3, "setup": {"<setup 除 author_kernel 外的全部键，原样>"}}
```

- **紧凑单行序列化**：`json.dumps(meta, ensure_ascii=False)` —— 默认分隔符 `, `/`: `（逗号/冒号后带一个空格）。**与资源资源的 indent=2 风格不同**；也与 `JSON.stringify(obj)`（无空格）不同。JS 复刻须选一种紧凑风格并保持稳定（建议自写 `compact = JSON.stringify(obj).replace(/,/g,', ').replace(/:/g,': ')` 的安全实现或在文档固化「用 JSON.stringify 紧凑」这一偏离——metadata_json 当前无人对其做二次哈希，风格偏离不破坏任何校验，但要在规范里点名）。
- `setup_schema_version: 3` 是魔法值，随 request_type v3 固定。
- 快照用途：审计回溯（deriv.user_input_snapshot 同构），运行期不参与校验。

---

## 10. mode=select 与 mode=create 差异总表

| 维度 | mode=select | mode=create |
|---|---|---|
| 入口门 E12/E13 | 库内反查链（4 FAIL + 2 WARN） | hints 相似度 WARN + 孤儿内核 WARN（无 FAIL） |
| schema 约束 | 必带 kernel_version_id+subject_hash（if/then） | 仅必带 mode+kernel_hints |
| 是否动内核 | 不创建内核；绑定既有版本 | 须经内核阶段（K 门 + persist_kernel）产出新内核 profile/version |
| payload 演化 | 直接进分身门 | 建核成功后自动缝合为 select 形态（内存 + 可选 --emit-payload），再进分身门 |
| 分身 parent 关系 | parent_version_id = 用户选定内核版本 | parent_version_id = 本次新建内核版本（缝合回填后同一机制） |
| 分身阶段代码路径 | 完全同一（G 门 + 六表 persist） | 完全同一 |
| 失败面 | 绑定错版本/hash 不符即 FAIL | 重名 FAIL（K3）；近重复仅 WARN |

本质：**create 只是多了「先造被绑对象」的前置段**，分身派生与项目落库对两种 mode 完全对称，parent 恒为某内核版本 id。

---

## 11. 幂等 / 重复创建防护现状

| 机制 | 层 | 级别 |
|---|---|---|
| 内核 display_name 查重（同 ownership='author_kernel'） | K3 | FAIL |
| 建核素材 Jaccard ≥ 0.8 | E13 | WARN |
| 孤儿内核提醒 | E13 | WARN |
| `resources UNIQUE(content_hash, media_type)`：同一候选字节级重复提交（如重跑同一 candidate）会在第 1 次 INSERT 即撞唯一约束 → IntegrityError → 整事务回滚 | DB | FAIL（异常路径） |
| `creator_profile_versions UNIQUE(profile_id, revision)` + IMMEDIATE 锁内 `MAX(revision)+1` | DB | 并发安全 |
| projects.name / setup.title **无**查重——同名项目可重复创建 | — | 无防护（现状如此，JS 门不得擅自加） |
| project_creator_bindings.project_id 主键 | DB | 每 project 至多一条绑定 |

JS 门注意：SQLite IntegrityError 必须显式捕获并转为清晰的 FAIL 报告（含冲突约束名），不能让异常裸奔成 500。

---

## 12. 魔法值总表

| 类别 | 值 |
|---|---|
| request_type | `novelos.project.create.v3`；`novelos.kernel.candidate.v1`；（revise 信封 `novelos.kernel.revise.v1` 仅作载荷约定，门内不校验其 schema） |
| schema_version | author-kernel 内 `const 1`；signature `enum [1,2]`（v2 ⇒ 必须 persona；v1 ⇒ 禁止 persona）；envelope signature.schema_version `const 2` |
| setup_schema_version | `3`（metadata_json 内） |
| ID 前缀 | `resource:` / `creator-profile:` / `creator-profile-version:` / `project:`（+ 小写连字号 UUIDv4） |
| kernel_version_id regex | `^creator-profile-version:[a-z0-9][a-z0-9-]*(:[0-9]+)?$`（允许历史复合后缀 `:N`） |
| hash 格式 | `sha256:` + 64 小写 hex（71 字符） |
| binding_mode | `kernel_derive`（本项目创建固定值；枚举另含 reuse/derive/create） |
| ownership | `user`（分身）/ `author_kernel`（内核）/ `system_archetype`（遗留） |
| status | creator_profiles: `active`/`archived`（绑定要求 active） |
| SCALES | `短篇（30万字以下）`、`中篇（30-100万字）`、`长篇（100-300万字）`、`超长篇（300万字以上）`（全角括号） |
| channel 枚举 | `男频`、`女频`、`全向` |
| SIGNATURE_FIELDS | sympathies, distrusts, recurring_attention, narrative_principles, forbidden_conveniences, expression_preferences, negative_constraints |
| KERNEL_IDENTITY_LIST_FIELDS | core_questions, value_axioms, aesthetic_commitments, creative_axioms |
| MISMATCH_MARKERS | `错配警告`, `mismatch`, `根本冲突`, `根本相斥`, `调和建议` |
| Jaccard 阈值 | `>= 0.8`（相似度显示两位小数） |
| 签名字段条数窗口 | `[2, 4]` |
| 逐字复制截断 | 前 30 字符 + `…` |
| revision 起点 | 1（新建）；revise = MAX+1；binding.profile_revision 固定 1；projects.version 固定 1 |
| 默认路径 | DB `data/novelos-v2.db`；词表 `plugin/client/project-wizard-data.js`；schema 目录 `config/schemas` |
| 退出码 | 0 / 1 / 2（§2 全表） |
| 运行环境注记 | 过渡期 py 门用仓库根 `.venv\Scripts\python.exe`（jsonschema 4.26.0）；全局 Python 不可用 |

---

## 13. legacy-python/scripts 其余含写库操作的脚本清单

评估「唯一写入口 = defineTool」需覆盖的面（grep INSERT/UPDATE/DELETE/commit/ex executescript 实证）：

| 脚本 | 写了什么 |
|---|---|
| `novelos_create_project.py` | 本门：内核事务（resources×2 + creator_profiles + creator_profile_versions ± UPDATE profiles.version）+ 项目六表事务（§8.2） |
| `novelos_register_characters.py` | characters 注册表幂等登记（BEGIN IMMEDIATE 单事务）：INSERT 新人物；重登 UPDATE role_class+state_json 合并（不覆盖 status/exit）；状态迁移 UPDATE status/exit_type/exit_chapter_id + state_json 状态史追加；对账漂移非零退出 |
| `novelos_propagate_stale.py` | planning_assets 上游修订传播：递归收集下游 locked 资产后批量 `UPDATE planning_assets SET status='stale', updated_at=CURRENT_TIMESTAMP`（隐式 deferred 事务 + commit，无 IMMEDIATE） |
| `novelos_delete_project.py` | 项目级联清除：`foreign_keys=OFF` 下按依赖逆序 DELETE（planning_asset_dependencies、reviews、planning_assets、characters、worlds、project_creator_bindings、books、volumes、chapters、projects、项目专属 resources + 可选孤儿清理），isolation_level=None 手动 BEGIN/COMMIT |
| `backup_novelos_database.py` | 不写权威库：生成备份文件 + manifest（sha256），恢复演练写临时副本后 commit |
| `export_novelos_data.py` | 权威库只读：导出确定性 JSONL；恢复演练时对**新导出目标库** executescript(schema.sql)+executemany INSERT+post_schema.sql+commit |

其余（compose_prompt / validate_* 六件套 / novelos_hash / export_kernel_roster / build_adapters / build_catalog_manifest / check_repository_hygiene）均为只读或不触库。R2 收敛后，上述前四个的业务语义须分别成为 host defineTool（create/gate、characters、stale-propagation、delete-project）或明确废弃。

---

## 14. JS 重实现风险点清单（按危险度排序）

**R1 · 哈希前像序列化漂移（最高危）**
`json.dumps(indent=2, ensure_ascii=False)` 与 `JSON.stringify(o,null,2)` 在常见 CJK 场景字节相同，但分歧点真实存在：① 浮点表示（Python `1.0` ↔ JS `1`；大整数 >2^53 在 JS parse 即失真）；② 控制字符/孤立代理对的 `\uXXXX` 转义细节；③ metadata_json 的紧凑串（Python `, `/`: ` 带空格）与 `JSON.stringify` 无空格不同。对策：固定「parse 后立刻序列化一次 → 该字符串同时用作 hash 前像与 BLOB 内容」，用金样向量（含浮点、emoji、CJK 标点）锁 byte-equal 测试；metadata_json 风格单独固化。

**R2 · ajv 与 jsonschema 语义差**
必须用 Ajv2020（$schema 2020-12）；`minLength/maxLength` 在 ajv 按 **UTF-16 code unit** 计数而 Python 按码点计数——含增补平面字符（emoji 等）的标题/文本长度判定可能一边过一边不过；`uniqueItems` 双方都是深度相等；`pattern` 都是 ECMA 部分匹配；Python jsonschema 对 `const/enum` 中 bool 与 int 的相等处理历史上与 JS 严格不等有微妙差异（`schema_version: true` 这类病态输入）——测试集要覆盖边界样本。

**R3 · BLOB 绑定与读回**
node:sqlite 写 BLOB 须传 `Buffer`/`Uint8Array`（传 string 会落 TEXT，破坏「bytes==hash 前像」不变量与后续 `CAST(r.content AS TEXT)` 的消费假设）；读回是 `Uint8Array`，必须显式 utf-8 decode 再 JSON.parse。IntegrityError（UNIQUE(content_hash,media_type) 撞车）要翻译成业务 FAIL + 回滚报告，而非裸异常。

**R4 · 事务纪律**
`PRAGMA foreign_keys=ON` 是**连接级**设置，每个新连接都要重设；node:sqlite 无 pysqlite 式隐式事务管理，须手动 `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK`，且**所有 throw 路径都必须走 ROLLBACK**（Python 里 `except Exception` 接不住 `SystemExit` 的坑证明：控制流异常也要回滚——JS 统一 try/catch/finally 即天然正确，但要写进测试）；六条 INSERT 顺序不可乱（RESTRICT FK）。

**R5 · 深比较与精确匹配语义**
E2/E11b 快照比对必须是键序无关的 deep-equal（naive `JSON.stringify(a)===JSON.stringify(b)` 会因键序误报 FAIL）；全部词表匹配是 CJK 精确匹配——严禁 trim/lowercase/全半角归一；Jaccard 的 trim 只发生在相似度内部。

**R6 · 门序与作用域保真**
E0 是唯一「FAIL 即短路」的步骤；其余步骤全部累加汇总；G8/G9（逐字复制+条数）仅在 parent 反查命中时执行；分身阶段拒收 create 形态 payload；`--dry-run` 在内核阶段会截断后续链路。这些控制流细节决定「同样的坏输入是否报出同样的一组错误」。

**R7 · 政策分歧点：mismatch 标记**
Python 现状 print-only（§7.4）。JS 门若按红线升级为阻断，属于**有意行为变更**而非等价复刻——必须在 R2 任务记录中显式声明，防止「以为等价实则收紧/放松」。

**R8 · 消息与退出码**
`SystemExit(str)`=exit 1、argparse 用法错=exit 2、门 FAIL=exit 1、成功/dry-run=exit 0；WARN/NOTE 前缀协议是主控编排的解析界面，JS 门要保持 `FAIL `/`WARN `/`NOTE ` 行前缀与汇总行模板。

---

## 15. 金样验收清单（建议随 R2 实现）

1. 合法 v3 select payload + 合法候选 → exit 0，六表行数与字段逐一断言。
2. 各 E1–E11 注入坏值 → 对应 FAIL 文案 + exit 1 + 零写入（事务回滚断言）。
3. E5/E11a/E12.5/E12.6/E13 → WARN 出现且 exit 由其他步骤决定。
4. select 绑定不存在/非 author_kernel/非 active/hash 不符 → 四类 FAIL。
5. 候选带围栏/尾部截断/中段错位 → NOTE/NOTE/致命 exit 1 三分支。
6. 逐字复制（四父列表任一命中）与条数 1/5 越界 → FAIL；row 缺失时不触发 G8/G9。
7. create 建核全链：K3 重名 FAIL；缝合 payload 与两段式 --emit-payload 字节一致。
8. 同一 candidate 二次提交 → UNIQUE(content_hash,media_type) 冲突 → FAIL + 回滚。
9. hash 金样：固定 signature JSON 的 sha256 前像字节与 Python 版一致。
10. metadata_json 紧凑串与 deriv/resource indent 串的风格断言。
