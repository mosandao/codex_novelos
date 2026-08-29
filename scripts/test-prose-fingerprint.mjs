#!/usr/bin/env node
/**
 * novelos-prose-fingerprint.mjs / novelos-canary.mjs 的测试脚本。
 *
 * 覆盖（R2 机器校验）：
 *   A 算法层：分段/引号配对/掩码/分句/signature
 *   B 规则层：43 条规则每条 ≥1 正 1 负例；对话内命中忽略（三家族引号）；≥50% 边界
 *   C 分母：叙述层 vs 全文构造例、para_100/nonfirst_pct、首段豁免
 *   D 段层 per-file 聚合（两篇拼接第二篇首段不算非首段——红方 F9-①）
 *   E 跨段命中丢弃（红方 F11：原文跑正则但区间不得跨 prose 段边界）
 *   F 未闭合引号段全掩 + 跨段续引（红方 F6：把漏检变成可断言数字）
 *   G advisory stats（dialogue_ratio / unclosed_quote_spans / max_para_mask_ratio）
 *   H CLI 子进程断言（exit 语义 / --stable / --rules / --max-hits）
 *   I canary：基线结构 / --save / --compare tier 分层判定 / 语料指纹 / tolerance
 *
 * 运行：node scripts/test-prose-fingerprint.mjs
 */

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const FP_CLI = path.join(__dirname, 'novelos-prose-fingerprint.mjs');
const CANARY_CLI = path.join(__dirname, 'novelos-canary.mjs');

const {
  RULES, ruleTableHash, compileRules, analyzeOne, analyzeFiles,
  splitParagraphs, buildDialogueSpans, buildDialogueMask, maskText,
  splitSentences, signature, runIsoWindows,
} = await import(`file://${FP_CLI.replace(/\\/g, '/')}`);

let passed = 0;
let failed = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`PASS ${name}`);
  } catch (e) {
    failed++;
    failures.push({ name, e });
    console.log(`FAIL ${name}: ${e.message}`);
  }
}

function runCli(cli, extraArgs, input) {
  return spawnSync(process.execPath, ['--no-warnings', cli, ...extraArgs], {
    encoding: 'utf8',
    cwd: ROOT,
    input,
  });
}

function closeTo(a, b, eps = 1e-6) {
  return Math.abs(a - b) <= eps;
}

// ================================================================ J 规则表完整性

test('J1 规则表 43 条且 id 唯一', () => {
  assert.equal(RULES.length, 43);
  const ids = RULES.map((r) => r.id);
  assert.equal(new Set(ids).size, 43);
});

test('J2 tier 账目：screen 12（句层 9 + 段层 3）/ measure 31', () => {
  const screen = RULES.filter((r) => r.tier === 'screen');
  const measure = RULES.filter((r) => r.tier === 'measure');
  assert.equal(screen.length, 12);
  assert.equal(measure.length, 31);
  assert.equal(screen.filter((r) => r.layer === 'sentence').length, 9);
  assert.equal(screen.filter((r) => r.layer === 'paragraph').length, 3);
  // 裁-8：L07b 首发 measure；B02 增设 measure；扩展三条全 measure
  assert.equal(RULES.find((r) => r.id === 'L07b').tier, 'measure');
  assert.equal(RULES.find((r) => r.id === 'B02').tier, 'measure');
  for (const id of ['L01b', 'L01c', 'L01d']) {
    assert.equal(RULES.find((r) => r.id === id).tier, 'measure');
  }
});

test('J3 规则字段完整 + 43/43 正则编译不抛（段层规则除外）', () => {
  for (const r of RULES) {
    for (const k of ['id', 'name', 're', 'flags', 'tier', 'layer', 'denominator', 'dialogue_filter', 'skill_ref', 'source']) {
      assert.ok(k in r, `${r.id} 缺字段 ${k}`);
    }
    assert.equal(typeof r.dialogue_filter, 'boolean');
    assert.ok(['han_1k_narrative', 'para_100', 'nonfirst_pct'].includes(r.denominator), `${r.id} denominator 非法`);
    if (r.layer === 'sentence') assert.ok(r.re, `${r.id} 句层规则须有正则`);
  }
  const compiled = compileRules();
  assert.equal(compiled.size, RULES.filter((r) => r.re).length);
});

test('J4 rule_table_hash 格式与稳定性', () => {
  assert.match(ruleTableHash(), /^sha256:[0-9a-f]{64}$/);
  assert.equal(ruleTableHash(), ruleTableHash());
  // 表内容变化 → hash 变化
  const patched = RULES.map((r) => (r.id === 'L01' ? { ...r, tier: 'measure' } : r));
  assert.notEqual(ruleTableHash(patched), ruleTableHash());
});

// ================================================================ A 算法层

test('A1 分段：md 结构行/短行不编号，prose 段 1-based 连续', () => {
  const text = [
    '# 标题行',                    // 结构：#
    '这是第一段正常的叙述内容。',   // prose 1
    '| 表格 | 行 |',               // 结构：|
    '```',                          // 结构：```
    '短行',                        // 结构：<8 字
    '- 列表项',                    // 结构：- 
    '> 引用内容啊这是引用块哦。',   // 结构：>
    '这是第二段正常的叙述内容。',   // prose 2
    '* 星号列表项啊。',            // 结构：* 
    '![图片alt](x.png)',           // 结构：!
    '[链接文字](x)',               // 结构：[
    '这是第三段正常的叙述内容。',   // prose 3
  ].join('\n');
  const paras = splitParagraphs(text);
  const prose = paras.filter((p) => p.prose);
  assert.equal(prose.length, 3);
  assert.deepEqual(prose.map((p) => p.proseIndex), [1, 2, 3]);
  assert.deepEqual(prose.map((p) => p.text), [
    '这是第一段正常的叙述内容。', '这是第二段正常的叙述内容。', '这是第三段正常的叙述内容。',
  ]);
});

test('A2a 引号配对：直角/嵌套/孤闭/未闭合/直引号翻转/不跨段', () => {
  // 「」配对（span 含引号本身：「=idx3，」=idx7 → [3,8)）
  let r = buildDialogueSpans('他说：「走吧。」然后离开。');
  assert.equal(r.spans.length, 1);
  assert.equal(r.unclosed_quote_spans, 0);
  assert.equal(r.spans[0].start, 3);
  assert.equal(r.spans[0].end, 8);
  // 「中嵌『』」嵌套 → 合并为 1 span
  r = buildDialogueSpans('「外层他说『内层』结束」完毕。');
  assert.equal(r.spans.length, 1);
  // 弯引号 “”
  r = buildDialogueSpans('他说：“走吧。”然后离开。');
  assert.equal(r.spans.length, 1);
  // 孤闭引号忽略
  r = buildDialogueSpans('他说完」就走掉了。');
  assert.equal(r.spans.length, 0);
  assert.equal(r.unclosed_quote_spans, 0);
  // 未闭合开引号 → 掩到段尾
  r = buildDialogueSpans('「这个方案没有闭合符');
  assert.equal(r.spans.length, 1);
  assert.equal(r.unclosed_quote_spans, 1);
  // 直引号翻转开关
  r = buildDialogueSpans('他说"走吧"然后离开。');
  assert.equal(r.spans.length, 1);
  r = buildDialogueSpans('他说"未闭合直引号');
  assert.equal(r.spans.length, 1);
  assert.equal(r.unclosed_quote_spans, 1);
  // 引号不跨段（行）：首行开引号未闭、次行闭引号成孤闭
  r = buildDialogueSpans('「第一行没有闭合\n第二行」才闭合。');
  assert.equal(r.spans.length, 1); // 仅首行的未闭合 span
  assert.equal(r.spans[0].end, 8); // 掩到第一行行尾
  assert.equal(r.unclosed_quote_spans, 1);
});

test('A2b 弯单引号家族配对，英文撇号风格孤立即忽略', () => {
  // ‘’ 配对
  let r = buildDialogueSpans('他说：‘走吧。’然后离开。');
  assert.equal(r.spans.length, 1);
  // 孤立 ’（无同族开引号）忽略
  r = buildDialogueSpans("他说完’就走掉了。");
  assert.equal(r.spans.length, 0);
});

test('A3 掩码等长且对话内句末符不产句边界', () => {
  const text = '他说：「走吧。我们回家。」然后离开。';
  const { spans } = buildDialogueSpans(text);
  const masked = maskText(text, spans);
  assert.equal(masked.length, text.length);
  const tokens = splitSentences(masked);
  assert.equal(tokens.length, 1); // 对话内两个 。被掩 → 不产假句界
  // 句末符被消耗不进 token：token = 掩码文本去掉最后一个句号
  assert.equal(tokens[0].text, '他说：' + '\uFFFC'.repeat(10) + '然后离开');
});

test('A4a 分句：句末符消耗、空片过滤', () => {
  const tokens = splitSentences('第一句内容比较长些。第二句也很长呀！');
  assert.equal(tokens.length, 2);
  assert.equal(tokens[0].text, '第一句内容比较长些');
  assert.equal(tokens[1].no, 2);
  // ？！连用产空片被滤
  assert.equal(splitSentences('这句话足够长可以保留？！').length, 1);
  assert.equal(splitSentences('这句话足够长可以保留？！后面还有一句够长。').length, 2);
});

test('A4b fillerRatio≥0.5 句标 break 且断同构窗', () => {
  const para = '叙述开头铺垫内容' + '\uFFFC'.repeat(24) + '叙述收尾。';
  const tokens = splitSentences(para);
  assert.equal(tokens.length, 1);
  assert.equal(tokens[0].break, true);
  // break 句断窗：两叙述句隔对话不算相邻
  const a = { no: 1, text: '他慢慢地拿起刀来，切了下去', break: false };
  const b = { no: 2, text: '\uFFFC'.repeat(30), break: true };
  const c = { no: 3, text: '他默默地放下刀来，擦了擦手', break: false };
  assert.equal(runIsoWindows([a, b, c].map((s) => ({ ...s, text: s.text })), 2), 0);
  assert.equal(runIsoWindows([a, { ...c }], 2), 1); // 无对话隔断时同构命中
});

test('A5 signature 四元组与长度档', () => {
  assert.deepEqual(signature('没有逗号的句子'), [0, false, false, 0]);
  assert.deepEqual(signature('有一逗号，还有冒号：（括）'), [1, true, true, 0]); // 13 字 → 档 0
  assert.deepEqual(signature('一二三四五六七八九十一二三四五'), [0, false, false, 1]); // 15 字 → 档 1
  assert.deepEqual(signature('一二三四五六七八九十一二三四五，'), [1, false, false, 1]);
  assert.deepEqual(signature('一二三四五六七八九十一二三四'), [0, false, false, 0]); // 14 字 → 档 0
});

// ================================================================ B 规则层：43 条正负例

const POS_NEG = {
  L01: { pos: '真正的壁垒不是技术，而是认知。', neg: '真正的壁垒是认知本身。' },
  L02: { pos: '数据采集、存储、展示一体。', neg: '采集、存储与展示都很重要。' },
  L03: { pos: '他找到了一条路——一条没人注意的路。', neg: '他找到了一条没人注意的路。' },
  L04: { pos: '一句话总结：这个方案成本太高。', neg: '他说过，明天再谈就好。' },
  L05: { pos: '首先，团队明确了今年的目标。', neg: '团队首先明确了今年的目标。' },
  L06: { pos: '他们完成了对整个系统的优化。', neg: '他们完成了系统的全部改造升级工作。' },
  L07a: { pos: '一种源于二十世纪中叶控制论与系统论思想的方法', neg: '一种简单而直接的方法' },
  L08: { pos: '当他推门时，屋里已经没有人了。', neg: '当他进门的时候，雨已经停了。' },
  L09: { pos: '对于初入行的新人来说，这很难。', neg: '对于初入行的新人，这很难。' },
  L10: { pos: '然而，事情并没有那么简单。', neg: '他嘴上答应，然而心里另有打算。' },
  L11: { pos: '这意味着所有人的成本都会上升。', neg: '这个结果对所有人都没有好处。' },
  M01: { pos: '更新更快、更稳的结果出现了。', neg: '更新带来更快的结果。' },
  M02: { pos: '要好好吃饭，要好好睡觉。', neg: '要好好吃饭和睡觉才行。' },
  M03: { pos: '他就是要走，谁也拦不住他。', neg: '他执意要走，谁也拦不住他。' },
  M04: { pos: '我觉得很好，就这样定了下来。', neg: '我觉得挺好，就这样定了下来。' },
  M05: { pos: '他吃完了饭，把碗筷都收走了。', neg: '他正在吃饭，你先别催他。' },
  M06: { pos: '但是他来了，其实没有准备好。', neg: '虽然他来了，却没有准备好。' },
  T01: { pos: '他被认为是这一行的开创者。', neg: '他是这一行的开创者之一。' },
  T02: { pos: '这件事受到了很多人的关注。', neg: '这件事让很多人都在关注。' },
  T03: { pos: '值得注意的是，价格仍在上涨。', neg: '大家要注意，价格仍在上涨。' },
  T04: { pos: '这里存在着明显的风险隐患。', neg: '这里的风险隐患相当明显。' },
  T05: { pos: '当他到达山顶的时候，天已经黑了。', neg: '他到达山顶的时候天已经黑了。' },
  T06: { pos: '在学习这门手艺的过程中，他会犯错。', neg: '学习这门手艺的过程相当漫长。' },
  T07: { pos: '如果明天下雨的话，活动就取消。', neg: '如果明天下雨，活动就取消。' },
  T08: { pos: '他会写代码，并且会画图，而且很勤快。', neg: '他会写代码，也会画图，还很勤快。' },
  T09: { pos: '团队对这个方案进行了认真的分析。', neg: '团队认真分析这个方案的内容。' },
  T10: { pos: '这不仅仅是一次失败的尝试。', neg: '这是一次失败的尝试而已。' },
  T11: { pos: '这正是问题真正的症结所在。', neg: '问题真正的症结就在这里。' },
  T12: { pos: '一系列的问题都等着人们去解决。', neg: '这些问题都等着人们去解决。' },
  T13: { pos: '在某种程度上，他说得也没有错。', neg: '某种程度上说，他也没有说错。' },
  T14: { pos: '他在这个项目里扮演了关键角色。', neg: '他在这个项目里是关键人物。' },
  T15: { pos: '以一种温和的方式拒绝了邀请。', neg: '用比较温和的方式拒绝了邀请。' },
  T16: { pos: '这使得整个团队能够快速迭代。', neg: '这让整个团队都能够快速迭代。' },
  L07b: { pos: '漂亮的衣服崭新的车子宽敞的房子', neg: '漂亮的衣服还有崭新的裤子。' },
  B01: { pos: '首先，大家坐下来开个短会。', neg: '大家首先坐下来开个短会。' },
  B02: { pos: '这不是一次失败？而是一次转折。', neg: '这不是一次失败的尝试而已。' },
  L01b: { pos: '与其说他聪明倒不如说他够坚持。', neg: '与其抱怨黑暗，不如点亮蜡烛。' },
  L01c: { pos: '表面平静实则暗流已经涌动。', neg: '表面平静，内里暗流已经涌动。' },
  L01d: { pos: '说到底，这一切都是命中注定。', neg: '我问说到底是谁的责任。' },
};

test('B1a 43 条规则逐条正例（count≥1 且 screen 层产明细）', () => {
  for (const [id, { pos }] of Object.entries(POS_NEG)) {
    const r = analyzeOne('t', pos);
    const count = r.ruleCounts.get(id);
    assert.ok(count >= 1, `${id} 正例未命中（count=${count}）`);
    const rule = RULES.find((x) => x.id === id);
    if (rule.tier === 'screen') {
      assert.ok(r.screenHits.some((h) => h.rule_id === id), `${id} screen 正例无明细`);
    }
  }
});

test('B1b 43 条规则逐条负例（count===0）', () => {
  for (const [id, { neg }] of Object.entries(POS_NEG)) {
    const r = analyzeOne('t', neg);
    const count = r.ruleCounts.get(id);
    assert.equal(count, 0, `${id} 负例误命中（count=${count}）`);
  }
});

test('B1c L01 与 B02 交叉包含（红方 F3）：L01 排除跨句、B02 命中', () => {
  const cross = '难道这不是终点？而是新的起点吗。';
  const r = analyzeOne('t', cross);
  assert.equal(r.ruleCounts.get('L01'), 0); // L01 排除 ！？
  assert.equal(r.ruleCounts.get('B02'), 1); // B02（BASELINE 口径）命中
  // L01 独有分支：不在于/而在于
  const r2 = analyzeOne('t', '关键不在于钱，而在于人心。');
  assert.equal(r2.ruleCounts.get('L01'), 1);
  assert.equal(r2.ruleCounts.get('B02'), 0); // B02 只认 而是
});

test('B2 对话内命中忽略：直角/弯/直引号三家族', () => {
  for (const [q1, q2] of [['「', '」'], ['“', '”'], ['"', '"']]) {
    const text = `他说：${q1}这不是终点，而是起点。${q2}说完他转身就走，没有回头。`;
    const r = analyzeOne('t', text);
    assert.equal(r.ruleCounts.get('L01'), 0, `引号家族 ${q1}${q2} 内 L01 未被抑制`);
  }
  // 嵌套引号内的命中
  const nested = '他说：「她讲『这不是终点，而是起点。』有道理。」然后走了。';
  assert.equal(analyzeOne('t', nested).ruleCounts.get('L01'), 0);
});

test('B3 ≥50% 口径边界：命中少部分在引号内保留并标 in_dialogue，过半则抑制', () => {
  // L02 命中 20 units，其中 7 units 在引号内 → <50% 保留
  const keep = analyzeOne('t', '大家采集、"存储、展示"这三类数据的过程。');
  assert.equal(keep.ruleCounts.get('L02'), 1);
  const hit = keep.screenHits.find((h) => h.rule_id === 'L02');
  assert.equal(hit.in_dialogue, true);
  assert.equal(hit.para, 1);
  // 命中 10 units 中 7 units 在引号内 → ≥50% 抑制
  const drop = analyzeOne('t', '采集、"存储、展示"。');
  assert.equal(drop.ruleCounts.get('L02'), 0);
});

test('B4 screen hits 结构：rule_id/para/sent/offset/excerpt 坐标可回指', () => {
  const text = '前面是一段铺垫的叙述内容。真正的壁垒不是技术，而是认知。';
  const r = analyzeOne('t', text);
  const hit = r.screenHits.find((h) => h.rule_id === 'L01');
  assert.ok(hit);
  assert.equal(hit.para, 1);
  assert.ok(hit.sent >= 1);
  assert.equal(hit.excerpt, '不是技术，而是');
  assert.equal(text.slice(hit.offset, hit.offset + hit.excerpt.length), hit.excerpt); // 坐标可回指
});

// ================================================================ C 分母正确性

test('C1 han_1k_narrative：叙述层 1000 汉字构造，density=1.0/千字', () => {
  const sent = '这不是终点，而是起点。'; // 9 汉字 + 逗号 + 句号
  const narr = '水'.repeat(400) + sent + '水'.repeat(591);
  assert.equal(analyzeOne('t', narr).stats.han_chars_narrative, 1000);
  const r = analyzeOne('t', narr);
  assert.equal(r.ruleCounts.get('L01'), 1);
  const row = analyzeFiles([{ label: 't', text: narr }]).rules.find((x) => x.id === 'L01');
  assert.equal(row.denominator_value, 1); // 1000/1000
  assert.ok(closeTo(row.density, 1.0), `density=${row.density}`);
});

test('C2 对话稀释免疫：加 500 汉字对话后叙述分母与 density 不变', () => {
  const sent = '这不是终点，而是起点。';
  const narr = '水'.repeat(400) + sent + '水'.repeat(591);
  const withDlg = narr + '\n「' + '金'.repeat(500) + '」';
  const a = analyzeFiles([{ label: 'a', text: narr }]);
  const b = analyzeFiles([{ label: 'b', text: withDlg }]);
  assert.equal(b.stats.han_chars_narrative, a.stats.han_chars_narrative);
  assert.equal(b.stats.han_chars_fulltext, 1500);
  assert.ok(closeTo(b.stats.dialogue_ratio, 500 / 1500, 1e-4));
  const la = a.rules.find((x) => x.id === 'L01');
  const lb = b.rules.find((x) => x.id === 'L01');
  assert.ok(closeTo(la.density, lb.density), `density 漂移：${la.density} → ${lb.density}`);
});

test('C3 para_100 分母：单段 1 处二连同构 → P01 density=100/百段', () => {
  const para = '他慢慢地拿起刀来，切了下去。他默默地放下刀来，擦了擦手。厨房里只剩下他一个人发着呆。';
  const r = analyzeFiles([{ label: 't', text: para }]);
  const p01 = r.rules.find((x) => x.id === 'P01');
  const p02 = r.rules.find((x) => x.id === 'P02');
  assert.equal(p01.count, 1);
  assert.equal(p02.count, 0);
  assert.ok(closeTo(p01.density, 100)); // 1 处 / 1 段 × 100
});

test('C4 三连同构：P01=2（两个二连窗）、P02=1', () => {
  const para = '他慢慢地拿起刀来，切了下去。他默默地放下刀来，擦了擦手。他轻轻地转过身来，出了门。';
  const r = analyzeOne('t', para);
  assert.equal(r.ruleCounts.get('P01'), 2);
  assert.equal(r.ruleCounts.get('P02'), 1);
});

test('C5 nonfirst_pct：10 段中段3 命中、段5 有回指豁免 → count=1、pct≈11.11', () => {
  const filler = '这一段是普普通通的叙述而已。';
  const paras = [filler, filler,
    '听起来这个安排完美无缺，几乎找不到任何破绽。', filler,
    '这听起来像个不错的安排，几乎没有任何破绽。',
    filler, filler, filler, filler, filler];
  const text = paras.join('\n');
  const r = analyzeFiles([{ label: 't', text }]);
  const p03 = r.rules.find((x) => x.id === 'P03');
  assert.equal(p03.count, 1);
  assert.equal(p03.denominator_value, 9); // 非首段 9
  assert.ok(closeTo(p03.density, 100 / 9, 1e-3));
});

test('C6 首段豁免：段首评论词在首段恒不命中', () => {
  const r = analyzeOne('t', '听起来这个安排完美无缺，几乎找不到任何破绽。');
  assert.equal(r.ruleCounts.get('P03'), 0);
  assert.equal(r.stats.paragraphs_nonfirst, 0);
});

test('C7 回指豁免：段首加「这」→ ANAPHOR 命中不算零回指', () => {
  const text = '这一段是普普通通的叙述而已。\n这听起来像个不错的安排，几乎没有任何破绽。';
  const r = analyzeOne('t', text);
  assert.equal(r.ruleCounts.get('P03'), 0);
  assert.equal(r.ruleCounts.get('P04'), 0);
});

// ================================================================ D 段层 per-file 聚合（红方 F9-①）

test('D1 两篇拼接：第二篇首段不算非首段，P01 滑窗不跨篇', () => {
  const f1 = [
    '他们在这个镇子上住了整整十二年，从来没有人怀疑过他们。',
    '听起来这个安排完美无缺，几乎找不到任何破绽。',
    '后来证明确实如此，一切都和他们料想的一样。',
  ].join('\n');
  const f2 = '听起来这个开头毫无破绽，几乎找不到任何问题所在。';
  const report = analyzeFiles([{ label: 'f1.md', text: f1 }, { label: 'f2.md', text: f2 }]);
  const p03 = report.rules.find((x) => x.id === 'P03');
  assert.equal(p03.count, 1); // join 全文口径会错计 f2 首段 → 2
  assert.deepEqual(p03.per_file.map((x) => x.count), [1, 0]);
  assert.deepEqual(p03.per_file.map((x) => x.paras), [3, 1]);
  assert.equal(report.stats.paragraphs_prose, 4);
  assert.equal(report.stats.paragraphs_nonfirst, 2); // f1 非首段 2 + f2 非首段 0
});

test('D2 单文件 P03 命中位置正确（段号回指）', () => {
  const f1 = [
    '他们在这个镇子上住了整整十二年，从来没有人怀疑过他们。',
    '听起来这个安排完美无缺，几乎找不到任何破绽。',
  ].join('\n');
  const r = analyzeOne('f1.md', f1);
  assert.equal(r.ruleCounts.get('P03'), 1);
  assert.equal(r.paraPerFile.nonfirst, 1);
});

// ================================================================ E 跨段命中丢弃（红方 F11）

test('E1 T02 命中区间跨 prose 段边界 → 丢弃；同行对照命中', () => {
  const cross = '他发觉这件事受到了很多\n的影响和关注，几乎无法收场。';
  assert.equal(analyzeOne('t', cross).ruleCounts.get('T02'), 0);
  const inline = '他发觉这件事受到了很多的影响，几乎无法收场。';
  assert.equal(analyzeOne('t', inline).ruleCounts.get('T02'), 1);
});

test('E2 B02 跨段丢弃：[^，。] 不排换行，但 F11 裁决越界丢弃', () => {
  const cross = '他发觉这不是失败\n而是新生活开始的时刻。';
  const r = analyzeOne('t', cross);
  assert.equal(r.ruleCounts.get('B02'), 0);
  assert.equal(r.ruleCounts.get('L01'), 0);
});

test('E3 结构行/短行命中 → 段定位失败丢弃（F11 越界丢弃的行内形态）', () => {
  // 短行（<8 字）为 structural 段：L10 在该行命中但段定位失败 → 丢弃，只计 prose 段
  const text = '然而，他走了。\n然而，事情并没有那么简单。';
  const r = analyzeOne('t', text);
  assert.equal(r.stats.paragraphs_prose, 1);
  assert.equal(r.ruleCounts.get('L10'), 1);
  assert.equal(r.screenHits.filter((h) => h.rule_id === 'L10').length, 1);
  assert.equal(r.screenHits[0].para, 1);
  // 对照：列表行（结构前缀）同理只计 prose 段（L05 measure 无明细）
  const r2 = analyzeOne('t', '- 首先，这是列表项的内容。\n首先，团队明确了今年的目标。');
  assert.equal(r2.ruleCounts.get('L05'), 1);
  assert.equal(r2.stats.paragraphs_prose, 1);
});

// ================================================================ F 未闭合引号 / 跨段续引（红方 F6）

test('F1 未闭合引号段全掩：L01 命中=0、unclosed=1、max_para_mask_ratio=1', () => {
  const text = '「这个方案不是最优解，而是权宜之计，先这样运行一段时间再说。';
  const r = analyzeOne('t', text);
  assert.equal(r.ruleCounts.get('L01'), 0);
  assert.equal(r.screenHits.filter((h) => h.rule_id === 'L01').length, 0);
  assert.equal(r.stats.unclosed_quote_spans, 1);
  assert.equal(r.stats.max_para_mask_ratio, 1);
});

test('F2 跨段续引：首段开引号未闭 → 该段句层 screen 命中为 0（可断言的漏检）', () => {
  const text = '「今天不是末日，而是转折点，谁都没想到会这样收场。\n新的序幕拉开的时候，所有人都沉默了。」';
  const r = analyzeOne('t', text);
  assert.equal(r.ruleCounts.get('L01'), 0);        // 首段全掩 → 漏检 1 处
  assert.equal(r.stats.unclosed_quote_spans, 1);   // advisory 暴露漏检原因
  // 对照：正常闭合时命中在引号内被抑制，unclosed=0
  const closed = '「今天不是末日，而是转折点。」所有人都沉默了。';
  const rc = analyzeOne('t', closed);
  assert.equal(rc.ruleCounts.get('L01'), 0);
  assert.equal(rc.stats.unclosed_quote_spans, 0);
});

test('F3 直引号奇数翻转 → 段尾全掩', () => {
  const text = '他压低声音说："这里不是案发第一现场，而是伪造的现场。';
  const r = analyzeOne('t', text);
  assert.equal(r.ruleCounts.get('L01'), 0);
  assert.equal(r.stats.unclosed_quote_spans, 1);
});

// ================================================================ G advisory stats

test('G advisory stats 字段存在且类型正确', () => {
  const report = analyzeFiles([{ label: 'a', text: '这一段是普普通通的叙述而已。' }]);
  for (const k of ['dialogue_ratio', 'unclosed_quote_spans', 'max_para_mask_ratio', 'han_chars_fulltext', 'han_chars_narrative']) {
    assert.ok(k in report.stats, `stats 缺 ${k}`);
  }
  assert.equal(typeof report.stats.dialogue_ratio, 'number');
  assert.equal(typeof report.stats.unclosed_quote_spans, 'number');
  assert.equal(typeof report.stats.max_para_mask_ratio, 'number');
  assert.ok(Array.isArray(report.meta.denominator_notes) && report.meta.denominator_notes.length >= 5);
});

// ================================================================ H CLI 子进程

const tmp = mkdtempSync(path.join(tmpdir(), 'fpr-test-'));
const sampleText = [
  '这一段是普普通通的叙述而已，没有任何花样。',
  '真正的壁垒不是技术，而是认知。真正的壁垒不是技术，而是认知。',
  '「对话里不是重点，而是氛围。」他说完就走了。',
].join('\n');
const sampleFile = path.join(tmp, 'sample.md');
writeFileSync(sampleFile, sampleText, 'utf8');

test('H1 --text-file 与 --stdin 输出等价（除 input/source 与文件标签）', () => {
  const a = runCli(FP_CLI, ['--text-file', sampleFile, '--stable']);
  const b = runCli(FP_CLI, ['--stdin', '--stable'], sampleText);
  assert.equal(a.status, 0);
  assert.equal(b.status, 0);
  const ja = JSON.parse(a.stdout);
  const jb = JSON.parse(b.stdout);
  assert.equal(jb.input.source, 'stdin');
  assert.equal(ja.input.source, 'file');
  // rules：数值字段逐条相等（per_file.file 标签不同，剥离后比较）
  const strip = (r) => ({ id: r.id, count: r.count, density: r.density, denominator_value: r.denominator_value, tier: r.tier });
  assert.equal(JSON.stringify(ja.rules.map(strip)), JSON.stringify(jb.rules.map(strip)));
  assert.equal(JSON.stringify(ja.stats), JSON.stringify(jb.stats));
  assert.equal(JSON.stringify(ja.hits.map((h) => [h.rule_id, h.para, h.sent, h.offset, h.excerpt])),
    JSON.stringify(jb.hits.map((h) => [h.rule_id, h.para, h.sent, h.offset, h.excerpt])));
});

test('H2 --json 默认输出、schema/版本/rule_table_hash 正确', () => {
  const r = runCli(FP_CLI, ['--text-file', sampleFile, '--stable']);
  const j = JSON.parse(r.stdout);
  assert.equal(j.schema, 'novelos.prose-fingerprint.v1');
  assert.equal(j.tool.name, 'novelos-prose-fingerprint');
  assert.match(j.tool.rule_table_hash, /^sha256:[0-9a-f]{64}$/);
  assert.equal(j.rules.length, 43);
  assert.ok(!('generated_at' in j.meta));
  const r2 = runCli(FP_CLI, ['--text-file', sampleFile]);
  const j2 = JSON.parse(r2.stdout);
  assert.ok(j2.meta.generated_at); // 默认非 stable 带时间戳
});

test('H3 --stable 两次运行逐字节相同', () => {
  const a = runCli(FP_CLI, ['--text-file', sampleFile, '--stable']);
  const b = runCli(FP_CLI, ['--text-file', sampleFile, '--stable']);
  assert.equal(a.stdout, b.stdout);
});

test('H4 --rules 过滤只跑指定规则', () => {
  const r = runCli(FP_CLI, ['--text-file', sampleFile, '--stable', '--rules', 'L01,P03']);
  const j = JSON.parse(r.stdout);
  assert.deepEqual(j.rules.map((x) => x.id).sort(), ['L01', 'P03']);
  assert.ok(j.hits.every((h) => ['L01', 'P03'].includes(h.rule_id)));
});

test('H5 --max-hits 截断并标记 hits_truncated', () => {
  const r = runCli(FP_CLI, ['--text-file', sampleFile, '--stable', '--max-hits', '1']);
  const j = JSON.parse(r.stdout);
  const l01 = j.rules.find((x) => x.id === 'L01');
  assert.equal(l01.count, 2);       // 计数不受截断影响
  assert.equal(l01.hits_truncated, true);
  assert.equal(j.hits.filter((h) => h.rule_id === 'L01').length, 1);
});

test('H6 大量命中仍 exit 0（只报事实不判级）', () => {
  const loud = Array.from({ length: 20 }, () => '真正的壁垒不是技术，而是认知。这不是终点——而是起点。').join('\n');
  const f = path.join(tmp, 'loud.md');
  writeFileSync(f, loud, 'utf8');
  const r = runCli(FP_CLI, ['--text-file', f, '--stable']);
  assert.equal(r.status, 0);
  const j = JSON.parse(r.stdout);
  assert.ok(j.rules.find((x) => x.id === 'L01').count >= 20);
});

test('H7 用法错误 exit 2（无输入/未知参数/规则号不存在/互斥输入）', () => {
  assert.equal(runCli(FP_CLI, []).status, 2);
  assert.equal(runCli(FP_CLI, ['--bogus']).status, 2);
  assert.equal(runCli(FP_CLI, ['--text-file', sampleFile, '--rules', 'XX99']).status, 2);
  assert.equal(runCli(FP_CLI, ['--text-file', sampleFile, '--stdin']).status, 2);
  assert.equal(runCli(FP_CLI, ['--text-file', sampleFile, '--max-hits', '-1']).status, 2);
});

// ================================================================ I canary

const ctmp = mkdtempSync(path.join(tmpdir(), 'canary-test-'));
/** 夹具精确文本（I 组还原时须逐字一致，否则触发语料指纹漂移）。 */
const PLAIN = [
  '山间的小路蜿蜒而上，两旁是高大的乔木。',
  '他走了很久，终于看到了山顶的轮廓，却说什么也迈不开步子了。',
  '「你到底想说什么。」他终于开口了，声音很轻。',
].join('\n');

function writeCanaryFixture() {
  mkdirSync(path.join(ctmp, 'g1'), { recursive: true });
  mkdirSync(path.join(ctmp, 'g2'), { recursive: true });
  writeFileSync(path.join(ctmp, 'g1', 'a.md'), PLAIN, 'utf8');
  writeFileSync(path.join(ctmp, 'g1', 'b.md'), PLAIN + '\n风把窗帘吹得鼓起来，又缓缓落下。', 'utf8');
  writeFileSync(path.join(ctmp, 'g2', 'c.md'), PLAIN, 'utf8');
  writeFileSync(path.join(ctmp, 'g2', 'd.md'), PLAIN, 'utf8');
  mkdirSync(path.join(ctmp, '_meta'), { recursive: true });
  writeFileSync(path.join(ctmp, '_meta', 'note.json'), '{}', 'utf8');
  writeFileSync(path.join(ctmp, 'g1', 'extra.jsonl'), '{}\n', 'utf8'); // jsonl 忽略
}

const baselinePath = path.join(ctmp, 'baseline.json');
const cdir = path.join(ctmp);

test('I0 canary 夹具就绪', () => {
  writeCanaryFixture();
  assert.ok(readFileSync(path.join(ctmp, 'g1', 'a.md'), 'utf8').length > 0);
});

test('I1 基线结构：匿名分组/files 清单/dialogue_ratio/adjudication 预留/rule_table_hash', () => {
  const r = runCli(CANARY_CLI, ['--dir', cdir, '--save', baselinePath, '--stable', '--pretty']);
  assert.equal(r.status, 0, r.stderr);
  const b = JSON.parse(readFileSync(baselinePath, 'utf8'));
  assert.equal(b.schema, 'novelos.canary-baseline.v1');
  assert.match(b.tool.rule_table_hash, /^sha256:[0-9a-f]{64}$/);
  assert.equal(b.false_positive_definition.includes('叙述层'), true);
  assert.equal(b.corpus.files_count, 4);
  assert.deepEqual(b.corpus.groups, [{ label: 'g1', files: 2 }, { label: 'g2', files: 2 }]);
  assert.equal(b.corpus.group_labels_are_anonymous, true);
  assert.equal(b.corpus.files.length, 4);
  assert.ok('dialogue_ratio' in b.corpus);
  assert.ok('han_chars_total' in b.corpus);
  assert.equal(Object.keys(b.rules).length, 43);
  const l01 = b.rules.L01;
  for (const k of ['tier', 'rate_unit', 'count', 'rate', 'docs_hit', 'docs_total', 'stability_spread', 'adjudication', 'notes']) {
    assert.ok(k in l01, `基线 rules.L01 缺 ${k}`);
  }
  assert.equal(l01.adjudication, null); // 方向1 预留位
  assert.equal(l01.count, 0);           // 夹具无 screen 命中
  // 现场汇总（无 --save）也能跑
  const s = runCli(CANARY_CLI, ['--dir', cdir]);
  assert.equal(s.status, 0);
  assert.ok(s.stdout.includes('screen 误报计数汇总'));
});

test('I2 同语料 --compare → exit 0', () => {
  const r = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath]);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(r.stdout.includes('PASS'));
});

test('I3 screen 回归被抓：语料加 L01 命中（内容漂移须显式放行）→ exit 1', () => {
  writeFileSync(path.join(ctmp, 'g1', 'a.md'),
    readFileSync(path.join(ctmp, 'g1', 'a.md'), 'utf8') + '\n真正的壁垒不是技术，而是认知。\n', 'utf8');
  // 汉字总数变化 = 语料指纹漂移 → 未放行时 exit 2（F9-②）
  const blocked = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath]);
  assert.equal(blocked.status, 2);
  assert.ok(blocked.stderr.includes('语料指纹漂移'));
  // 显式放行漂移后，screen 回归被拦
  const r = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath, '--allow-corpus-drift']);
  assert.equal(r.status, 1);
  assert.ok(r.stdout.includes('REGRESSION'));
  assert.ok(r.stdout.includes('FAIL'));
});

test('I4 measure 层只出 diff 不拦：加「就」字（M03）→ exit 0', () => {
  writeFileSync(path.join(ctmp, 'g2', 'c.md'),
    readFileSync(path.join(ctmp, 'g2', 'c.md'), 'utf8') + '\n他就是要走，谁也拦不住他。\n', 'utf8');
  // L01 回归仍在 → exit 1
  const r = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath, '--allow-corpus-drift']);
  assert.equal(r.status, 1);
  // 还原 L01 命中后，仅剩 measure 变化 → exit 0
  writeFileSync(path.join(ctmp, 'g1', 'a.md'), PLAIN, 'utf8');
  const r2 = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath, '--allow-corpus-drift']);
  assert.equal(r2.status, 0, r2.stdout);
  assert.ok(r2.stdout.includes('diff（measure 仅报告）'));
  writeFileSync(path.join(ctmp, 'g2', 'c.md'), PLAIN, 'utf8'); // 还原
});

test('I5 语料指纹漂移：加文件 → exit 2；--allow-corpus-drift 放行', () => {
  writeFileSync(path.join(ctmp, 'g2', 'e.md'),
    '山间的小路蜿蜒而上，两旁是高大的乔木。他走了很久。', 'utf8');
  const r = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath]);
  assert.equal(r.status, 2);
  assert.ok(r.stderr.includes('语料指纹漂移'));
  const r2 = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath, '--allow-corpus-drift']);
  assert.equal(r2.status, 0);
  // 还原
  rmSync(path.join(ctmp, 'g2', 'e.md'));
  const r3 = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath]);
  assert.equal(r3.status, 0);
});

test('I6 tolerance 放行边界内的 screen 回升', () => {
  // 加回 L01 命中（1 处）：默认 tolerance → exit 1；大 tolerance → exit 0
  writeFileSync(path.join(ctmp, 'g1', 'a.md'),
    readFileSync(path.join(ctmp, 'g1', 'a.md'), 'utf8') + '\n真正的壁垒不是技术，而是认知。\n', 'utf8');
  const strict = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath, '--allow-corpus-drift']);
  assert.equal(strict.status, 1);
  const loose = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath, '--allow-corpus-drift', '--tolerance', '999']);
  assert.equal(loose.status, 0);
  // unit=value 形式
  const unit = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath, '--allow-corpus-drift', '--tolerance', 'per_1k_han=999,per_100_paras=999,pct=999']);
  assert.equal(unit.status, 0);
  const bad = runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath, '--allow-corpus-drift', '--tolerance', 'bogus=1']);
  assert.equal(bad.status, 2);
  writeFileSync(path.join(ctmp, 'g1', 'a.md'), PLAIN, 'utf8'); // 还原
});

test('I7 规则表 hash 变更：报告新增/移除与告警，无回归则 exit 0', () => {
  const b = JSON.parse(readFileSync(baselinePath, 'utf8'));
  b.tool.rule_table_hash = 'sha256:' + '0'.repeat(64);
  delete b.rules.L01;
  b.rules.ZZ01 = { tier: 'screen', count: 0, rate: 0, rate_unit: 'per_1k_han' };
  const tampered = path.join(ctmp, 'tampered.json');
  writeFileSync(tampered, JSON.stringify(b), 'utf8');
  const r = runCli(CANARY_CLI, ['--dir', cdir, '--compare', tampered]);
  assert.equal(r.status, 0);
  assert.ok(r.stdout.includes('规则表 hash：变更'));
  assert.ok(r.stdout.includes('ZZ01'));
});

test('I8 canary 用法错误 exit 2（--save 与 --compare 互斥/目录不存在/基线非法）', () => {
  assert.equal(runCli(CANARY_CLI, ['--dir', cdir, '--save', 'x.json', '--compare', baselinePath]).status, 2);
  assert.equal(runCli(CANARY_CLI, ['--dir', path.join(tmpdir(), 'no-such-dir-xyz')]).status, 2);
  const badBase = path.join(ctmp, 'bad.json');
  writeFileSync(badBase, '{not json', 'utf8');
  assert.equal(runCli(CANARY_CLI, ['--dir', cdir, '--compare', badBase]).status, 2);
  assert.equal(runCli(CANARY_CLI, ['--dir', cdir, '--compare', baselinePath, '--bogus']).status, 2);
});

// ================================================================ 汇总

if (failures.length) {
  console.error(`\n${passed} PASS, ${failed} FAIL`);
  process.exit(1);
} else {
  console.log(`\n${passed} PASS, 0 FAIL`);
  process.exit(0);
}
