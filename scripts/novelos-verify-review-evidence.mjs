#!/usr/bin/env node
/**
 * G2 引文机器验证（Review Receipt ↔ 草稿）。
 *
 * 设计权威：tasks/r5-plans/d2-machine-gates.plan.md §3.3 + 红方 F7/F8 处置。
 * 职责：抽取 Receipt 每条 finding 的 excerpt，与被审草稿做归一化字符串命中；
 * 对不上 = 纸面化证据 = exit 1 供主控打回；同时校验 subject_hash ↔ 草稿绑定
 * （复用组装器 contentHash，'sha256:'+sha256(utf8)，零重复实现）。
 *
 * 四路 FATAL（任一命中 exit 1）：
 *   ① no_hit      —— blocking/warning finding 的 excerpt 归一化后在草稿中无命中
 *   ② missing     —— blocking/warning finding 缺 excerpt / 空串
 *   ③ hash_mismatch —— subject_hash ≠ 'sha256:'+sha256(草稿 utf8 字节)
 *   ④ empty_findings_approved —— findings=0 且 verdict=approved（空查回执，红方 F7；
 *      R7-A1 起默认 FATAL——原「--strict 才拦」口径作废；确需放行空回执加 --allow-empty，
 *      降为 advisory 并在输出留痕豁免字样）
 * ADVISORY（默认只报；--strict 升级 FATAL）：
 *   · excerpt 归一化后 < 8 字符（weak）
 *   · 命中次数 > 1（多处命中 = 证据力弱）
 * note / strength 级 finding 不做 FATAL 检查（只统计；R2 轮任务口径，
 * 与 §3.3 的「--strict 全升级」差异在此声明）；strength 无 excerpt = exempt（SKILL 允许纯推理）。
 *
 * 【边界声明（红方 F8）】G2 验证的是证据「存在性」与「回执↔草稿版本绑定」，
 * 不验证引文「相关性」——reviewer 可从草稿抄真话作无关 excerpt，机器必判 hit，
 * 相关性归主控/红方抽查。归一化（全半角折叠/删空白/引号统一）会扩大误命中面，
 * weak + 多处命中标记即为该边界的补偿性提示，不是消除。
 *
 * 用法：
 *   node scripts/novelos-verify-review-evidence.mjs --receipt <回执.json|内联JSON> --draft <草稿.md>
 *       [--stdin-draft] [--json] [--strict] [--allow-empty] [--no-check-hash]
 * 回执兼容两种形态：candidate（findings 数组）/ DB 行（findings_json 字符串）；
 * --receipt 以 { 开头按内联 JSON 解析（对齐 composer --review-feedback 习惯）。
 * exit：0 = 通过（可落库）；1 = 存在 FATAL（纸面化回执，打回重审）；2 = 用法/输入错误。
 * 零 npm、零 DB、零 schema 依赖。
 */

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { contentHash } from './novelos-compose-prompt.mjs';

const PROG = 'novelos-verify-review-evidence';
const VERSION = '1.1.0';
const SCHEMA = 'novelos.review-evidence-verify.v1';
const WEAK_THRESHOLD = 8; // 归一化后 <8 字符 = weak（红方 F8 处置：6 升 8）

const PROBLEM_SEVERITIES = new Set(['blocking', 'warning']);
const SEVERITY_ENUM = new Set(['blocking', 'warning', 'note', 'strength']);

export class UsageError extends Error {}

// ---------------------------------------------------------------- 归一化

/**
 * 归一化（对 excerpt 与草稿同侧应用，故折叠选择本身是匹配中立的；
 * 折叠的意义在于消除 excerpt 与草稿「同文异形」的假 no_hit）：
 *   ① 全角 ASCII 区 FF01-FF5E → -0xFEE0（！→! ，→,）；U+3000 → ' '
 *   ② 中西标点等价折叠：。(U+3002)→'.' 、(U+3001)→','
 *   ③ 引号统一：「」『』“”‘’"' → `"`（开闭统一，excerpt 嵌引号不致错杀）
 *   ④ 破折号 ——（U+2014 连串）与 –（U+2013 连串）折叠为单个 —
 *   ⑤ 省略号：\.{2,} 与 …+ 折叠为单个 …
 *   ⑥ 删全部空白 \s+ → ''（换行断句的引文照常命中；JS \s 含 U+FEFF BOM 一并删除）
 */
export function normalizeForMatch(s) {
  let out = '';
  for (const ch of String(s)) {
    const code = ch.codePointAt(0);
    if (code >= 0xFF01 && code <= 0xFF5E) {
      out += String.fromCharCode(code - 0xFEE0);
    } else if (code === 0x3000) {
      out += ' ';
    } else {
      out += ch;
    }
  }
  out = out.replace(/[\u3002]/g, '.').replace(/[\u3001]/g, ',');
  out = out.replace(/[「」『』“”‘’"']/g, '"');
  out = out.replace(/\u2014{2,}|\u2013+/g, '\u2014');
  out = out.replace(/\.{2,}/g, '\u2026').replace(/\u2026+/g, '\u2026');
  out = out.replace(/\s+/g, '');
  return out;
}

function countOccurrences(hay, needle) {
  if (!needle) return 0;
  let count = 0;
  let idx = hay.indexOf(needle);
  while (idx !== -1) {
    count++;
    idx = hay.indexOf(needle, idx + needle.length);
  }
  return count;
}

// ---------------------------------------------------------------- 回执装载

/** 兼容 candidate（findings 数组）与 DB 行（findings_json 字符串）两种形态。 */
export function loadReceipt(raw) {
  const obj = typeof raw === 'string' ? JSON.parse(raw) : raw;
  if (!obj || typeof obj !== 'object') throw new UsageError('回执不是 JSON 对象');
  if (!Array.isArray(obj.findings)) {
    if (typeof obj.findings_json === 'string') {
      try {
        obj.findings = JSON.parse(obj.findings_json);
      } catch {
        throw new UsageError('findings_json 不是合法 JSON 数组文本');
      }
    } else {
      throw new UsageError('回执既无 findings 数组也无 findings_json 字段（candidate/DB 行两形态均不匹配）');
    }
  }
  if (!Array.isArray(obj.findings)) throw new UsageError('findings/findings_json 解析后不是数组');
  obj.__form = typeof raw === 'string' && raw.includes('"findings_json"') && !raw.includes('"findings"')
    ? 'db_row' : 'candidate';
  return obj;
}

// ---------------------------------------------------------------- 判定引擎

/**
 * 逐 finding 判定。返回 findings 报告行数组 + 汇总。
 * receipt 级 advisory（空 findings + approved，红方 F7）由调用方合成。
 */
export function checkFindings(receiptFindings, draftNorm) {
  const rows = [];
  const summary = {
    findings_total: receiptFindings.length,
    hit: 0, no_hit: 0, missing_excerpt: 0, weak_excerpt: 0, multi_hit: 0,
    exempt: 0, note_findings: 0, finding_fatals: 0, advisories: 0,
  };
  for (let i = 0; i < receiptFindings.length; i++) {
    const f = receiptFindings[i] ?? {};
    const severity = typeof f.severity === 'string' ? f.severity : '';
    const code = typeof f.code === 'string' && f.code.length > 0 ? f.code : null;
    const excerpt = typeof f.excerpt === 'string' ? f.excerpt : '';
    const missing = excerpt.trim() === '';
    const norm = missing ? '' : normalizeForMatch(excerpt);
    const hitCount = missing ? 0 : countOccurrences(draftNorm, norm);
    const weak = !missing && norm.length < WEAK_THRESHOLD;
    const multiHit = hitCount > 1;

    let status;
    let fatal = false;
    const advisories = [];
    if (!SEVERITY_ENUM.has(severity)) advisories.push(`未知 severity（${severity || '空'}），按 note 级只统计`);

    if (severity === 'strength') {
      if (missing) {
        status = 'exempt'; // SKILL：strength 可只引推理，豁免
        summary.exempt++;
      } else {
        // 照验但不 FATAL（no_hit 仅 advisory）
        status = hitCount > 0 ? 'hit' : 'no_hit';
        if (status === 'no_hit') advisories.push('strength 引文未命中（仅提示）');
        if (weak) advisories.push('weak_excerpt');
        if (multiHit) advisories.push('多处命中');
      }
    } else if (severity === 'note') {
      summary.note_findings++;
      // note 级不做 FATAL 检查（只统计；R2 轮任务口径）
      status = missing ? 'missing' : (hitCount > 0 ? 'hit' : 'no_hit');
      if (missing) advisories.push('note 缺 excerpt（仅统计）');
      else if (status === 'no_hit') advisories.push('note 引文未命中（仅统计）');
      if (!missing && weak) advisories.push('weak_excerpt');
      if (!missing && multiHit) advisories.push('多处命中');
    } else if (PROBLEM_SEVERITIES.has(severity)) {
      if (missing) {
        status = 'missing';
        fatal = true;
      } else if (hitCount === 0) {
        status = 'no_hit';
        fatal = true;
      } else {
        status = 'hit';
        if (weak) advisories.push('weak_excerpt');
        if (multiHit) advisories.push('多处命中');
      }
    } else {
      // 未知 severity：按 note 级只统计（不 FATAL）
      status = missing ? 'missing' : (hitCount > 0 ? 'hit' : 'no_hit');
    }

    const advisory = advisories.length > 0;
    if (fatal) summary.finding_fatals++;
    if (advisory) summary.advisories++;
    if (status === 'hit') summary.hit++;
    else if (status === 'no_hit') summary.no_hit++;
    else if (status === 'missing') summary.missing_excerpt++;
    if (weak) summary.weak_excerpt++;
    if (multiHit) summary.multi_hit++;

    rows.push({
      index: i,
      id: code ?? `finding:${i}`,
      severity: severity || null,
      code,
      excerpt_head: excerpt.slice(0, 24),
      status,
      hit_count: hitCount,
      weak,
      multi_hit: multiHit,
      fatal,
      advisory,
      detail: advisories.length > 0 ? advisories.join('；') : '',
    });
  }
  return { rows, summary };
}

// ---------------------------------------------------------------- 报告

function buildReport({ receipt, receiptForm, draftSource, draftHash, checkHash, strict, allowEmpty, rows, summary, fatalList, advisories }) {
  const hashOk = !checkHash || fatalList.every((x) => x.type !== 'hash_mismatch');
  const verdict = fatalList.length > 0 ? 'FAIL' : 'PASS';
  summary.fatal_total = fatalList.length; // finding 级 + 回执级合计（成功路径恒可判的口径）
  return {
    schema: SCHEMA,
    meta: {
      tool: PROG,
      version: VERSION,
      boundary: 'G2 验证证据存在性与回执↔草稿版本绑定，不验证引文相关性（红方 F8 边界，相关性归主控/红方抽查）',
      normalization: '全半角折叠+中西标点折叠+引号统一+破折号/省略号折叠+删全部空白',
      strict,
      allow_empty: allowEmpty,
      check_hash: checkHash,
    },
    receipt: {
      verdict: typeof receipt.verdict === 'string' ? receipt.verdict : null,
      reviewer_profile: typeof receipt.reviewer_profile === 'string' ? receipt.reviewer_profile : null,
      subject_hash: typeof receipt.subject_hash === 'string' ? receipt.subject_hash : null,
      subject_hash_match: hashOk,
      findings_total: summary.findings_total,
      form: receiptForm,
    },
    draft: { source: draftSource, content_hash: draftHash },
    fatal: fatalList,
    advisory_receipt: advisories,
    findings: rows,
    summary,
    verdict,
  };
}

function toHuman(r) {
  const lines = [];
  lines.push(`${PROG} v${r.meta.version}（G2 引文验证：存在性+版本绑定；不验证相关性）`);
  lines.push(`回执：verdict=${r.receipt.verdict} reviewer=${r.receipt.reviewer_profile ?? '-'} findings=${r.receipt.findings_total} hash_match=${r.receipt.subject_hash_match}`);
  lines.push(`草稿：${r.draft.source} ${r.draft.content_hash}`);
  for (const f of r.findings) {
    const flag = f.fatal ? 'FATAL' : (f.advisory ? 'ADVISORY' : 'ok');
    lines.push(`  [${flag}] #${f.index} ${f.severity ?? '-'} ${f.id} ${f.status}×${f.hit_count}${f.weak ? ' weak' : ''}${f.multi_hit ? ' multi' : ''}${f.detail ? ' — ' + f.detail : ''}「${f.excerpt_head}」`);
  }
  for (const x of r.fatal) lines.push(`  FATAL(${x.type}): ${x.detail}`);
  for (const a of r.advisory_receipt) lines.push(`  ADVISORY(回执级): ${a.detail}`);
  const s = r.summary;
  lines.push(`汇总：hit=${s.hit} no_hit=${s.no_hit} missing=${s.missing_excerpt} weak=${s.weak_excerpt} multi=${s.multi_hit} exempt=${s.exempt} note=${s.note_findings} FATAL=${s.fatal_total}（finding 级 ${s.finding_fatals}） ADVISORY=${s.advisories}`);
  lines.push(`verdict: ${r.verdict}`);
  return lines.join('\n');
}

// ---------------------------------------------------------------- CLI

function usage() {
  return [
    `用法：node scripts/${PROG}.mjs --receipt <回执.json|内联JSON> --draft <草稿.md> [--stdin-draft] [--json] [--strict] [--allow-empty] [--no-check-hash]`,
    '',
    '四路 FATAL（exit 1 = 纸面化回执，打回重审、不得落库）：',
    '  no_hit       blocking/warning 的 excerpt 归一化后在草稿中无命中',
    '  missing      blocking/warning 缺 excerpt / 空串',
    '  hash_mismatch  subject_hash ≠ sha256(草稿 utf8)（回执对错版本草稿同样判纸面化）',
    '  empty_findings_approved  findings=0 且 verdict=approved（空查回执，默认 FATAL；',
    '             确需放行加 --allow-empty，降为 advisory 并留痕豁免字样）',
    'ADVISORY（默认只报；--strict 升级 FATAL）：excerpt 归一化后 <8 字符（weak）/ 命中次数>1（多处命中）',
    'note / strength 级不做 FATAL（只统计）；strength 无 excerpt = exempt。',
    '',
    '边界声明（红方 F8）：本验证只管证据「存在性」与「回执↔草稿版本绑定」，',
    '不验证引文「相关性」——相关性归主控/红方抽查。',
    'exit：0 = 通过（可落库）；1 = 存在 FATAL；2 = 用法/输入错误。',
  ].join('\n');
}

async function main() {
  const argv = process.argv.slice(2);
  let receiptArg = null;
  let draftArg = null;
  let stdinDraft = false;
  let jsonOut = false;
  let strict = false;
  let allowEmpty = false;
  let checkHash = true;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    switch (a) {
      case '--receipt': receiptArg = argv[++i]; break;
      case '--draft': draftArg = argv[++i]; break;
      case '--stdin-draft': stdinDraft = true; break;
      case '--json': jsonOut = true; break;
      case '--strict': strict = true; break;
      case '--allow-empty': allowEmpty = true; break;
      case '--no-check-hash': checkHash = false; break;
      case '--help': case '-h': console.log(usage()); return;
      default: throw new UsageError(`未知参数：${a}`);
    }
  }
  if (!receiptArg) throw new UsageError('缺少 --receipt <回执.json|内联JSON>');
  if (!draftArg && !stdinDraft) throw new UsageError('缺少 --draft <草稿路径>（或 --stdin-draft）');

  // 回执：内联 JSON（以 { 开头）或文件路径
  let receiptRaw;
  if (receiptArg.trimStart().startsWith('{')) {
    receiptRaw = receiptArg;
  } else {
    receiptRaw = readFileSync(receiptArg, 'utf8');
  }
  const receipt = loadReceipt(receiptRaw);

  // 草稿：文件或 stdin（utf8 全文）
  let draftText;
  let draftSource;
  if (stdinDraft) {
    draftText = readFileSync(0, 'utf8');
    draftSource = '<stdin>';
  } else {
    draftText = readFileSync(draftArg, 'utf8');
    draftSource = draftArg;
  }
  const draftHash = contentHash(draftText);
  const draftNorm = normalizeForMatch(draftText);

  // 三路 FATAL 之 ③：subject_hash 版本绑定（--no-check-hash 可关）
  const fatalList = [];
  if (checkHash) {
    if (typeof receipt.subject_hash !== 'string' || receipt.subject_hash.length === 0) {
      fatalList.push({ type: 'hash_mismatch', detail: '回执缺 subject_hash，无法绑定草稿版本' });
    } else if (receipt.subject_hash !== draftHash) {
      fatalList.push({ type: 'hash_mismatch', detail: `subject_hash ${receipt.subject_hash} ≠ 草稿 ${draftHash}（回执对另一版草稿写的）` });
    }
  }

  const { rows, summary } = checkFindings(receipt.findings, draftNorm);

  // finding 级 FATAL（no_hit / missing）汇入 fatalList——exit 1 的判定源
  for (const row of rows) {
    if (row.fatal) {
      fatalList.push({
        type: row.status === 'missing' ? 'missing_excerpt' : 'no_hit',
        detail: `#${row.index} ${row.id}（${row.severity}）excerpt「${row.excerpt_head}」${row.status === 'missing' ? '缺失/空串' : '归一化后未在草稿命中'}`,
      });
    }
  }

  // 回执级 ④：空 findings + approved（红方 F7 空查回执防线）
  // R7-A1 起默认 FATAL（原「--strict 才拦」口径作废——对抗审查 P4-1：标准命令无人传 --strict，
  // 橡皮图章回执曾默认放行）；--allow-empty 显式豁免 = 降为 advisory 并留痕豁免字样。
  const advisories = [];
  if (summary.findings_total === 0 && receipt.verdict === 'approved') {
    if (allowEmpty) {
      advisories.push({
        type: 'empty_findings_approved',
        detail: 'findings 总数=0 且 verdict=approved：什么都没查的回执（--allow-empty 显式豁免留痕；相关性仍归主控/红方抽查）',
      });
    } else {
      fatalList.push({
        type: 'empty_findings_approved',
        detail: 'findings 总数=0 且 verdict=approved：什么都没查的回执（R7-A1 默认 FATAL；确需放行加 --allow-empty 并留痕）',
      });
    }
  }

  // --strict：仅 blocking/warning 的 finding 级 advisory（weak / 多处命中）升级 FATAL
  // （note/strength 级不做 FATAL 检查——R2 轮任务口径）
  if (strict) {
    for (const row of rows) {
      if (row.advisory && !row.fatal && PROBLEM_SEVERITIES.has(row.severity)) {
        fatalList.push({ type: 'advisory_escalated', detail: `#${row.index} ${row.id}（${row.detail}）—— --strict 升级` });
      }
    }
  }

  const report = buildReport({
    receipt,
    receiptForm: receipt.__form,
    draftSource,
    draftHash,
    checkHash,
    strict,
    allowEmpty,
    rows,
    summary,
    fatalList,
    advisories,
  });
  console.log(jsonOut ? JSON.stringify(report, null, 2) : toHuman(report));
  process.exitCode = fatalList.length > 0 ? 1 : 0;
}

const invokedDirectly = (() => {
  try {
    return Boolean(process.argv[1])
      && path.resolve(process.argv[1]).toLowerCase() === fileURLToPath(import.meta.url).toLowerCase();
  } catch {
    return false;
  }
})();

if (invokedDirectly) {
  try {
    await main();
  } catch (e) {
    if (e instanceof UsageError) {
      console.error(`${e.message}\n\n${usage()}`);
      process.exitCode = 2;
    } else {
      console.error(e && e.stack ? e.stack : String(e));
      process.exitCode = 2; // 读文件失败/JSON 解析失败等输入错误 ≠ 纸面化 FATAL
    }
  }
}
