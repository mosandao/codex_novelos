#!/usr/bin/env node
/**
 * novelos-compose-prompt.mjs 的测试脚本。
 *
 * 覆盖：
 *   ① direction 资产对生产库真实项目产出非空文本（含主干标题与输入数据区标记）
 *   ② 未知 asset 报错且退出码非 0
 *   ③ --asset direction-review 缺 --subject 时报错
 *   ④ when 规则求值纯函数单测（equals/not_null/is_null/non_empty/all/query ops/异常路径）
 *   附：pyJsonDumps 格式等价、content_hash 向量、自检节抽取、fusion 载荷结构校验
 *
 * 运行：node scripts/test-compose-prompt.mjs
 */

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CLI = path.join(__dirname, 'novelos-compose-prompt.mjs');
const ROOT = path.resolve(__dirname, '..');

const { evaluateWhen, getField, pyJsonDumps, contentHash, extractChecklist,
  extractModuleChecklist, validateFusionPayloadStruct } = await import(
  `file://${CLI.replace(/\\/g, '/')}`);

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

function runCli(extraArgs) {
  return spawnSync(process.execPath, ['--no-warnings', CLI, ...extraArgs], {
    encoding: 'utf8',
    cwd: ROOT,
  });
}

// ---------------------------------------------------------------- 环境准备

function firstProjectId() {
  const db = new DatabaseSync(path.join(ROOT, 'data', 'novelos-v2.db'), { readOnly: true });
  try {
    const row = db.prepare('SELECT id FROM projects LIMIT 1').get();
    return row ? row.id : null;
  } finally {
    db.close();
  }
}

const projectId = firstProjectId();

// ---------------------------------------------------------------- ① direction 对真实项目

test('①a direction 资产对生产项目 exit=0 且输出非空', () => {
  assert.ok(projectId, '生产库无项目可测');
  const r = runCli(['--asset', 'direction', '--project', projectId, '--no-log']);
  assert.equal(r.status, 0, `stderr: ${r.stderr}`);
  assert.ok(r.stdout.length > 1000, '输出过短');
});

test('①b 输出含主干标题（prompt.md 首个 H1）', () => {
  const promptMd = readFileSync(
    path.join(ROOT, 'catalog/skills/planning/story-direction/prompt.md'), 'utf8');
  const h1 = promptMd.split('\n').find((l) => l.startsWith('# '));
  assert.ok(h1 && h1.length > 2);
  const r = runCli(['--asset', 'direction', '--project', projectId, '--no-log']);
  assert.ok(r.stdout.includes(h1.trim()), `缺主干标题「${h1.trim()}」`);
});

test('①c 输出含输入数据区标记', () => {
  const r = runCli(['--asset', 'direction', '--project', projectId, '--no-log']);
  assert.ok(r.stdout.includes('## 输入数据（权威源，正文引用以此为准）'));
});

test('①d 输出含尾部自检汇总节', () => {
  const r = runCli(['--asset', 'direction', '--project', projectId, '--no-log']);
  assert.ok(r.stdout.includes('## 交付前自检（普适项 + 条件模块附加项，逐项通过才返回）'));
});

// ---------------------------------------------------------------- ② 未知 asset

test('② 未知 asset 报错退出码非 0', () => {
  const r = runCli(['--asset', 'does-not-exist', '--project', projectId]);
  assert.notEqual(r.status, 0);
  assert.ok(r.stderr.includes("invalid choice: 'does-not-exist'"), r.stderr);
});

// ---------------------------------------------------------------- ③ 缺 --subject

test('③ direction-review 缺 --subject 报错', () => {
  const r = runCli(['--asset', 'direction-review', '--project', projectId, '--no-log']);
  assert.notEqual(r.status, 0);
  assert.ok(r.stderr.includes('--subject'), r.stderr);
});

// ---------------------------------------------------------------- ④ when 规则纯函数

test('④a equals 命中与未命中', () => {
  const ctx = { setup: { channel: '男频' } };
  assert.equal(evaluateWhen({ field: 'setup.channel', equals: '男频' }, ctx), true);
  assert.equal(evaluateWhen({ field: 'setup.channel', equals: '女频' }, ctx), false);
});

test('④b 深层路径取不到返回 null（is_null 命中）', () => {
  const ctx = { setup: {} };
  assert.equal(getField(ctx, 'setup.platform_traits.model'), null);
  assert.equal(evaluateWhen({ field: 'setup.platform_traits.model', is_null: true }, ctx), true);
  assert.equal(evaluateWhen({ field: 'setup.a.b.c', not_null: true }, ctx), false);
});

test('④c not_null / non_empty 区分 null 与空串', () => {
  const ctx = { genre_profile: {}, aesthetic_styles: [], note: '' };
  assert.equal(evaluateWhen({ field: 'genre_profile', not_null: true }, ctx), true);
  assert.equal(evaluateWhen({ field: 'note', not_null: true }, ctx), true); // '' 非 None
  assert.equal(evaluateWhen({ field: 'note', non_empty: true }, ctx), false); // '' 为假
  assert.equal(evaluateWhen({ field: 'aesthetic_styles', non_empty: true }, ctx), false);
  assert.equal(evaluateWhen({ field: 'missing', is_null: true }, ctx), true);
});

test('④d all 组合（与）', () => {
  const ctx = { setup: { channel: '男频', platform_traits: { model: '免费算法' } } };
  assert.deepEqual(evaluateWhen({
    all: [
      { field: 'setup.channel', equals: '男频' },
      { field: 'setup.platform_traits.model', equals: '免费算法' },
    ],
  }, ctx), true);
  assert.deepEqual(evaluateWhen({
    all: [
      { field: 'setup.channel', equals: '男频' },
      { field: 'setup.channel', equals: '女频' },
    ],
  }, ctx), false);
});

test('④e query 比较符 ==/!=/>/>=/</<=', () => {
  const ctx = { persona_library_count: 12 };
  assert.equal(evaluateWhen({ query: 'persona_library_count', op: '==', value: 12 }, ctx), true);
  assert.equal(evaluateWhen({ query: 'persona_library_count', op: '!=', value: 12 }, ctx), false);
  assert.equal(evaluateWhen({ query: 'persona_library_count', op: '>=', value: 10 }, ctx), true);
  assert.equal(evaluateWhen({ query: 'persona_library_count', op: '>', value: 10 }, ctx), true);
  assert.equal(evaluateWhen({ query: 'persona_library_count', op: '<=', value: 10 }, ctx), false);
  assert.equal(evaluateWhen({ query: 'persona_library_count', op: '<', value: 20 }, ctx), true);
});

test('④f query 目标缺失返回 false；未知 op 抛 ValueError', () => {
  const ctx = {};
  assert.equal(evaluateWhen({ query: 'absent', op: '==', value: 1 }, ctx), false);
  assert.throws(() => evaluateWhen({ query: 'x', op: '~', value: 1 }, { x: 1 }), /未知 op/);
});

test('④g 未知 when 规则抛错', () => {
  assert.throws(() => evaluateWhen({}, {}), /未知 when 规则/);
});

// ---------------------------------------------------------------- 附加等价件单测

test('附1 pyJsonDumps(indent=1) 与 json.dumps(indent=1) 同形', () => {
  const obj = { a: ['x', 'y'], b: '中文', n: 3, empty: [], none: null };
  assert.equal(pyJsonDumps(obj, 1), [
    '{',
    ' "a": [',
    '  "x",',
    '  "y"',
    ' ],',
    ' "b": "中文",',
    ' "n": 3,',
    ' "empty": [],',
    ' "none": null',
    '}',
  ].join('\n'));
});

test('附2 pyJsonDumps 紧凑模式分隔符为 ", " / ": "（py 默认）', () => {
  assert.equal(pyJsonDumps({ a: 1, b: [1, 2] }), '{"a": 1, "b": [1, 2]}');
});

test('附3 content_hash 与 sha256 标准向量一致', () => {
  // sha256("abc") = ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
  assert.equal(contentHash('abc'),
    'sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
});

test('附4 extractChecklist 把自检节剪切到尾部结构位', () => {
  const md = '# T\n\n## A\n正文A\n\n## 交付前自检\n- 项1\n\n## B\n正文B\n';
  const [rest, checklist] = extractChecklist(md.replace(/\r/g, ''));
  assert.ok(rest.includes('## A') && rest.includes('## B'));
  assert.ok(!rest.includes('## 交付前自检'));
  assert.ok(checklist.startsWith('## 交付前自检'));
  assert.ok(checklist.includes('- 项1'));
});

test('附5 extractModuleChecklist 抽出附加自检正文并去标题', () => {
  const mod = '模块正文\n\n## 附加自检\n- 检查点X';
  const [rest, checklist] = extractModuleChecklist(mod);
  assert.equal(rest.includes('## 附加自检'), false);
  assert.ok(rest.includes('模块正文'));
  assert.equal(checklist, '- 检查点X');
});

test('附6 fusion 载荷结构校验：合法放行、非法报字段路径', () => {
  const good = {
    request_type: 'novelos.project.create.v3',
    setup: {
      title: 'T', author_kernel: { mode: 'create', kernel_hints: {} }, channel: '全向',
      platform: 'p', platform_traits: null, scale: '短篇（30万字以下）',
      primary_genre: 'g', secondary_directions: [], emotional_surface: ['燃'],
      emotional_core: 'c', tonal_contrast: null, aesthetic_styles: ['冷'],
      genre_profile: null, reference_material: null,
    },
  };
  assert.deepEqual(validateFusionPayloadStruct(good), []);
  const bad = { ...good, extra: 1 };
  bad.setup.channel = '无效频道';
  bad.setup.emotional_surface = [];
  const errs = validateFusionPayloadStruct(bad);
  assert.ok(errs.some((e) => e.includes('extra')), JSON.stringify(errs));
  assert.ok(errs.some((e) => e.includes('setup.channel')), JSON.stringify(errs));
  assert.ok(errs.some((e) => e.includes('setup.emotional_surface')), JSON.stringify(errs));
});

// ---------------------------------------------------------------- 汇总

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  for (const f of failures) console.error(`- ${f.name}: ${f.e.stack || f.e.message}`);
  process.exit(1);
}
