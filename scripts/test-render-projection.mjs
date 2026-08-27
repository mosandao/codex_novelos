// 投影渲染测试：单元测试（人物契约拆分，移植自 tests/test_projection_character_split.py）
// + 端到端集成测试（临时 SQLite 库 → 渲染 → manifest 校验 → 确定性/篡改/归属保护/兜底）。
// 运行：node scripts/test-render-projection.mjs —— 全部 PASS 退出码 0，任一 FAIL 非零退出。
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { DatabaseSync } from 'node:sqlite';
import {
  splitCharacterContract,
  loadSnapshot,
  render,
  verifyManifest,
  sanitizeFilename,
  cnNum,
  contentHash,
  ProjectionError,
} from './novelos-render-projection.mjs';

let passCount = 0;
let failCount = 0;

function check(name, ok, detail = '') {
  if (ok) {
    passCount++;
    console.log(`PASS ${name}`);
  } else {
    failCount++;
    console.log(`FAIL ${name}${detail ? ' —— ' + detail : ''}`);
  }
}

function expectThrow(name, fn, fragment) {
  try {
    fn();
    check(name, false, '未抛出异常');
  } catch (err) {
    check(name, err instanceof ProjectionError && err.message.includes(fragment), `message=${err.message}`);
  }
}

// --------------------------------------------------------------------------- //
// 单元测试：sanitize_filename / cn_num / content_hash
// --------------------------------------------------------------------------- //
check('sanitize 空串回退', sanitizeFilename('') === 'untitled');
check('sanitize 非法字符替换', sanitizeFilename('a/b:c*?') === 'a_b_c__');
check('sanitize 纯点号回退', sanitizeFilename('..') === 'untitled');
check('sanitize 首尾点空格剥离', sanitizeFilename('.隐藏. ') === '隐藏');
check('sanitize 含 .. 回退', sanitizeFilename('a..b') === 'untitled');
check('sanitize 合法中文保留', sanitizeFilename('风起·第一夜') === '风起·第一夜');

check('cnNum 1→一', cnNum(1) === '一');
check('cnNum 10→十', cnNum(10) === '十');
check('cnNum 11→十一', cnNum(11) === '十一');
check('cnNum 21→二十一', cnNum(21) === '二十一');
check('cnNum 100→一百', cnNum(100) === '一百');
check('cnNum 105→一百零五', cnNum(105) === '一百零五');
check('cnNum 1000→数字', cnNum(1000) === '1000');

check(
  'contentHash sha256 前缀与摘要',
  contentHash('abc') === 'sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
);

// --------------------------------------------------------------------------- //
// 单元测试：人物契约拆分（移植自 py 版 5 个用例）
// --------------------------------------------------------------------------- //

// 符合新结构约定的样例：总则/立场矩阵/对World假设（跨人物）+ 四个人物档案。
const WELL_FORMED = `# 人物契约：示例

## 人物设计总则

三条铁律……

## 人物档案：主角｜塞维尔

### 初始状态
流放次子。

### 核心执念
拒绝成为棋子。

## 人物档案：主锚点｜伊诺

未定型存在。

## 人物档案：棋手｜渡脉者

旧神偷渡者。

## 人物档案：棋手｜余烬记录者

反驳派。

## central_contradiction 立场矩阵

五人光谱……

## Character 对 World 的假设

1. 假设一
`;

// 主角不在第一个位置，用于验证排序。
const PROTAGONIST_NOT_FIRST = `## 人物档案：棋手｜渡脉者

旧神偷渡者。

## 人物档案：主角｜塞维尔

拒绝成为棋子。
`;

// 无「人物档案」标题（如当前西幻 r3 残缺契约风格），应触发兜底。
const NO_CHARACTER_HEADINGS = `# 人物契约（修订版·核心执念补充）

## 核心执念（新增一级维度）

### 主角塞维尔的核心执念

**核心执念：拒绝成为任何棋手定义的棋子。**

## 早期失稳设计（前 30 章）

失稳点一……
`;

{
  const result = splitCharacterContract(WELL_FORMED);
  check('拆分 结构良好契约 返回非空', result !== null);
  check('拆分 人物数量 4', result?.characters.length === 4);
  check('拆分 总览含跨人物内容', (result?.overview ?? '').includes('人物设计总则') && result.overview.includes('立场矩阵') && result.overview.includes('对 World 的假设'));
  check('拆分 人物 body 含标题行', result?.characters[0].body.startsWith('## 人物档案：主角'));
  check('拆分 人物 body 含字段', result?.characters[0].body.includes('核心执念') && result.characters[0].body.includes('流放次子'));
}

{
  const result = splitCharacterContract(PROTAGONIST_NOT_FIRST);
  check('拆分 主角排序第一', result?.characters[0].role === '主角' && result.characters[0].name === '塞维尔');
  check('拆分 非主角保持序位', result?.characters[1].role === '棋手');
}

{
  const r1 = splitCharacterContract(NO_CHARACTER_HEADINGS);
  const r2 = splitCharacterContract('');
  check('拆分 无人物档案标题回退 null', r1 === null && r2 === null);
}

{
  const result = splitCharacterContract('## 人物档案: 主角 | 塞维尔\n\n拒绝成为棋子。\n');
  check('拆分 兼容中英冒号竖线', result?.characters[0].role === '主角' && result.characters[0].name === '塞维尔');
}

{
  const text =
    '## 人物档案：主角｜塞维尔\n\n主角。\n\n' +
    '## 人物档案：棋手｜渡脉者\n\nA。\n\n' +
    '## 人物档案：棋手｜余烬记录者\n\nB。\n';
  const result = splitCharacterContract(text);
  const roles = (result?.characters ?? []).map((c) => c.role).join(',');
  const names = (result?.characters ?? []).map((c) => c.name).join(',');
  check('拆分 同类多人各自独立', roles === '主角,棋手,棋手' && names === '塞维尔,渡脉者,余烬记录者');
}

// --------------------------------------------------------------------------- //
// 集成测试：临时 SQLite 库 → 快照 → 渲染 → manifest 校验
// --------------------------------------------------------------------------- //

const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'novelos-proj-test-'));
const dbPath = path.join(tmpRoot, 'fixture.db');
const outRoot = path.join(tmpRoot, 'novels');

const db = new DatabaseSync(dbPath);
try {
  db.exec(`
    CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}', version INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE resources (id TEXT PRIMARY KEY, content BLOB NOT NULL);
    CREATE TABLE planning_assets (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, asset_type TEXT NOT NULL, scope_ref TEXT NOT NULL, status TEXT NOT NULL, content_resource_id TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}', version INTEGER NOT NULL DEFAULT 1, title TEXT);
    CREATE TABLE creator_profiles (id TEXT PRIMARY KEY, display_name TEXT NOT NULL);
    CREATE TABLE creator_profile_versions (id TEXT PRIMARY KEY, content_resource_id TEXT NOT NULL, derivation_resource_id TEXT);
    CREATE TABLE project_creator_bindings (project_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, profile_version_id TEXT NOT NULL, profile_revision INTEGER NOT NULL, subject_hash TEXT NOT NULL, binding_mode TEXT NOT NULL);
    CREATE TABLE books (id TEXT PRIMARY KEY, project_id TEXT NOT NULL);
    CREATE TABLE volumes (id TEXT PRIMARY KEY, book_id TEXT NOT NULL, number INTEGER NOT NULL, title TEXT NOT NULL);
    CREATE TABLE chapters (id TEXT PRIMARY KEY, volume_id TEXT NOT NULL, number INTEGER NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL, content_resource_id TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE characters (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL, role_class TEXT NOT NULL DEFAULT 'secondary', status TEXT NOT NULL DEFAULT 'active', description_resource_id TEXT, state_json TEXT NOT NULL DEFAULT '{}', exit_type TEXT, version INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE worlds (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL, description_resource_id TEXT, state_json TEXT NOT NULL DEFAULT '{}', version INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE narrative_promises (id TEXT PRIMARY KEY, project_id TEXT NOT NULL);
    CREATE TABLE expectation_ledgers (id TEXT PRIMARY KEY, project_id TEXT NOT NULL);
    CREATE TABLE relationship_states (id TEXT PRIMARY KEY, project_id TEXT NOT NULL);
    CREATE TABLE arc_states (id TEXT PRIMARY KEY, project_id TEXT NOT NULL);
    CREATE TABLE timelines (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, sequence INTEGER NOT NULL, label TEXT NOT NULL);
    CREATE TABLE chapter_facts (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, status TEXT NOT NULL);
  `);

  const insRes = db.prepare('INSERT INTO resources (id, content) VALUES (?, ?)');
  const blob = (s) => Buffer.from(s, 'utf8');
  const sha = (s) => contentHash(s);

  // resources
  insRes.run('res-dir', blob('# 故事方向\n\n## 一句话梗概\n\n少年觉醒。\n'));
  insRes.run('res-arch', blob('# 故事架构\n\n三幕结构。\n'));
  insRes.run('res-cc', blob(`# 人物契约：示例

## 人物设计总则

三条铁律……

## 人物档案：主锚点｜伊诺

未定型存在。

## 人物档案：主角｜塞维尔

### 核心执念
拒绝成为棋子。

## 人物档案：棋手｜渡脉者

旧神偷渡者。
`));
  insRes.run('res-vol1', blob('# 第一卷卷纲\n\n风起于青萍。\n'));
  insRes.run('res-vol2', blob('# 第二卷卷纲\n\n夜行。\n'));
  insRes.run('res-cp1', blob('# 第一章章纲\n\n初入江湖。\n'));
  insRes.run('res-cp21', blob('# 第二十一章章纲\n\n巅峰对决。\n'));
  insRes.run('res-ch1', blob('第一章正文……\n'));
  insRes.run('res-ch2', blob('第二章正文……\n'));
  insRes.run('res-ch3draft', blob('第三章草稿，不应投影。\n'));
  insRes.run('res-desc1', blob('流放次子。\n'));
  insRes.run('res-desc2', blob('未定型存在。\n'));
  insRes.run('res-world', blob('西境大陆。\n'));
  insRes.run(
    'res-sig',
    blob(
      JSON.stringify({
        persona: {
          narrative: '写人先写困境。',
          anchors: {
            profile_sketch: '边缘视角的观察者。',
            five_dimensions: { generation_age: '九十年代生人', education_horizon: '跨学科' },
            trait_profile: ['克制', '留白'],
            theme_orientation: { dominant: 'dual', evidence: '既写个人也写群像' },
            inner_tension: '理性与共情',
            voice_samples: ['短句。', '留白。'],
            blindspots: { refuses: ['万能机械降神'], cannot_write: ['纯爱情喜剧'] },
          },
        },
        sympathies: ['小人物'],
        narrative_principles: ['因果必然'],
      }),
    ),
  );
  insRes.run(
    'res-deriv',
    blob(
      JSON.stringify({
        parent_display_name: '作者内核原型',
        parent_version_id: 'pv-0',
        auxiliary_archetypes: ['边缘观察者'],
        user_input_snapshot: { user_persona_hints: { 口头禅: ['稳住'] } },
        rationale: '人格画像吻合。',
      }),
    ),
  );

  // projects / creator 链
  db.prepare('INSERT INTO projects (id, name, metadata_json, version) VALUES (?, ?, ?, ?)').run(
    'project:test-1',
    '试炼:测试/项目',
    JSON.stringify({
      setup: {
        channel: '男频',
        platform: '起点',
        platform_traits: { model: '追读', patience: '高' },
        scale: '长篇',
        primary_genre: '玄幻',
        secondary_directions: ['无敌流'],
        emotional_surface: ['爽感'],
        emotional_core: '守护',
        tonal_contrast: '外爽内深',
        aesthetic_styles: ['东方玄幻'],
      },
    }),
    1,
  );
  db.prepare("INSERT INTO creator_profiles (id, display_name) VALUES ('prof-1', '示例签名')").run();
  db.prepare(
    "INSERT INTO creator_profile_versions (id, content_resource_id, derivation_resource_id) VALUES ('pv-1', 'res-sig', 'res-deriv')",
  ).run();
  db.prepare(
    `INSERT INTO project_creator_bindings (project_id, profile_id, profile_version_id, profile_revision, subject_hash, binding_mode)
     VALUES ('project:test-1', 'prof-1', 'pv-1', 3, ?, 'create')`,
  ).run(sha('sig'));

  // planning_assets（locked）
  const insPlan = db.prepare(
    `INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, status, content_resource_id, metadata_json, version, title)
     VALUES (?, ?, ?, ?, 'locked', ?, ?, 1, ?)`,
  );
  insPlan.run('pa-dir', 'project:test-1', 'direction', 'project', 'res-dir',
    JSON.stringify({ book_soul: { organizing_principle: '能力与代价等价', power_currency: ['寿元'], forbidden_resolutions: ['无代价变强'] } }), null);
  insPlan.run('pa-arch', 'project:test-1', 'architecture', 'project', 'res-arch', '{}', null);
  insPlan.run('pa-cc', 'project:test-1', 'character_contract', 'project', 'res-cc', '{}', null);
  insPlan.run('pa-vol1', 'project:test-1', 'volume_outline', 'volume:vol-1', 'res-vol1', '{}', '风起');
  insPlan.run('pa-vol2', 'project:test-1', 'volume_outline', 'volume:vol-2', 'res-vol2', '{}', '夜行');
  insPlan.run('pa-cp1', 'project:test-1', 'chapter_plan', 'volume:vol-1:chapter_1', 'res-cp1', '{}', '第一章执行卡');
  insPlan.run('pa-cp21', 'project:test-1', 'chapter_plan', 'volume:vol-2:chapter_21', 'res-cp21', '{}', null);

  // books / volumes / chapters
  db.prepare("INSERT INTO books (id, project_id) VALUES ('book-1', 'project:test-1')").run();
  db.prepare("INSERT INTO volumes (id, book_id, number, title) VALUES ('vol-1', 'book-1', 1, '风起')").run();
  db.prepare("INSERT INTO volumes (id, book_id, number, title) VALUES ('vol-2', 'book-1', 2, '夜行')").run();
  const insCh = db.prepare(
    `INSERT INTO chapters (id, volume_id, number, title, status, content_resource_id, version)
     VALUES (?, ?, ?, ?, ?, ?, 1)`,
  );
  insCh.run('ch-1', 'vol-1', 1, '风起', 'accepted', 'res-ch1');
  insCh.run('ch-2', 'vol-1', 2, '夜谈', 'accepted', 'res-ch2');
  insCh.run('ch-3', 'vol-2', 3, '未定稿', 'draft', 'res-ch3draft');

  // characters / worlds
  db.prepare(
    `INSERT INTO characters (id, project_id, name, role_class, status, description_resource_id, state_json, exit_type, version)
     VALUES ('char-1', 'project:test-1', '塞维尔', 'main', 'active', 'res-desc1', '{"执念":"不做棋子"}', NULL, 1)`,
  ).run();
  db.prepare(
    `INSERT INTO characters (id, project_id, name, role_class, status, description_resource_id, state_json, exit_type, version)
     VALUES ('char-2', 'project:test-1', '伊诺', 'secondary', 'peripheral', 'res-desc2', '{}', '迁移型', 1)`,
  ).run();
  db.prepare(
    `INSERT INTO worlds (id, project_id, name, description_resource_id, state_json, version)
     VALUES ('world-1', 'project:test-1', '西境', 'res-world', '{"纪元":"第二纪"}', 1)`,
  ).run();

  // continuity ledgers
  db.prepare("INSERT INTO narrative_promises (id, project_id) VALUES ('np-1', 'project:test-1')").run();
  db.prepare("INSERT INTO expectation_ledgers (id, project_id) VALUES ('el-1', 'project:test-1')").run();
  db.prepare("INSERT INTO relationship_states (id, project_id) VALUES ('rs-1', 'project:test-1')").run();
  db.prepare("INSERT INTO arc_states (id, project_id) VALUES ('as-1', 'project:test-1')").run();
  db.prepare("INSERT INTO timelines (id, project_id, sequence, label) VALUES ('tl-1', 'project:test-1', 1, '开篇')").run();
  db.prepare("INSERT INTO chapter_facts (id, project_id, status) VALUES ('cf-1', 'project:test-1', 'accepted')").run();
  db.prepare("INSERT INTO chapter_facts (id, project_id, status) VALUES ('cf-2', 'project:test-1', 'superseded')").run();

  // 1) 快照与渲染
  const snapshot = loadSnapshot(db, 'project:test-1');
  check('快照 项目元数据', snapshot.project.name === '试炼:测试/项目');
  check('快照 权威 hash 格式', /^sha256:[0-9a-f]{64}$/.test(snapshot.authority_snapshot_hash));
  check('快照 book_soul 提取', snapshot.book_soul?.book_soul.organizing_principle === '能力与代价等价');
  check('快照 accepted 章节数 2', snapshot.chapters.length === 2);
  check('快照 账本齐全', Object.keys(snapshot.continuity).length === 6);

  const result = render(snapshot, 'project:test-1', outRoot);
  const outDir = result.output_directory;
  check('渲染 目录名清理非法字符', path.basename(outDir) === '试炼_测试_项目');
  check('渲染 文件计数 = manifest + 25', result.rendered_file_count === 26);

  const manifest = JSON.parse(fs.readFileSync(path.join(outDir, 'manifest.json'), 'utf8'));
  check('manifest project_id 正确', manifest.project_id === 'project:test-1');
  check('manifest file_count 一致', manifest.file_count === manifest.files.length);
  check('manifest 文件排序', manifest.files.every((f, i, a) => i === 0 || a[i - 1].relative_path < f.relative_path));

  const expectedFiles = [
    'README.md',
    '创作约束/作者签名.md',
    '创作约束/本书创作灵魂.md',
    '规划/01-故事方向.md',
    '规划/02-故事架构.md',
    '规划/人物契约/00-总览.md',
    '规划/人物契约/01-主角-塞维尔.md',
    '规划/人物契约/02-主锚点-伊诺.md',
    '规划/人物契约/03-棋手-渡脉者.md',
    '大纲/第一卷/卷纲.md',
    '大纲/第一卷/第001章-章纲.md',
    '大纲/第二卷/卷纲.md',
    '大纲/第二卷/第021章-章纲.md',
    '正文/第一卷/第001章-风起.md',
    '正文/第一卷/第002章-夜谈.md',
    '人物/塞维尔.md',
    '人物/伊诺.md',
    '世界/西境.md',
    '连续性/伏笔与叙事承诺.md',
    '连续性/读者期待.md',
    '连续性/人物关系.md',
    '连续性/故事弧状态.md',
    '连续性/时间线.md',
    '连续性/正文事实.md',
    '连续性/人物状态注册表.md',
  ];
  const actual = manifest.files.map((f) => f.relative_path);
  const missing = expectedFiles.filter((f) => !actual.includes(f));
  const extra = actual.filter((f) => !expectedFiles.includes(f));
  check(
    '渲染 文件集合完整',
    missing.length === 0 && extra.length === 0 && actual.length === expectedFiles.length,
    `missing=[${missing}] extra=[${extra}] actual=${actual.length} expected=${expectedFiles.length}`,
  );

  check(
    '渲染 主角排序第一（契约原文主角在第二）',
    fs.readFileSync(path.join(outDir, '规划/人物契约/01-主角-塞维尔.md'), 'utf8').includes('核心执念'),
  );
  check(
    '渲染 总览含跨人物总则',
    fs.readFileSync(path.join(outDir, '规划/人物契约/00-总览.md'), 'utf8').includes('人物设计总则'),
  );
  check(
    '渲染 README 含 setup 定位摘要',
    (() => {
      const t = fs.readFileSync(path.join(outDir, 'README.md'), 'utf8');
      return t.includes('频道×平台') && t.includes('试炼:测试/项目') && t.includes('表里基调');
    })(),
  );
  check(
    '渲染 草稿章节不投影',
    !actual.some((f) => f.includes('003')) && !actual.some((f) => f.includes('未定稿')),
  );
  check(
    '渲染 正文事实只含 accepted',
    (() => {
      const t = fs.readFileSync(path.join(outDir, '连续性/正文事实.md'), 'utf8');
      return JSON.parse(t.slice(t.indexOf('\n\n') + 2)).length === 1;
    })(),
  );
  check(
    '渲染 作者签名含 persona 与派生溯源',
    (() => {
      const t = fs.readFileSync(path.join(outDir, '创作约束/作者签名.md'), 'utf8');
      return t.includes('创作者人格') && t.includes('派生溯源') && t.includes('用户人格素材');
    })(),
  );

  // 2) manifest 校验
  const vr = verifyManifest(outDir);
  check('校验 manifest 全部通过', vr.errors.length === 0 && vr.verified_file_count === manifest.files.length, vr.errors.join(';'));

  // 3) 确定性：重渲染 → 同 hash、同 manifest 字节
  const snapshot2 = loadSnapshot(db, 'project:test-1');
  const manifestBytes1 = fs.readFileSync(path.join(outDir, 'manifest.json'), 'utf8');
  render(snapshot2, 'project:test-1', outRoot);
  const manifestBytes2 = fs.readFileSync(path.join(outDir, 'manifest.json'), 'utf8');
  check('确定性 权威快照 hash 稳定', snapshot.authority_snapshot_hash === snapshot2.authority_snapshot_hash);
  check('确定性 manifest 字节级一致', manifestBytes1 === manifestBytes2);

  // 4) 篡改检测
  const chFile = path.join(outDir, '正文/第一卷/第001章-风起.md');
  fs.appendFileSync(chFile, '\n被篡改。');
  const vrTampered = verifyManifest(outDir);
  check('校验 篡改文件被检出', vrTampered.errors.some((e) => e.includes('001章-风起.md')));
  fs.writeFileSync(chFile, fs.readFileSync(chFile, 'utf8').replace('\n被篡改。', ''));

  // 5) 项目归属保护：同名目录属于其他项目 → 拒绝覆盖
  db.prepare("INSERT INTO projects (id, name, metadata_json, version) VALUES ('project:test-2', '试炼:测试/项目', '{}', 1)").run();
  const snapshotOther = loadSnapshot(db, 'project:test-2');
  expectThrow('归属保护 同名目录拒绝覆盖', () => render(snapshotOther, 'project:test-2', outRoot), '拒绝覆盖');

  // 6) 残缺人物契约 → 单文件兜底
  db.prepare("INSERT INTO projects (id, name, metadata_json, version) VALUES ('project:test-3', '残缺契约', '{}', 1)").run();
  insPlan.run('pa-cc3', 'project:test-3', 'character_contract', 'project', 'res-cc-broken', '{}', null);
  insRes.run('res-cc-broken', blob('# 人物契约（修订版）\n\n## 核心执念\n\n无人物档案标题。\n'));
  const snapshot3 = loadSnapshot(db, 'project:test-3');
  render(snapshot3, 'project:test-3', outRoot);
  check(
    '兜底 残缺契约退化为单文件',
    fs.existsSync(path.join(outRoot, '残缺契约', '规划/04-人物契约.md')) &&
      !fs.existsSync(path.join(outRoot, '残缺契约', '规划/人物契约/00-总览.md')),
  );

  // 7) 缺失项目报错
  expectThrow('报错 项目不存在', () => loadSnapshot(db, 'project:nope'), '找不到项目');
} finally {
  db.close();
  fs.rmSync(tmpRoot, { recursive: true, force: true });
}

// --------------------------------------------------------------------------- //
console.log(`\n投影渲染测试: ${passCount} PASS / ${failCount} FAIL`);
process.exit(failCount > 0 ? 1 : 0);
