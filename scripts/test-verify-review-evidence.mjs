#!/usr/bin/env node
/**
 * novelos-verify-review-evidence.mjs 的测试脚本（G2 引文验证夹具）。
 *
 * 覆盖（d2 计划 §3.4.F + 红方 F7/F8 处置）：
 *   ① 全命中回执 PASS（blocking/warning/note/strength 混排，strength 无 excerpt=exempt）
 *   ② 编造引文 no_hit → FATAL exit 1
 *   ③ blocking 缺 excerpt missing → FATAL exit 1
 *   ④ subject_hash 错配 hash_mismatch → FATAL exit 1；--no-check-hash 放行
 *   ⑤ 空 findings+approved：默认 ADVISORY exit 0；--strict exit 1（红方 F7 空查回执防线）
 *   ⑥ weak excerpt（归一化后 <8 字符）与多处命中（hit_count>1）报告；--strict 升级 FATAL
 *   ⑦ note-only 回执 PASS（note 缺 excerpt/未命中只统计不 FATAL——R2 轮任务口径）
 *   ⑧ 归一化变体：换行断句/全角逗号→半角/「」→“"" 引号统一 → hit
 *   ⑨ DB 行形态（findings_json 字符串）解析成功
 *   ⑩ 用法/输入错误 exit 2；--stdin-draft 与 --draft 等价
 *
 * 运行：node scripts/test-verify-review-evidence.mjs
 */

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CLI = path.join(__dirname, 'novelos-verify-review-evidence.mjs');
const COMPOSER = path.join(__dirname, 'novelos-compose-prompt.mjs');

const { normalizeForMatch, loadReceipt, checkFindings } = await import(`file://${CLI.replace(/\\/g, '/')}`);
const { contentHash } = await import(`file://${COMPOSER.replace(/\\/g, '/')}`);

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

function runCli(extraArgs, input) {
  return spawnSync(process.execPath, ['--no-warnings', CLI, ...extraArgs], {
    encoding: 'utf8',
    cwd: path.resolve(__dirname, '..'),
    input,
  });
}

// ---------------------------------------------------------------- 夹具（临时目录，不入仓）

const tmp = mkdtempSync(path.join(tmpdir(), 'g2-verify-'));

const DRAFT = [
  '# 第 1 章 试炼',
  '',
  '雪停在凌晨三点，江离把北城的轮廓记熟了。这不是他第一次来北城，而是第一次以「执行人」的身份来。',
  '风从街口灌进来，他忽然觉得冷。',
  '任务失败不是惩罚，而是清零——积分、装备，还有他在三个世界里攒下的全部人脉，一样都留不住。',
  '系统提示音适时地响起：任务开始。',
  '',
].join('\n');
const draftPath = path.join(tmp, 'draft.md');
writeFileSync(draftPath, DRAFT, 'utf8');
const draftHash = contentHash(DRAFT);

/** 组装最小合法 receipt（字段名以 review-receipt-candidate.schema.json 为准）。 */
function receipt({ findings, verdict = 'rejected', subject_hash = draftHash }) {
  return {
    subject_type: 'chapter',
    subject_ref: 'chapter:test-0000',
    subject_hash,
    verdict,
    reviewer_profile: 'model:fixture:model-x',
    findings,
    evidence_refs: ['chapters:chapter:test-0000'],
  };
}
const finding = (over = {}) => ({
  severity: 'blocking',
  message: '[fpr:L01] 测试 finding',
  evidence_refs: ['para:1'],
  ...over,
});

function writeReceipt(name, obj) {
  const p = path.join(tmp, name);
  writeFileSync(p, typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2), 'utf8');
  return p;
}

// ---------------------------------------------------------------- 纯函数单测

test('归一化：全角 ASCII 折叠（！→! ，→, Ａ→A）', () => {
  assert.equal(normalizeForMatch('任务开始！'), normalizeForMatch('任务开始!'));
  assert.equal(normalizeForMatch('，'), ',');
  assert.equal(normalizeForMatch('Ａｂ'), 'Ab');
});

test('归一化：引号统一（「」『』“”\'"→"）', () => {
  assert.equal(normalizeForMatch('「执行人」'), normalizeForMatch('“执行人”'));
  assert.equal(normalizeForMatch('『执行人』'), normalizeForMatch("'执行人'"));
});

test('归一化：破折号与省略号折叠、删全部空白（换行断句照常命中）', () => {
  assert.equal(normalizeForMatch('清零——积分'), normalizeForMatch('清零—积分'));
  assert.equal(normalizeForMatch('清零–积分'), normalizeForMatch('清零—积分'));
  assert.equal(normalizeForMatch('……'), '…');
  assert.equal(normalizeForMatch('...'), '…');
  assert.equal(normalizeForMatch('不是惩罚，\n而是清零'), '不是惩罚,而是清零');
});

test('loadReceipt：candidate 与 DB 行（findings_json 字符串）双形态', () => {
  const cand = loadReceipt(JSON.stringify(receipt({ findings: [] })));
  assert.equal(cand.__form, 'candidate');
  const row = {
    ...receipt({ findings: [] }),
    findings: undefined,
    findings_json: JSON.stringify([finding({ severity: 'note' })]),
  };
  const parsed = loadReceipt(JSON.stringify(row));
  assert.equal(parsed.__form, 'db_row');
  assert.equal(parsed.findings.length, 1);
});

test('checkFindings：strength 无 excerpt = exempt；未知 severity 只统计不 FATAL', () => {
  const { rows, summary } = checkFindings(
    [finding({ severity: 'strength', message: '亮点', evidence_refs: ['x'] }), finding({ severity: 'weird' })],
    normalizeForMatch(DRAFT),
  );
  assert.equal(rows[0].status, 'exempt');
  assert.equal(rows[1].fatal, false);
  assert.equal(summary.exempt, 1);
  assert.equal(summary.finding_fatals, 0);
});

// ---------------------------------------------------------------- CLI 子进程断言

test('① 全命中回执 PASS（exit 0，summary 计数正确）', () => {
  const p = writeReceipt('ok.json', receipt({
    findings: [
      finding({ excerpt: '任务失败不是惩罚，而是清零' }),
      finding({ severity: 'warning', message: 'w', evidence_refs: ['x'], excerpt: '风从街口灌进来' }),
      finding({ severity: 'note', message: 'n', evidence_refs: ['x'], excerpt: '雪停在凌晨三点' }),
      finding({ severity: 'strength', message: 's', evidence_refs: ['x'] }),
    ],
  }));
  const r = runCli(['--receipt', p, '--draft', draftPath, '--json']);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const j = JSON.parse(r.stdout);
  assert.equal(j.schema, 'novelos.review-evidence-verify.v1');
  assert.equal(j.verdict, 'PASS');
  assert.equal(j.receipt.subject_hash_match, true);
  assert.deepEqual([j.summary.hit, j.summary.no_hit, j.summary.missing_excerpt, j.summary.exempt], [3, 0, 0, 1]);
  assert.ok(j.meta.boundary.includes('不验证引文相关性'));
});

test('② 编造引文 no_hit → FATAL exit 1', () => {
  const p = writeReceipt('nohit.json', receipt({
    findings: [
      finding({ excerpt: '任务失败不是惩罚，而是清零' }),
      finding({ message: '整体节奏拖沓', evidence_refs: ['x'], excerpt: '这句话在草稿里根本不存在' }),
    ],
  }));
  const r = runCli(['--receipt', p, '--draft', draftPath, '--json']);
  assert.equal(r.status, 1);
  const j = JSON.parse(r.stdout);
  assert.equal(j.verdict, 'FAIL');
  assert.equal(j.findings[1].status, 'no_hit');
  assert.equal(j.findings[1].fatal, true);
  assert.equal(j.summary.fatal_total, 1);
});

test('③ blocking 缺 excerpt / 空串 → missing FATAL exit 1', () => {
  const p = writeReceipt('missing.json', receipt({
    findings: [
      finding({ message: '没给证据' }),
      finding({ message: '空串', excerpt: '   ' }),
    ],
  }));
  const r = runCli(['--receipt', p, '--draft', draftPath, '--json']);
  assert.equal(r.status, 1);
  const j = JSON.parse(r.stdout);
  assert.equal(j.findings[0].status, 'missing');
  assert.equal(j.findings[1].status, 'missing');
  assert.equal(j.summary.fatal_total, 2);
});

test('④ subject_hash 错配 → hash_mismatch FATAL；--no-check-hash 放行', () => {
  const p = writeReceipt('hashbad.json', receipt({
    subject_hash: 'sha256:' + '0'.repeat(64),
    findings: [finding({ excerpt: '任务失败不是惩罚，而是清零' })],
  }));
  const r1 = runCli(['--receipt', p, '--draft', draftPath, '--json']);
  assert.equal(r1.status, 1);
  const j1 = JSON.parse(r1.stdout);
  assert.equal(j1.fatal[0].type, 'hash_mismatch');
  assert.equal(j1.receipt.subject_hash_match, false);
  // excerpt 本身命中，仅关掉绑定校验即 PASS
  const r2 = runCli(['--receipt', p, '--draft', draftPath, '--json', '--no-check-hash']);
  assert.equal(r2.status, 0, r2.stdout + r2.stderr);
});

test('⑤ 空 findings+approved：默认 ADVISORY exit 0；--strict FATAL exit 1（红方 F7）', () => {
  const p = writeReceipt('empty.json', receipt({ verdict: 'approved', findings: [] }));
  const r1 = runCli(['--receipt', p, '--draft', draftPath, '--json']);
  assert.equal(r1.status, 0, r1.stdout + r1.stderr);
  const j1 = JSON.parse(r1.stdout);
  assert.equal(j1.advisory_receipt[0].type, 'empty_findings_approved');
  assert.equal(j1.verdict, 'PASS');
  const r2 = runCli(['--receipt', p, '--draft', draftPath, '--json', '--strict']);
  assert.equal(r2.status, 1);
  assert.equal(JSON.parse(r2.stdout).fatal[0].type, 'empty_findings_approved');
  // 空 findings + rejected 不触发该 advisory（F7 只对准 approved 空查）
  const p2 = writeReceipt('empty-rej.json', receipt({ verdict: 'rejected', findings: [] }));
  const r3 = runCli(['--receipt', p2, '--draft', draftPath, '--json']);
  assert.equal(r3.status, 0);
  assert.equal(JSON.parse(r3.stdout).advisory_receipt.length, 0);
});

test('⑥ weak excerpt（<8 字符）与多处命中报告；--strict 升级 FATAL', () => {
  const p = writeReceipt('weak.json', receipt({
    findings: [
      finding({ message: '超短引文', evidence_refs: ['x'], excerpt: '雪停在' }),        // 3 字，命中 1 → weak
      finding({ message: '正常长度', evidence_refs: ['x'], excerpt: '系统提示音适时地响起' }), // 10 字，命中 1
    ],
  }));
  // 构造多处命中：excerpt 选草稿里出现 2 次的串
  const doubled = DRAFT + '\n风从街口灌进来，他忽然觉得冷。\n';
  const draft2 = path.join(tmp, 'draft2.md');
  writeFileSync(draft2, doubled, 'utf8');
  const p2 = writeReceipt('multi.json', receipt({
    subject_hash: contentHash(doubled),
    findings: [finding({ excerpt: '风从街口灌进来' })],
  }));
  const r1 = runCli(['--receipt', p, '--draft', draftPath, '--json']);
  assert.equal(r1.status, 0, r1.stdout + r1.stderr);
  const j1 = JSON.parse(r1.stdout);
  assert.equal(j1.findings[0].weak, true);
  assert.equal(j1.summary.weak_excerpt, 1);
  assert.equal(j1.summary.fatal_total, 0);
  const r2 = runCli(['--receipt', p2, '--draft', draft2, '--json']);
  assert.equal(r2.status, 0);
  const j2 = JSON.parse(r2.stdout);
  assert.equal(j2.findings[0].hit_count, 2);
  assert.equal(j2.findings[0].multi_hit, true);
  // --strict：advisory 升级 FATAL
  const r3 = runCli(['--receipt', p, '--draft', draftPath, '--json', '--strict']);
  assert.equal(r3.status, 1);
  assert.ok(JSON.parse(r3.stdout).fatal.length >= 1);
});

test('⑦ note-only 回执 PASS（缺 excerpt/未命中只统计，--strict 也不升级——R2 轮任务口径）', () => {
  const p = writeReceipt('noteonly.json', receipt({
    verdict: 'approved',
    findings: [
      finding({ severity: 'note', message: '没证据的备注' }),
      finding({ severity: 'note', message: '抄错的备注', evidence_refs: ['x'], excerpt: '这句备注也不在草稿里' }),
      finding({ severity: 'strength', message: '抄错的高亮', evidence_refs: ['x'], excerpt: '这句高亮也不在草稿里' }),
    ],
  }));
  const r1 = runCli(['--receipt', p, '--draft', draftPath, '--json']);
  assert.equal(r1.status, 0, r1.stdout + r1.stderr);
  const j1 = JSON.parse(r1.stdout);
  assert.equal(j1.summary.note_findings, 2);
  assert.equal(j1.summary.fatal_total, 0);
  const r2 = runCli(['--receipt', p, '--draft', draftPath, '--json', '--strict']);
  assert.equal(r2.status, 0, 'note/strength 级不做 FATAL 检查（只统计）');
});

test('⑧ 归一化变体：换行断句/全半角/引号体例混用 → hit', () => {
  const p = writeReceipt('norm.json', receipt({
    findings: [
      // 草稿原文含「执行人」直角引号，excerpt 用弯引号
      finding({ excerpt: '以“执行人”的身份来' }),
      // 草稿原文「，而是」，excerpt 用半角逗号
      finding({ excerpt: '不是惩罚,而是清零——积分' }),
    ],
  }));
  const r = runCli(['--receipt', p, '--draft', draftPath, '--json']);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const j = JSON.parse(r.stdout);
  assert.equal(j.findings[0].status, 'hit');
  assert.equal(j.findings[1].status, 'hit');
});

test('⑨ DB 行形态（findings_json 字符串）解析成功', () => {
  const row = {
    id: 'review:fixture',
    subject_ref: 'chapter:test-0000',
    subject_hash: draftHash,
    verdict: 'rejected',
    reviewer_profile: 'agent:fix@model-x',
    findings_json: JSON.stringify([finding({ excerpt: '任务失败不是惩罚，而是清零' })]),
    evidence_refs_json: '[]',
  };
  const p = writeReceipt('dbrow.json', JSON.stringify(row));
  const r = runCli(['--receipt', p, '--draft', draftPath, '--json']);
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const j = JSON.parse(r.stdout);
  assert.equal(j.receipt.form, 'db_row');
  assert.equal(j.findings[0].status, 'hit');
});

test('⑩ 用法/输入错误 exit 2；--stdin-draft 与 --draft 等价；内联 JSON 回执', () => {
  assert.equal(runCli(['--draft', draftPath]).status, 2);                    // 缺 --receipt
  assert.equal(runCli(['--receipt', '{}']).status, 2);                       // 缺 --draft
  assert.equal(runCli(['--receipt', 'x', '--draft', 'y', '--bogus']).status, 2); // 未知参数
  const bad = writeReceipt('bad.json', '{ not json');
  assert.equal(runCli(['--receipt', bad, '--draft', draftPath]).status, 2);  // JSON 解析失败
  const nofind = writeReceipt('nofindings.json', JSON.stringify({ subject_hash: draftHash, verdict: 'approved' }));
  assert.equal(runCli(['--receipt', nofind, '--draft', draftPath]).status, 2); // 两形态均不匹配
  const p = writeReceipt('inline-ok.json', receipt({ findings: [finding({ excerpt: '雪停在凌晨三点' })] }));
  const viaFile = runCli(['--receipt', p, '--draft', draftPath, '--json']);
  const viaStdin = runCli(['--receipt', p, '--stdin-draft', '--json'], DRAFT);
  assert.equal(viaFile.status, 0);
  assert.equal(viaStdin.status, 0);
  assert.equal(JSON.parse(viaStdin.stdout).draft.source, '<stdin>');
  // 内联 JSON（以 { 开头）
  const inline = runCli(['--receipt', JSON.stringify(receipt({ findings: [finding({ excerpt: '雪停在凌晨三点' })] })), '--draft', draftPath, '--json']);
  assert.equal(inline.status, 0);
});

// ---------------------------------------------------------------- 汇总

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  for (const f of failures) console.error(`- ${f.name}: ${f.e.stack || f.e.message}`);
  process.exitCode = 1;
} else {
  rmSync(tmp, { recursive: true, force: true });
}
