#!/usr/bin/env node
/**
 * novelos-prose-fingerprint.mjs —— AI 味文本指纹预筛（只报事实，不判级；成功恒 exit 0）。
 *
 * 规则表 43 条 = 39 源（compare-human-ai.py 17 + check-structure.py 4 + check-translationese.py
 * MARKERS 21 + BASELINE 4，减 4 重叠、减 3 别名）+ 3 扩展（L01b/c/d）+ 1 增设 B02
 * （逐字移植 BASELINE「不是…而是」——红方 F3：与 L01 交叉包含非覆盖）。
 * 账目：screen 12（句层 9 + 段层 3）/ measure 31。L07b 首发 measure（裁-8，跨顿号误报前科
 * 见 lieflat RESEARCH 失误#3）。
 *
 * 对话过滤（红方 F6/F11 处置）：
 *   句层 = 在原文上跑正则保坐标（可回指），命中区间不得跨 prose 段边界（越界丢弃），
 *          命中字符 ≥50% 落在对话掩码内则抑制；掩码来自栈式引号配对（直角「」『』/弯“”‘’/
 *          直引号 " 三家族，未闭合开引号掩到段尾）。
 *   段层 = U+FFFC 等长掩码后分段（对话内句末符不产假句界），per-file 聚合
 *          （每篇独立分段、非首段每篇重置——红方 F9-①，绝不 join 全文跑段层）。
 *
 * 分母（叙述层口径，红方 F2/F5）：han_1k_narrative = 掩码后 [\u4e00-\u9fff] 计数；
 * para_100 = 叙述段数；nonfirst_pct = 非首段数。母本锚点为全文口径（论述文≈叙述层），
 * 与叙述层口径对照须标注不可比（裁-4）。
 *
 * CLI：
 *   node scripts/novelos-prose-fingerprint.mjs --text-file <草稿.md> [--text-file …] [--stdin]
 *        [--rules L01,L03] [--max-hits 20] [--pretty] [--stable] [--table]
 *   cat 草稿.md | node scripts/novelos-prose-fingerprint.mjs --stdin
 *
 * exit：0 = 成功（命中多少都不算失败）；1 = 内部错误；2 = 用法错误。
 * 零 npm、零 DB、零 schema 依赖（Node 22+ 纯标准库）。
 */

import { createHash } from 'node:crypto';
import { readFileSync, readSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

// ---------------------------------------------------------------- 常量区

const PROG = 'novelos-prose-fingerprint';
const VERSION = '1.0.0';
const SCHEMA = 'novelos.prose-fingerprint.v1';
/** 对话掩码填充符（Object Replacement Character）：不属于 [。！？]、不属于任何规则字符类。 */
const FILLER = '\uFFFC';
/** md 结构行前缀（母本 check-structure.py:31 口径）：表格/代码块/标题/列表/引用/图片/链接。 */
export const STRUCTURAL_PREFIXES = ['#', '|', '```', '>', '- ', '* ', '!', '['];
/** prose 段最小长度（母本口径）。 */
const MIN_PARA_LEN = 8;

/** 引号三家族：直角「」『』（港台体例）/ 弯“”‘’（简体体例）/ 直引号 "（翻转开关兜底）。 */
const OPEN_SET = new Set(['\u300C', '\u300E', '\u201C', '\u2018']); // 「 『 “ ‘
const CLOSE_SET = new Set(['\u300D', '\u300F', '\u201D', '\u2019']); // 」 』 ” ’
const FAMILY_OF = {
  '\u300C': 'corner', '\u300E': 'corner', '\u300D': 'corner', '\u300F': 'corner',
  '\u201C': 'curly', '\u2018': 'curly', '\u201D': 'curly', '\u2019': 'curly',
};
const STRAIGHT_QUOTE = '"';
// 口径注记（红方 F11）：书名号《》〈〉不在引号字符集——「《A》、《B》、《C》」书名并列
// 会让 L02 命中，属有意口径选择（「引号内不检」哲学不覆盖书名号）。

const HAN_CHAR = /[\u4e00-\u9fff]/;
/** 句边界 = 强句末点号 。！？（母本口径；省略号/分号/冒号不作句边界）。 */
const SENT_END = /[。！？]/;
/** JS \s 与 py3 基本一致（JS 多含 U+FEFF，行首 BOM 被多消化一字符，计数等价——红方 F11 注记）。 */
const WS = /\s/;

// ---------------------------------------------------------------- 规则表（冻结；ID 发布后不改义、不复用、只追加）

/**
 * @typedef {Object} FprRule
 * @property {string}  id              稳定规则号（finding code = `fpr:${id}`，裁-1 主键）
 * @property {string}  name            中文名
 * @property {string}  re              正则源串（JS 方言；段层算法规则为 ''）
 * @property {string}  flags           'g' | 'gm'
 * @property {'screen'|'measure'} tier screen=预筛候选（注入审查供证伪）；measure=仅测量（永不进候选）
 * @property {'sentence'|'paragraph'} layer
 * @property {'han_1k_narrative'|'para_100'|'nonfirst_pct'} denominator
 * @property {boolean} dialogue_filter 对话过滤管线开关（句层=≥50% 抑制；段层=U+FFFC 掩码；当前全表为 true）
 * @property {string}  skill_ref       lieflat SKILL.md 现行规则号 / 「不作为表」/「基准」/「扩展」
 * @property {string}  source          母本出处（py:行）或 'd2-ext'
 */
export const RULES = Object.freeze([
  // ---- 表 A：compare-human-ai.py RULES（17 条逐条；旧字典编号已换算为 SKILL 现行编号）
  { id: 'L01', name: '翻案腔（窄版）', re: '(?:不是|并非|不在于)[^，。！？\\n]{1,20}[，]?(?:而是|而在于)', flags: 'g', tier: 'screen', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 1', source: 'compare-human-ai.py:17' },
  { id: 'L02', name: '顿号罗列过密', re: '[^，。！？；：、\\n]{1,14}、[^，。！？；：、\\n]{1,14}、[^，。！？；：、\\n]{1,14}', flags: 'g', tier: 'screen', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 2', source: 'compare-human-ai.py:19' },
  { id: 'M01', name: '（已删）句内同构-更X', re: '更[\\u4e00-\\u9fff]{1,3}[、，][^，。\\n]{0,8}更[\\u4e00-\\u9fff]{1,3}', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: '不作为表·句内排比', source: 'compare-human-ai.py:21' },
  { id: 'M02', name: '（已删）句内同构-同字两项', re: '([\\u4e00-\\u9fff]{1,2})[^，。、\\n]{2,12}[、，]\\1[^，。、\\n]{2,12}', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: '不作为表·句内排比', source: 'compare-human-ai.py:22' },
  { id: 'L03', name: '破折号', re: '——', flags: 'g', tier: 'screen', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 4', source: 'compare-human-ai.py:28' },
  { id: 'L04', name: '提示性冒号', re: '(?:一句话(?:总结|说|概括)|简单说|说白了|总结|小结|结论|核心(?:是|在于|观点)?|关键(?:是|在于)?|重点(?:是)?|原因(?:如下|有|在于)?|问题(?:是|在于)?|答案(?:是)?|本质(?:是|上)?|定义(?:是)?|具体(?:来说|如下|包括)?|举例(?:来说)?|换句话说|也就是说|我的(?:观点|判断|结论)|建议(?:是)?)[：:]', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 5', source: 'compare-human-ai.py:30-33' },
  { id: 'L05', name: '序数词当小标题', re: '^\\s*(?:首先|其次|再次|最后|第一|第二|第三|一方面|另一方面)[，、]', flags: 'gm', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 6', source: 'compare-human-ai.py:34（(?:^|\\n)\\s* 改 ^+m，语义等价）' },
  { id: 'L06', name: '动词名词化', re: '(?:完成|实现|进行|开展)了?(?:对)?[^，。\\n]{0,10}的(?:优化|提升|调整|分析|改造|升级)', flags: 'g', tier: 'screen', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 8', source: 'compare-human-ai.py:39' },
  { id: 'L07a', name: '过长前置定语', re: '(?:一个|一种|一套|这种|这个)[^，。、；：！？\\n]{15,}的[\\u4e00-\\u9fff]{2,5}', flags: 'g', tier: 'screen', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10.1', source: 'compare-human-ai.py:40' },
  { id: 'L08', name: '当…时（从句前置）', re: '当[^，。\\n]{2,20}(?<!的时候)时，', flags: 'g', tier: 'screen', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10.2', source: 'compare-human-ai.py:41' },
  { id: 'L09', name: '前置话题壳', re: '(?:对于[^，。\\n]{2,15}来说|对[^，。\\n]{2,15}而言|就[^，。\\n]{2,15}而言|在[^，。\\n]{2,12}方面)', flags: 'g', tier: 'screen', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10.3', source: 'compare-human-ai.py:42' },
  { id: 'L10', name: '句首连接词当路标', re: '^\\s*(?:然而|因此|此外|与此同时|换言之|总而言之)[，、]', flags: 'gm', tier: 'screen', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10.4', source: 'compare-human-ai.py:43（同 L05 改写）' },
  { id: 'L11', name: '这意味着式复述', re: '(?:这意味着|这表明|这说明|换句话说)', flags: 'g', tier: 'screen', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10.5', source: 'compare-human-ai.py:44' },
  { id: 'M03', name: '（已删）就字', re: '就', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: '不作为表·单字虚词', source: 'compare-human-ai.py:35' },
  { id: 'M04', name: '（已删）很字', re: '很', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: '不作为表·单字虚词', source: 'compare-human-ai.py:36' },
  { id: 'M05', name: '（已删）了字', re: '了', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: '不作为表·单字虚词', source: 'compare-human-ai.py:37' },
  { id: 'M06', name: '（已删）口语连接词', re: '但是|其实|不过|就是', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: '不作为表·口语连接词', source: 'compare-human-ai.py:38' },

  // ---- 表 B：check-structure.py 段层 4 指标（算法规则，非表驱动正则；re 为空、正则内嵌引擎）
  { id: 'P01', name: '相邻句同构（连续 2 句）', re: '', flags: '', tier: 'screen', layer: 'paragraph', denominator: 'para_100', dialogue_filter: true, skill_ref: 'SKILL 3', source: 'check-structure.py:37-50' },
  { id: 'P02', name: '连续 3 句同构', re: '', flags: '', tier: 'screen', layer: 'paragraph', denominator: 'para_100', dialogue_filter: true, skill_ref: 'SKILL 3', source: 'check-structure.py:37-50' },
  { id: 'P03', name: '段首零回指', re: '', flags: '', tier: 'screen', layer: 'paragraph', denominator: 'nonfirst_pct', dialogue_filter: true, skill_ref: 'SKILL 11', source: 'check-structure.py:16-22,61-67' },
  { id: 'P04', name: '比喻起段（对照项）', re: '', flags: '', tier: 'measure', layer: 'paragraph', denominator: 'para_100', dialogue_filter: true, skill_ref: '不作为表·比喻', source: 'check-structure.py:24,61-63' },

  // ---- 表 C：check-translationese.py MARKERS（与表 A 重叠 4 条不重复建；16 条 measure + L07b）
  { id: 'T01', name: '被动-抽象', re: '被(?:认为|视为|称为|设计为|应用于|赋予|看作)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:16' },
  { id: 'T02', name: '受到…的', re: '受到[^，。]{0,12}的(?:关注|影响|重视|挑战)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:17' },
  { id: 'T03', name: '形式主语', re: '(?:值得注意的是|有必要指出的是|可以说的是|需要指出的是)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:18' },
  { id: 'T04', name: '存在着/有着', re: '(?:存在着|有着)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:19' },
  { id: 'T05', name: '当…的时候（宽版）', re: '当[^，。]{2,20}(?:的时候|时)，', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:20' },
  { id: 'T06', name: '在…的过程中', re: '在[^，。]{2,20}(?:的过程中|的情况下)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:21' },
  { id: 'T07', name: '如果…的话', re: '如果[^，。]{2,20}的话', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:22' },
  // T08 注记（红方 F11）：母本已知缺陷口径——RESEARCH 失误#2 明确否定（规则是「一句内两次以上」，
  // 正则测的是单个「而且/并且」）；measure 保留仅作趋势对照，金丝雀复评时不可当规则口径。
  { id: 'T08', name: '并列连词密集', re: '并且|而且', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:23（母本已知缺陷口径，仅作趋势对照）' },
  { id: 'T09', name: '轻动词（宽版）', re: '(?:进行|作出|给予|予以)了?[^，。]{0,6}(?:分析|调整|优化|支持|评估|检查|讨论)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:24' },
  { id: 'T10', name: '不仅仅是', re: '(?:不仅仅是|远不止是|不过是|无非是)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:25' },
  { id: 'T11', name: '正是/恰恰是', re: '(?:正是|恰恰是)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:26' },
  { id: 'T12', name: '复数硬译', re: '(?:一系列的|各种各样的|诸多)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:27' },
  { id: 'T13', name: '程度直译', re: '(?:在某种程度上|一定程度上|从某种意义上说|在很大程度上|相对而言)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:28' },
  { id: 'T14', name: '扮演角色', re: '(?:扮演|承担)了?[^，。]{0,8}角色', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:32' },
  { id: 'T15', name: '以一种…方式', re: '以一种[^，。]{2,12}的(?:方式|形式)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:33' },
  { id: 'T16', name: '使得…能够', re: '使得?[^，。]{0,12}(?:能够|可以)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10·未收录', source: 'check-translationese.py:34' },
  // L07b 注记（裁-8 / 红方 F4）：首发 measure——跨顿号误报前科（RESEARCH 失误#3：
  // 「巴西的LGPD、印度的DPDPA、日本的APPI」偏正并列必命中），R0 基线零误报后按升降级流程升 screen。
  { id: 'L07b', name: '的…的…的连用', re: '的[^，。]{1,8}的[^，。]{1,8}的', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: 'SKILL 10.1', source: 'check-translationese.py:35→SKILL 10.1' },

  // ---- BASELINE（对照基准 4 条）：破折号/提示性冒号与 L03/L04 逐字相同 = 别名不建；
  //      B01 忠实移植；B02 独立建（红方 F3：与 L01 交叉包含，锚点 0.70/千字属 B02 口径）。
  { id: 'B01', name: '［基准］段首序数词（宽版）', re: '^\\s*(?:首先|其次|再次|最后|第一|第二|第三|一方面|另一方面)', flags: 'gm', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: '基准', source: 'check-translationese.py:41' },
  { id: 'B02', name: '［基准］不是…而是', re: '(?:不是|并非)[^，。]{1,20}(?:，|)而是', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: '基准', source: 'check-translationese.py:42（红方 F3 增设）' },

  // ---- 表 D：D2 扩展（3 条，全部 measure 起步——升降级纪律：金丝雀误报 0 且方向1 出判据文本后才可升 screen）
  // L01c 注记（红方 F11）：未收录变体「你以为…其实」「回头才发现」等，防误以为全覆盖。
  // L01d 注记（红方 F11）：「说到底」与 P03 的 COMMENT 段首清单双报（measure 期无碍；升 screen 后注入去重）。
  { id: 'L01b', name: '翻案腔变体·与其说', re: '(?:与其说|与其讲)[^，。！？\\n]{1,20}(?:不如说|倒不如说|毋宁说)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: '扩展', source: 'd2-ext（SKILL 1 宽变体）' },
  { id: 'L01c', name: '翻案腔变体·表里翻转', re: '(?:表面上?|看似|看上去)[^，。！？\\n]{1,20}(?:实际上?|实则|其实)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: '扩展', source: 'd2-ext（SKILL 1 宽变体；未收录「你以为…其实」「回头才发现」）' },
  { id: 'L01d', name: '翻案腔变体·裁决腔', re: '(?:^|[。！？\\n])(?:说到底|归根结底|答案恰恰相反)', flags: 'g', tier: 'measure', layer: 'sentence', denominator: 'han_1k_narrative', dialogue_filter: true, skill_ref: '扩展', source: 'd2-ext（SKILL 1 宽变体；「说到底」与 P03 COMMENT 双报）' },
]);

/** 段首评论语（省掉回指成分时读者要翻回上一段）——check-structure.py:16 逐字。 */
export const COMMENT_RE = '^(?:听起来|看起来|看上去|听上去|说白了|说到底|换句话说|意味着|值得注意|不难看出|细看|再看|回过头看|问题在于|原因在于|结果是|有意思的是|更重要的是|关键在于|真正的)';
/** 回指成分（把上文接回来）——check-structure.py:22 逐字。 */
export const ANAPHOR_RE = '^(?:这|那|其|此|上面|前面|刚才|以上|该|它|他|她|它们|他们|同样|类似|相比|反过来|但|不过|所以|因此|于是|而|另|除此|与此)';
/** 比喻起段（对照项）——check-structure.py:24 逐字。 */
export const METAPHOR_RE = '^(?:像|就像|好比|好像|仿佛|如同|这就像)';

const RATE_UNIT = Object.freeze({
  han_1k_narrative: 'per_1k_han',
  para_100: 'per_100_paras',
  nonfirst_pct: 'pct',
});

const DENOMINATOR_NOTES = Object.freeze([
  'han_1k_narrative = 每千叙述层汉字（对话掩码后计数，非全文汉字）：AI 味句式主要发生在叙述层，对话密集章 density 读数系统性偏高、叙述密集章与锚点可比；跨章判级须按 dialogue_ratio 分层或声明适用范围（红方 F5）。',
  '「对话内命中一律豁免」是有意口径：deny 率与误报率统计均基于叙述层（红方 F5）。',
  '母本锚点倍率的分母是全文汉字（论述文≈叙述层），仅近似适用于叙述密集章；与金丝雀叙述层测量对照须标注不可比（裁-4/红方 F2）。',
  '段层指标 per-file 聚合：每篇独立分段、非首段每篇重置，绝不 join 全文跑段层（红方 F9-①）。',
  'G1 误报定义 = 对话抑制后叙述层 screen 命中（裁-4/裁-8/红方 F1/F2），显式声明而非掩码静默实现。',
]);

/** 规则表规范化 JSON 的 sha256（规则表变更可被 G1 比对发现——tier/正则/分母任何改动都会变 hash）。 */
export function ruleTableHash(rules = RULES) {
  const norm = rules.map((r) => ({
    id: r.id, re: r.re, flags: r.flags, tier: r.tier, layer: r.layer,
    denominator: r.denominator, dialogue_filter: r.dialogue_filter,
  }));
  return 'sha256:' + createHash('sha256').update(JSON.stringify(norm)).digest('hex');
}

/** 启动时全表编译，任一抛错即 fail-fast。返回 Map<id, RegExp>。 */
export function compileRules(rules = RULES) {
  const compiled = new Map();
  for (const r of rules) {
    if (!r.re) continue; // 段层算法规则无正则
    compiled.set(r.id, new RegExp(r.re, r.flags));
  }
  return compiled;
}

// ---------------------------------------------------------------- 文本层：分段 / 引号配对 / 掩码 / 分句 / 签名

/** 按行切段（母本口径：行=段）。prose 段 1-based 连续编号；结构行/短行不编号。 */
export function splitParagraphs(text) {
  const out = [];
  let offset = 0;
  let proseCounter = 0;
  for (const raw of text.split('\n')) {
    const lineStart = offset;
    const lineEnd = lineStart + raw.length;
    offset += raw.length + 1;
    const trimmed = raw.trim();
    const start = lineStart + (raw.length - raw.trimStart().length);
    const structural = trimmed.length === 0 || trimmed.length < MIN_PARA_LEN
      || STRUCTURAL_PREFIXES.some((pre) => trimmed.startsWith(pre));
    out.push({
      lineStart, lineEnd, start, end: start + trimmed.length, text: trimmed,
      prose: !structural,
      proseIndex: structural ? null : ++proseCounter,
    });
  }
  return out;
}

function mergeSpans(spans) {
  spans.sort((a, b) => a.start - b.start || a.end - b.end);
  const out = [];
  for (const s of spans) {
    const last = out[out.length - 1];
    if (last && s.start <= last.end) {
      if (s.end > last.end) last.end = s.end;
    } else {
      out.push({ start: s.start, end: s.end });
    }
  }
  return out;
}

/**
 * 栈式引号配对（嵌套超出正则语言能力，须栈扫描）。逐行扫描（引号不跨段/行）：
 *  - 开引号压栈；闭引号向栈底找最近同家族开引号配对（无匹配=孤闭引号，忽略——红方 F6 防守）；
 *  - 直引号 " 为翻转开关（中西文混排兜底）；
 *  - 段尾未闭合的开引号：掩到段尾（多掩=少报=少误报，向 G1 假阳性约束倾斜；
 *    代价是假阴性，由 stats.unclosed_quote_spans / max_para_mask_ratio 监控——红方 F6）。
 * 返回 { spans: [{start,end}]（全文 code unit 坐标，含引号本身）, unclosed_quote_spans }。
 */
export function buildDialogueSpans(text) {
  const rawSpans = [];
  let unclosed = 0;
  let offset = 0;
  for (const line of text.split('\n')) {
    const lineStart = offset;
    const lineEnd = lineStart + line.length;
    offset += line.length + 1;
    const stack = [];
    let straightOpen = -1;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      const off = lineStart + i;
      if (OPEN_SET.has(ch)) {
        stack.push({ family: FAMILY_OF[ch], idx: off });
      } else if (CLOSE_SET.has(ch)) {
        const fam = FAMILY_OF[ch];
        let j = stack.length - 1;
        while (j >= 0 && stack[j].family !== fam) j--;
        if (j >= 0) {
          const open = stack.splice(j, 1)[0];
          rawSpans.push({ start: open.idx, end: off + 1 });
        } // 无同族开引号 → 孤闭引号忽略
      } else if (ch === STRAIGHT_QUOTE) {
        if (straightOpen >= 0) {
          rawSpans.push({ start: straightOpen, end: off + 1 });
          straightOpen = -1;
        } else {
          straightOpen = off;
        }
      }
    }
    if (straightOpen >= 0) {
      unclosed += 1;
      rawSpans.push({ start: straightOpen, end: lineEnd });
    }
    if (stack.length > 0) {
      unclosed += stack.length;
      rawSpans.push({ start: stack[0].idx, end: lineEnd }); // 最早未闭合开引号 → 段尾
    }
  }
  return { spans: mergeSpans(rawSpans), unclosed_quote_spans: unclosed };
}

/** 对话掩码：Uint8Array(text.length)，对话 span 内 =1。 */
export function buildDialogueMask(text, spans) {
  const mask = new Uint8Array(text.length);
  for (const s of spans) mask.fill(1, s.start, Math.min(s.end, text.length));
  return mask;
}

/** 等长掩码：对话 span 逐 code unit 替换为 FILLER（长度保持 → 句序/段长档/坐标不漂移）。 */
export function maskText(text, spans) {
  if (!spans.length) return text;
  let out = '';
  let pos = 0;
  for (const s of spans) {
    const end = Math.min(s.end, text.length);
    if (s.start > pos) out += text.slice(pos, s.start);
    out += FILLER.repeat(Math.max(0, end - s.start));
    pos = end;
  }
  if (pos < text.length) out += text.slice(pos);
  return out;
}

/**
 * 掩码后段内分句：split(/[。！？]/) 消耗分隔符（母本口径）；strip 后非空 token 记 1-based 句序。
 * fillerRatio = FILLER 占比，>=0.5（近纯对话句）标 break：不进同构滑窗且断开相邻性
 * （隔对话的两叙述句不算「相邻句」）。FILLER 不是句末符 → 对话内句末符不产假句界。
 */
export function splitSentences(paraText) {
  const out = [];
  let segStart = 0;
  let no = 0;
  const push = (endIdx) => {
    const raw = paraText.slice(segStart, endIdx);
    const s = raw.trim();
    segStart = endIdx + 1;
    if (!s) return;
    no += 1;
    let fillers = 0;
    for (const ch of s) if (ch === FILLER) fillers++;
    out.push({
      no, start: endIdx - raw.length, end: endIdx, text: s,
      fillerRatio: fillers / s.length,
      break: fillers * 2 >= s.length,
    });
  };
  for (let i = 0; i < paraText.length; i++) {
    if (SENT_END.test(paraText[i])) push(i);
  }
  push(paraText.length);
  return out;
}

/** 句子结构指纹四元组（check-structure.py:39 逐字）：逗号数、含全角冒号、含括号、长度档。 */
export function signature(sent) {
  let commas = 0;
  for (const ch of sent) if (ch === '，') commas++;
  return [commas, sent.includes('：'), sent.includes('（') || sent.includes('('), Math.floor(sent.length / 15)];
}

function sameSig(a, b) {
  return a[0] === b[0] && a[1] === b[1] && a[2] === b[2] && a[3] === b[3];
}

/** P01/P02：段内滑窗 n 句全同构且窗口首句逗号数 ≥1；有效句=len>10；break 句断块（窗不跨对话）。 */
export function runIsoWindows(sents, n) {
  let hits = 0;
  const blocks = [];
  let cur = [];
  for (const s of sents) {
    if (s.break) {
      if (cur.length) blocks.push(cur);
      cur = [];
    } else {
      cur.push(s);
    }
  }
  if (cur.length) blocks.push(cur);
  for (const block of blocks) {
    for (let i = 0; i + n <= block.length; i++) {
      const sigs = block.slice(i, i + n).map((s) => signature(s.text));
      if (sigs[0][0] >= 1 && sigs.every((sg) => sameSig(sg, sigs[0]))) hits++;
    }
  }
  return hits;
}

function isWs(ch) { return WS.test(ch); }

/**
 * 句层命中区间 → prose 段定位（红方 F11 裁决：在原文上跑保坐标，但命中区间不得跨
 * prose 段边界，越界丢弃）。命中区间先修剪首尾空白（消化 `^\\s*` 行锚点前缀），
 * 再要求修剪后区间完全落在同一 prose 段 [start,end) 内；结构行/跨行命中一律丢弃。
 */
export function locateProseParagraph(paragraphs, hitStart, hitEnd, text) {
  let s = hitStart;
  let e = hitEnd;
  while (s < e && isWs(text[s])) s++;
  while (e > s && isWs(text[e - 1])) e--;
  if (s >= e) return null;
  // 二分找 s 所在行（段按行序排列）
  let lo = 0;
  let hi = paragraphs.length - 1;
  let idx = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (paragraphs[mid].lineStart <= s) { idx = mid; lo = mid + 1; } else { hi = mid - 1; }
  }
  if (idx < 0) return null;
  const para = paragraphs[idx];
  if (!para.prose) return null;      // 结构行/空行命中 → 丢弃
  if (e > para.end) return null;     // 跨段（跨行）命中 → 丢弃
  if (s < para.start) return null;   // 落在段前空白之外（异常防御）
  return para;
}

// ---------------------------------------------------------------- 引擎层

/**
 * 句层规则：在原文上 matchAll（保坐标可回指）→ 段定位（越界丢弃）→ 对话抑制
 * （命中字符中掩码=1 的数量 * 2 >= 命中长度 → 丢弃）。measure 规则只计数不产明细（体积纪律）。
 */
function runSentenceRules(text, mask, masked, paragraphs, compiled, rules, maxHits) {
  const counts = new Map();
  const hits = [];
  const truncated = new Map();
  // 每个 prose 段的句 token 缓存（掩码后分句，供句序定位）
  const sentCache = new Map();
  for (const rule of rules) {
    if (rule.layer !== 'sentence') continue;
    const rx = compiled.get(rule.id);
    if (!rx) { counts.set(rule.id, 0); continue; }
    let count = 0;
    let hitsForRule = 0;
    for (const m of text.matchAll(rx)) {
      let maskedCount = 0;
      for (let i = m.index; i < m.index + m[0].length; i++) maskedCount += mask[i];
      if (maskedCount * 2 >= m[0].length) continue; // 对话抑制（≥50% 在引号内）
      const para = locateProseParagraph(paragraphs, m.index, m.index + m[0].length, text);
      if (!para) continue; // 结构行命中 / 跨段命中 → 丢弃
      count += 1;
      if (rule.tier !== 'screen') continue; // measure 只计数
      if (hitsForRule >= maxHits) { truncated.set(rule.id, true); continue; }
      let sentNo = 0;
      if (!sentCache.has(para.proseIndex)) {
        sentCache.set(para.proseIndex, splitSentences(masked.slice(para.start, para.end)));
      }
      const tokens = sentCache.get(para.proseIndex);
      const rel = m.index - para.start;
      for (const t of tokens) {
        if (rel >= t.start && rel < t.end) { sentNo = t.no; break; }
      }
      hits.push({
        rule_id: rule.id, para: para.proseIndex, sent: sentNo,
        offset: m.index, excerpt: m[0], in_dialogue: maskedCount > 0,
      });
      hitsForRule += 1;
    }
    counts.set(rule.id, count);
  }
  return { counts, hits, truncated };
}

/**
 * 段层规则（per-file：每篇独立分段、非首段每篇重置——红方 F9-①）。
 * 全部在 U+FFFC 掩码后的段文本上跑：对话内句末符不产假句界、段首 FILLER 不匹配 COMMENT。
 */
function runParagraphRules(masked, paragraphs) {
  const COMMENT = new RegExp(COMMENT_RE);
  const ANAPHOR = new RegExp(ANAPHOR_RE);
  const METAPHOR = new RegExp(METAPHOR_RE);
  let iso2 = 0;
  let iso3 = 0;
  let zero = 0;
  let meta = 0;
  let paras = 0;
  let nonfirst = 0;
  let sentences = 0;
  let maxParaMaskRatio = 0;
  for (const para of paragraphs) {
    if (!para.prose) continue;
    const paraText = masked.slice(para.start, para.end);
    let maskedCount = 0;
    for (let i = para.start; i < para.end; i++) maskedCount += maskOf(masked, i);
    if (para.end > para.start) {
      maxParaMaskRatio = Math.max(maxParaMaskRatio, maskedCount / (para.end - para.start));
    }
    paras += 1;
    const sents = splitSentences(paraText);
    sentences += sents.length;
    const valid = sents.filter((s) => s.text.length > 10);
    iso2 += runIsoWindows(valid, 2);
    iso3 += runIsoWindows(valid, 3);
    if (METAPHOR.test(paraText)) meta += 1;
    if (para.proseIndex === 1) continue; // 首段豁免（母本 i==0: continue）
    nonfirst += 1;
    if (COMMENT.test(paraText) && !ANAPHOR.test(paraText)) zero += 1;
  }
  return {
    counts: { P01: iso2, P02: iso3, P03: zero, P04: meta },
    paras, nonfirst, sentences, maxParaMaskRatio,
  };
}

// maskOf：从掩码字符串取字符是否 FILLER（runParagraphRules 内用；等长掩码下与 mask 数组等价）
function maskOf(masked, i) { return masked[i] === FILLER ? 1 : 0; }

function countHan(s) {
  let n = 0;
  for (const ch of s) if (HAN_CHAR.test(ch)) n++;
  return n;
}

/**
 * 单文本分析。stats 分母全部取叙述层（对话抑制后），与分子口径一致。
 * 返回 { label, stats, ruleCounts, screenHits, truncated, paraPerFile, unclosed }。
 */
export function analyzeOne(label, text, { maxHits = 20, ruleFilter = null } = {}) {
  const rules = ruleFilter ? RULES.filter((r) => ruleFilter.has(r.id)) : RULES;
  const compiled = compileRules(rules);
  const { spans, unclosed_quote_spans } = buildDialogueSpans(text);
  const mask = buildDialogueMask(text, spans);
  const masked = maskText(text, spans);
  const paragraphs = splitParagraphs(text);

  const sent = runSentenceRules(text, mask, masked, paragraphs, compiled, rules, maxHits);
  const para = runParagraphRules(masked, paragraphs);

  const hanFull = countHan(text);
  const hanNar = countHan(masked);
  let proseParas = 0;
  for (const p of paragraphs) if (p.prose) proseParas++;

  const ruleCounts = new Map();
  for (const rule of rules) {
    ruleCounts.set(rule.id, rule.layer === 'paragraph' ? para.counts[rule.id] ?? 0 : sent.counts.get(rule.id) ?? 0);
  }
  const paraPerFile = {
    paras: para.paras, nonfirst: para.nonfirst,
    counts: Object.fromEntries(rules.filter((r) => r.layer === 'paragraph').map((r) => [r.id, para.counts[r.id] ?? 0])),
  };

  return {
    label,
    stats: {
      lines_total: text.split('\n').length,
      paragraphs_prose: proseParas,
      paragraphs_nonfirst: Math.max(0, para.nonfirst),
      sentences: para.sentences,
      han_chars_fulltext: hanFull,
      han_chars_narrative: hanNar,
      dialogue_chars: Math.max(0, hanFull - hanNar),
      dialogue_ratio: hanFull > 0 ? Math.round((1 - hanNar / hanFull) * 10000) / 10000 : 0,
      unclosed_quote_spans: unclosed_quote_spans,
      max_para_mask_ratio: Math.round(para.maxParaMaskRatio * 10000) / 10000,
    },
    ruleCounts,
    screenHits: sent.hits,
    truncated: sent.truncated,
    paraPerFile,
  };
}

function denomValue(kind, agg) {
  if (kind === 'han_1k_narrative') return agg.han / 1000;
  if (kind === 'para_100') return agg.paras;
  return agg.nonfirst; // nonfirst_pct
}
/** density = count / 原始分母 × 档位（han_1k→每千字；段层→每百段/百分比）。 */
function densityOf(kind, count, agg) {
  const raw = kind === 'han_1k_narrative' ? agg.han : kind === 'para_100' ? agg.paras : agg.nonfirst;
  if (raw <= 0) return 0;
  const scale = kind === 'han_1k_narrative' ? 1000 : 100;
  return Math.round((count / raw) * scale * 10000) / 10000;
}

/**
 * 多文件聚合 → 输出 JSON 结构（schema novelos.prose-fingerprint.v1）。
 * hits[] 仅 screen 层明细；段层规则附 per_file 数值（红方 F9-① 可核查）。
 */
export function analyzeFiles(files, { maxHits = 20, ruleFilter = null, source = 'file', stable = false } = {}) {
  const results = files.map((f) => analyzeOne(f.label, f.text, { maxHits, ruleFilter }));
  const rules = ruleFilter ? RULES.filter((r) => ruleFilter.has(r.id)) : RULES;
  const agg = {
    han: 0, paras: 0, nonfirst: 0,
    hanFull: 0, dialogue: 0, lines: 0, sentences: 0,
    unclosed: 0, maxParaMaskRatio: 0,
  };
  for (const r of results) {
    agg.han += r.stats.han_chars_narrative;
    agg.hanFull += r.stats.han_chars_fulltext;
    agg.dialogue += r.stats.dialogue_chars;
    agg.paras += r.stats.paragraphs_prose;
    agg.nonfirst += r.stats.paragraphs_nonfirst;
    agg.lines += r.stats.lines_total;
    agg.sentences += r.stats.sentences;
    agg.unclosed += r.stats.unclosed_quote_spans;
    agg.maxParaMaskRatio = Math.max(agg.maxParaMaskRatio, r.stats.max_para_mask_ratio);
  }

  const ruleRows = [];
  const hits = [];
  for (const rule of rules) {
    const count = results.reduce((s, r) => s + (r.ruleCounts.get(rule.id) ?? 0), 0);
    const row = {
      id: rule.id, name: rule.name, tier: rule.tier, layer: rule.layer,
      denominator: rule.denominator, rate_unit: RATE_UNIT[rule.denominator],
      count,
      density: densityOf(rule.denominator, count, agg),
      denominator_value: Math.round(denomValue(rule.denominator, agg) * 10000) / 10000,
    };
    if (rule.layer === 'paragraph') {
      row.per_file = results.map((r) => ({
        file: r.label, count: r.paraPerFile.counts[rule.id] ?? 0,
        paras: r.paraPerFile.paras, nonfirst: r.paraPerFile.nonfirst,
      }));
    }
    if (rule.tier === 'screen' && results.some((r) => r.truncated.get(rule.id))) {
      row.hits_truncated = true;
    }
    ruleRows.push(row);
    if (rule.tier === 'screen') {
      for (const r of results) {
        for (const h of r.screenHits) {
          if (h.rule_id !== rule.id) continue;
          hits.push({ rule_id: rule.id, file: r.label, para: h.para, sent: h.sent, offset: h.offset, excerpt: h.excerpt, in_dialogue: h.in_dialogue });
        }
      }
    }
  }

  const meta = {
    denominator_units: {
      han_1k_narrative: '每千叙述层汉字（对话掩码后计数）',
      para_100: '每百叙述段',
      nonfirst_pct: '占非首段百分比',
    },
    denominator_notes: DENOMINATOR_NOTES,
    false_positive_definition: 'G1 误报 = 对话抑制后的叙述层 screen 命中（裁-4/裁-8）',
  };
  if (!stable) meta.generated_at = new Date().toISOString();

  return {
    schema: SCHEMA,
    tool: { name: PROG, version: VERSION, rule_table_hash: ruleTableHash() },
    input: { source, files: files.map((f) => f.label) },
    meta,
    stats: {
      files: files.length,
      lines_total: agg.lines,
      paragraphs_prose: agg.paras,
      paragraphs_nonfirst: agg.nonfirst,
      sentences: agg.sentences,
      han_chars_fulltext: agg.hanFull,
      han_chars_narrative: agg.han,
      dialogue_chars: agg.dialogue,
      dialogue_ratio: agg.hanFull > 0 ? Math.round((agg.dialogue / agg.hanFull) * 10000) / 10000 : 0,
      unclosed_quote_spans: agg.unclosed,
      max_para_mask_ratio: agg.maxParaMaskRatio,
    },
    rules: ruleRows,
    hits,
  };
}

// ---------------------------------------------------------------- 输出层

function toHumanTable(report) {
  const lines = [];
  lines.push(`${PROG} v${VERSION}（只报事实不判级；命中不阻断落库）`);
  lines.push(`输入：${report.stats.files} 篇 · 叙述层汉字 ${report.stats.han_chars_narrative}（全文 ${report.stats.han_chars_fulltext}）· 对话占比 ${report.stats.dialogue_ratio} · 叙述段 ${report.stats.paragraphs_prose}（非首段 ${report.stats.paragraphs_nonfirst}）`);
  lines.push(`advisory：unclosed_quote_spans=${report.stats.unclosed_quote_spans} max_para_mask_ratio=${report.stats.max_para_mask_ratio}`);
  lines.push('');
  lines.push('规则       tier     层         计数   密度        分母');
  for (const r of report.rules) {
    const den = r.denominator_value;
    lines.push(`${r.id.padEnd(10)}${r.tier.padEnd(8)}${r.layer.padEnd(10)}${String(r.count).padEnd(6)}${String(r.density).padEnd(11)}${den}`);
  }
  if (report.hits.length) {
    lines.push('');
    lines.push('screen 明细（前 40 条）：');
    for (const h of report.hits.slice(0, 40)) {
      const excerpt = h.excerpt.replace(/\s+/g, '');
      lines.push(`  ${h.rule_id} 段${h.para}·句${h.sent} @${h.offset}${h.in_dialogue ? '（部分在对话内）' : ''}「${excerpt.slice(0, 30)}」`);
    }
    if (report.hits.length > 40) lines.push(`  …共 ${report.hits.length} 条`);
  }
  return lines.join('\n');
}

// ---------------------------------------------------------------- CLI

class UsageError extends Error {}

function parseArgs(argv) {
  const opts = { textFiles: [], stdin: false, rules: null, maxHits: 20, pretty: false, stable: false, table: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--text-file') {
      const v = argv[++i];
      if (!v) throw new UsageError('--text-file 需要路径参数');
      opts.textFiles.push(v);
    } else if (a === '--stdin') {
      opts.stdin = true;
    } else if (a === '--rules') {
      const v = argv[++i];
      if (!v) throw new UsageError('--rules 需要 id 列表（逗号分隔）');
      opts.rules = new Set(v.split(',').map((s) => s.trim()).filter(Boolean));
    } else if (a === '--max-hits') {
      const v = Number(argv[++i]);
      if (!Number.isInteger(v) || v < 0) throw new UsageError('--max-hits 需要非负整数');
      opts.maxHits = v;
    } else if (a === '--json') {
      // 默认即 JSON；flag 兼容保留
    } else if (a === '--pretty') {
      opts.pretty = true;
    } else if (a === '--stable') {
      opts.stable = true;
    } else if (a === '--table') {
      opts.table = true;
    } else {
      throw new UsageError(`未知参数：${a}`);
    }
  }
  if (opts.stdin && opts.textFiles.length) {
    throw new UsageError('--stdin 与 --text-file 不可同时使用');
  }
  if (!opts.stdin && !opts.textFiles.length) {
    throw new UsageError('缺少输入：用 --text-file <路径>（可多次）或 --stdin');
  }
  if (opts.rules) {
    const known = new Set(RULES.map((r) => r.id));
    for (const id of opts.rules) {
      if (!known.has(id)) throw new UsageError(`未知规则号：${id}（可用：${RULES.map((r) => r.id).join(',')}）`);
    }
  }
  return opts;
}

function readStdin() {
  const chunks = [];
  const buf = Buffer.alloc(1 << 16);
  while (true) {
    let n;
    try {
      n = readSync(0, buf, 0, buf.length, null);
    } catch (e) {
      if (e.code === 'EAGAIN') break;
      throw e;
    }
    if (!n) break;
    chunks.push(Buffer.from(buf.subarray(0, n)));
  }
  return Buffer.concat(chunks).toString('utf8');
}

function main(argv) {
  let opts;
  try {
    opts = parseArgs(argv);
  } catch (e) {
    if (e instanceof UsageError) {
      console.error(`${e.message}\n用法：node scripts/${PROG}.mjs --text-file <草稿.md> [--text-file …] | --stdin [--rules L01,L03] [--max-hits 20] [--pretty] [--stable] [--table]`);
      return 2;
    }
    throw e;
  }
  // 规则表编译自检：任一正则抛错即 fail-fast
  compileRules();
  const files = opts.textFiles.map((p) => ({ label: p, text: readFileSync(p, 'utf8') }));
  if (opts.stdin) files.push({ label: '<stdin>', text: readStdin() });
  const report = analyzeFiles(files, {
    maxHits: opts.maxHits, ruleFilter: opts.rules, stable: opts.stable,
    source: opts.stdin ? 'stdin' : 'file',
  });
  if (opts.table) {
    console.log(toHumanTable(report));
  } else {
    process.stdout.write(JSON.stringify(report, null, opts.pretty ? 2 : 0) + '\n');
  }
  return 0; // 只报事实不判级：成功恒 0
}

// 入口判定：直接执行时才跑 main（测试 import 时跳过）；exitCode 而非 process.exit，保证大 JSON 完整输出
const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  process.exitCode = main(process.argv.slice(2));
}
