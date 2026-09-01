#!/usr/bin/env node
/**
 * novelos-gate.mjs 测试（R7-T3 验收集，≥40 例）。
 *
 * 断言来源：旧写门测试移植（27d34a4 propagate-delete.test.ts 10 例语义 +
 * da9ee5c register-characters.test.ts 12 关键例）+ WP5 状态机记账语义重写
 * （state-machine 例组——其 .ts 从未入库，按 tasks/README.md WP5 记账重建）
 * + R7 新增关口（P4-2 前缀/A1 空回执/生产库保护/Claremont）。
 * 全部跑在 :memory: 夹具库（schema.sql 空库重建），生产库零接触。
 *
 * 夹具依赖图（planning_assets id 每 revision 一行）：
 *   dir-r1(rev1, superseded) / dir-r2(rev2, locked，内容与 rev1 不同)
 *     ↑ strat1(strategy, locked, edge→dir-r1 v=1) ↑ vol1(volume_outline, locked, edge→strat1 v=1)
 *   char1(character_contract, candidate, edge→dir-r1 v=1)
 *
 * 运行：node scripts/test-gate.mjs
 */

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const GATE = path.join(__dirname, 'novelos-gate.mjs');

const gate = await import(`file://${GATE.replace(/\\/g, '/')}`);
const { contentHash } = await import(`file://${path.join(__dirname, 'novelos-compose-prompt.mjs').replace(/\\/g, '/')}`);

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

// ── 夹具库 ──────────────────────────────────────────────────────────────────

function freshDb() {
  const conn = new DatabaseSync(':memory:');
  conn.exec(readFileSync(path.join(ROOT, 'db/migrations/schema.sql'), 'utf8'));
  return conn;
}

const DRAFT = '第 1 章\n\n雪停在凌晨三点。任务失败不是惩罚，而是清零——积分、装备，一样都留不住。\n';

function fixture(db) {
  db.prepare("INSERT INTO projects (id, name, metadata_json) VALUES ('project:t1', '测试项目', ?)")
    .run(JSON.stringify({ setup: { scale: '长篇（100-300万字）' } }));
  db.prepare("INSERT INTO books (id, project_id, title) VALUES ('book:t1', 'project:t1', '测试书')").run();
  db.prepare("INSERT INTO volumes (id, book_id, number, title) VALUES ('volume:t1', 'book:t1', 1, '第一卷')").run();

  const addResource = (id, content, mediaType = 'text/markdown') => {
    db.prepare('INSERT INTO resources (id, media_type, content, content_hash) VALUES (?, ?, ?, ?)')
      .run(id, mediaType, content, contentHash(content));
  };
  let chapterNo = 0;
  const addChapter = (id, resourceId, status = 'draft') => {
    chapterNo += 1;
    db.prepare(
      'INSERT INTO chapters (id, volume_id, number, title, status, content_resource_id) VALUES (?, ?, ?, ?, ?, ?)',
    ).run(id, 'volume:t1', chapterNo, `测试章节${chapterNo}`, status, resourceId);
  };
  const addAsset = (id, type, scope, revision, status, resourceId, metadata = {}) => {
    db.prepare(
      'INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role, metadata_json) '
      + "VALUES (?, 'project:t1', ?, ?, ?, ?, ?, 'planning:direction', ?)",
    ).run(id, type, scope, revision, status, resourceId, JSON.stringify(metadata));
  };
  const addReview = (id, subjectRef, subjectHash, verdict = 'approved') => {
    db.prepare(
      "INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict, reviewer_profile, findings_json) "
      + "VALUES (?, 'chapter', ?, ?, ?, 'model:fixture:m1', '[]')",
    ).run(id, subjectRef, subjectHash, verdict);
  };

  // 章节
  addResource('resource:ch1', DRAFT);
  addChapter('chapter:t1', 'resource:ch1');
  addResource('resource:ch2', DRAFT + '\n（第二版内容）\n');
  addChapter('chapter:t2', 'resource:ch2', 'accepted');
  addResource('resource:ch3', DRAFT + '\n（第三版内容）\n');
  addChapter('chapter:t3', 'resource:ch3', 'superseded');

  // 依赖图（id 每 revision 一行）
  addResource('resource:dir-v1', 'direction 内容 v1');
  addResource('resource:dir-v2', 'direction 内容 v2');
  addAsset('planning:dir-r1', 'direction', 'main', 1, 'superseded', 'resource:dir-v1');
  addAsset('planning:dir-r2', 'direction', 'main', 2, 'locked', 'resource:dir-v2');
  addResource('resource:strat', 'strategy 内容');
  addAsset('planning:strat1', 'strategy', 'main', 1, 'locked', 'resource:strat');
  addResource('resource:vol', 'volume_outline 内容');
  addAsset('planning:vol1', 'volume_outline', '1', 1, 'locked', 'resource:vol');
  addResource('resource:char', 'character 内容');
  addAsset('planning:char1', 'character_contract', 'main', 1, 'candidate', 'resource:char');
  db.prepare("INSERT INTO planning_asset_dependencies (asset_id, upstream_asset_id, upstream_version) VALUES ('planning:strat1', 'planning:dir-r1', 1)").run();
  db.prepare("INSERT INTO planning_asset_dependencies (asset_id, upstream_asset_id, upstream_version) VALUES ('planning:vol1', 'planning:strat1', 1)").run();
  db.prepare("INSERT INTO planning_asset_dependencies (asset_id, upstream_asset_id, upstream_version) VALUES ('planning:char1', 'planning:dir-r1', 1)").run();

  // 回执
  addReview('review:ok-ch1', 'chapter:t1', contentHash(DRAFT), 'approved');
  addReview('review:rej-ch1', 'chapter:t1', contentHash(DRAFT), 'rejected');
  addReview('review:ok-ch2', 'chapter:t2', contentHash(DRAFT + '\n（第二版内容）\n'), 'approved');
  addReview('review:ok-strat', 'planning:strat1', contentHash('strategy 内容'), 'approved');
  db.prepare("UPDATE reviews SET subject_type='planning' WHERE id='review:ok-strat'").run();
  addReview('review:ok-char1', 'planning:char1', contentHash('character 内容'), 'approved');
  db.prepare("UPDATE reviews SET subject_type='planning' WHERE id='review:ok-char1'").run();
  db.prepare("UPDATE chapters SET review_id='review:ok-ch2' WHERE id='chapter:t2'").run();
  addResource('resource:world', 'world 内容');
  addAsset('planning:world1', 'world_contract', 'main', 1, 'candidate', 'resource:world');

  return { addResource, addChapter, addAsset, addReview };
}

const throwsGate = (fn, frag) => assert.throws(fn, (e) => e instanceof gate.GateFail && (frag === undefined || e.message.includes(frag)));

// ═══ propagate-stale（移植 propagate-delete.test.ts 10 例语义） ═══════════════

test('P1 dry-run 只报告不执行 UPDATE（coarse）', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.propagateStale(db, 'planning:dir-r1', { dryRun: true });
  assert.equal(r.marked, 2); // strat1 + vol1（char1 是 candidate 不标）
  assert.equal(r.dryRun, true);
  assert.equal(db.prepare("SELECT status FROM planning_assets WHERE id='planning:strat1'").get().status, 'locked');
  assert.equal(db.prepare("SELECT status FROM planning_assets WHERE id='planning:vol1'").get().status, 'locked');
});

test('P2 coarse 执行：直接+间接下游全量标 stale，candidate 不动', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.propagateStale(db, 'planning:dir-r1', { dryRun: false });
  assert.equal(r.marked, 2);
  assert.equal(db.prepare("SELECT status FROM planning_assets WHERE id='planning:strat1'").get().status, 'stale');
  assert.equal(db.prepare("SELECT status FROM planning_assets WHERE id='planning:vol1'").get().status, 'stale');
  assert.equal(db.prepare("SELECT status FROM planning_assets WHERE id='planning:char1'").get().status, 'candidate');
});

test('P3 无下游引用 marked=0 且不报错（dir-r2 刚锁定、尚无依赖边指向它）', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.propagateStale(db, 'planning:dir-r2', { dryRun: false });
  assert.equal(r.marked, 0);
});

test('P4 资产不存在抛 GateFail（阻断）', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => gate.propagateStale(db, 'planning:nonexistent'), '资产不存在');
});

test('P5 fine：依赖边 rev 对齐判 neutral，不误伤', () => {
  const db = freshDb();
  fixture(db);
  db.prepare("UPDATE planning_asset_dependencies SET upstream_version = 2 WHERE asset_id='planning:strat1'").run();
  const r = gate.propagateStale(db, 'planning:dir-r1', { fine: true, dryRun: true });
  const strat = r.classification.find((c) => c.id === 'planning:strat1');
  assert.equal(strat.verdict, 'neutral');
  assert.equal(r.marked, 0);
});

test('P6 fine：内容未变（当前 rev 与依赖 rev 同 content_hash）判 neutral', () => {
  const db = freshDb();
  fixture(db);
  // 真实时序：rev3 锁定前 rev2 须先翻 superseded（部分唯一索引 idx_planning_assets_current）
  db.prepare("UPDATE planning_assets SET status='superseded' WHERE id='planning:dir-r2'").run();
  db.prepare(
    "INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role) "
    + "VALUES ('planning:dir-r3', 'project:t1', 'direction', 'main', 3, 'locked', 'resource:dir-v2', 'planning:direction')",
  ).run();
  db.prepare("UPDATE planning_asset_dependencies SET upstream_version = 2 WHERE asset_id='planning:strat1'").run();
  const r = gate.propagateStale(db, 'planning:dir-r1', { fine: true, dryRun: true });
  const strat = r.classification.find((c) => c.id === 'planning:strat1');
  assert.equal(strat.verdict, 'neutral', strat.reason);
  assert.ok(strat.reason.includes('content_hash 相同'));
});

test('P7 fine：内容已变判 stale', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.propagateStale(db, 'planning:dir-r1', { fine: true, dryRun: true });
  const strat = r.classification.find((c) => c.id === 'planning:strat1');
  assert.equal(strat.verdict, 'stale');
  assert.ok(strat.reason.includes('内容已变'));
});

test('P8 fine：间接下游列 indirectPending 不自动标', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.propagateStale(db, 'planning:dir-r1', { fine: true, dryRun: true });
  assert.deepEqual(r.indirectPending, ['planning:vol1']);
  assert.equal(r.classification.some((c) => c.id === 'planning:vol1'), false);
});

test('P9 fine --commit：只标 stale，neutral 不动', () => {
  const db = freshDb();
  fixture(db);
  db.prepare("UPDATE planning_asset_dependencies SET upstream_version = 2 WHERE asset_id='planning:strat1'").run();
  const r = gate.propagateStale(db, 'planning:dir-r1', { fine: true, dryRun: false });
  assert.equal(r.marked, 0);
  assert.equal(db.prepare("SELECT status FROM planning_assets WHERE id='planning:strat1'").get().status, 'locked');
});

test('P10 coarse --commit 后 updated_at 被刷新（可审计）', () => {
  const db = freshDb();
  fixture(db);
  gate.propagateStale(db, 'planning:dir-r1', { dryRun: false });
  const row = db.prepare("SELECT updated_at FROM planning_assets WHERE id='planning:strat1'").get();
  assert.ok(row.updated_at); // CURRENT_TIMESTAMP 已写入
});

// ═══ register-characters（移植 register-characters.test.ts 12 关键例） ════════

test('R1 normName：NFKC 全半角折叠 + 去空白 + 小写折叠', () => {
  assert.equal(gate.normName(' Ｌｅｏ Ｋ '), 'leok');
  assert.equal(gate.normName('江离'), gate.normName('江 离'));
});

test('R2 entry 四规则：name/role_class/预期退场/来源卷', () => {
  const errs = gate.validateEntries([
    { name: '   ' },
    { name: '甲', role_class: 'boss' },
    { name: '乙', '预期退场': '忽然消失' },
    { name: '丙', '来源卷': 0 },
    { name: '丁', '来源卷': 2.5 },
    { name: '戊', '预期退场': '完成型' }, // 合法
  ]);
  assert.equal(errs.length, 5);
  assert.ok(errs[0].includes('name 非空必填'));
  assert.ok(errs[3].includes('1-99 整数'));
});

test('R3 status-update：dead 必须带 死亡型', () => {
  const errs = gate.validateStatusUpdate({ name: '甲', status: 'dead', exit_type: '休眠型' });
  assert.ok(errs.some((e) => e.includes('死亡型')));
  assert.equal(gate.validateStatusUpdate({ name: '甲', status: 'dead', exit_type: '死亡型' }).length, 0);
});

test('R4 非退场状态禁带 exit_type', () => {
  const errs = gate.validateStatusUpdate({ name: '甲', status: 'active', exit_type: '完成型' });
  assert.ok(errs.some((e) => e.includes('非退场状态')));
});

test('R5 status 非法即短路（后续规则不累加）', () => {
  const errs = gate.validateStatusUpdate({ name: '甲', status: 'flying', exit_type: '完成型' });
  assert.equal(errs.length, 1);
  assert.ok(errs[0].includes('status 非法'));
});

test('R6 roster+entry 单事务落库：ID 格式 + state_json py 紧凑串', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.registerCharactersRun(db, {
    projectId: 'project:t1',
    roster: [{ name: '江离', role_class: 'main', arc_role: '执行人', '登场卷': 1, '预期退场': '持续活跃' }],
    entries: [{ name: '当铺老板', role_class: 'minor', '来源卷': 1, first_chapter_id: 'chapter:t1' }],
  });
  assert.equal(r.results.length, 2);
  const row = db.prepare("SELECT id, state_json FROM characters WHERE name='当铺老板'").get();
  assert.match(row.id, /^character:[0-9a-f-]{36}$/);
  assert.ok(row.state_json.includes('"来源卷": 1'));
  const rosterRow = db.prepare("SELECT status, role_class, state_json FROM characters WHERE name='江离'").get();
  assert.equal(rosterRow.status, 'active');
  assert.equal(rosterRow.role_class, 'main');
  assert.ok(rosterRow.state_json.includes('"arc_role": "执行人"'));
});

test('R7 幂等重入：合并补充字段，绝不覆盖 status/exit', () => {
  const db = freshDb();
  fixture(db);
  gate.registerCharactersRun(db, { projectId: 'project:t1', entries: [{ name: '甲', role_class: 'minor' }] });
  gate.registerCharactersRun(db, { projectId: 'project:t1', statusUpdate: { name: '甲', status: 'departed', exit_type: '完成型' } });
  gate.registerCharactersRun(db, { projectId: 'project:t1', entries: [{ name: '甲', role_class: 'secondary', '新字段': '补' }] });
  const row = db.prepare("SELECT status, exit_type, role_class, state_json FROM characters WHERE name='甲'").get();
  assert.equal(row.status, 'departed');
  assert.equal(row.exit_type, '完成型');
  assert.equal(row.role_class, 'secondary');
  assert.ok(row.state_json.includes('新字段'));
});

test('R8 first_chapter_id COALESCE：重入未带值不清既有值', () => {
  const db = freshDb();
  fixture(db);
  gate.registerCharactersRun(db, { projectId: 'project:t1', entries: [{ name: '乙', first_chapter_id: 'chapter:t1' }] });
  gate.registerCharactersRun(db, { projectId: 'project:t1', entries: [{ name: '乙' }] });
  assert.equal(db.prepare("SELECT first_chapter_id FROM characters WHERE name='乙'").get().first_chapter_id, 'chapter:t1');
});

test('R9 退场迁移：写 status/exit 字段并追加状态史', () => {
  const db = freshDb();
  fixture(db);
  gate.registerCharactersRun(db, { projectId: 'project:t1', entries: [{ name: '丙' }] });
  gate.registerCharactersRun(db, { projectId: 'project:t1', statusUpdate: { name: '丙', status: 'dead', exit_type: '死亡型', exit_chapter_id: 'chapter:t1' } });
  const row = db.prepare("SELECT status, exit_type, exit_chapter_id, state_json FROM characters WHERE name='丙'").get();
  assert.equal(row.status, 'dead');
  assert.equal(row.exit_type, '死亡型');
  assert.equal(row.exit_chapter_id, 'chapter:t1');
  const hist = JSON.parse(row.state_json)['状态史'];
  assert.equal(hist.length, 1);
  assert.equal(hist[0].from, 'active');
  assert.equal(hist[0].to, 'dead');
});

test('R10 复活/回归整体清空退场痕迹，状态史累计两条', () => {
  const db = freshDb();
  fixture(db);
  gate.registerCharactersRun(db, { projectId: 'project:t1', entries: [{ name: '丁' }] });
  gate.registerCharactersRun(db, { projectId: 'project:t1', statusUpdate: { name: '丁', status: 'dormant', exit_type: '休眠型' } });
  gate.registerCharactersRun(db, { projectId: 'project:t1', statusUpdate: { name: '丁', status: 'active' } });
  const row = db.prepare("SELECT status, exit_type, exit_chapter_id, state_json FROM characters WHERE name='丁'").get();
  assert.equal(row.status, 'active');
  assert.equal(row.exit_type, null);
  assert.equal(row.exit_chapter_id, null);
  assert.equal(JSON.parse(row.state_json)['状态史'].length, 2);
});

test('R11 连续性提名的未登记人物按 minor 自动补建（补登标记）', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.registerCharactersRun(db, { projectId: 'project:t1', statusUpdate: { name: '路人戊', status: 'departed', exit_type: '迁移型' } });
  const row = db.prepare("SELECT role_class, state_json FROM characters WHERE name='路人戊'").get();
  assert.equal(row.role_class, 'minor');
  assert.ok(row.state_json.includes('补登'));
  assert.ok(r.results[0].includes('active -> departed'));
});

test('R12 批内中途 FK 失败 → ROLLBACK 整体回滚（此前成功项一并撤销）', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => gate.registerCharactersRun(db, {
    projectId: 'project:t1',
    entries: [
      { name: '先落库的' },
      { name: '坏 FK 的', first_chapter_id: 'chapter:nonexistent' },
    ],
  }));
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM characters WHERE name='先落库的'").get().n, 0);
});

// ═══ 状态机门 lock-asset / accept-chapter / commit-review（WP5 语义重建 + R7 新增） ══

test('S1 lock：资产不存在 → GateFail', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => gate.lockAsset(db, { assetId: 'planning:nope', reviewId: 'review:ok-strat' }), '资产不存在');
});

test('S2 lock：rejected 回执 → 跳审阻断', () => {
  const db = freshDb();
  fixture(db);
  db.prepare("UPDATE reviews SET subject_ref='planning:char1', subject_type='planning' WHERE id='review:rej-ch1'").run();
  throwsGate(() => gate.lockAsset(db, { assetId: 'planning:char1', reviewId: 'review:rej-ch1' }), '跳审阻断');
});

test('S3 lock：subject_ref 错绑 → GateFail', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => gate.lockAsset(db, { assetId: 'planning:char1', reviewId: 'review:ok-strat' }), '错绑阻断');
});

test('S4 lock：subject_hash 错版 → GateFail', () => {
  const db = freshDb();
  fixture(db);
  db.prepare("UPDATE reviews SET subject_ref='planning:char1', subject_type='planning', subject_hash=? WHERE id='review:ok-strat'").run('sha256:' + '0'.repeat(64));
  throwsGate(() => gate.lockAsset(db, { assetId: 'planning:char1', reviewId: 'review:ok-strat' }), '错版阻断');
});

test('S5 lock：dry-run 对 candidate 资产零写入', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.lockAsset(db, { assetId: 'planning:char1', reviewId: 'review:ok-char1', dryRun: true });
  assert.ok(r.results[0].startsWith('dry-run'));
  assert.equal(db.prepare("SELECT status FROM planning_assets WHERE id='planning:char1'").get().status, 'candidate');
});

test('S6 lock：candidate 合法锁定（写 locked_review_id）', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.lockAsset(db, { assetId: 'planning:char1', reviewId: 'review:ok-char1', dryRun: false });
  const row = db.prepare("SELECT status, locked_review_id FROM planning_assets WHERE id='planning:char1'").get();
  assert.equal(row.status, 'locked');
  assert.equal(row.locked_review_id, 'review:ok-char1');
  assert.ok(r.results[0].includes('已锁定'));
});

test('S7 lock：同 key 旧 locked 翻 superseded（rev2 锁定 → rev1 superseded）', () => {
  const db = freshDb();
  fixture(db);
  gate.lockAsset(db, { assetId: 'planning:char1', reviewId: 'review:ok-char1', dryRun: false });
  db.prepare(
    "INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role) "
    + "SELECT 'planning:char1-r2', 'project:t1', 'character_contract', 'main', 2, 'candidate', content_resource_id, producer_role FROM planning_assets WHERE id='planning:char1'",
  ).run();
  db.prepare(
    "INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict, reviewer_profile, findings_json) "
    + "SELECT 'review:ok-char-r2', 'planning', 'planning:char1-r2', subject_hash, 'approved', reviewer_profile, findings_json FROM reviews WHERE id='review:ok-char1'",
  ).run();
  gate.lockAsset(db, { assetId: 'planning:char1-r2', reviewId: 'review:ok-char-r2', dryRun: false });
  assert.equal(db.prepare("SELECT status FROM planning_assets WHERE id='planning:char1'").get().status, 'superseded');
  assert.equal(db.prepare("SELECT status FROM planning_assets WHERE id='planning:char1-r2'").get().status, 'locked');
});

test('S8 lock：已锁定同回执 → 幂等重放零写入', () => {
  const db = freshDb();
  fixture(db);
  db.prepare("UPDATE planning_assets SET locked_review_id='review:ok-strat' WHERE id='planning:strat1'").run();
  const r = gate.lockAsset(db, { assetId: 'planning:strat1', reviewId: 'review:ok-strat', dryRun: false });
  assert.equal(r.idempotent, true);
});

test('S9 lock：已锁定不同回执 → GateFail（走修订流程）', () => {
  const db = freshDb();
  fixture(db);
  db.prepare(
    "INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict, reviewer_profile, findings_json) "
    + "SELECT 'review:ok-strat-2', 'planning', 'planning:strat1', subject_hash, 'approved', reviewer_profile, findings_json FROM reviews WHERE id='review:ok-strat'",
  ).run();
  throwsGate(() => gate.lockAsset(db, { assetId: 'planning:strat1', reviewId: 'review:ok-strat-2', dryRun: false }), '已锁定');
});

test('S10 lock：stale 资产 → GateFail', () => {
  const db = freshDb();
  fixture(db);
  db.prepare("UPDATE planning_assets SET status='stale' WHERE id='planning:strat1'").run();
  throwsGate(() => gate.lockAsset(db, { assetId: 'planning:strat1', reviewId: 'review:ok-strat', dryRun: false }), '仅 candidate 可锁定');
});

test('S11 accept：draft + approved → accepted + review_id 机器痕迹', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.acceptChapter(db, { chapterId: 'chapter:t1', reviewId: 'review:ok-ch1', dryRun: false });
  const row = db.prepare("SELECT status, review_id FROM chapters WHERE id='chapter:t1'").get();
  assert.equal(row.status, 'accepted');
  assert.equal(row.review_id, 'review:ok-ch1');
  assert.ok(r.results[0].includes('已接受'));
});

test('S12 accept：rejected 回执 → GateFail', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => gate.acceptChapter(db, { chapterId: 'chapter:t1', reviewId: 'review:rej-ch1', dryRun: false }), '跳审阻断');
});

test('S13 accept：subject_ref 错绑 → GateFail', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => gate.acceptChapter(db, { chapterId: 'chapter:t1', reviewId: 'review:ok-ch2' }), '错绑阻断');
});

test('S14 accept：hash 错版 → GateFail', () => {
  const db = freshDb();
  fixture(db);
  db.prepare("UPDATE reviews SET subject_hash=? WHERE id='review:ok-ch1'").run('sha256:' + '0'.repeat(64));
  throwsGate(() => gate.acceptChapter(db, { chapterId: 'chapter:t1', reviewId: 'review:ok-ch1', dryRun: false }), '错版阻断');
});

test('S15 accept：已接受同回执 → 幂等重放', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.acceptChapter(db, { chapterId: 'chapter:t2', reviewId: 'review:ok-ch2', dryRun: false });
  assert.equal(r.idempotent, true);
});

test('S16 accept：已接受不同回执 → GateFail（免审直改禁止）', () => {
  const db = freshDb();
  fixture(db);
  db.prepare(
    "INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict, reviewer_profile, findings_json) "
    + "SELECT 'review:ok-ch2-b', 'chapter', 'chapter:t2', subject_hash, 'approved', reviewer_profile, findings_json FROM reviews WHERE id='review:ok-ch2'",
  ).run();
  throwsGate(() => gate.acceptChapter(db, { chapterId: 'chapter:t2', reviewId: 'review:ok-ch2-b', dryRun: false }), '免审直改禁止');
});

test('S17 accept：superseded → GateFail', () => {
  const db = freshDb();
  fixture(db);
  const ch3Content = DRAFT + '\n（第三版内容）\n';
  db.prepare(
    "INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict, reviewer_profile, findings_json) "
    + "VALUES ('review:ok-ch3', 'chapter', 'chapter:t3', ?, 'approved', 'model:fixture:m1', '[]')",
  ).run(contentHash(ch3Content));
  throwsGate(() => gate.acceptChapter(db, { chapterId: 'chapter:t3', reviewId: 'review:ok-ch3', dryRun: false }), '仅 draft 可接受');
});

test('S18 accept：dry-run 零写入', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.acceptChapter(db, { chapterId: 'chapter:t1', reviewId: 'review:ok-ch1', dryRun: true });
  assert.ok(r.results[0].startsWith('dry-run'));
  assert.equal(db.prepare("SELECT status FROM chapters WHERE id='chapter:t1'").get().status, 'draft');
});

const receiptFor = (over = {}) => JSON.stringify({
  subject_type: 'chapter',
  subject_ref: 'chapter:t1',
  subject_hash: contentHash(DRAFT),
  verdict: 'approved',
  reviewer_profile: 'model:fixture:m1',
  findings: [{ severity: 'blocking', code: 'L01', message: '测试', excerpt: '任务失败不是惩罚，而是清零', evidence_refs: ['para:1'] }],
  ...over,
});

test('S19 commit-review：reviewer_profile 无前缀 → GateFail（P4-2 机器强制）', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => gate.commitReview(db, { receiptRaw: receiptFor({ reviewer_profile: 'prose-v1' }), dryRun: false }), 'P4-2');
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM reviews').get().n, 5);
});

test('S20 commit-review：空 findings+approved 默认 GateFail（A1），零写入', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => gate.commitReview(db, { receiptRaw: receiptFor({ findings: [] }), dryRun: false }), 'R9 M5');
});

test('S20b commit-review：note-only+approved = 空查 GateFail；--allow-empty 放行且留痕（R9 M5）', () => {
  const db = freshDb();
  fixture(db);
  const noteOnly = [{ severity: 'note', code: 'N1', message: '凑数', excerpt: '任务失败不是惩罚', evidence_refs: [] }];
  throwsGate(() => gate.commitReview(db, { receiptRaw: receiptFor({ findings: noteOnly }), dryRun: false }), 'note 级凑数不算查过');
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM reviews').get().n, 5);
  const r = gate.commitReview(db, { receiptRaw: receiptFor({ findings: noteOnly }), allowEmpty: true, dryRun: false });
  const row = db.prepare('SELECT metadata_json FROM reviews WHERE id=?').get(r.reviewId);
  assert.ok(row.metadata_json.includes('allow_empty'), '豁免须留痕');
});

test('S24 commit-review：写作/审查同模型 GateFail；--allow-same-provider 豁免留痕（R9 M6）', () => {
  const db = freshDb();
  fixture(db);
  // receiptFor 的 reviewer_profile = model:fixture:m1；写作端同模型 → collusion_risk
  throwsGate(() => gate.commitReview(db, {
    receiptRaw: receiptFor(), dryRun: false, writerProfile: 'model:fixture:m1',
  }), 'collusion_risk');
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM reviews').get().n, 5);
  // provider 前缀不同但模型 token 相同（agent:@model 形态）同样拦截
  throwsGate(() => gate.commitReview(db, {
    receiptRaw: receiptFor({ reviewer_profile: 'agent:prose-review-perspectives@m1' }), dryRun: false,
    writerProfile: 'deepseek-official/m1',
  }), 'collusion_risk');
  // 豁免 → PASS 且 metadata.same_provider_allowed=true + advisory
  const r = gate.commitReview(db, {
    receiptRaw: receiptFor(), dryRun: false, writerProfile: 'model:fixture:m1', allowSameProvider: true,
  });
  const row = db.prepare('SELECT metadata_json FROM reviews WHERE id=?').get(r.reviewId);
  assert.ok(row.metadata_json.includes('same_provider_allowed'), '豁免须入 metadata');
});

test('S25 commit-review：写作/审查异模型正常落库（R9 M6 不误伤）', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.commitReview(db, {
    receiptRaw: receiptFor(), dryRun: false, writerProfile: 'model:deepseek-official/deepseek-v4-pro',
  });
  assert.equal(r.dryRun, false);
});

test('S26 lock/accept：同 subject ≥3 回执且无裁决单 → 升级裁决门 GateFail；开裁决后由互锁接管（R9 M10）', () => {
  const db = freshDb();
  fixture(db);
  const H = 'sha256:' + 'cd'.repeat(32);
  // 锁定路径：planning:strat1 累积 3 条同 subject 回执（内容 hash 与锁定资产一致，避免错绑先拦）
  const stratHash = db.prepare("SELECT r.content_hash AS h FROM planning_assets pa JOIN resources r ON r.id=pa.content_resource_id WHERE pa.id='planning:strat1'").get().h;
  const insP = db.prepare(
    "INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict, reviewer_profile, findings_json) "
    + "VALUES (?, 'planning', 'planning:strat1', ?, 'rejected', 'model:fixture:m1', '[]')",
  );
  insP.run('review:p1', stratHash);
  insP.run('review:p2', stratHash);
  insP.run('review:p3', stratHash);
  throwsGate(() => gate.lockAsset(db, { assetId: 'planning:strat1', reviewId: 'review:p3', dryRun: false }), '升级裁决门');
  // 接受路径：chapter:t1 累积 3 条同 subject 回执
  const ins = db.prepare(
    "INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict, reviewer_profile, findings_json) "
    + "VALUES (?, 'chapter', 'chapter:t1', ?, 'rejected', 'model:fixture:m1', '[]')",
  );
  ins.run('review:r1', H);
  ins.run('review:r2', H);
  ins.run('review:r3', H);
  throwsGate(() => gate.acceptChapter(db, { chapterId: 'chapter:t1', reviewId: 'review:r3', dryRun: false }), '升级裁决门');
  // 开 open 裁决后：M10 让位给互锁（仍阻断，但语义为未决裁决）——open 行存在时不重复报 ≥3
  db.exec("INSERT INTO adjudications (id, project_id, subject_type, subject_ref, reason) VALUES ('adjudication:m10', 'project:t1', 'chapter', 'chapter:t1', '三轮不收敛')");
  throwsGate(() => gate.acceptChapter(db, { chapterId: 'chapter:t1', reviewId: 'review:r3', dryRun: false }), '未决裁决阻断');
});

test('S20c commit-review：--no-check-hash 落库 metadata 留痕 check_hash=false（R9 M5/D-3）', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.commitReview(db, { receiptRaw: receiptFor(), checkHash: false, dryRun: false });
  const row = db.prepare('SELECT metadata_json FROM reviews WHERE id=?').get(r.reviewId);
  assert.ok(row.metadata_json.includes('check_hash'), 'check_hash 须入 metadata');
  assert.ok(row.metadata_json.includes('false'), '跳过值须为 false');
});

test('S21 commit-review：--allow-empty 落库成功且 metadata 留痕', () => {
  const db = freshDb();
  fixture(db);
  const r = gate.commitReview(db, { receiptRaw: receiptFor({ findings: [] }), allowEmpty: true, dryRun: false });
  assert.equal(r.dryRun, false);
  const row = db.prepare('SELECT metadata_json FROM reviews WHERE id=?').get(r.reviewId);
  assert.ok(row.metadata_json.includes('allow_empty'));
});

test('S22 commit-review：dry-run 零写入 → --commit 落库可回读（findings_json DB 行形态）', () => {
  const db = freshDb();
  fixture(db);
  const before = db.prepare('SELECT COUNT(*) AS n FROM reviews').get().n;
  const r1 = gate.commitReview(db, { receiptRaw: receiptFor(), dryRun: true });
  assert.equal(r1.dryRun, true);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM reviews').get().n, before);
  const r2 = gate.commitReview(db, { receiptRaw: receiptFor(), dryRun: false });
  const row = db.prepare('SELECT findings_json, verdict FROM reviews WHERE id=?').get(r2.reviewId);
  assert.equal(row.verdict, 'approved');
  assert.ok(row.findings_json.includes('L01'));
  const reparsed = gate.commitReview; // 模块存活引用（防意外 tree-shake 语义漂移）
  assert.ok(typeof reparsed === 'function');
});

test('S23 commit-review：编造引文 no_hit → GateFail 零写入', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => gate.commitReview(db, {
    receiptRaw: receiptFor({ findings: [{ severity: 'blocking', code: 'X1', message: '编造', excerpt: '这句话不在草稿里', evidence_refs: [] }] }),
    dryRun: false,
  }), 'no_hit');
});

// ═══ CLI 层（exit 语义 + 生产库保护） + validate-asset ══════════════════════

function runCli(args, input) {
  return spawnSync(process.execPath, ['--no-warnings', GATE, ...args], { encoding: 'utf8', cwd: ROOT, input });
}

test('C1 CLI 用法错误 exit 2；未知子命令 exit 2', () => {
  assert.equal(runCli(['bogus-subcommand']).status, 2);
  assert.equal(runCli(['lock-asset']).status, 2); // 缺 --asset
});

test('C2 CLI 生产库写保护：--commit 无 --allow-production → exit 2（未触库）', () => {
  const r = runCli(['propagate-stale', '--asset', 'planning:nonexistent', '--commit']);
  assert.equal(r.status, 2);
  assert.ok(r.stderr.includes('--allow-production'));
});

test('C3 CLI 对生产库只读 dry-run 允许（资产不存在 → GateFail exit 1）', () => {
  const r = runCli(['propagate-stale', '--asset', 'planning:nonexistent']);
  assert.equal(r.status, 1);
  assert.ok(r.stderr.includes('GATE FAIL'));
});

test('C4 CLI --json 端到端（临时库路径 ≠ 生产路径 → --commit 直接受理）', () => {
  const fs = await_import_fs();
  const dbPath = path.join(ROOT, 'data', `gate-cli-fixture-${Date.now()}.tmp.db`);
  try {
    const db = new DatabaseSync(dbPath);
    db.exec(readFileSync(path.join(ROOT, 'db/migrations/schema.sql'), 'utf8'));
    fixture(db);
    db.close();
    const r = runCli(['propagate-stale', '--asset', 'planning:dir-r1', '--commit', '--json', '--db', dbPath]);
    assert.equal(r.status, 0, r.stdout + r.stderr);
    const j = JSON.parse(r.stdout);
    assert.equal(j.marked, 2);
  } finally {
    rmSync(dbPath, { force: true });
  }
});
function await_import_fs() { return { rmSync }; } // fs 顶部已静态导入（命名保留测试可读性）

test('V1 validate-asset：strategy 阶段数超档位 + 消费表缺行 → 双 FAIL', () => {
  const db = freshDb();
  fixture(db);
  db.prepare(
    "INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role, metadata_json) "
    + "VALUES ('planning:strat-meta', 'project:t1', 'strategy', 'main', 2, 'candidate', 'resource:strat', 'planning:strategy', ?)",
  ).run(JSON.stringify({ stages: Array.from({ length: 9 }, () => ({ payoff: 'heavy', word_range: { max: 10 } })) }));
  const r = gate.validateAsset(db, { assetId: 'planning:strat-meta' });
  assert.ok(r.errors.some((e) => e.includes('阶段数 9')));
  assert.ok(r.errors.some((e) => e.includes('上游消费表缺行')));
});

test('V2 validate-asset：全对 PASS（0 errors），scale 库内自动解析', () => {
  const db = freshDb();
  fixture(db);
  const consumption = ['rhythm_table', 'reveal_ladder', 'promise_cadence', 'power_escalation', 'spiral_rotation', 'engine_config', 'upstream_receipts']
    .map((output) => ({ output }));
  const stages = Array.from({ length: 3 }, () => ({ payoff: 'heavy', word_range: { max: 10 } }));
  db.prepare(
    "INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role, metadata_json) "
    + "VALUES ('planning:strat-ok', 'project:t1', 'strategy', 'main', 3, 'candidate', 'resource:strat', 'planning:strategy', ?)",
  ).run(JSON.stringify({ stages, consumption, midpoint_renewal: { stage: 2 } }));
  const r = gate.validateAsset(db, { assetId: 'planning:strat-ok' });
  assert.deepEqual(r.errors, []);
  assert.equal(r.scale, '长篇');
});

test('V3 validate-asset：story_arc 缺必需字段 → error 且语义门跳过（零 npm 结构层偏离声明）', () => {
  const db = freshDb();
  fixture(db);
  db.prepare(
    "INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role, metadata_json) "
    + "VALUES ('planning:arc-bad', 'project:t1', 'story_arc', 'main', 1, 'candidate', 'resource:vol', 'planning:story_arc', '{}')",
  ).run();
  const r = gate.validateAsset(db, { assetId: 'planning:arc-bad' });
  assert.equal(r.errors.length, 4);
  assert.ok(r.errors[0].includes('schema 必填'));
});

test('V4 validate-asset：world 席位重名 + 代价两轴门（压制缺 release）', () => {
  const db = freshDb();
  fixture(db);
  db.prepare(
    "INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role, metadata_json) "
    + "VALUES ('planning:world-meta', 'project:t1', 'world_contract', 'main', 2, 'candidate', 'resource:world', 'planning:world', ?)",
  ).run(JSON.stringify({
    seats: [{ name: 'A' }, { name: 'A' }],
    dimension_costs: [{ dimension: '寿命', reversibility: '压制', release: '' }],
  }));
  const r = gate.validateAsset(db, { assetId: 'planning:world-meta' });
  assert.ok(r.errors.some((e) => e.includes('岗位重名')));
  assert.ok(r.errors.some((e) => e.includes('缺解除通道 release')));
});

test('V5 validate-asset：--asset 不存在 → GateFail', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => gate.validateAsset(db, { assetId: 'planning:nope' }), '资产不存在');
});

test('V6 Claremont 收口：open 伏笔 >2 → accept 输出 WARN（不阻断）', () => {
  const db = freshDb();
  fixture(db);
  for (const key of ['p1', 'p2', 'p3']) {
    db.prepare(
      'INSERT INTO narrative_promises (id, project_id, promise_key, description_resource_id, status, source_chapter_id, source_content_hash) '
      + "VALUES (?, 'project:t1', ?, 'resource:ch1', 'open', 'chapter:t1', ?)",
    ).run(`promise:${key}`, key, contentHash(DRAFT));
  }
  const r = gate.acceptChapter(db, { chapterId: 'chapter:t1', reviewId: 'review:ok-ch1', dryRun: false });
  assert.ok(r.results.some((l) => l.includes('Claremont') && l.includes('>2')));
  assert.equal(r.claremont.open, 3);
});

test('V7 Claremont 收口：open ≤2 无 WARN', () => {
  const db = freshDb();
  fixture(db);
  db.prepare(
    'INSERT INTO narrative_promises (id, project_id, promise_key, description_resource_id, status, source_chapter_id, source_content_hash) '
    + "VALUES ('promise:p1', 'project:t1', 'p1', 'resource:ch1', 'open', 'chapter:t1', ?)",
  ).run(contentHash(DRAFT));
  const r = gate.acceptChapter(db, { chapterId: 'chapter:t1', reviewId: 'review:ok-ch1', dryRun: false });
  assert.equal(r.claremont.warn, false);
  assert.ok(!r.results.some((l) => l.includes('Claremont')));
});

test('V8 promise_events 流水（021）：CHECK 拒非法 event_type；追加+按 key 查询跑通', () => {
  const db = freshDb();
  fixture(db);
  db.prepare(
    'INSERT INTO narrative_promises (id, project_id, promise_key, description_resource_id, status, source_chapter_id, source_content_hash) '
    + "VALUES ('promise:k1', 'project:t1', 'k1', 'resource:ch1', 'open', 'chapter:t1', ?)",
  ).run(contentHash(DRAFT));
  assert.throws(() => db.prepare(
    "INSERT INTO promise_events (id, project_id, promise_key, event_type) VALUES ('pe:bad', 'project:t1', 'k1', 'bogus')",
  ).run()); // CHECK
  db.prepare(
    "INSERT INTO promise_events (id, project_id, promise_key, chapter_id, event_type, note, source_content_hash) "
    + "VALUES ('pe:1', 'project:t1', 'k1', 'chapter:t1', 'plant', '埋设', ?)",
  ).run(contentHash(DRAFT));
  db.prepare(
    "INSERT INTO promise_events (id, project_id, promise_key, chapter_id, event_type) VALUES ('pe:2', 'project:t1', 'k1', 'chapter:t1', 'progress')",
  ).run();
  const flow = db.prepare(
    'SELECT promise_key, event_type, chapter_id FROM promise_events WHERE project_id=? AND promise_key=? ORDER BY created_at, rowid',
  ).all('project:t1', 'k1');
  assert.deepEqual(flow.map((r) => r.event_type), ['plant', 'progress']);
});

test('V9 narrative_promises.resolved_chapter_id 列在位（021 schema 同步）', () => {
  const db = freshDb();
  fixture(db);
  const cols = db.prepare("SELECT name FROM pragma_table_info('narrative_promises')").all().map((r) => r.name);
  assert.ok(cols.includes('resolved_chapter_id'));
});

// ═══ A5 TBD 物化：open/resolve-adjudication + 门互锁（R8-T2，022） ═══════════

const openAdj = (db, over = {}) => gate.openAdjudication(db, {
  projectId: 'project:t1', subjectType: 'planning', subjectRef: 'planning:strat1',
  reason: '3 轮未收敛：节奏判级反复', rounds: [{ round: 1, blocking: '节奏超档' }, { round: 2, blocking: '同因复发' }],
  dryRun: false, ...over,
});

test('AD1 open-adjudication：dry-run 零写入', () => {
  const db = freshDb();
  fixture(db);
  const r = openAdj(db, { dryRun: true });
  assert.equal(r.dryRun, true);
  assert.ok(r.results[0].startsWith('dry-run'));
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM adjudications').get().n, 0);
});

test('AD2 open-adjudication：commit 落行，rounds_json 留痕', () => {
  const db = freshDb();
  fixture(db);
  const r = openAdj(db);
  assert.equal(r.dryRun, false);
  const row = db.prepare('SELECT * FROM adjudications WHERE id=?').get(r.adjudicationId);
  assert.equal(row.status, 'open');
  assert.equal(row.subject_ref, 'planning:strat1');
  const rounds = JSON.parse(row.rounds_json);
  assert.equal(rounds.length, 2);
  assert.equal(rounds[1].blocking, '同因复发');
});

test('AD3 重复开单 → GateFail（同 subject 已 open；022 部分唯一索引兜底）', () => {
  const db = freshDb();
  fixture(db);
  openAdj(db);
  throwsGate(() => openAdj(db, { reason: '再开一单' }), '重复开单');
  // 直接绕过门插库也须被 DB 约束拦截
  assert.throws(() => db.prepare(
    "INSERT INTO adjudications (id, project_id, subject_type, subject_ref, reason) VALUES ('adjudication:dup', 'project:t1', 'planning', 'planning:strat1', 'dup')",
  ).run());
});

test('AD4 subject 不存在 / 错项目 / 非法 subject_type → GateFail', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => openAdj(db, { subjectRef: 'planning:nonexistent' }), 'subject 不存在');
  throwsGate(() => openAdj(db, { projectId: 'project:other' }), '错项目开单');
  throwsGate(() => openAdj(db, { subjectType: 'volume' }), 'subject_type 须为');
});

test('AD5 门互锁：open 后 lock-asset 阻断，resolve 后放行', () => {
  const db = freshDb();
  fixture(db);
  gate.openAdjudication(db, {
    projectId: 'project:t1', subjectType: 'planning', subjectRef: 'planning:char1',
    reason: '人物契约 3 轮未收敛', rounds: [], dryRun: false,
  });
  throwsGate(() => gate.lockAsset(db, { assetId: 'planning:char1', reviewId: 'review:ok-char1', dryRun: true }), '未决裁决阻断');
  throwsGate(() => gate.lockAsset(db, { assetId: 'planning:char1', reviewId: 'review:ok-char1', dryRun: false }), '未决裁决阻断');
  // 裁决放行
  const adjId = db.prepare("SELECT id FROM adjudications WHERE status='open'").get().id;
  gate.resolveAdjudication(db, { adjudicationId: adjId, resolution: '用户裁决：按第 2 轮版本放行', dryRun: false });
  const r = gate.lockAsset(db, { assetId: 'planning:char1', reviewId: 'review:ok-char1', dryRun: false });
  assert.ok(r.results[0].includes('已锁定'));
});

test('AD6 门互锁：chapter subject open 后 accept-chapter 阻断（幂等重放也拦）', () => {
  const db = freshDb();
  fixture(db);
  gate.openAdjudication(db, {
    projectId: 'project:t1', subjectType: 'chapter', subjectRef: 'chapter:t1',
    reason: 'mismatch 待裁决', rounds: [], dryRun: false,
  });
  throwsGate(() => gate.acceptChapter(db, { chapterId: 'chapter:t1', reviewId: 'review:ok-ch1', dryRun: true }), '未决裁决阻断');
  throwsGate(() => gate.acceptChapter(db, { chapterId: 'chapter:t1', reviewId: 'review:ok-ch1', dryRun: false }), '未决裁决阻断');
});

test('AD7 resolve-adjudication：不存在 / 已 resolved / resolution 必填 → GateFail', () => {
  const db = freshDb();
  fixture(db);
  throwsGate(() => gate.resolveAdjudication(db, { adjudicationId: 'adjudication:ghost', resolution: 'x', dryRun: false }), '裁决单不存在');
  const r = openAdj(db);
  throwsGate(() => gate.resolveAdjudication(db, { adjudicationId: r.adjudicationId, resolution: '', dryRun: false }), 'resolution 必填');
  gate.resolveAdjudication(db, { adjudicationId: r.adjudicationId, resolution: '放行', dryRun: false });
  throwsGate(() => gate.resolveAdjudication(db, { adjudicationId: r.adjudicationId, resolution: '再裁一次', dryRun: false }), '终态不可重裁决');
});

test('AD8 缺表兼容：022 未应用时互锁静默放行，open 显式报错不静默', () => {
  const db = freshDb();
  fixture(db);
  db.exec('DROP INDEX IF EXISTS idx_adjudications_project; DROP INDEX IF EXISTS idx_adjudications_open_subject; DROP TABLE adjudications;');
  const r = gate.lockAsset(db, { assetId: 'planning:char1', reviewId: 'review:ok-char1', dryRun: true }); // 不抛
  assert.ok(r.results[0].startsWith('dry-run'));
  throwsGate(() => openAdj(db, { dryRun: true }), 'migration 022');
});

test('AD9 open 不拦 commit-review（裁决期间补审查是合法输入）', () => {
  const db = freshDb();
  fixture(db);
  openAdj(db); // planning:strat1
  const r = gate.commitReview(db, { receiptRaw: receiptFor(), dryRun: false }); // chapter:t1 新回执照常落库
  assert.equal(r.dryRun, false);
  assert.ok(db.prepare('SELECT COUNT(*) AS n FROM reviews').get().n >= 6);
});

test('AD10 adjudication 生命周期全链（open → 阻断 → resolve → 放行 → 再开新单）', () => {
  const db = freshDb();
  fixture(db);
  const r1 = openAdj(db);
  gate.resolveAdjudication(db, { adjudicationId: r1.adjudicationId, resolution: '首轮裁决：修订后重审', dryRun: false });
  const row = db.prepare('SELECT status, resolution, resolved_at FROM adjudications WHERE id=?').get(r1.adjudicationId);
  assert.equal(row.status, 'resolved');
  assert.ok(row.resolved_at !== null);
  const r2 = openAdj(db, { reason: '修订后同因复发，二次升级' }); // resolve 后可再开
  assert.notEqual(r2.adjudicationId, r1.adjudicationId);
});

test('AD11 CLI open/resolve：临时库端到端（dry-run 零写入 → --commit → --json 回读）', () => {
  const fsMod = await_import_fs();
  const dbPath = path.join(ROOT, 'data', `gate-adj-fixture-${Date.now()}.tmp.db`);
  try {
    const db = new DatabaseSync(dbPath);
    db.exec(readFileSync(path.join(ROOT, 'db/migrations/schema.sql'), 'utf8'));
    fixture(db);
    db.close();
    const dry = runCli(['open-adjudication', '--project', 'project:t1', '--subject-type', 'planning',
      '--subject-ref', 'planning:char1', '--reason', 'CLI 演练', '--db', dbPath]);
    assert.equal(dry.status, 0, dry.stdout + dry.stderr);
    assert.ok(dry.stdout.includes('dry-run'));
    const conn = new DatabaseSync(dbPath);
    assert.equal(conn.prepare('SELECT COUNT(*) AS n FROM adjudications').get().n, 0);
    conn.close();
    const commit = runCli(['open-adjudication', '--project', 'project:t1', '--subject-type', 'planning',
      '--subject-ref', 'planning:char1', '--reason', 'CLI 演练', '--rounds', '[{"round":1,"blocking":"b"}]', '--commit', '--db', dbPath]);
    assert.equal(commit.status, 0, commit.stdout + commit.stderr);
    const commit2 = runCli(['open-adjudication', '--project', 'project:t1', '--subject-type', 'planning',
      '--subject-ref', 'planning:char1', '--reason', 'dup', '--commit', '--db', dbPath]);
    assert.equal(commit2.status, 1); // 重复开单 GateFail
    const list = runCli(['resolve-adjudication', '--adjudication', 'adjudication:ghost', '--resolution', 'x', '--db', dbPath]);
    assert.equal(list.status, 1); // 不存在
    const j = runCli(['open-adjudication', '--project', 'project:t1', '--subject-type', 'planning',
      '--subject-ref', 'planning:strat1', '--reason', 'json 演练', '--commit', '--json', '--db', dbPath]);
    assert.equal(j.status, 0, j.stdout + j.stderr);
    const parsed = JSON.parse(j.stdout.slice(j.stdout.indexOf('{'))); // results 行先打，JSON 尾随（pretty 多行）
    assert.ok(parsed.adjudicationId.startsWith('adjudication:'));
  } finally {
    fsMod.rmSync(dbPath, { force: true });
  }
});

test('AD12 CLI 生产库写保护同样覆盖 open-adjudication', () => {
  const r = runCli(['open-adjudication', '--project', 'project:x', '--subject-type', 'planning',
    '--subject-ref', 'planning:x', '--reason', 'r', '--commit']);
  assert.equal(r.status, 2);
  assert.ok(r.stderr.includes('--allow-production'));
});

// ═══ 汇总 ═══════════════════════════════════════════════════════════════════

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  for (const f of failures) console.error(`- ${f.name}: ${f.e.stack || f.e.message}`);
  process.exitCode = 1;
}
