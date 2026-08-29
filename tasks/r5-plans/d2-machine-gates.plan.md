# D2 · 机器校验工具链——可执行技术设计

> 状态：`IN PROGRESS`（设计文档，待 G4 红方规格审）
> 归属：R5 知识吸收计划方向2（规划员）。覆盖 R0 canary 脚本 + R2 全部改动（`tasks/R5-knowledge-absorption.md:75-85`、`:102-113`）。
> 红线继承：零 Python、零 npm 依赖（Node 22+ 纯标准库）、不动 schema、不动 composer（方向3）、不动 catalog（R1/方向1 的事）、不动 DB。
> 移植母本（只读参照，不入本仓）：`/Users/yiyi/Documents/refs/lieflat-less-ai-tone/scripts/` 三份 py。

---

## 1. 现状盘点（file:line）

### 1.1 移植母本（三个 py）

| 母本 | 关键位置 | 内容 |
|---|---|---|
| `compare-human-ai.py` | `:16-45`（RULES 字典 17 条，其中 6 条 `(已删)` 仅供复查测量）；`:61-70`（measure：千汉字分母 `re.findall(r"[一-鿿]")/1000`，每规则三元组 频率/总数/覆盖篇数）；`:91-98`（分组稳定性 spread=max/min≤5 稳定，且**不打印各组数值**——语料构成保密） | 句层规则正则 + 分组稳定性方法论 |
| `check-structure.py` | `:16-24`（COMMENT/ANAPHOR/METAPHOR 三个段首正则）；`:27-34`（paragraphs：按行切、strip、`len<8` 或结构前缀 `#`/`\|`/``` ` ```/`>`/`- `/`* `/`!`/`[` 跳过）；`:37-40`（signature 四元组：逗号数、有无冒号、有无括号、`len//15` 长度档）；`:42-50`（isomorphic：滑窗 n 句全同构且 `sigs[0][0]>=1`）；docstring `:5-9` **分母纪律**：结构指标以同类元素为分母（每百段/占非首段%），按千字算会虚高 30 倍 | 段层规则 + 分母纪律 |
| `check-translationese.py` | `:15-37`（MARKERS 21 条，每千汉字）；`:40-49`（BASELINE 4 条对照基准）；`:52-54`（model_of：按文件名切模型） | 翻译腔标记 + 基准对照方法论 |

母本 SKILL 规则编号（`lieflat-less-ai-tone/SKILL.md` 现行版）：1 翻案腔 / 2 顿号罗列 / 3 相邻句同构 / 4 破折号 / 5 冒号滥用 / 6 序数词小标题 / 7 拟人化喻体 / 8 具体数据回写（含名词化）/ 9 禁用起手式 / 10 翻译腔五种（10.1 过长前置定语、10.2 当…时、10.3 前置话题壳、10.4 句首连接词、10.5 这意味着）/ 11 段首零主语评论。**注意**：`compare-human-ai.py` 字典键用的是旧编号（「2 翻案腔」实为现行 SKILL 第 1 条），本设计一律换算为现行编号。

R5 总计划 §1.1（`tasks/R5-knowledge-absorption.md:19-28`）的处置裁定，直接决定本脚本规则分层：
- **收（→ screen 预筛层）**：翻案腔宽触发、顿号罗列、相邻句同构、破折号、翻译腔五种、段首零回指。
- **不收进判级（→ measure 仅测层）**：序数词小标题 / 空转句引列表 / 提示语冒号（论述文专属）、「不作为改写理由」表全部条目（翻译腔 21 标记中低于收录门槛者）。
- 倍率数字只作临时锚点，阈值语义归方向1。

### 1.2 本仓脚本与测试风格

| 文件 | 关键位置 | 风格结论 |
|---|---|---|
| `scripts/novelos-compose-prompt.mjs` | `:52-78` ASSET_DIRS；`:87-102` `fail()`（stderr + exit 1）/`argFail()`（usage + exit 2）；`:300-345` 手写结构校验（报错含字段路径）；`:1238-1247` slotReviewFeedback（只注 blocking+warning）；`:1326-1344` SLOT_REGISTRY；`:1366-1370` 动态槽分发；`:1405` contentHash；`:1461-1536` 手写 CLI 解析 | 手写参数解析 + ExitError 约定；导出纯函数供测试 import（`:55` test-guardrails 即 `await import('./novelos-compose-prompt.mjs')` 取 SLOT_REGISTRY） |
| `scripts/test-guardrails.mjs` | `:15-23` 本地 `check(name, ok, detail)` 计数器；`:91-92` 全 PASS exit 0、任一 FAIL exit 1 | 轻量自研 harness，无测试框架 |
| `scripts/test-compose-prompt.mjs` | `:15` `node:assert/strict`；`:26-28` `await import('file://'+CLI)` 取导出函数；`:34-44` 本地 `test()` runner；`:46-51` `runCli()` 用 `spawnSync` 跑 CLI 断言 exit code | **两种测法混用**：纯函数单测 + CLI 子进程断言。新测试沿用此风格 |

### 1.3 Review Receipt schema 实读（引文验证的输入契约）

`config/schemas/review-receipt-candidate.schema.json`：
- findings 数组（`:40-86`）：每条必填 `severity`（`:47-49` 枚举 `blocking/warning/note/strength`）、`message`（`:54-56`）、`evidence_refs`（`:62-69`）；可选 `code`（`:50-53`，任意非空串——**deny 率留痕的落点，无需 schema 变更**）、`excerpt`（`:59-61`，**引文验证的抽取字段**）、`defer_to_downstream`/`accepted_risk`/`accepted_by`。
- 顶层必填（`:7-15`）：`subject_type/subject_ref/subject_hash/verdict/findings/reviewer_profile/evidence_refs`；`subject_hash`（`:32-35`）pattern `^sha256:[0-9a-f]{64}$`——可复用 composer 的 `contentHash()` 做回执↔草稿版本绑定校验。
- DB 侧落库形态（`.agents/skills/novel-project/sql-reference.md:208`）：`reviews.findings_json` 为 JSON 数组文本——验证脚本须同时接受 candidate 形态（`findings` 数组）与 DB 行形态（`findings_json` 字符串）。

`novel-review/SKILL.md:15` 语义分档：问题类（blocking/warning/note）须给「最小直接证据和原文片段」，`strength` 可只引推理——**引文验证对 strength 从宽**。

### 1.4 工作流接线点现状

- `AGENTS.md` 小说工作流节：步骤 2「`$novel-writing` 起草 → sub agent → 主控按 sql-reference.md 模板落库（draft）」；步骤 3「`$novel-review` 审查：blocking+warning 必修…」。
- `.agents/skills/novel-writing/SKILL.md`：step 1（`:12` 组装注入）、step 6（`:17-27` 落库 draft，含 content_hash 约定）、step 7（`:28` 交审查）。
- `.agents/skills/novel-review/SKILL.md`：step 4（`:15` severity 四档）、step 6（`:17-23` 回执落库模板，findingsJson/reviewerProfile 前缀纪律）、修复循环（`:40-43`）。
- `catalog/skills/craft/prose-anti-ai-fingerprint/prompt.md`（§1-§5，`:5-59`）：现有阈值卡（「不是…而是」≤2 次/章等），R1 轮吸收 lieflat 语言层规则后与本脚本规则号对齐（接口见 §8）。

### 1.5 依赖与缺口

- `data/canary/` **尚不存在**（R0 导入工具产出）→ canary 脚本设计为 `--dir` 可覆盖 + 空目录友好报错（exit 2），测试用临时目录夹具，真跑依赖 R0。
- 本方向三个脚本全部**零 DB 依赖**（文本进、JSON 出），DB 读写仍归主控——符合「sub agent/工具不持库」纪律。

---

## 2. 规则移植总表（逐条）

### 2.1 规则对象数据结构

```js
// scripts/novelos-prose-fingerprint.mjs 顶部（冻结表，ID 一次发布即不可变）
/**
 * @typedef {Object} FprRule
 * @property {string}   id          稳定规则号（finding code = `fpr:${id}`）
 * @property {string}   name        中文名
 * @property {string}   re          正则源串（JS 方言，字符串形态，启动时 new RegExp(re, flags)）
 * @property {string}   flags       'g' | 'gm'（m 用于行锚点规则的 ^ 形态）
 * @property {'screen'|'measure'} tier  screen=预筛候选（注入审查，供证伪）；measure=仅测量（金丝雀/回归用，永不进候选清单）
 * @property {'sentence'|'paragraph'} layer
 * @property {'han_1k'|'para_100'|'nonfirst_pct'} denominator
 * @property {'suppress'|'mask'} dialogue  suppress=句层：命中字符 ≥50% 落在对话掩码内即丢弃；mask=段层：对话以 U+FFFC 等长掩码后参与结构计算
 * @property {string}   skillRef    lieflat SKILL.md 规则号（现行编号）
 * @property {string}   source      母本出处（py:行 / 'd2-ext'）
 */
export const RULES = Object.freeze([ /* §2.2-§2.5 逐条 */ ]);
```

- **规则号不可变**：发布后 ID 永不改义、不复用；新规则只追加。`fpr:<RULE_ID>` 是 finding code 留痕契约（§3.5），改号=破坏审查可追溯性。
- `rule_table_hash = 'sha256:' + sha256(JSON.stringify(RULES.map(({id,re,flags,tier,layer,denominator,dialogue}=>...)))`，进一切输出与基线（规则表变更可被 G1 比对发现）。
- 计 42 条：screen 13（句层 10 + 段层 3）、measure 29。

### 2.2 表 A：compare-human-ai.py `RULES`（17 条逐条）

| 规则号 | 名称 | 正则（JS 字符串形态） | 分母 | 对话 | tier | SKILL 号 | 源 |
|---|---|---|---|---|---|---|---|
| L01 | 翻案腔（窄版） | `(?:不是\|并非\|不在于)[^，。！？\n]{1,20}[，]?(?:而是\|而在于)` flags `g` | han_1k | suppress | **screen** | 1 | py:17 |
| L02 | 顿号罗列过密 | `[^，。！？；：、\n]{1,14}、[^，。！？；：、\n]{1,14}、[^，。！？；：、\n]{1,14}` | han_1k | suppress | **screen** | 2 | py:19 |
| L03 | 破折号 | `——` | han_1k | suppress | **screen** | 4 | py:28 |
| L04 | 提示性冒号 | `(?:一句话(?:总结\|说\|概括)\|简单说\|说白了\|总结\|小结\|结论\|核心(?:是\|在于\|观点)?\|关键(?:是\|在于)?\|重点(?:是)?\|原因(?:如下\|有\|在于)?\|问题(?:是\|在于)?\|答案(?:是)?\|本质(?:是\|上)?\|定义(?:是)?\|具体(?:来说\|如下\|包括)?\|举例(?:来说)?\|换句话说\|也就是说\|我的(?:观点\|判断\|结论)\|建议(?:是)?)[：:]` | han_1k | suppress | measure（R5 §1.1 论述文专属不收） | 5 | py:30-33 |
| L05 | 序数词当小标题 | `^\s*(?:首先\|其次\|再次\|最后\|第一\|第二\|第三\|一方面\|另一方面)[，、]` flags `gm` | han_1k | suppress | measure（同上） | 6 | py:34（原 `(?:^\|\n)\s*` 改 `^`+m，语义等价） |
| L06 | 动词名词化 | `(?:完成\|实现\|进行\|开展)了?(?:对)?[^，。\n]{0,10}的(?:优化\|提升\|调整\|分析\|改造\|升级)` | han_1k | suppress | **screen**（机器只报结构；SKILL 8 的「同段须有具体数据」条件由审查 confirm/deny） | 8 | py:39 |
| L07a | 过长前置定语 | `(?:一个\|一种\|一套\|这种\|这个)[^，。、；：！？\n]{15,}的[一-鿿]{2,5}`（源码写 `[一-鿿]`，实现用 `[\u4e00-\u9fff]`，等价） | han_1k | suppress | **screen** | 10.1 | py:40 |
| L08 | 当…时（从句前置） | `当[^，。\n]{2,20}(?<!的时候)时，`（lookbehind，Node 22 直接支持，见 §2.6） | han_1k | suppress | **screen** | 10.2 | py:41 |
| L09 | 前置话题壳 | `(?:对于[^，。\n]{2,15}来说\|对[^，。\n]{2,15}而言\|就[^，。\n]{2,15}而言\|在[^，。\n]{2,12}方面)` | han_1k | suppress | **screen** | 10.3 | py:42 |
| L10 | 句首连接词当路标 | `^\s*(?:然而\|因此\|此外\|与此同时\|换言之\|总而言之)[，、]` flags `gm` | han_1k | suppress | **screen** | 10.4 | py:43（同 L05 改写） |
| L11 | 这意味着式复述 | `(?:这意味着\|这表明\|这说明\|换句话说)` | han_1k | suppress | **screen**（SKILL 要求「后文与前句同义」——机器只报结构，语义条件归审查） | 10.5 | py:44 |
| M01 | （已删）句内同构-更X | `更[\u4e00-\u9fff]{1,3}[、，][^，。\n]{0,8}更[\u4e00-\u9fff]{1,3}` | han_1k | suppress | measure（母本已删，保留测量） | 不作为表·句内排比 | py:21 |
| M02 | （已删）句内同构-同字两项 | `([\u4e00-\u9fff]{1,2})[^，。、\n]{2,12}[、，]\1[^，。、\n]{2,12}`（反向引用 `\1`，JS 等价，已验证） | han_1k | suppress | measure（同上） | 同上 | py:22 |
| M03 | （已删）就字 | `就` | han_1k | suppress | measure | 不作为表·单字虚词 | py:35 |
| M04 | （已删）很字 | `很` | han_1k | suppress | measure | 同上 | py:36 |
| M05 | （已删）了字 | `了` | han_1k | suppress | measure | 同上 | py:37 |
| M06 | （已删）口语连接词 | `但是\|其实\|不过\|就是` | han_1k | suppress | measure | 同上 | py:38 |

### 2.3 表 B：check-structure.py（段层 4 指标，算法规则非表驱动正则）

| 规则号 | 名称 | 实现要点 | 分母 | 对话 | tier | SKILL 号 | 源 |
|---|---|---|---|---|---|---|---|
| P01 | 相邻句同构（连续 2 句） | signature 四元组 `(逗号数, 含'：', 含'（'或'(', floor(len/15))`；滑窗 2 句全同构且首元逗号数 ≥1；句切分与过滤见 §3.1.3 | para_100 | mask | **screen** | 3 | py:37-50 |
| P02 | 连续 3 句同构 | 同上，窗口 n=3 | para_100 | mask | **screen** | 3 | py:37-50 |
| P03 | 段首零回指 | 非首段 ∧ COMMENT 命中 ∧ ANAPHOR 不命中。COMMENT=`^(?:听起来\|看起来\|看上去\|听上去\|说白了\|说到底\|换句话说\|意味着\|值得注意\|不难看出\|细看\|再看\|回过头看\|问题在于\|原因在于\|结果是\|有意思的是\|更重要的是\|关键在于\|真正的)`；ANAPHOR=`^(?:这\|那\|其\|此\|上面\|前面\|刚才\|以上\|该\|它\|他\|她\|它们\|他们\|同样\|类似\|相比\|反过来\|但\|不过\|所以\|因此\|于是\|而\|另\|除此\|与此)` | nonfirst_pct（占非首段 %） | mask | **screen** | 11 | py:16-22, 61-67 |
| P04 | 比喻起段（对照项） | `^(?:像\|就像\|好比\|好像\|仿佛\|如同\|这就像)`；人类更多，仅测 | para_100 | mask | measure（对照） | 不作为表·比喻 | py:24, 61-63 |

### 2.4 表 C：check-translationese.py `MARKERS` 21 条 + `BASELINE` 4 条

与表 A 重叠 4 条（句首连接词=L10、这意味着=L11、前置话题壳=L09、长前置定语=L07a）→ 不重复建规则；`的…的…的连用` 是 SKILL 10.1 的触发标记之一 → 升为 screen 并入 L07 家族；其余 16 条全部 measure（SKILL 10 实测低于收录门槛 / 列入「不作为改写理由」表——保留测量供金丝雀复评与 G1 回归，**永不进预筛候选**）。

| 规则号 | 名称 | 正则（JS） | 分母 | tier | 源 |
|---|---|---|---|---|---|
| T01 | 被动-抽象 | `被(?:认为\|视为\|称为\|设计为\|应用于\|赋予\|看作)`（捕获组改非捕获，计数不变） | han_1k | measure | py:16 |
| T02 | 受到…的 | `受到[^，。]{0,12}的(?:关注\|影响\|重视\|挑战)` | han_1k | measure | py:17 |
| T03 | 形式主语 | `(?:值得注意的是\|有必要指出的是\|可以说的是\|需要指出的是)` | han_1k | measure | py:18 |
| T04 | 存在着/有着 | `(?:存在着\|有着)` | han_1k | measure | py:19 |
| T05 | 当…的时候（宽版） | `当[^，。]{2,20}(?:的时候\|时)，`（含「的时候」，与 L08 互为宽窄口径） | han_1k | measure | py:20 |
| T06 | 在…的过程中 | `在[^，。]{2,20}(?:的过程中\|的情况下)` | han_1k | measure | py:21 |
| T07 | 如果…的话 | `如果[^，。]{2,20}的话` | han_1k | measure | py:22 |
| T08 | 并列连词密集 | `并且\|而且` | han_1k | measure | py:23 |
| T09 | 轻动词（宽版） | `(?:进行\|作出\|给予\|予以)了?[^，。]{0,6}(?:分析\|调整\|优化\|支持\|评估\|检查\|讨论)`（宽于 L06，含作出/给予/予以） | han_1k | measure | py:24 |
| T10 | 不仅仅是 | `(?:不仅仅是\|远不止是\|不过是\|无非是)` | han_1k | measure | py:25 |
| T11 | 正是/恰恰是 | `(?:正是\|恰恰是)` | han_1k | measure | py:26 |
| T12 | 复数硬译 | `(?:一系列的\|各种各样的\|诸多)` | han_1k | measure | py:27 |
| T13 | 程度直译 | `(?:在某种程度上\|一定程度上\|从某种意义上说\|在很大程度上\|相对而言)` | han_1k | measure | py:28 |
| T14 | 扮演角色 | `(?:扮演\|承担)了?[^，。]{0,8}角色` | han_1k | measure | py:32 |
| T15 | 以一种…方式 | `以一种[^，。]{2,12}的(?:方式\|形式)` | han_1k | measure | py:33 |
| T16 | 使得…能够 | `使得?[^，。]{0,12}(?:能够\|可以)` | han_1k | measure | py:34 |
| L07b | 的…的…的连用 | `的[^，。]{1,8}的[^，。]{1,8}的`（SKILL 10.1「『的』字连续两个以上」标记） | han_1k | suppress | **screen** | py:35→SKILL 10.1 |
| B01 | ［基准］段首序数词（宽版） | `^\s*(?:首先\|其次\|再次\|最后\|第一\|第二\|第三\|一方面\|另一方面)` flags `gm`（宽于 L05：不要求后随 [，、]） | han_1k | measure | py:41 |
| （别名） | ［基准］不是…而是 | 母本 `(不是\|并非)[^，。]{1,20}(，\|)而是`——`(，\|)` 空交替等价于 `，?`，语义被 L01 覆盖，不另建规则 | — | — | 别名→L01 | py:42 |
| （别名） | ［基准］破折号 / ［基准］提示性冒号 | 与 L03 / L04 逐字相同 | — | — | 别名 | py:43-48 |

### 2.5 表 D：D2 扩展（3 条，全部 measure 起步）

R5 计划 R1 提到「翻案腔宽触发变体清单」，SKILL 1 的宽变体在母本中无正则。按 G1 纪律（新增条目单项误报 >0 必须降级或撤回），扩展规则一律从 measure 起步，金丝雀误报为 0 且方向1 出判据文本后才可升 screen：

| 规则号 | 名称 | 正则（JS） | 分母 | tier | 依据 |
|---|---|---|---|---|---|
| L01b | 翻案腔变体·与其说 | `(?:与其说\|与其讲)[^，。！？\n]{1,20}(?:不如说\|倒不如说\|毋宁说)` | han_1k | measure | SKILL 1 |
| L01c | 翻案腔变体·表里翻转 | `(?:表面上?\|看似\|看上去)[^，。！？\n]{1,20}(?:实际上?\|实则\|其实)` | han_1k | measure（叙事文高频，误报风险高，金丝雀先测） | SKILL 1 |
| L01d | 翻案腔变体·裁决腔 | `(?:^|[。！？\n])(?:说到底\|归根结底\|答案恰恰相反)` | han_1k | measure | SKILL 1 |

**screen/measure 升降级机制**（接口给方向1，见 §8）：tier 是 RULES 表中的字面量，升降级=改表+跑 `novelos-canary.mjs --compare` 验证误报不升，任何升降级都改变 `rule_table_hash` 被 G1 追踪。

### 2.6 py→JS 语义差异与适配清单（逐条）

| # | 差异点 | 适配方案 |
|---|---|---|
| 1 | `(?<!的时候)` lookbehind（L08，py:41） | JS ES2018 支持，Node 22（V8）完整可用且**支持变长 lookbehind**（比 Python `re` 的定宽限制更宽）。已实测 `当他推门时，…进门的时候，` 只命中前者。直接移植，无适配。浏览器场景才需担心（Safari<16.4 不支持），本仓 Node-only 无此问题。 |
| 2 | `[一-鿿]` 汉字区间（= U+4E00..U+9FFF，CJK 统一表意文字基本区） | 保留母本口径，源码写 `[\u4e00-\u9fff]`。**不用** `\p{Script=Han}`：后者含日文汉字/韩文汉字用字且需 `u` flag（见 §9 来源），而母本全部倍率数字基于基本区口径，换口径=破坏可比性。扩展 B/G 区生僻字不计入（与母本一致，可接受，记录在案）。 |
| 3 | `re.findall` 带捕获组返回组内容而非全匹配（如 M02、translationese 原版 `被(...)`） | 统一改 `String.prototype.matchAll` + 取 `m[0]` 全匹配：计数等价（每匹配产出一项），且 excerpt 直接可用。捕获组一律改非捕获（计数不变），仅 M02 保留捕获组（`\1` 反向引用需要）。 |
| 4 | `(?:^|\n)\s*` 行锚点（L05/L10/B01） | 改 `^` + `m` flag（`^\s*...` /gm），语义等价。注意 JS `\s` 与 py3 str 模式一致，均含 U+3000 全角空格——中文缩进恰好被消化，无害。 |
| 5 | `(，\|)` 空交替（BASELINE 不是…而是） | JS 合法但等价于 `，?`，且被 L01 覆盖，按别名处理不移植。 |
| 6 | `re.split(r"[。！？]", para)` 句切分消耗分隔符 | JS `para.split(/[。！？]/)` 行为一致：**句末符不留在句子内**，`len>10` 过滤口径不变。半角 `!?` 不是句边界（母本口径，保持）。 |
| 7 | `len(sent) // 15` 长度档 | `Math.floor(sent.length / 15)`（长度恒正，floor==trunc）。`sent.count('，')` → `(s.match(/，/g) ?? []).length`。 |
| 8 | Python 字典序稳定性（RULES 遍历序=插入序） | JS 对象字面量插入序同样稳定；RULES 用数组，天然有序。 |
| 9 | py 正则字符串无双重转义问题（r-string） | RULES 表用 JS 字符串形态，`\n`、`\\1` 需转义；测试用例覆盖每条规则编译通过 + 1 正例命中（防转义错）。 |
| 10 | 母本 `re.compile` 无 flags 直译 | 表中 flags 字段显式声明；启动时全表 `new RegExp(re, flags)` 编译，任一抛错即 fail-fast exit 1。 |

---

## 3. 改动清单（含核心代码骨架）

新增 4 个文件（scripts/ 下 3 工具 + 1 测试），修改 3 个文件各 1 处（AGENTS.md + 两个 SKILL.md 的接线行，§3.5）。全部零 npm、零 DB、零 schema、零 catalog 改动。

### 3.1 `scripts/novelos-prose-fingerprint.mjs`（新建，核心）

**模块划分**（单文件内分节，风格对齐 composer 的 `// ---- 分节注释`）：

```
novelos-prose-fingerprint.mjs
├── 常量区    PROG/VERSION/FILLER('\uFFFC')/结构行前缀表/引号字符集
├── RULES     §2 规则表（冻结）+ ruleTableHash()
├── 文本层    splitParagraphs() / buildDialogueSpans() / buildDialogueMask()
│             / maskParagraph() / splitSentences() / signature()
├── 引擎层    runSentenceRules() / runIsoWindows() / runZeroAnaphora()
│             / runParagraphRules() / analyze()
├── 输出层    toHumanTable() / toReport()
└── CLI       手写参数解析（--text-file/--stdin/--json/--all/--rules/--max-hits/--pretty/--stable）
```

**3.1.1 分段与 md 结构行排除**（母本 check-structure.py:27-34 口径，逐行=段）：

```js
export const STRUCTURAL_PREFIXES = ['#', '|', '```', '>', '- ', '* ', '!', '['];
/** 按行切段：strip 后 len>=8 且非结构行 → prose 段（1-based 序号）；其余记 structural 段（不编号）。 */
export function splitParagraphs(text) {
  return text.split('\n').map((raw, i) => {
    const p = raw.trim();
    const structural = p.length === 0 || p.length < 8
      || STRUCTURAL_PREFIXES.some((pre) => p.startsWith(pre));
    return { lineIndex: i, text: p, proseIndex: structural ? null : proseCounter++, start, end };
  });
}
```

（表格行 `|`、代码块行 ```` ``` ````、标题 `#`、列表 `- `/`* `、引用 `>`、图片 `!`、链接 `[` 全排除——小说草稿为 md 存储，正文段天然不受影响。）

**3.1.2 引号配对与对话掩码**（引号任意深度嵌套超出正则语言能力，须栈式扫描，见 §9 来源 8-10）：

```js
// 引号字符集（体例依据见 §9 来源 11）：简体弯引号 ""''、港台直角引号「」『』、直引号 " 保守处理为开关
const OPEN  = new Set(['\u300C' /*「*/, '\u300E' /*『*/, '\u201C' /*“*/, '\u2018' /*‘*/]);
const CLOSE = new Set(['\u300D' /*」*/, '\u300F' /*』*/, '\u201D' /*”*/, '\u2019' /*’*/]);
const FAMILY = { '「': 'corner', '『': 'corner', '“': 'curly', '‘': 'curly' }; // 闭引号按家族弹栈

/**
 * 逐段扫描（引号不跨段），栈式配对：
 *  - 开引号压栈 {char, idx}；闭引号弹同家族最近开引号（无匹配开引号则忽略：孤闭引号）；
 *  - 直引号 " 为翻转开关（中西文混排兜底）；
 *  - 段尾未闭合的开引号：掩到段尾（网文未闭合续引的保守处理——多掩=少报=少误报，向 G1 假阳性约束倾斜）；
 *  - 返回 spans: [{start, end}]（含引号本身，全文 char 坐标）。
 */
export function buildDialogueSpans(paragraphs) { /* 栈扫描，O(n) */ }

/** 掩码：Uint8Array(text.length)，对话内=1；供句层命中抑制按坐标查询。 */
export function buildDialogueMask(text, spans) { /* ... */ }

/** 等长掩码：对话 span（含引号）替换为 FILLER('\uFFFC')。长度保持 → 句序/段长档/坐标不漂移。
 *  FILLER 不属于 [。！？]（对话内句末符被掩 → 不产生假句边界）、不属于任何规则字符类（『，』等），
 *  句法指纹（逗号数/冒号/括号）自动只统计叙述层。 */
export function maskText(text, spans) { /* ... */ }
```

**3.1.3 中文分句与句序**（强边界=。！？，与母本及 W3C clreq「句末点号」一致；省略号/分号/冒号不作句边界——母本口径，冒号逗号作边界不可靠，见 §9 来源 4/7）：

```js
/** 掩码后段内分句：split(/[。！？]/) → strip → 过滤 len<=10 → 记录 {text, sentIndex, fillerRatio}。
 *  fillerRatio = FILLER 字符占比。fillerRatio >= 0.5 的句子（近纯对话句）标记 break=true：
 *  不进同构滑窗，且**断开相邻性**（隔对话的两叙述句不算「相邻句」）。 */
export function splitSentences(maskedPara) { /* ... */ }
```

**3.1.4 引擎与分母纪律**：

```js
/** 句层：在原文上跑正则（保坐标可回指原文），命中后做对话抑制——
 *  命中字符中掩码=1 的数量 * 2 >= 命中长度 → 丢弃（“引号内不检”，≥50% 口径，确定可测）。 */
export function runSentenceRules(text, mask, paragraphs, rules, maxHits) {
  // for rule of rules: for (const m of text.matchAll(compiled)) { 定位 prose 段/句序; 抑制判定; push hit }
}
export function signature(sent) {
  return [countChar(sent, '，'), sent.includes('：'),
          sent.includes('（') || sent.includes('('), Math.floor(sent.length / 15)];
}
export function runIsoWindows(sentences, n) { // P01/P02：滑窗全同构 && sig[0][0]>=1；break 句断窗 }
export function runZeroAnaphora(proseParas) { // P03：i>0 && COMMENT.test(掩码段) && !ANAPHOR.test(掩码段) }

/** 总入口。stats 分母全部取叙述层（对话抑制后），与分子口径一致：
 *  han_1k 分母 = 掩码后 [\u4e00-\u9fff] 计数（非全文汉字数）——【与母本的口径偏差，声明】
 *  母本语料无对话故金丝雀基线不受影响；草稿对话占比 30%+ 时若分母含对话会把密度稀释 ~1/3，不可比。 */
export function analyze(text, { tiers = ['screen'], rules = null, maxHits = 20 } = {}) {
  // → { schema, tool, input, stats, rules: [{id, name, tier, layer, denominator,
  //      denominator_value, count, density, hits: [{rule_id, para, sent, offset, excerpt, context, in_dialogue}]}] }
}
```

**输出 JSON schema**（`--json`，schema 标识 `novelos.prose-fingerprint.v1`）：

```json
{
  "schema": "novelos.prose-fingerprint.v1",
  "tool": { "name": "novelos-prose-fingerprint", "version": "1.0.0", "rule_table_hash": "sha256:…" },
  "input": { "source": "file", "label": "novels/xx/…/ch001.md" },
  "stats": { "han_chars_total": 3120, "han_chars_narration": 2210, "dialogue_ratio": 0.29,
             "lines_total": 88, "paragraphs_prose": 60, "paragraphs_nonfirst": 59, "sentences": 210 },
  "rules": [
    { "id": "L01", "name": "翻案腔（窄版）", "tier": "screen", "layer": "sentence",
      "denominator": "han_1k", "denominator_value": 2.21,
      "count": 3, "density": 1.36,
      "hits": [ { "rule_id": "L01", "para": 3, "sent": 2, "offset": 187,
                  "excerpt": "不是引路的灯，而是", "context": "他手里提的…不是引路的灯，而是一截…烧剩的麻绳",
                  "in_dialogue": false } ] }
  ]
}
```

字段口径：`para`=prose 段 1-based 序号（结构段不编号）；`sent`=段内句序 1-based（段级规则=0）；`offset`=全文字符偏移（掩码前原文坐标）；`density` 单位随 denominator（每千叙述汉字 / 每百叙述段 / 占非首段%）；每规则 hits 截 `--max-hits`（默认 20，注入体积纪律），被截断时附 `hits_truncated: true`。`--stable` 省略时间戳字段保证确定性输出（测试与基线 diff 用）。

**CLI**：

```
node scripts/novelos-prose-fingerprint.mjs --text-file <草稿.md> [--json] [--all] [--rules L01,L03] [--max-hits 20] [--pretty] [--stable]
cat 草稿.md | node scripts/novelos-prose-fingerprint.mjs --stdin --json
```

- 默认输出人类可读表格（规则/计数/密度/首个 excerpt）；`--json` 输出上述结构。
- **exit code：成功恒 0**——本脚本「只报事实不判级」（R5 计划 R2 改动 1 的原文约束），命中多少都不该让主控把它当失败；1=内部错误，2=用法错误（对齐 composer 的 fail/argFail 约定）。

### 3.2 `scripts/novelos-canary.mjs`（新建，R0 交付 + G1 常驻）

**职责**：对人类金丝雀语料（`data/canary/*.md`，R0 产出；递归收集，跳过 `_meta` 目录——母本约定）跑全部 42 条规则（含 measure），产出**基线 JSON**；`--compare` 对比两份基线（或重跑现语料 vs 旧基线），回归即 exit 1（G1 机器门）。人类语料上 screen 规则的任何命中=误报（G1 定义）。

```js
import { analyze, RULES, ruleTableHash } from './novelos-prose-fingerprint.mjs';

// 语料装载：--dir（默认 data/canary）递归 *.md；分组 = 顶级子目录匿名化为 g1/g2…（母本纪律：不打印各组数值，防语料构成泄露）
// 每规则汇总：count / rate（分母=各规则 denominator，叙述层口径）/ docs_hit / docs_total / stability_spread（组间 max÷max(min,0.01)，≤5 稳定）
// 基线 JSON（schema: novelos.canary-baseline.v1）：
{
  "schema": "novelos.canary-baseline.v1",
  "generated_at": "2026-…",
  "tool": { "script": "novelos-canary", "fingerprint_version": "1.0.0", "rule_table_hash": "sha256:…" },
  "corpus": { "dir": "data/canary", "files": 18, "han_chars_total": 132000, "han_chars_narration": 131200,
              "paragraphs_prose": 940, "groups": [{ "label": "g1", "files": 6 }],
              "group_labels_are_anonymous": true },
  "rules": {
    "L01": { "tier": "screen", "count": 12, "rate": 0.091, "rate_unit": "per_1k_han",
             "docs_hit": 3, "docs_total": 18, "stability_spread": 2.4,
             "adjudication": null, "notes": null }   // ← 预留字段，方向1 填判据文本（§8 接口）
  }
}
```

**`--compare` 判定**（阈值语义归方向1，脚本给机制）：对每个规则，`new_rate > old_rate + tolerance`（默认 tolerance=0）且 `new_count > old_count` → 回归；旧基线无此规则且新跑 count>0 → 回归（新增条目误报>0 必须降级/撤回，R5 计划 G1 原文）；`rule_table_hash` 变化时输出变更清单（哪些规则 tier/正则动了）要求人工确认。输出对比表 + exit 0/1。

**CLI**：

```
node scripts/novelos-canary.mjs                                          # 现场测量，打印每规则误报计数/误报率
node scripts/novelos-canary.mjs --write-baseline docs/knowledge/canary-baseline.json   # R0 落基线
node scripts/novelos-canary.mjs --compare docs/knowledge/canary-baseline.json [--tolerance 0.02]
```

空/缺目录：打印「金丝雀目录不存在（R0 未跑？）」exit 2。**不访问 DB**。md 报告（`docs/knowledge/canary-baseline.md`）由 R0/主控从 JSON 手工整理，脚本只产 JSON（单源纪律）。

### 3.3 `scripts/novelos-verify-review-evidence.mjs`（新建，G2 引文验证）

**职责**：抽取 Receipt 每条 finding 的 `excerpt`，与草稿做**归一化字符串命中**；对不上=纸面化=exit 1 供主控打回。同时校验 `subject_hash` ↔ 草稿 content_hash 绑定（复用 composer 的 `contentHash`，零重复实现）。

**归一化策略**（`normalizeForMatch(s)`，空白/全半角标点）：

```js
// 顺序：① 全角 ASCII 区折叠 FF01-FF5E → -0xFEE0（ａｂｃ→abc，！→!）；U+3000→' '
//      ② 中西标点等价折叠到半角 canonical: ，→,  。→.  ；→;  ：→:  ！→!  ？→?  （→(  ）→)  ．→.
//      ③ 引号折叠：「『“‘ → " ，」』”’ → "（开闭统一；excerpt 引文嵌引号不致错杀）
//      ④ 破折号：—— 与 – 折叠为单个 —（em-dash）            ⑧ ……
//      ⑤ 省略号：\.{2,} 与 …+ 折叠为单个 …
//      ⑥ 删全部空白 \s+ → ''（换行断句的引文照常命中）
export function normalizeForMatch(s) { /* 纯函数，导出供测试 */ }
```

**判定逻辑**：

```js
// receipt 兼容两种形态：candidate（findings 数组）/ DB 行（findings_json 字符串）——检测键名分发
// 逐 finding：
//   severity ∈ {blocking, warning}：必须有 excerpt 且 normalize 后 includes 命中 → 否则 FATAL(no_hit / missing_excerpt)
//   severity = note：excerpt 缺失 → ADVISORY(missing_excerpt)；给了就必须命中（no_hit 亦 ADVISORY）……--strict 下全部升 FATAL
//   severity = strength：豁免（SKILL 允许纯推理），但 excerpt 给了则照验（no_hit=ADVISORY）
//   normalize 后长度 < 6 → 标记 weak_excerpt（ADVISORY：过短引文到处能命中，证据力存疑，报告但不打回）
// subject_hash 校验（默认开，--no-check-hash 关）：receipt.subject_hash === contentHash(draft) → 不等 FATAL(hash_mismatch)
//   ——回执若是对着另一版草稿写的，同样判纸面化
```

**输出**（schema `novelos.review-evidence-verify.v1`）：

```json
{
  "schema": "novelos.review-evidence-verify.v1",
  "receipt": { "verdict": "rejected", "reviewer_profile": "model:…", "subject_hash": "sha256:…",
               "subject_hash_match": true, "findings_total": 8 },
  "draft": { "source": "ch001-draft.md", "content_hash": "sha256:…" },
  "findings": [
    { "index": 0, "severity": "blocking", "code": "fpr:L01", "excerpt_head": "不是引路的灯…",
      "status": "hit", "fatal": false, "detail": "命中 1 处（offset≈187）" },
    { "index": 3, "severity": "blocking", "code": null, "excerpt_head": "整体节奏拖沓…",
      "status": "no_hit", "fatal": true, "detail": "归一化后未在草稿命中" }
  ],
  "summary": { "hit": 6, "no_hit": 1, "missing_excerpt": 0, "weak_excerpt": 1, "exempt": 0 },
  "verdict": "FAIL"
}
```

**CLI**：`node scripts/novelos-verify-review-evidence.mjs --receipt <路径|以{开头的内联JSON> --draft <草稿路径> [--stdin-draft] [--json] [--strict] [--no-check-hash]`。exit：0=通过（可落库）；1=存在 FATAL（打回重审）；2=用法错。`--receipt` 内联 JSON 约定复用 composer `--review-feedback` 的既有习惯（composer 头注释 `:27-29`）。

### 3.4 `scripts/test-prose-fingerprint.mjs`（新建，测试）

风格照抄 `test-compose-prompt.mjs`：`node:assert/strict` + 本地 `test()` runner + `spawnSync` runCli；夹具全部**内嵌字符串常量 + `fs.mkdtempSync(os.tmpdir())` 临时目录**（不新增仓库夹具文件）。规划用例（≥70）：

**A. 算法层（分句/掩码/分段/签名）**
1. 分段：md 结构行（`# 标题` / `- 列表` / `| 表格 |` / ``` 代码块 ``` / `> 引用`）不编号；`len<8` 短行排除；prose 段 1-based 连续编号。
2. 引号配对：「」配对、「中嵌『』」嵌套、`“…”` 配对、孤闭引号 `」` 忽略、未闭合 `「` 掩到段尾、`"` 翻转开关、引号不跨段。
3. 掩码：等长（`masked.length === text.length`）；对话内 `。！？` 不产生句边界（`他说："走吧。我们回家。"` → 掩后 1 句）。
4. 分句：`。！？` 切分消耗分隔符；`？！` 连用产空片被 len>10 滤掉；fillerRatio≥0.5 句标记 break 且断同构窗。
5. signature：逗号数/全角冒号/中英括号/长度档四元组正确；15 字边界档位。

**B. 规则层（screen 13 条每条 ≥1 正 1 负 + 对话抑制）**

每条正例取自 SKILL.md 触发标记（如 L01「真正的壁垒不是技术，而是认知」、L02「采集、存储、展示」、L08「当所有人都能用 AI 写文章时，内容…」、P03 非首段「听起来像一条功能描述…」无回指 → 命中、加「这」前缀 → 不命中、首段 → 恒不命中）；负例为语义近似但不满足触发（L01 只有「不是」无「而是」；L08「…的时候，」被 lookbehind 排除）。对话抑制统一例：`"这里不是A而是B。"` 弯引号内整句 → L01 count=0；`他说："——"` → L03 count=0；跨边界命中（叙述起句引号收尾）保留与否按 ≥50% 口径断言。measure 规则（29 条）逐条 1 正例循环（母本标记词直接构造）+ 编译完整性（42/42 `new RegExp` 不抛）。

**C. 分母正确性构造例**
1. han_1k：998 个叙述汉字 + 1 句含 2 处 L01 → `density === 2.0`（denominator=1.0 千字）。
2. 对话稀释免疫：上例再加大段对话（500 汉字引号内）→ `han_chars_narration` 不变、density 仍 2.0（分母叙述层口径）。
3. para_100：100 prose 段恰好 3 段各含 1 处同构二连 → P01 density=3.0；P02 构造 1 处三连 → 1.0。
4. nonfirst_pct：10 段，段 3 命中零回指、段 5 有「这」回指 → count=1、nonfirst=9、pct≈11.11。
5. 首段豁免：P03 在段 1 → 恒 0（母本 `i==0: continue`）。

**D. CLI 子进程断言**：`--stdin` 与 `--text-file` 等价；`--json` 可 `JSON.parse` 且 schema 标识正确；`--stable` 两次运行输出逐字节相同；`--rules L01` 只跑单规则；`--max-hits 1` 截断标记；错误用法 exit 2；成功（哪怕大量命中）exit 0。

**E. canary（spawnSync + tmpdir 夹具）**：临时目录放 2 个子目录各 2 篇小文 → 基线 JSON 结构断言（匿名分组标签、docs_total、rate）；人为构造 L01 命中的语料 → count>0 进基线；`--compare` 用同一语料 → exit 0；改夹具加一条 L01 命中再 compare → exit 1（回归被机器抓住）；tolerance 生效。
**F. 引文验证（spawnSync + tmpdir 假回执）**：真引文（原句、换行断开版、全角逗号→半角版、`「`→`“` 版）→ hit/exit 0；编造引文（草稿不存在的句子）→ no_hit/exit 1；blocking 缺 excerpt → missing_excerpt/exit 1；note 缺 excerpt → ADVISORY/exit 0、`--strict` exit 1；strength 无 excerpt → exempt；subject_hash 对不上 → hash_mismatch/exit 1；DB 行形态（findings_json 字符串）解析成功；4 字超短引文 → weak_excerpt 标记。

### 3.5 主控工作流接线点（3 处编辑 + deny 率留痕约定）

**① `AGENTS.md`「小说工作流」节**——步骤 2 行（「`$novel-writing` 起草 → sub agent → 主控按 sql-reference.md 模板落库（draft）。」）之后**追加一句**（同段内）：

> 落库前后跑机器预筛自查：`node scripts/novelos-prose-fingerprint.mjs --text-file <草稿> --json` 产出候选清单（只报事实不判级），screen 计数摘要写入章节 `metadata_json` 的 `prescreen` 字段（`{tool, rule_table_hash, screen_counts:{L01:n,…}}`）；候选清单经组装器注入审查侧（标注「仅供证伪，须逐条 confirm/deny」，注入槽由方向3 落地）。

步骤 3 行（「`$novel-review` 审查：blocking+warning 必修…」）**追加一句**：

> 回执落库前先过 G2 引文验证：`node scripts/novelos-verify-review-evidence.mjs --receipt <回执> --draft <该版草稿>`，exit 1 = 纸面化回执，打回重审，不得落库；任何规则/阈值/catalog 文风卡变更后跑 `node scripts/novelos-canary.mjs --compare docs/knowledge/canary-baseline.json` 守 G1（回归即先降级再查因）。

**② `.agents/skills/novel-writing/SKILL.md`** step 6（落库 draft 段，`:17-27`）**末尾追加一句**：

> 落库前后跑 `node scripts/novelos-prose-fingerprint.mjs --text-file <草稿> --json` 预筛自查（只报事实不判级，命中不阻断落库），摘要写入章节 metadata_json 的 `prescreen` 字段——预筛候选是审查侧证伪线索，不是写作方的整改清单。

**③ `.agents/skills/novel-review/SKILL.md`** 工作流 step 4 之后**插一行**（step 编号顺延）：

> 4.5 对注入的机器预筛候选清单逐条表态（G3）：确认成立 → 该 finding 的 `code` 写 `fpr:<规则号>`（如 `fpr:L01`）；否认 → 落一条 `severity:'note'` 的 finding，`code` 写 `fpr-deny:<规则号>`，message 给 deny 理由。禁止照抄机器结论不表态（deny 率趋零=锚定偏差告警项）。回执落库前由主控跑 `novelos-verify-review-evidence.mjs` 引文验证。

**deny 率采集点（G3，零 schema 变更）**：完全复用 `findings[].code` + `severity` 现有字段——`fpr:<ID>`（confirm）/`fpr-deny:<ID>`（deny+理由）；deny 率 = Σ`fpr-deny:` ÷ (Σ`fpr:` + Σ`fpr-deny:`)，可 SQL 统计（`SELECT … FROM reviews WHERE findings_json LIKE '%fpr-deny:%'`）；预筛候选总数在章节 `metadata_json.prescreen.screen_counts` 留痕（分子分母两侧都可查）。**若未来需要结构化专用字段（deny 理由分类等），声明为与方向4/5 的合并接口**（review-receipt-candidate.schema.json finding 层扩展），本方向不单独动 schema。

**候选注入格式契约（给方向3 的渲染输入）**：fingerprint `--json` 的 `rules[]`（tier=screen）渲染为：

```
## 机器预筛候选（只报事实不判级；仅供证伪，须逐条 confirm/deny）
| 规则 | 计数 | 密度 | 位置与原文片段（节选） |
| L01 翻案腔 | 3 | 1.36/千字 | 段3·句2「不是引路的灯，而是…」 |
表态格式：确认 → finding code=fpr:<规则号>；否认 → note code=fpr-deny:<规则号> + 理由
```

---

## 4. 执行步骤（带验证命令）

| 步 | 内容 | 验证命令 | 通过标准 |
|---|---|---|---|
| 0 | 建骨架：fingerprint 常量区+RULES 表（先只填 screen 13 条）+ CLI 骨架 | `node --check scripts/novelos-prose-fingerprint.mjs && printf '真正的壁垒不是技术，而是认知。' \| node scripts/novelos-prose-fingerprint.mjs --stdin --json` | exit 0，L01 count=1 |
| 1 | 文本层：分段/引号配对/掩码/分句/signature + 测试文件 A/B(screen)/D 节 | `node scripts/test-prose-fingerprint.mjs` | A、B、D 全 PASS |
| 2 | 段层引擎：P01/P02/P03/P04 + 分母口径 + 测试 C 节 | `node scripts/test-prose-fingerprint.mjs` && 手工构造 100 段夹具（内嵌测试） | C 全 PASS（density 断言精确相等） |
| 3 | measure 全量（表 A 余 6 + 表 C 16 + B01 + 表 D 3）+ 启动编译自检 | `node scripts/novelos-prose-fingerprint.mjs --stdin --all --json < 任意md` | 42 规则全部出现在报告 |
| 4 | `novelos-canary.mjs` + 测试 E 节（tmpdir 夹具） | `node scripts/test-prose-fingerprint.mjs`；真跑待 R0：`node scripts/novelos-canary.mjs --write-baseline docs/knowledge/canary-baseline.json` | E 全 PASS；R0 就绪后基线含每规则误报计数 |
| 5 | `novelos-verify-review-evidence.mjs` + 测试 F 节 | `node scripts/test-prose-fingerprint.mjs`（F 节含假回执被抓断言） | 假回执 exit 1、真引文（含换行/标点变体）exit 0 |
| 6 | 接线：AGENTS.md + 两个 SKILL.md 三处编辑（§3.5 措辞，独立 commit） | `node scripts/test-guardrails.mjs && node scripts/test-compose-prompt.mjs && node scripts/test-render-projection.mjs` | 全部既有测试不退化 |
| 7 | 冒烟：对库内真实章节草稿（只读 SELECT 导出临时 md）全流程 | `node scripts/novelos-prose-fingerprint.mjs --text-file /tmp/ch.md --json` → 人造回执 → verify | 全链路 exit 语义正确；基线首跑数字呈报用户（R0 裁决点） |

每步独立 commit，可单独回退；步骤 4 的真实基线运行**依赖 R0 完成**（`data/canary/` 存在），不阻塞其余步骤。

---

## 5. 对抗门设计

| 门 | 本方向的机器实现 | 防什么 |
|---|---|---|
| **G1 金丝雀回归** | `novelos-canary.mjs --compare`：任一规则误报率上升/新增规则误报>0 → exit 1；`rule_table_hash` 变更清单强制呈报 | 规则越收越紧（假阳性无约束）——升降级 tier 必须过此门 |
| **G2 引文机器验证** | `novelos-verify-review-evidence.mjs`：编造引文 no_hit / 缺 excerpt / hash 错配三路 FATAL；主控按 exit 1 打回 | 「多处/整体」式纸面化审查；回执对错版本草稿 |
| **G3 deny 率采集** | `fpr:`/`fpr-deny:` code 留痕 + `prescreen.screen_counts` 候选总数留痕（§3.5）；**消费与趋零告警归方向5**，本方向只保证分子分母两侧可 SQL 查询 | 预筛锚定偏差（reviewer 照抄机器） |
| **G5 红方产物审** | 对抗样例清单（已内嵌测试 F/E 节 + R2 轮交红方）：① 破折号/翻案腔在对话内（应忽略）；② 未闭合引号段（掩到段尾，多掩少报）；③ 引文跨行断开/全半角标点变体/引号体例混用（verify 应 hit）；④ 编造引文、口语转述式引文（应 no_hit）；⑤ 超短引文（weak_excerpt）；⑥ 首段零回指豁免、`？！` 连用、结构行干扰 | 实现偏离规格 |
| **G6 收敛纪律** | 不变（沿用 3 轮升级）；「指纹豁免援引」分歧类型的呈报由 R1 的 craft 卡措辞承担，脚本侧仅保证规则号可指认（finding 必须带 `fpr:<ID>` 才能 claim 指纹豁免） | 无限打转、总豁免滥用 |

---

## 6. 验收判据（R2 DONE 条件）

1. `node scripts/test-prose-fingerprint.mjs` 全绿（≥70 用例：42 规则每条 ≥1 正例、screen 13 条每条 1 负例 + 对话抑制例、5 组分母构造例、CLI/canary/verify 子进程断言）。
2. 假 Receipt 被抓：编造引文/缺 excerpt/hash 错配三场景 exit 1；真引文三种变体（原句/断行/标点归一）exit 0。
3. 金丝雀误报计数入档：R0 数据就绪后 `--write-baseline` 产出含每规则误报计数与 docs 覆盖的基线 JSON，数字呈报用户（裁决点：screen 规则在人类语料的过紧程度）。
4. `--stable` 确定性：同一输入两次运行输出逐字节一致（金丝雀比对可信的前提）。
5. deny 率首测记录：任一真实章节审查轮后 SQL 可查 `fpr:`/`fpr-deny:` 计数（方向5 消费）。
6. 既有护栏不退化：test-guardrails / test-compose-prompt / test-render-projection 全绿。
7. 三个脚本零 npm、零 DB、零 schema 依赖（`grep -l "node:sqlite" scripts/novelos-{prose-fingerprint,canary,verify-review-evidence}.mjs` 无输出）。

---

## 7. 风险与回滚

| 风险 | 概率/影响 | 预案 |
|---|---|---|
| 未闭合引号把整段误掩为对话（叙述被漏检） | 中/低（多掩=少报，方向安全） | `stats.dialogue_ratio>0.6` 时输出 advisory 警示行，主控人工抽查该章引号体例；测试覆盖孤引号形态 |
| 全半角混排草稿让 L01 等全角标点正则漏检 | 低/低（草稿经 craft 卡全角标点硬约束产出） | fingerprint 是预筛不是闸门，漏检由审查兜底；后续如需可在 analyze 前做归一化预处理（本版不做，保持与母本口径一致） |
| 汉字计数不含扩展区（B/G 区生僻字，如人名用字） | 低/极低 | 与母本 `[一-鿿]` 口径一致；偏差影响分母 <0.1%，记录在案 |
| 引号配对对西文撇号 `'`（英文所有格）误判 | 低/低 | `'`/`’` 区分：仅 U+2019 参与配对且须有同族开引号，孤立即忽略；测试覆盖 |
| 规则表膨胀撑爆审查上下文 | 中/中 | 注入只走 screen 13 条且 `--max-hits` 截断（默认每规则 20 条）；measure 永不注入 |
| py 母本旧编号与 SKILL 新编号混淆导致 finding 指错规则 | 中/中 | 本设计统一现行编号并在 skillRef 双注（现行号+母本键名）；测试断言 RULES 内 id 唯一且 `fpr:` 前缀一致性 |
| 接线后主控误把预筛当闸门（命中即打回） | 中/中 | AGENTS.md/SKILL 措辞三处显式写「只报事实不判级/不阻断落库」；fingerprint 恒 exit 0 |
| **回滚** | — | 四个新文件删除即净；三处接线行 git revert（独立 commit）；无 DB/catalog/schema/composer 足迹，零存量风险 |

---

## 8. 接口声明（对外契约）

**对方向1（阈值与判据语义）**
- 输入接口：基线 JSON 的 `rules[*].adjudication` 与 `notes` 字段为方向1 专属预留位（判据文本、体裁折扣标注）；金丝雀选样规则影响 `corpus.groups` 构成，选样变更=新基线。
- 升降级接口：tier 变更流程 = 改 RULES 表 → `novelos-canary.mjs --compare`（误报不升才放行）→ rule_table_hash 变更呈报；L01b/c/d（D2 扩展）与 L04/L05（论述文专属）升 screen 的判据文本由方向1 出。
- 阈值消费接口：fingerprint 只产 `count/density/denominator_value`，不内置任何「超标」判定——阈值写在 craft 卡（R1），机器数数、卡片判级、审查裁决三层分离。

**对方向3（composer/组装器）**
- 注入契约：`novelos-prose-fingerprint.mjs --json` 输出（§3.1 schema）→ §3.5 末渲染模板；建议槽名 `prescreen_candidates`（注册进 SLOT_REGISTRY/recipes/manifest 的工作全部归方向3）；`--max-hits` 默认值即体积预算的一部分，方向3 可用 `--rules`/`--max-hits` 参数裁剪。
- 本方向不改 composer 任何代码；测试 F 节对注入文本格式无耦合。

**对方向4/5（schema 与 deny 率规程）**
- 零 schema 变更：deny 留痕走 `findings[].code`（`fpr:`/`fpr-deny:`）+ `severity='note'`，候选总数走章节 `metadata_json.prescreen.screen_counts`，两侧均可 SQL 统计。
- 若方向5 需要更细的 deny 结构（理由分类、置信度），合并接口 = review-receipt-candidate.schema.json 的 finding 对象扩展，由方向4 主导、本方向消费，双方 schema 版本对齐后再动。
- 方向5 的 deny 率告警（趋零/连续3章）消费本采集点，告警阈值语义不在本方向。

**对主控（L1 编排）**
- 三个 CLI 的 exit code 语义：fingerprint 0/1/2（成功恒 0，只报事实）；canary 0/1/2（1=金丝雀回归，须先降级再查因）；verify 0/1/2（1=纸面化回执，打回不得落库）。
- prescreen 摘要落 `chapters.metadata_json.prescreen`（约定字段，无 schema 强制）；回执验证在「审查组装 → sub agent 回 Receipt → 落库前」时点执行（novel-review SKILL step 6 之前）。

**对 R0**：`novelos-canary.mjs` 是 R0 的第 3 个交付物（`tasks/R5-knowledge-absorption.md:83`）；`data/canary/` 目录结构与 `_meta` 排除约定由 R0 的导入工具保证。

---

## 9. 来源引用（联网补全）

1. MDN — Unicode character class escape（`\p{...}` 必须 `u` flag；Script vs Script_Extensions 语义）：https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Regular_expressions/Unicode_character_class_escape
2. MDN — Lookbehind assertion（ES2018；JS 支持**变长** lookbehind，宽于多数引擎）：https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Regular_expressions/Lookbehind_assertion
3. Mathias Bynens — Unicode property escapes（Node 10+ 可用；u flag 是语法门，错环境在**解析期**即 SyntaxError）：https://mathiasbynens.be/notes/es-unicode-property-escapes
4. W3C《中文排版需求》（clreq）——点号分类：句内点号（顿/逗/分/冒）vs 句末点号（句/问/叹），分句边界取强边界的规范依据：https://www.w3.org/TR/clreq/
5. CSDN — 中文分句的解决方案（实践先「引号段替换占位符→再分句→再还原」，与本设计等长掩码方案互相印证）：https://blog.csdn.net/PolarisRisingWar/article/details/132210842
6. 《自动化学报》基于篇章的汉语句法结构树库（句号/问号/叹号作句边界最可靠，冒号/逗号需谨慎——分句口径依据）：http://www.aas.net.cn/cn/article/pdf/preview/10.16383/jiis.c190828.pdf
7. 知乎 — spaCy 中文分句微调（对话/省略号/连用标点是分句难点，佐证 §3.1.3 处理清单）：https://zhuanlan.zhihu.com/p/1926392024078194432
8. 火山引擎 — 含嵌套引号的正则捕获方案（闭合须与开头一致；嵌套需显式分层）：https://www.volcengine.com/article/1420140
9. 稀土掘金 — 正确使用正则匹配双引号（**嵌套双引号常规正则无能为力**，需变通）：https://juejin.cn/post/7444840395849023507
10. 土法炼钢 — 正则与自动机理论（任意深度嵌套超出正则语言（Chomsky-3），需下推自动机/栈——引号配对用栈扫描的理论依据）：https://quant67.com/post/algorithms/regex/regex.html
11. sparanoid/chinese-copywriting-guidelines #153（简体 `“”`→`‘’`、繁体/港台 `「」`→`『』` 的体例差异——引号字符集与家族配对的依据）：https://github.com/sparanoid/chinese-copywriting-guidelines/issues/153
12. ayaka.shn.hk — How to match Chinese characters（`\p{Script=Han}` 会命中日文汉字/韩文汉字，「Han≠中文」——本设计沿用母本 `[\u4e00-\u9fff]` 区间的理由）：https://ayaka.shn.hk/hanregex/
13. V8.dev — RegExp v flag（Node 20+ 的 u 超集；本设计不需要 set notation/字符串属性，维持 `u`-less 字面正则降低复杂度）：https://v8.dev/features/regexp-v-flag
