#!/usr/bin/env node
// R6 S0 演练隔离脚本(裁-10)。零默认生产路径:--source/--drill 必填,防误触。
// 用法: node scripts/novelos-drill-prepare.mjs --source <库> --drill <副本路径> [--checkpoint] [--skip-backup]
//   --checkpoint  对 source 执行 PRAGMA wal_checkpoint(TRUNCATE)(S0 正式流程;缺省跳过——
//                 prepare-only/测试场景不碰生产库)。checkpoint 需要写句柄,属计划内唯一写动作。
//   --skip-backup 跳过 .bak-drill-<ts> 备份(仅 /tmp 试验用;正式流程禁止)。
// 输出: S0 报告(sha256/wal 字节/迁移版本/chapters 列清单,source 与 drill 各一份)+ S1 冒烟清单。
// 零污染证明口径(裁-10/D5 红方 P1-2): checkpoint(TRUNCATE) 后主库 sha256 前后一致 且 -wal 恒 0 字节。
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, statSync, readFileSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';

function arg(name) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : undefined;
}
const has = (name) => process.argv.includes(`--${name}`);
const source = arg('source');
const drill = arg('drill');
if (!source || !drill || !existsSync(source)) {
  console.error('用法: node scripts/novelos-drill-prepare.mjs --source <库> --drill <副本> [--checkpoint] [--skip-backup]\n--source/--drill 必填且 source 必须存在;不设默认生产路径。');
  process.exit(2);
}
const sha = (p) => createHash('sha256').update(readFileSync(p)).digest('hex');
const walOf = (p) => { const w = p + '-wal'; return existsSync(w) ? statSync(w).size : 0; };
const report = {};

// 0. 前置状态(只读)
{
  const db = new DatabaseSync(source, { readOnly: true });
  report.source_before = {
    sha256: sha(source), wal_bytes: walOf(source),
    schema_migrations: db.prepare('SELECT MAX(version) v FROM schema_migrations').get()?.v ?? null,
    chapters_has_review_id: db.prepare('PRAGMA table_info(chapters)').all().some(c => c.name === 'review_id'),
    chapters_count: db.prepare('SELECT COUNT(*) c FROM chapters').get()?.c ?? null,
    projects_count: db.prepare('SELECT COUNT(*) c FROM projects').get()?.c ?? null,
  };
  db.close();
}
console.error(`[S0] source before: ${JSON.stringify(report.source_before)}`);

// 1. checkpoint(仅 --checkpoint;S0 正式流程对生产库的一次性维护动作)
if (has('checkpoint')) {
  const db = new DatabaseSync(source); // 写句柄,仅此一步
  const r = db.prepare('PRAGMA wal_checkpoint(TRUNCATE)').get();
  db.close();
  console.error(`[S0] wal_checkpoint(TRUNCATE): ${JSON.stringify(r)}`);
} else {
  console.error('[S0] 未传 --checkpoint,跳过 checkpoint(测试/prepare 模式)');
}

// 2. 备份(S0 正式流程禁止跳过)
if (!has('skip-backup')) {
  const bak = join(dirname(source), `${basename(source)}.bak-drill-${new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)}`);
  copyFileSync(source, bak);
  report.backup = bak;
  console.error(`[S0] 备份: ${bak}`);
}

// 3. 副本(VACUUM INTO——checkpoint 后主库即一致快照;VACUUM INTO 再得紧凑副本)
{
  if (existsSync(drill)) { console.error(`[S0] drill 目标已存在,拒绝覆盖: ${drill}`); process.exit(1); }
  const db = new DatabaseSync(source);
  db.prepare(`VACUUM INTO '${drill}'`).run();
  db.close();
}

// 4. 后置核验(双方只读)
for (const [k, p] of [['source_after', source], ['drill', drill]]) {
  const db = new DatabaseSync(p, { readOnly: true });
  report[k] = {
    sha256: sha(p), wal_bytes: walOf(p),
    schema_migrations: db.prepare('SELECT MAX(version) v FROM schema_migrations').get()?.v ?? null,
    chapters_has_review_id: db.prepare('PRAGMA table_info(chapters)').all().some(c => c.name === 'review_id'),
    chapters_count: db.prepare('SELECT COUNT(*) c FROM chapters').get()?.c ?? null,
    projects_count: db.prepare('SELECT COUNT(*) c FROM projects').get()?.c ?? null,
  };
  db.close();
}
report.zero_pollution = report.source_before.sha256 === report.source_after.sha256
  && report.source_before.wal_bytes === 0 && report.source_after.wal_bytes === 0;
report.s1_checklist = [
  `schema_migrations 版本 = ${report.source_after.schema_migrations}(019 应用与否决定 S4 接受步骤可用性——U11 裁决项)`,
  `chapters.review_id 存在 = ${report.drill.chapters_has_review_id}(false ⇒ S4 记「接受步骤跳过(待 019)」,不得造假)`,
  `项目数 = ${report.drill.projects_count};章节数 = ${report.drill.chapters_count}(规划链空白 ⇒ 从 direction 起跑)`,
  `零污染 = ${report.zero_pollution}(主库 sha256 前后一致且 wal=0;演练期间主库只允许只读打开)`,
];
console.log(JSON.stringify(report, null, 2));
