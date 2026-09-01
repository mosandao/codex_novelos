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
import { readFileSync, rmSync, copyFileSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CLI = path.join(__dirname, 'novelos-compose-prompt.mjs');
const ROOT = path.resolve(__dirname, '..');

const { evaluateWhen, getField, pyJsonDumps, contentHash, extractChecklist,
  extractModuleChecklist, validateFusionPayloadStruct, resolveKnowledge, verifyKernelBinding,
  validateManifestStruct } = await import(
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

const prodProjectId = firstProjectId();
const FIXTURE_DB = '/tmp/r3-compose-fixture.db';
const FIXTURE_LOG = '/tmp/r3-compose-fixture-log';

function buildFixtureDb() {
  rmSync(FIXTURE_DB, { force: true });
  rmSync(FIXTURE_LOG, { recursive: true, force: true });
  copyFileSync(path.join(ROOT, 'data', 'novelos-v2.db'), FIXTURE_DB);
  const db = new DatabaseSync(FIXTURE_DB);
  let pRow = db.prepare('SELECT id FROM projects LIMIT 1').get();
  let pid;
  if (!pRow) {
    pid = 'project:zzfix-001';
    const setup = {
      channel: '男频',
      platform: '起点',
      scale: '中篇（50-100万字）',
      primary_genre: '诸天无限',
      secondary_directions: ['无限流'],
      emotional_surface: ['爽快'],
      emotional_core: '对抗宿命',
      tonal_contrast: null,
      aesthetic_styles: ['硬朗'],
      genre_profile: { primary_genre: '诸天无限' },
      reference_material: ''
    };
    db.prepare(`INSERT INTO projects (id, name, description, version, metadata_json)
      VALUES (?, '测试项目', '用于测试', 1, ?)`).run(pid, JSON.stringify({ setup_schema_version: 3, setup }));

    const sigJson = JSON.stringify({
      schema_version: 2,
      display_name: '测试创作者',
      persona: {
        narrative_voice: '冷峻克制',
        anchors: {
          five_dimensions: { life_trajectory: '工程师转型', career_track: '技术' },
          trait_profile: '严谨',
          inner_tension: '理性与情感',
          theme_orientation: { dominant: '秩序' }
        },
        blindspots: { cannot_write: ['宫斗'], refuses: ['无脑装逼'] }
      },
      creative_boundaries: { core_interests: ['机制设计'], taboos: ['机械降神'] }
    });
    const sigHash = 'sha256:' + createHash('sha256').update(sigJson, 'utf8').digest('hex');
    db.prepare(`INSERT INTO resources (id, media_type, content, content_hash) VALUES ('resource:zzfix-sig', 'application/json', CAST(? AS BLOB), ?)`).run(sigJson, sigHash);
    db.prepare(`INSERT INTO creator_profiles (id, display_name, ownership) VALUES ('creator-profile:zzfix', '测试创作者', 'user')`).run();
    db.prepare(`INSERT INTO creator_profile_versions (id, profile_id, revision, content_resource_id, subject_hash)
      VALUES ('creator-profile-version:zzfix', 'creator-profile:zzfix', 1, 'resource:zzfix-sig', ?)`).run(sigHash);
    db.prepare(`INSERT INTO project_creator_bindings (project_id, profile_id, profile_version_id, profile_revision, subject_hash, binding_mode)
      VALUES (?, 'creator-profile:zzfix', 'creator-profile-version:zzfix', 1, ?, 'kernel_derive')`).run(pid, sigHash);
  } else {
    pid = pRow.id;
  }
  const planText = '第一章章纲：主角进入拍卖行，与对手展开谈判与多轮对话；'
    + '开篇用危机切入，中段战斗收尾。';
  const hash = 'sha256:' + createHash('sha256').update(planText, 'utf8').digest('hex');
  db.prepare("INSERT OR REPLACE INTO resources (id, media_type, content, content_hash) "
    + "VALUES ('resource:zzfix-plan', 'text/markdown', CAST(? AS BLOB), ?)").run(planText, hash);
  db.prepare("INSERT OR REPLACE INTO planning_assets (id, project_id, asset_type, scope_ref, revision, "
    + "status, content_resource_id, producer_role, metadata_json) "
    + "VALUES ('planning:zzfix-plan', ?, 'chapter_plan', 'volume:zzfix#1', 1, 'locked', "
    + "'resource:zzfix-plan', 'chapter_plan', '{}')").run(pid);
  db.close();
  return pid;
}

const projectId = prodProjectId || buildFixtureDb();
const baseArgs = prodProjectId ? [] : ['--db', FIXTURE_DB];

// ---------------------------------------------------------------- ① direction 对真实项目

test('①a direction 资产对生产/夹具项目 exit=0 且输出非空', () => {
  assert.ok(projectId, '无项目可测');
  const r = runCli(['--asset', 'direction', '--project', projectId, ...baseArgs, '--no-log']);
  assert.equal(r.status, 0, `stderr: ${r.stderr}`);
  assert.ok(r.stdout.length > 1000, '输出过短');
});

test('①b 输出含主干标题（prompt.md 首个 H1）', () => {
  const promptMd = readFileSync(
    path.join(ROOT, 'catalog/skills/planning/story-direction/prompt.md'), 'utf8');
  const h1 = promptMd.split('\n').find((l) => l.startsWith('# '));
  assert.ok(h1 && h1.length > 2);
  const r = runCli(['--asset', 'direction', '--project', projectId, ...baseArgs, '--no-log']);
  assert.ok(r.stdout.includes(h1.trim()), `缺主干标题「${h1.trim()}」`);
});

test('①c 输出含输入数据区标记', () => {
  const r = runCli(['--asset', 'direction', '--project', projectId, ...baseArgs, '--no-log']);
  assert.ok(r.stdout.includes('## 输入数据（权威源，正文引用以此为准）'));
});

test('①d 输出含尾部自检汇总节', () => {
  const r = runCli(['--asset', 'direction', '--project', projectId, ...baseArgs, '--no-log']);
  assert.ok(r.stdout.includes('## 交付前自检（普适项 + 条件模块附加项，逐项通过才返回）'));
});

// ---------------------------------------------------------------- ② 未知 asset

test('② 未知 asset 报错退出码非 0', () => {
  const r = runCli(['--asset', 'does-not-exist', '--project', projectId, ...baseArgs]);
  assert.notEqual(r.status, 0);
  assert.ok(r.stderr.includes("invalid choice: 'does-not-exist'"), r.stderr);
});

// ---------------------------------------------------------------- ③ 缺 --subject

test('③ direction-review 缺 --subject 报错', () => {
  const r = runCli(['--asset', 'direction-review', '--project', projectId, ...baseArgs, '--no-log']);
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

// ---------------------------------------------------------------- ⑦ knowledge 槽（R3）

const rfSync = readFileSync;

/** 内存夹具库：planning_assets + resources 最小结构（knowledgePlanText 查询面）。 */
function makeMemoryDb(planText) {
  const db = new DatabaseSync(':memory:');
  db.exec('CREATE TABLE planning_assets (id TEXT PRIMARY KEY, project_id TEXT, '
    + 'asset_type TEXT, scope_ref TEXT, revision INTEGER, status TEXT, '
    + 'content_resource_id TEXT, metadata_json TEXT)');
  db.exec('CREATE TABLE resources (id TEXT PRIMARY KEY, content BLOB)');
  if (planText !== null) {
    db.prepare("INSERT INTO resources VALUES ('res:1', ?)").run(planText);
    db.prepare("INSERT INTO planning_assets VALUES ('pa:1', 'project:x', 'chapter_plan', "
      + "'vol:1', 1, 'locked', 'res:1', '{}')").run();
  }
  return db;
}

/** 临时夹具蒸馏文件（config/knowledge/distilled.zz-kfix.json），测试后清理。 */
const FIXTURE_FILE = path.join(ROOT, 'config', 'knowledge', 'distilled.zz-kfix.json');
function buildFixtureDoc({ longEntries = 3, fillerEntries = 30 } = {}) {
  const longTrigger = '对话场景。' + '超长触发场景。'.repeat(120); // 含场景词抬高命中分；≈1000B 渲染必超 512B
  const entries = [];
  for (let i = 1; i <= longEntries; i++) {
    entries.push({
      id: `kg-zz-kfix-${String(i).padStart(3, '0')}`,
      name: `长条目${i}`,
      trigger_scene: longTrigger,
      formula: ['步骤甲', '步骤乙', '步骤丙'],
      anti_patterns: ['反例一', '反例二'],
      genres: ['ZZ题材九'],
      source: { orig_ids: [987654], book_sources: ['ZZ书名'] },
      placement: 'slot',
      scene_tags: ['对话'],
    });
  }
  for (let i = longEntries + 1; i <= longEntries + fillerEntries; i++) {
    entries.push({
      id: `kg-zz-kfix-${String(i).padStart(3, '0')}`,
      name: i === longEntries + 1 ? '白名单探测条目' : `短条目${i}`,
      trigger_scene: '短触发场景，含对话。',
      formula: ['一步', '两步'],
      anti_patterns: ['一反'],
      genres: ['ZZ题材九'],
      source: { orig_ids: [987654], book_sources: ['ZZ书名'] },
      placement: 'slot',
      scene_tags: ['对话'],
    });
  }
  return {
    domain: 'zz-kfix',
    generated: '2026-08-29',
    entries,
    card_module_md: '1. 夹具卡面模块(仅测试用)。',
  };
}
function withFixtureFile(doc, fn) {
  writeFileSync(FIXTURE_FILE, JSON.stringify(doc), 'utf8');
  try {
    fn();
  } finally {
    rmSync(FIXTURE_FILE, { force: true });
  }
}

test('⑦a knowledge 槽渲染：槽头标注/溯源标记/字段白名单/512B 单条截断', () => {
  withFixtureFile(buildFixtureDoc(), () => {
    const db = makeMemoryDb('本章为章纲：开场是一场谈判与多次对话。');
    try {
      const sections = resolveKnowledge(db, 'zz-kfix', 'project:x');
      assert.ok(sections !== null, '夹具域文件存在时槽不得静默跳过');
      const [title, body] = sections[0];
      assert.ok(title.includes('knowledge:zz-kfix'), title);
      assert.ok(body.includes('非 Canon、无对账义务，示例表述不构成成稿标准'), '缺槽头标注');
      // 探测条目（kg-zz-kfix-004，score 最高组）必在第一组
      assert.ok(body.includes('（kg-zz-kfix-004）'), '缺条目溯源标记');
      assert.ok(body.includes('白名单探测条目'), '探测条目未渲染');
      // 字段白名单（P2-15）：source/orig_ids/genres 不渲染
      assert.ok(!body.includes('987654'), '泄漏 orig_ids');
      assert.ok(!body.includes('ZZ书名'), '泄漏 book_sources');
      assert.ok(!body.includes('ZZ题材九'), '泄漏 genres');
      // 单条 ≤512B（超限 UTF-8 安全截断）
      const itemLines = body.split('\n').filter((l) => l.startsWith('- '));
      assert.ok(itemLines.length > 0, '无条目行');
      for (const line of itemLines) {
        assert.ok(Buffer.byteLength(line, 'utf8') <= 512,
          `单条超 512B：${Buffer.byteLength(line, 'utf8')}B`);
      }
      const truncated = itemLines.filter((l) => l.includes('…'));
      assert.ok(truncated.length > 0, '超长条目未被截断（缺省略号标记）');
      db.close();
    } catch (e) {
      db.close();
      throw e;
    }
  });
});

test('⑦b knowledge 槽总限 4096B：超限按排名截断且脚注如实', () => {
  // 12 条长条目（各渲染至 512B）→ top-5×2 组全为长条目，10×512B > 4096B 触发总限截断
  withFixtureFile(buildFixtureDoc({ longEntries: 12, fillerEntries: 0 }), () => {
    const db = makeMemoryDb('章纲：对话与谈判密集。');
    try {
      const [title, body] = resolveKnowledge(db, 'zz-kfix', 'project:x')[0];
      assert.ok(Buffer.byteLength(body, 'utf8') <= 4096,
        `槽 body ${Buffer.byteLength(body, 'utf8')}B 超 4096B`);
      assert.ok(body.includes('超限按排名截断'), '超限场景缺截断脚注');
      assert.ok(body.includes('—— 命中最多的 5 条 ——'), '缺第一组标签');
      assert.ok(body.includes('—— 次高的 5 条 ——'), '缺第二组标签');
      db.close();
    } catch (e) {
      db.close();
      throw e;
    }
  });
});

test('⑦c 蒸馏源全缺 = 槽静默跳过（P2-13 惰性读取）；无章纲 = 显式缺位节', () => {
  const db = makeMemoryDb(null);
  try {
    assert.equal(resolveKnowledge(db, 'zz-absent-domain', 'project:x'), null,
      '不存在的域文件应返回 null（零行为变化）');
    withFixtureFile(buildFixtureDoc({ longEntries: 0, fillerEntries: 2 }), () => {
      const [title, body] = resolveKnowledge(db, 'zz-kfix', 'project:x')[0];
      assert.ok(body.includes('场景检索缺位'), '无 locked chapter_plan 应显式缺位');
    });
    db.close();
  } catch (e) {
    db.close();
    throw e;
  }
});

// ---- ⑦d/⑦e/⑦f CLI 冒烟：/tmp 夹具库副本（生产库零写入） ----

const hasFixture = existsSync(path.join(ROOT, 'data', 'novelos-v2.db'));

test('⑦d chapter-draft 组装含 knowledge 槽（槽头标注+≥1 条 kg 条目），槽体 ≤4096B', () => {
  if (!hasFixture) return; // 无生产库环境跳过（夹具库依赖副本源）
  const pid = buildFixtureDb();
  const r = runCli(['--asset', 'chapter-draft', '--project', pid, '--db', FIXTURE_DB,
    '--no-log']);
  assert.equal(r.status, 0, `stderr: ${r.stderr}`);
  assert.ok(r.stdout.includes('### 知识参照（knowledge:techniques'), '缺 knowledge 槽节标题');
  assert.ok(r.stdout.includes('非 Canon、无对账义务，示例表述不构成成稿标准'), '缺槽头标注');
  assert.ok(/（kg-(dialogue|opening|pacing)-\d{3}）/.test(r.stdout), '缺 kg 条目溯源标记');
  // 槽体积实测：从节标题切到下一个 ### 节
  const at = r.stdout.indexOf('### 知识参照（knowledge:techniques');
  const rest = r.stdout.slice(at);
  const next = rest.indexOf('\n### ', 1);
  const section = next === -1 ? rest : rest.slice(0, next);
  assert.ok(Buffer.byteLength(section, 'utf8') <= 4096 + 80,
    `knowledge 节实测 ${Buffer.byteLength(section, 'utf8')}B（含标题余量）`);
});

test('⑦e --without-slot knowledge:techniques 生效且组装日志记录禁用清单', () => {
  if (!hasFixture) return;
  const pid = buildFixtureDb();
  const r = runCli(['--asset', 'chapter-draft', '--project', pid, '--db', FIXTURE_DB,
    '--no-log', '--without-slot', 'knowledge:techniques']);
  assert.equal(r.status, 0, `stderr: ${r.stderr}`);
  assert.ok(!r.stdout.includes('knowledge:techniques'), '禁用槽仍出现在产物中');
  // 留痕：不带 --no-log 再跑一次，断言 index.jsonl 的 without_slots
  const r2 = runCli(['--asset', 'chapter-draft', '--project', pid, '--db', FIXTURE_DB,
    '--log-dir', FIXTURE_LOG, '--without-slot', 'knowledge:techniques',
    '--without-slot', 'dialogue-techniques']);
  assert.equal(r2.status, 0, `stderr: ${r2.stderr}`);
  assert.ok(!r2.stdout.includes('### 知识参照（knowledge:techniques'), '槽未跳过');
  assert.ok(!r2.stdout.includes('对白技法'), 'craft 卡禁用未生效');
  const index = rfSync(path.join(FIXTURE_LOG, 'index.jsonl'), 'utf8').trim().split('\n');
  const last = JSON.parse(index[index.length - 1]);
  assert.deepEqual(last.without_slots, ['knowledge:techniques', 'dialogue-techniques']);
});

test('⑦f prose-blindtest 可组装（subject + 指纹 craft 卡）', () => {
  if (!hasFixture) return;
  const pid = buildFixtureDb();
  const r = runCli(['--asset', 'prose-blindtest', '--project', pid,
    '--subject', 'planning:zzfix-plan', '--db', FIXTURE_DB, '--no-log']);
  assert.equal(r.status, 0, `stderr: ${r.stderr}`);
  assert.ok(r.stdout.includes('盲测执行卡'), '缺盲测卡主干');
  assert.ok(r.stdout.includes('双向判据表'), '缺判据表协议');
  assert.ok(r.stdout.includes('被审对象全文'), '缺 subject 槽注入');
});

// ---- ⑧ 规划层参照模块（R4 modules 预组合通道，裁-7） ----
// when 路由语义（selectModules/evaluateWhen 实读）：{"field": "setup.genre_profile",
// "non_empty": true} = pyTruthy（null/{} 为假，非空对象为真）。夹具走 /tmp 副本，
// 生产库零写入；genre_profile 通过 UPDATE metadata_json 调整。

/** 改 /tmp 夹具库项目的 setup.genre_profile（null = 反例），返回影响行数。 */
function setFixtureGenreProfile(pid, genreProfile) {
  const db = new DatabaseSync(FIXTURE_DB);
  try {
    const row = db.prepare('SELECT metadata_json FROM projects WHERE id = ?').get(pid);
    const meta = JSON.parse(row.metadata_json);
    meta.setup.genre_profile = genreProfile;
    return db.prepare('UPDATE projects SET metadata_json = ? WHERE id = ?')
      .run(JSON.stringify(meta), pid).changes;
  } finally {
    db.close();
  }
}

test('⑧a direction 组装 when 命中（genre_profile 非空）：参照模块在场+信封头+日志留痕', () => {
  if (!hasFixture) return;
  const pid = buildFixtureDb();
  setFixtureGenreProfile(pid, { primary_genre: '诸天无限' });
  const r = runCli(['--asset', 'direction', '--project', pid, '--db', FIXTURE_DB,
    '--log-dir', FIXTURE_LOG]);
  assert.equal(r.status, 0, `stderr: ${r.stderr}`);
  assert.ok(r.stdout.includes('参照素材(非 Canon、无对账义务)'), '缺参照信封头');
  assert.ok(r.stdout.includes('读者承诺形态谱系'), '缺参照模块正文');
  assert.ok(r.stdout.includes('不得直接复用其题材场景、书名与设定'), '信封隔离条款缺失');
  // 组装日志留痕：index.jsonl 末条 modules 含参照模块 id（writeCompositionLog L1580）
  const index = rfSync(path.join(FIXTURE_LOG, 'index.jsonl'), 'utf8').trim().split('\n');
  const last = JSON.parse(index[index.length - 1]);
  assert.ok(last.modules.includes('reference-book-appeal'),
    `modules 未留痕: ${JSON.stringify(last.modules)}`);
});

test('⑧b direction 组装 when 不命中（genre_profile=null）：参照模块不出现', () => {
  if (!hasFixture) return;
  const pid = buildFixtureDb();
  setFixtureGenreProfile(pid, null);
  const r = runCli(['--asset', 'direction', '--project', pid, '--db', FIXTURE_DB,
    '--no-log']);
  assert.equal(r.status, 0, `stderr: ${r.stderr}`);
  assert.ok(!r.stdout.includes('读者承诺形态谱系'), '参照模块未按 when 跳过');
  assert.ok(!r.stdout.includes('非 Canon、无对账义务):以下为成品网书'), '信封头未随模块跳过');
});

/** 向 /tmp 夹具库插入一条 locked 上游资产（world-contract 上游缺失即停）。 */
function insertFixtureUpstream(pid, assetType, scopeRef, text) {
  const db = new DatabaseSync(FIXTURE_DB);
  try {
    const hash = 'sha256:' + createHash('sha256').update(text, 'utf8').digest('hex');
    const rid = `resource:zzfix-${assetType}`;
    db.prepare('INSERT OR REPLACE INTO resources (id, media_type, content, content_hash) '
      + "VALUES (?, 'text/markdown', ?, ?)").run(rid, text, hash);
    db.prepare('INSERT OR REPLACE INTO planning_assets (id, project_id, asset_type, scope_ref, '
      + "revision, status, content_resource_id, producer_role, metadata_json) VALUES "
      + "(?, ?, ?, ?, 1, 'locked', ?, ?, '{}')")
      .run(`planning:zzfix-${assetType}`, pid, assetType, scopeRef, rid, assetType);
  } finally {
    db.close();
  }
}

test('⑧c world-contract 组装同规则命中/不命中：形态谱系随 genre_profile 出现或消失', () => {
  if (!hasFixture) return;
  const pid = buildFixtureDb();
  insertFixtureUpstream(pid, 'architecture', 'book:zzfix', '架构夹具：三幕式主干。');
  insertFixtureUpstream(pid, 'strategy', 'book:zzfix', '战略夹具：阶段收益配比。');
  setFixtureGenreProfile(pid, { primary_genre: '诸天无限' });
  const hit = runCli(['--asset', 'world-contract', '--project', pid, '--db', FIXTURE_DB, '--no-log']);
  assert.equal(hit.status, 0, `stderr: ${hit.stderr}`);
  assert.ok(hit.stdout.includes('非 Canon、无对账义务):以下为成品网书世界设定的形态归纳'),
    '缺 world 参照信封头');
  assert.ok(hit.stdout.includes('力量体系形态'), '缺 world 参照模块正文');
  assert.ok(hit.stdout.includes('语域/词表唯一来源仍是 genre_pack'), '缺词表单源声明');

  setFixtureGenreProfile(pid, null);
  const miss = runCli(['--asset', 'world-contract', '--project', pid, '--db', FIXTURE_DB, '--no-log']);
  assert.equal(miss.status, 0, `stderr: ${miss.stderr}`);
  assert.ok(!miss.stdout.includes('力量体系形态'), '参照模块未按 when 跳过');
});

// ---------------------------------------------------------------- 附11 R9 RT-B1 内核绑定三查

test('附11 RT-B1 内核绑定三查：风格卡冒充拒/非active拒/hash不符拒/真内核放行', () => {
  const db = new DatabaseSync(FIXTURE_DB);
  const realErr = console.error;
  const capture = (fn) => {
    const buf = [];
    console.error = (...a) => buf.push(a.join(' '));
    try {
      fn();
      return { threw: false, buf };
    } catch {
      return { threw: true, buf };
    } finally {
      console.error = realErr;
    }
  };
  try {
    // ① 库内真实 style_seed 卡冒充内核 → ownership 查获拒
    const seedRow = db.prepare(
      "SELECT v.id FROM creator_profile_versions v JOIN creator_profiles cp ON cp.id=v.profile_id "
      + "WHERE cp.ownership='style_seed' LIMIT 1").get();
    assert.ok(seedRow, '夹具库应含 style_seed 卡');
    const r1 = capture(() => verifyKernelBinding(db, seedRow.id, null));
    assert.ok(r1.threw && r1.buf.join('').includes("ownership='style_seed'"), r1.buf.join(''));

    // ② 真内核 + active → 放行；hash 不符 → 拒；非 active → 拒
    const khash = 'sha256:' + createHash('sha256').update('rt-b1-kernel-body', 'utf8').digest('hex');
    db.prepare(`INSERT OR REPLACE INTO resources (id, media_type, content, content_hash)
      VALUES ('resource:rtb1-k', 'application/json', CAST(? AS BLOB), ?)`)
      .run('rt-b1-kernel-body', khash);
    db.prepare(`INSERT OR REPLACE INTO creator_profiles (id, display_name, ownership, status)
      VALUES ('creator-profile:rtb1', 'RT内核', 'author_kernel', 'active')`).run();
    db.prepare(`INSERT OR REPLACE INTO creator_profile_versions
      (id, profile_id, revision, content_resource_id, subject_hash)
      VALUES ('creator-profile-version:rtb1', 'creator-profile:rtb1', 1, 'resource:rtb1-k', ?)`)
      .run(khash);
    const ok = verifyKernelBinding(db, 'creator-profile-version:rtb1', khash);
    assert.equal(ok.ownership, 'author_kernel');
    const r2 = capture(() => verifyKernelBinding(db, 'creator-profile-version:rtb1', 'sha256:' + '0'.repeat(64)));
    assert.ok(r2.threw && r2.buf.join('').includes('subject_hash 不相符'), r2.buf.join(''));
    db.prepare("UPDATE creator_profiles SET status='archived' WHERE id='creator-profile:rtb1'").run();
    const r3 = capture(() => verifyKernelBinding(db, 'creator-profile-version:rtb1', khash));
    assert.ok(r3.threw && r3.buf.join('').includes("status='archived'"), r3.buf.join(''));
  } finally {
    console.error = realErr;
    db.close();
  }
});

// ---------------------------------------------------------------- 附12 R9 M12 modules.file 白名单

test('附12 M12 manifest.modules.file 白名单：穿越与非法名拒绝、合法名放行', () => {
  const base = { id: 'm1', when: undefined };
  assert.throws(() => validateManifestStruct({
    data_slots: [],
    modules: [{ ...base, file: '../../../../etc/passwd' }],
  }), /R9 M12|\\.md/);
  assert.throws(() => validateManifestStruct({
    data_slots: [],
    modules: [{ ...base, file: 'a..b.md' }],
  }), /R9 M12|\.\./);
  assert.throws(() => validateManifestStruct({
    data_slots: [],
    modules: [{ ...base, file: 'Module.TXT' }],
  }), /\.md/);
  // 合法：现有命名习惯（小写数字点连字符 + .md）
  assert.doesNotThrow(() => validateManifestStruct({
    data_slots: [],
    modules: [{ ...base, file: 'reference-coolpoint-cadence.md' }],
  }));
});

// ---------------------------------------------------------------- 汇总

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  for (const f of failures) console.error(`- ${f.name}: ${f.e.stack || f.e.message}`);
  process.exit(1);
}
