#!/usr/bin/env node
/**
 * novelos-canary.mjs —— G1 金丝雀回归门（人类语料误报基线 + tier 分层 compare）。
 *
 * 装载 `data/canary/g{N}/*.md`（顶级子目录=分组，匿名化为 g1/g2/…；`_meta/` 跳过；jsonl 忽略——
 * 只收 *.md；组内递归收集）。对全部 43 条规则（screen + measure）测量，产出基线 JSON 或
 * 现场汇总。**G1 误报定义 = 对话抑制后的叙述层 screen 命中**（裁-4/裁-8/红方 F1/F2）。
 *
 * --compare tier 分层判定（裁-8 / 红方 F1 处置）：
 *   - screen 层：rate 回归（new_rate > old_rate + tolerance 且 new_count > old_count）或
 *     新增 screen 规则误报 > 0 → exit 1；
 *   - measure 层：只输出 diff 报告，永不拦截（否则「measure 起步」机制死锁）；
 *   - 语料指纹校验（files 数 + han_chars_total，红方 F9-②）：漂移须 --allow-corpus-drift；
 *   - tolerance 按 rate_unit 区分（红方 F9-③）：内建默认 per_1k_han=0.02 / per_100_paras=0.5 /
 *     pct=1.0；--tolerance 可给单一数值（全单位）或 unit=value 逗号列表。
 *
 * 分组离散度 spread = max(rate)/max(min(rate),0.01)（≤5 稳定，母本口径）；各组数值不打印、
 * 不入基线（语料构成保密纪律），只留 spread 标量。
 *
 * CLI：
 *   node scripts/novelos-canary.mjs                                    # 现场汇总
 *   node scripts/novelos-canary.mjs --save <baseline.json> [--pretty]  # 落基线
 *   node scripts/novelos-canary.mjs --compare <baseline.json> [--tolerance …]
 *        [--allow-corpus-drift] [--dir data/canary]
 *
 * exit：0 = 通过；1 = 金丝雀回归（screen 层，须先降级再查因）；2 = 用法/环境错误。
 * 基线 JSON 的 rules[*].adjudication / notes 为方向1 预留位（判据文本、体裁折扣标注）。
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync, readdirSync } from 'node:fs';
import { join, relative, dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import {
  RULES, ruleTableHash, analyzeOne, compileRules,
} from './novelos-prose-fingerprint.mjs';

const PROG = 'novelos-canary';
const BASELINE_SCHEMA = 'novelos.canary-baseline.v1';
const FP_VERSION = '1.0.0';
/** 默认 tolerance 按 rate_unit 区分（红方 F9-③）。 */
const TOLERANCE_DEFAULTS = Object.freeze({
  per_1k_han: 0.02,
  per_100_paras: 0.5,
  pct: 1.0,
});

const RATE_UNIT = { han_1k_narrative: 'per_1k_han', para_100: 'per_100_paras', nonfirst_pct: 'pct' };

class UsageError extends Error {}

// ---------------------------------------------------------------- 语料装载

function walkMd(dir, base, out) {
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const ent of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const full = join(dir, ent.name);
    if (ent.isDirectory()) {
      if (ent.name === '_meta') continue; // 母本约定：_meta 目录跳过
      walkMd(full, base, out);
    } else if (ent.isFile() && ent.name.endsWith('.md')) {
      out.push(relative(base, full));
    } // jsonl / 其他扩展名忽略
  }
}

/** 装载金丝雀语料：顶级子目录 = 分组（排序后匿名化 g1..gN）。返回 null 表示目录不可用。 */
export function loadCanary(dir) {
  if (!existsSync(dir) || !statSync(dir).isDirectory()) return null;
  const groups = [];
  const topEntries = readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isDirectory() && e.name !== '_meta')
    .sort((a, b) => a.name.localeCompare(b.name));
  const looseFiles = [];
  walkMd(dir, dir, looseFiles);
  const topNames = new Set(topEntries.map((e) => e.name));
  for (const ent of topEntries) {
    const files = [];
    walkMd(join(dir, ent.name), dir, files);
    if (files.length) groups.push({ label: `g${groups.length + 1}`, realName: ent.name, files });
  }
  if (!groups.length && looseFiles.length) {
    groups.push({ label: 'g1', realName: '(根目录)', files: looseFiles });
  }
  const files = [];
  for (const g of groups) files.push(...g.files);
  return { dir, groups, files, topNames };
}

function readCorpus(canary) {
  return canary.files.map((rel) => {
    let text = '';
    try {
      text = readFileSync(join(canary.dir, rel), 'utf8');
    } catch {
      // 母本行为：不可读文件跳过（计 0）
    }
    return { label: rel, text, group: canary.groups.find((g) => g.files.includes(rel))?.label ?? null };
  });
}

// ---------------------------------------------------------------- 测量与聚合

function measure(fileEntries, rules = RULES) {
  const compiled = compileRules(rules);
  const per = [];
  for (const f of fileEntries) {
    const r = analyzeOne(f.label, f.text, { ruleFilter: rules ? new Set(rules.map((x) => x.id)) : null });
    per.push({ ...r, group: f.group });
  }
  return per;
}

function aggregate(per, rules = RULES) {
  const agg = { han: 0, hanFull: 0, dialogue: 0, paras: 0, nonfirst: 0, sentences: 0, lines: 0, unclosed: 0, maxMask: 0 };
  for (const r of per) {
    agg.han += r.stats.han_chars_narrative;
    agg.hanFull += r.stats.han_chars_fulltext;
    agg.dialogue += r.stats.dialogue_chars;
    agg.paras += r.stats.paragraphs_prose;
    agg.nonfirst += r.stats.paragraphs_nonfirst;
    agg.sentences += r.stats.sentences;
    agg.lines += r.stats.lines_total;
    agg.unclosed += r.stats.unclosed_quote_spans;
    agg.maxMask = Math.max(agg.maxMask, r.stats.max_para_mask_ratio);
  }
  const rows = new Map();
  for (const rule of rules) {
    let count = 0;
    let docsHit = 0;
    for (const r of per) {
      const c = r.ruleCounts.get(rule.id) ?? 0;
      count += c;
      if (c > 0) docsHit += 1;
    }
    const denom = rule.denominator === 'han_1k_narrative' ? agg.han
      : rule.denominator === 'para_100' ? agg.paras : agg.nonfirst;
    const scale = rule.denominator === 'han_1k_narrative' ? 1000 : 100;
    const rate = denom > 0 ? Math.round((count / denom) * scale * 10000) / 10000 : 0;
    rows.set(rule.id, {
      id: rule.id, name: rule.name, tier: rule.tier, denominator: rule.denominator,
      rate_unit: RATE_UNIT[rule.denominator], count, rate, denominator_value: denom,
      docs_hit: docsHit, docs_total: per.length,
    });
  }
  return { agg, rows, n: per.length };
}

function groupSpread(per, ruleId, rule, groups) {
  if (groups.length < 2) return null;
  const vals = [];
  for (const g of groups) {
    const members = per.filter((r) => r.group === g.label);
    if (!members.length) continue;
    let count = 0;
    let denom = 0;
    for (const m of members) {
      count += m.ruleCounts.get(ruleId) ?? 0;
      if (rule.denominator === 'han_1k_narrative') denom += m.stats.han_chars_narrative;
      else if (rule.denominator === 'para_100') denom += m.stats.paragraphs_prose;
      else denom += m.stats.paragraphs_nonfirst;
    }
    const scale = rule.denominator === 'han_1k_narrative' ? 1000 : 100;
    vals.push(denom > 0 ? (count / denom) * scale : 0);
  }
  if (vals.length < 2) return null;
  const max = Math.max(...vals);
  const min = Math.min(...vals);
  return Math.round((max / Math.max(min, 0.01)) * 100) / 100;
}

/** 基线 JSON 结构（rules[*].adjudication/notes 为方向1 预留位）。 */
export function buildBaseline(canary, per, { dir, stable = false }) {
  const { agg, rows, n } = aggregate(per);
  const rules = {};
  for (const rule of RULES) {
    const row = rows.get(rule.id);
    rules[rule.id] = {
      id: rule.id, name: rule.name, tier: rule.tier, denominator: rule.denominator,
      rate_unit: row.rate_unit, count: row.count, rate: row.rate,
      docs_hit: row.docs_hit, docs_total: row.docs_total,
      stability_spread: groupSpread(per, rule.id, rule, canary.groups),
      adjudication: null, // 方向1 预留：判据文本
      notes: null,        // 方向1 预留：体裁折扣标注
    };
  }
  const baseline = {
    schema: BASELINE_SCHEMA,
    tool: { script: PROG, fingerprint_version: FP_VERSION, rule_table_hash: ruleTableHash() },
    false_positive_definition: 'G1 误报 = 对话抑制后的叙述层 screen 命中（裁-4/裁-8；红方 F1/F2）',
    corpus: {
      dir,
      files: canary.files,
      files_count: n,
      groups: canary.groups.map((g) => ({ label: g.label, files: g.files.length })),
      group_labels_are_anonymous: true,
      han_chars_fulltext: agg.hanFull,
      han_chars_total: agg.han, // 叙述层汉字（与测量分母同口径；语料指纹比对用）
      dialogue_ratio: agg.hanFull > 0 ? Math.round((agg.dialogue / agg.hanFull) * 10000) / 10000 : 0,
      unclosed_quote_spans: agg.unclosed,
      max_para_mask_ratio: agg.maxMask,
    },
    rules,
  };
  if (!stable) baseline.generated_at = new Date().toISOString();
  return baseline;
}

// ---------------------------------------------------------------- 现场汇总输出

function printSummary(baseline) {
  const c = baseline.corpus;
  const lines = [];
  lines.push(`== ${PROG} 现场汇总（误报定义=对话抑制后的叙述层 screen 命中）==`);
  lines.push(`语料：${c.files_count} 篇 · ${c.groups.length} 组（匿名 ${c.groups.map((g) => `${g.label}=${g.files}篇`).join(' ')}）`);
  lines.push(`叙述层汉字 ${c.han_chars_total}（全文 ${c.han_chars_fulltext}）· 对话占比 ${c.dialogue_ratio} · advisory unclosed=${c.unclosed_quote_spans} max_para_mask_ratio=${c.max_para_mask_ratio}`);
  lines.push('');
  lines.push('规则       tier     count  rate        单位            spread  误报覆盖');
  const screenSummary = [];
  for (const rule of RULES) {
    const r = baseline.rules[rule.id];
    const spread = r.stability_spread === null ? '-' : String(r.stability_spread);
    lines.push(`${r.id.padEnd(10)}${r.tier.padEnd(8)}${String(r.count).padEnd(6)}${String(r.rate).padEnd(11)}${r.rate_unit.padEnd(15)}${spread.padEnd(7)}${r.docs_hit}/${r.docs_total}`);
    if (r.tier === 'screen') screenSummary.push(`${r.id}=${r.count}`);
  }
  lines.push('');
  lines.push(`screen 误报计数汇总：${screenSummary.join(' ')}`);
  return lines.join('\n');
}

// ---------------------------------------------------------------- compare（tier 分层判定）

function parseTolerance(str) {
  const out = { ...TOLERANCE_DEFAULTS };
  if (/^[0-9]+(\.[0-9]+)?$/.test(str)) {
    const v = Number(str);
    for (const k of Object.keys(out)) out[k] = v;
    return out;
  }
  for (const part of str.split(',')) {
    const m = part.match(/^(per_1k_han|per_100_paras|pct)=([0-9.]+)$/);
    if (!m) {
      throw new UsageError(`--tolerance 格式错误：${part}（可给单一数值或 unit=value 逗号列表，unit ∈ per_1k_han/per_100_paras/pct）`);
    }
    out[m[1]] = Number(m[2]);
  }
  return out;
}

/** parseTolerance 的安全包装：UsageError 原样返回，交由调用方转 usage/exit 2。 */
function parseToleranceSafe(str) {
  if (!str) return { ...TOLERANCE_DEFAULTS };
  try {
    return parseTolerance(str);
  } catch (e) {
    if (e instanceof UsageError) return e;
    throw e;
  }
}

function fmt(x) { return Number.isFinite(x) ? String(x) : String(x); }

function runCompare(baselineOld, baselineNew, { tolerance, allowCorpusDrift }) {
  const lines = [];
  let regressions = 0;
  const oldRules = baselineOld.rules ?? {};
  const newRules = baselineNew.rules ?? {};
  const oldIds = new Set(Object.keys(oldRules));
  const newIds = new Set(Object.keys(newRules));
  const added = [...newIds].filter((id) => !oldIds.has(id));
  const removed = [...oldIds].filter((id) => !newIds.has(id));

  lines.push(`== ${PROG} compare（tier 分层判定：exit 1 仅拦 screen；measure 只出 diff——裁-8/红方 F1）==`);

  const hashSame = baselineOld.tool?.rule_table_hash === baselineNew.tool?.rule_table_hash;
  lines.push(`规则表 hash：${hashSame ? '一致' : `变更（old=${baselineOld.tool?.rule_table_hash ?? '?'}）`}`);
  if (!hashSame) {
    if (added.length) lines.push(`  新增规则：${added.join(', ')}`);
    if (removed.length) lines.push(`  移除规则：${removed.join(', ')}`);
    const tierChanged = [...newIds].filter((id) => oldIds.has(id) && oldRules[id].tier !== newRules[id].tier);
    if (tierChanged.length) lines.push(`  tier 变更：${tierChanged.map((id) => `${id} ${oldRules[id].tier}→${newRules[id].tier}`).join(', ')}`);
    lines.push('  ⚠ 规则表已变更：须人工确认升降级走 canary 门（G1）后重落基线。');
  }

  const co = baselineOld.corpus ?? {};
  const cn = baselineNew.corpus;
  const drift = co.files_count !== cn.files_count || co.han_chars_total !== cn.han_chars_total;
  lines.push(`语料指纹：${drift ? `漂移（files ${co.files_count ?? '?'}→${cn.files_count}，han_chars_total ${co.han_chars_total ?? '?'}→${cn.han_chars_total}）${allowCorpusDrift ? '——--allow-corpus-drift 放行' : ''}` : '一致'}`);

  lines.push('');
  lines.push('规则       tier     old rate → new rate      old/new count  判定');
  for (const rule of RULES) {
    const nw = newRules[rule.id];
    if (!nw) continue;
    const old = oldRules[rule.id];
    const tag = `[${nw.tier}]`.padEnd(9);
    if (!old) {
      if (nw.tier === 'screen' && nw.count > 0) {
        regressions += 1;
        lines.push(`${nw.id.padEnd(10)}${tag}（新增）rate=${nw.rate} count=${nw.count}      REGRESSION（新增 screen 规则误报>0）`);
      } else if (nw.tier === 'screen') {
        lines.push(`${nw.id.padEnd(10)}${tag}（新增）rate=${nw.rate} count=${nw.count}      ok（新增 screen 零误报）`);
      } else {
        lines.push(`${nw.id.padEnd(10)}${tag}（新增）rate=${nw.rate} count=${nw.count}      note（measure 新规则不拦）`);
      }
      continue;
    }
    const tol = tolerance[nw.rate_unit] ?? 0;
    const rateUp = nw.rate > old.rate + tol;
    const countUp = nw.count > old.count;
    if (nw.tier === 'screen') {
      if (rateUp && countUp) {
        regressions += 1;
        lines.push(`${nw.id.padEnd(10)}${tag}${fmt(old.rate)} → ${fmt(nw.rate)}      ${old.count}/${nw.count}        REGRESSION（rate 超容差 +${tol} 且 count 回升）`);
      } else {
        lines.push(`${nw.id.padEnd(10)}${tag}${fmt(old.rate)} → ${fmt(nw.rate)}      ${old.count}/${nw.count}        ok`);
      }
    } else {
      const d = Math.round((nw.rate - old.rate) * 10000) / 10000;
      lines.push(`${nw.id.padEnd(10)}${tag}${fmt(old.rate)} → ${fmt(nw.rate)} (Δ${d >= 0 ? '+' : ''}${d})  ${old.count}/${nw.count}        diff（measure 仅报告）`);
    }
  }
  for (const id of removed) {
    lines.push(`${id.padEnd(10)}（移除）——仅报告，不影响判定`);
  }
  lines.push('');
  lines.push(`tolerance（按 rate_unit）：${JSON.stringify(tolerance)}`);
  lines.push(`verdict: ${regressions > 0 ? `FAIL（screen 回归 ${regressions} 条——先降级再查因）` : 'PASS'}`);
  return { verdict: regressions > 0 ? 'FAIL' : 'PASS', regressions, report: lines.join('\n') };
}

// ---------------------------------------------------------------- CLI

function parseArgs(argv) {
  const opts = { dir: 'data/canary', save: null, compare: null, tolerance: null, allowCorpusDrift: false, pretty: false, stable: false, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--dir') {
      opts.dir = argv[++i];
      if (!opts.dir) throw new UsageError('--dir 需要路径参数');
    } else if (a === '--save') {
      opts.save = argv[++i];
      if (!opts.save) throw new UsageError('--save 需要输出路径参数');
    } else if (a === '--compare') {
      opts.compare = argv[++i];
      if (!opts.compare) throw new UsageError('--compare 需要基线路径参数');
    } else if (a === '--tolerance') {
      opts.tolerance = argv[++i];
      if (!opts.tolerance) throw new UsageError('--tolerance 需要数值或 unit=value 列表');
    } else if (a === '--allow-corpus-drift') {
      opts.allowCorpusDrift = true;
    } else if (a === '--pretty') {
      opts.pretty = true;
    } else if (a === '--stable') {
      opts.stable = true;
    } else if (a === '--json') {
      opts.json = true;
    } else {
      throw new UsageError(`未知参数：${a}`);
    }
  }
  if (opts.save && opts.compare) throw new UsageError('--save 与 --compare 不可同时使用');
  return opts;
}

function usage(e) {
  console.error(`${e.message}
用法：
  node scripts/${PROG}.mjs [--dir data/canary] [--json]
  node scripts/${PROG}.mjs --save <baseline.json> [--pretty] [--stable]
  node scripts/${PROG}.mjs --compare <baseline.json> [--tolerance 0.02|unit=val,…] [--allow-corpus-drift] [--dir data/canary]`);
}

function main(argv) {
  let opts;
  try {
    opts = parseArgs(argv);
  } catch (e) {
    if (e instanceof UsageError) {
      usage(e);
      return 2;
    }
    throw e;
  }
  const dirAbs = resolve(opts.dir);
  const canary = loadCanary(dirAbs);
  if (!canary || !canary.files.length) {
    console.error(`金丝雀目录不存在或为空（R0 未跑？）：${dirAbs}`);
    return 2;
  }
  compileRules();
  const corpus = readCorpus(canary);
  const per = measure(corpus);

  if (opts.save) {
    const baseline = buildBaseline(canary, per, { dir: opts.dir, stable: opts.stable });
    mkdirSync(dirname(opts.save), { recursive: true });
    writeFileSync(opts.save, JSON.stringify(baseline, null, opts.pretty ? 2 : 0) + '\n');
    console.log(`基线已写入：${opts.save}（${baseline.corpus.files_count} 篇 / ${baseline.corpus.groups.length} 组 / rule_table_hash=${baseline.tool.rule_table_hash.slice(0, 19)}…）`);
    console.log(printSummary(baseline));
    return 0;
  }

  if (opts.compare) {
    let old;
    try {
      old = JSON.parse(readFileSync(opts.compare, 'utf8'));
    } catch (e) {
      console.error(`基线不可读/非法 JSON：${opts.compare}（${e.message}）`);
      return 2;
    }
    if (old.schema !== BASELINE_SCHEMA) {
      console.error(`基线 schema 不符：${old.schema ?? '(缺)'} ≠ ${BASELINE_SCHEMA}`);
      return 2;
    }
    const tolerance = parseToleranceSafe(opts.tolerance);
    if (tolerance instanceof UsageError) {
      usage(tolerance);
      return 2;
    }
    const newBaseline = buildBaseline(canary, per, { dir: opts.dir, stable: true });
    const co = old.corpus ?? {};
    const drift = co.files_count !== newBaseline.corpus.files_count
      || co.han_chars_total !== newBaseline.corpus.han_chars_total;
    if (drift && !opts.allowCorpusDrift) {
      console.error(`语料指纹漂移（files ${co.files_count ?? '?'}→${newBaseline.corpus.files_count}，han_chars_total ${co.han_chars_total ?? '?'}→${newBaseline.corpus.han_chars_total}）；确认语料变更属预期后加 --allow-corpus-drift 重跑。`);
      return 2;
    }
    const result = runCompare(old, newBaseline, { tolerance, allowCorpusDrift: opts.allowCorpusDrift });
    console.log(result.report);
    return result.verdict === 'FAIL' ? 1 : 0;
  }

  // 现场汇总
  const baseline = buildBaseline(canary, per, { dir: opts.dir, stable: opts.stable });
  if (opts.json) {
    process.stdout.write(JSON.stringify(baseline, null, opts.pretty ? 2 : 0) + '\n');
  } else {
    console.log(printSummary(baseline));
  }
  return 0;
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  process.exitCode = main(process.argv.slice(2));
}
