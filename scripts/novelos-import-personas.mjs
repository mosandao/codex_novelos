#!/usr/bin/env node
/**
 * novelos-import-personas.mjs —— kb_author_personas → 风格种子试点（R5 / U6 呈报材料生成器）。
 *
 * 通道（裁-5）：MySQL nwriter.kb_author_personas 只读 → author_name 归并预处理（trim +
 * 别名归并表，红方 F5）→ 选样（q≥9 / 归并后同作者 ≤2 / 女频必取 ≥2 / weaknesses 非空 /
 * 题材轴覆盖 / 12-16 卡）→ 产出：
 *   - data/knowledge/personas-pilot.json（gitignore；每卡归一化字段 + conversion_notes +
 *     归并记录；persona_prompt 原文只落此处与库内 BLOB，禁入 git）
 *   - config/knowledge/personas-alias-map.json（入 git 裁决材料；由脚本内置规则投影，每次运行重写，内容确定）
 *
 * 写库纪律（AGENTS.md）：默认 --dry-run 不写任何库；--commit 须显式 --db 指向副本库，
 * 指向生产库 data/novelos-v2.db 时硬编码拒绝（生产库零写入红线）。目标库须已应用
 * migration 020（creator_profiles.ownership CHECK 含 'style_seed'，落库前查 sqlite_master
 * 断言）且无存量 style_seed 行（防重复导入）。resources 经 BLOB 写入并同步 content_hash
 * （'sha256:'+hex，node:crypto）；多表单事务 BEGIN IMMEDIATE，任一步失败整体回滚零写入。
 *
 * CLI：
 *   node scripts/novelos-import-personas.mjs                          # 选样 + 产出 JSON + dry-run 行预览
 *   node scripts/novelos-import-personas.mjs --commit --db /tmp/xxx.db  # 写副本库（先在副本应用 020）
 * 环境变量：MYSQL_PWD 必填；MYSQL_HOST(127.0.0.1)/MYSQL_PORT(3306)/MYSQL_DB(nwriter)/MYSQL_USER(root) 可覆盖。
 * 版权边界（裁-5/U12）：卡片是拆解方法论非原文；不整表搬运（试点 <15%）；归并记录只含 id+作者名。
 */

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PILOT_OUT = path.join(ROOT, 'data/knowledge/personas-pilot.json');
const ALIAS_OUT = path.join(ROOT, 'config/knowledge/personas-alias-map.json');
const PROD_DB = path.join(ROOT, 'data/novelos-v2.db');

const args = process.argv.slice(2);
const COMMIT = args.includes('--commit');
const dbFlagIdx = args.indexOf('--db');
const TARGET_DB = dbFlagIdx !== -1 ? path.resolve(args[dbFlagIdx + 1] ?? '') : null;

// ── author_name 归并规则（内置权威；投影到 config/knowledge/personas-alias-map.json）──
// 匹配在 trim 之后进行；无法机械归并的变体须呈报用户裁决（红方 F5）。
const ALIAS_RULES = [
  {
    pattern: '^刘慈欣',
    to: '刘慈欣',
    note: '刘慈欣 5 名变体 6 条：刘慈欣 / 刘慈欣风格×2 / 刘慈欣（三体1风格）/ 刘慈欣（三体2风格）/ 刘慈欣·硬科幻风格（D4 红方实测）；q≥9 池内命中 4 条（id 2/63/83/84）',
  },
  {
    pattern: '^三九音域\\s*\\|',
    to: '三九音域',
    note: 'id=116「三九音域 | 提取维度：7维度人格分析」（q=8 不在试点池，防未来混入）',
  },
];
const TRIM_NOTE = '前后空白（实测命中 id=200「␣Priest」前导空格——不归并则女频必取判据直接落空）';

// ── 选样轴（D4 计划 §3.5 题材轴覆盖 + 女频必取 ≥2；pick=该轴取卡数）──
const AXIS_PLAN = [
  { axis: '女频（必取）', pick: 2, authors: ['Priest', '海宴'], note: 'U6：女频必取 ≥2，防种子库全男频；Priest 经 trim 归并入池' },
  { axis: '科幻', pick: 2, authors: ['刘慈欣'], note: '每作者 ≤2，同书去重取信息密度高者' },
  { axis: '仙侠', pick: 2, authors: ['辰东', '耳根'] },
  { axis: '历史武侠/权谋', pick: 2, authors: ['猫腻', '烽火戏诸侯'] },
  { axis: '武侠经典', pick: 2, authors: ['金庸', '古龙'] },
  { axis: '都市诡异', pick: 1, authors: ['爱潜水的乌贼'] },
  { axis: '游戏电竞', pick: 1, authors: ['蝴蝶蓝'] },
  { axis: '悬疑', pick: 1, authors: ['紫金陈', '雷米'] },
  { axis: '历史向', pick: 1, authors: ['当年明月'] },
  { axis: '群像参考', pick: 1, authors: ['吹牛者'] },
];
const TARGET_CARDS = 15; // 12-16 区间；按轴覆盖恰为 15

// ── MySQL 只读 ────────────────────────────────────────────────────────────────

function readMysqlRows() {
  const env = process.env;
  if (!env.MYSQL_PWD) {
    console.error('FAIL 缺 MYSQL_PWD —— 先 export MYSQL_PWD=…（只读账号）再运行');
    process.exit(2);
  }
  const sql = 'SELECT id, author_name, book_source, narrative_drive, emotional_style, '
    + 'structure_preference, world_building_style, character_style, sentence_style, '
    + 'dialogue_style, signature_techniques, strengths, weaknesses, persona_prompt, quality_score '
    + 'FROM kb_author_personas ORDER BY id';
  const res = spawnSync('mysql', [
    '-B', '-h', env.MYSQL_HOST ?? '127.0.0.1', '-P', env.MYSQL_PORT ?? '3306',
    '-u', env.MYSQL_USER ?? 'root', env.MYSQL_DB ?? 'nwriter', '-e', sql,
  ], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env: { ...env } });
  if (res.error || res.status !== 0) {
    console.error(`FAIL mysql 读取失败: ${res.error?.message ?? res.stderr?.trim()}`);
    process.exit(2);
  }
  const lines = res.stdout.split('\n');
  const header = splitTsvLine(lines[0]);
  return lines.slice(1).filter((l) => l.length > 0).map((line) => {
    const cells = splitTsvLine(line);
    const row = {};
    header.forEach((h, i) => { row[h] = cells[i] === 'NULL' ? null : cells[i]; });
    return row;
  });
}

function splitTsvLine(line) {
  const cells = [];
  let cur = '';
  for (let i = 0; i < line.length; i++) {
    if (line[i] === '\\') {
      const nxt = line[i + 1];
      if (nxt === 'n') { cur += '\n'; i++; }        // 字段内换行（mysql -B 转义）
      else if (nxt === 't') { cur += '\t'; i++; }   // 字段内制表符
      else if (nxt === 'r') { cur += '\r'; i++; }
      else if (nxt === '0') { cur += '\0'; i++; }
      else if (nxt === '\\') { cur += '\\'; i++; }
      else { cur += line[i]; }
    } else if (line[i] === '\t') {
      cells.push(cur); cur = '';
    } else {
      cur += line[i];
    }
  }
  cells.push(cur);
  return cells;
}

// ── 归并 + 归一化 ─────────────────────────────────────────────────────────────

function normalizeAuthor(raw, mergeLog) {
  const trimmed = raw.trim();
  if (trimmed !== raw) mergeLog.trimHits.push({ raw });
  for (const rule of ALIAS_RULES) {
    if (new RegExp(rule.pattern).test(trimmed)) {
      mergeLog.aliasHits.push({ raw, to: rule.to, rule: rule.pattern });
      return rule.to;
    }
  }
  return trimmed;
}

function toList(text, fieldName, notes) {
  if (text === null || text === undefined || text === '') return [];
  const t = text.trim();
  if (t.startsWith('[')) {
    try {
      const arr = JSON.parse(t);
      if (Array.isArray(arr)) {
        notes.push(`${fieldName}: JSON 数组原样解析（${arr.length} 条）`);
        return arr.map((x) => String(x).trim()).filter(Boolean);
      }
    } catch { /* 落入分隔符拆分 */ }
  }
  const parts = t.split(/[,，、;；]+/).map((x) => x.trim()).filter(Boolean);
  if (parts.length > 1) notes.push(`${fieldName}: 分隔符串拆数组（${parts.length} 条）`);
  else notes.push(`${fieldName}: 单条文本保留为单元素数组`);
  return parts;
}

function unwrapScoreEnvelope(text, fieldName, notes) {
  if (text === null || text === undefined) return { text: '', score: null };
  const t = text.trim();
  if (t.startsWith('{')) {
    try {
      const obj = JSON.parse(t);
      if (obj && typeof obj.description === 'string') {
        notes.push(`${fieldName}: 剥 {"score":..,"description":..} 信封（原 score=${obj.score ?? '缺失'}）`);
        return { text: obj.description.trim(), score: obj.score ?? null };
      }
    } catch { /* 原样保留 */ }
  }
  return { text: t, score: null };
}

function buildSeedCard(row, mergeLog) {
  const notes = [];
  const authorRaw = row.author_name ?? '';
  const author = normalizeAuthor(authorRaw, mergeLog);
  if (authorRaw !== author) notes.push(`author_name 归并：${JSON.stringify(authorRaw)} → ${author}`);
  const nd = unwrapScoreEnvelope(row.narrative_drive, 'narrative_drive', notes);
  const card = {
    source_row_id: Number(row.id),
    author_raw: authorRaw,
    author,
    book_source: (row.book_source ?? '').trim(),
    quality_score: Number(row.quality_score),
    narrative_drive: nd.text,
    narrative_drive_score: nd.score,
    emotional_style: (row.emotional_style ?? '').trim(),
    structure_preference: (row.structure_preference ?? '').trim(),
    world_building_style: (row.world_building_style ?? '').trim(),
    character_style: (row.character_style ?? '').trim(),
    sentence_style: (row.sentence_style ?? '').trim(),
    dialogue_style: (row.dialogue_style ?? '').trim(),
    signature_techniques: toList(row.signature_techniques, 'signature_techniques', notes),
    strengths: toList(row.strengths, 'strengths', notes),
    weaknesses: toList(row.weaknesses, 'weaknesses', notes),
    seed_prompt: (row.persona_prompt ?? '').trim(),
    conversion_notes: notes,
  };
  if (notes.length === 0) notes.push('字段格式规整，仅 trim');
  return card;
}

// ── 选样 ──────────────────────────────────────────────────────────────────────

function selectCards(rows, mergeLog) {
  const pool = rows
    .map((r) => buildSeedCard(r, mergeLog))
    .filter((c) => c.quality_score >= 9);
  const weaknessesEmpty = pool.filter((c) => c.weaknesses.length === 0);
  const usable = pool.filter((c) => c.weaknesses.length > 0);

  // 组内排序（q 降序 → 信息密度降序 → id 升序），同作者同书去重取密度高者
  const byAuthor = new Map();
  for (const c of usable) {
    if (!byAuthor.has(c.author)) byAuthor.set(c.author, []);
    byAuthor.get(c.author).push(c);
  }
  const candidates = new Map();
  for (const [author, cards] of byAuthor) {
    cards.sort((a, b) => b.quality_score - a.quality_score
      || b.seed_prompt.length - a.seed_prompt.length
      || a.source_row_id - b.source_row_id);
    const seenBooks = new Set();
    const kept = [];
    for (const c of cards) {
      if (seenBooks.has(c.book_source)) {
        mergeLog.sameBookDropped.push({ author, book: c.book_source, dropped_id: c.source_row_id });
        continue;
      }
      seenBooks.add(c.book_source);
      kept.push(c);
    }
    candidates.set(author, kept);
  }

  const picked = [];
  const takenIds = new Set();
  const authorCount = new Map();
  const take = (c, axis, note) => {
    if (!c || takenIds.has(c.source_row_id) || (authorCount.get(c.author) ?? 0) >= 2) return false;
    takenIds.add(c.source_row_id);
    authorCount.set(c.author, (authorCount.get(c.author) ?? 0) + 1);
    picked.push({ ...c, axis, selection_note: note });
    return true;
  };

  for (const plan of AXIS_PLAN) {
    let got = 0;
    for (const author of plan.authors) {
      for (const c of candidates.get(author) ?? []) {
        if (got >= plan.pick) break;
        if (take(c, plan.axis, plan.note ?? '')) got++;
      }
      if (got >= plan.pick) break;
    }
    if (got < plan.pick) {
      mergeLog.axisShortfall.push({ axis: plan.axis, wanted: plan.pick, got, authors: plan.authors });
    }
  }

  // 兜底补足到 TARGET_CARDS（q → 密度序，同作者 ≤2 硬约束）
  const rest = usable.filter((c) => !takenIds.has(c.source_row_id))
    .sort((a, b) => b.quality_score - a.quality_score
      || b.seed_prompt.length - a.seed_prompt.length
      || a.source_row_id - b.source_row_id);
  for (const c of rest) {
    if (picked.length >= TARGET_CARDS) break;
    take(c, '补足', '按 q/信息密度补足至 15 卡，同作者 ≤2');
  }

  // 每作者溢出记录（同作者 >2 的其余行）
  for (const [author, cards] of candidates) {
    const overflow = cards.filter((c) => !takenIds.has(c.source_row_id));
    if (overflow.length > 0) mergeLog.authorOverflow.push({ author, not_selected_ids: overflow.map((c) => c.source_row_id) });
  }
  return { picked, poolSize: pool.length, weaknessesEmptyIds: weaknessesEmpty.map((c) => c.source_row_id) };
}

// ── 写库计划 / 事务 ───────────────────────────────────────────────────────────

const sha256Hex = (s) => crypto.createHash('sha256').update(s, 'utf8').digest('hex');

function buildWritePlan(cards) {
  return cards.map((card) => {
    const seedJson = JSON.stringify({
      seed_kind: 'style_seed',
      author: card.author,
      book_source: card.book_source,
      quality_score: card.quality_score,
      narrative_drive: card.narrative_drive,
      narrative_drive_score: card.narrative_drive_score,
      emotional_style: card.emotional_style,
      structure_preference: card.structure_preference,
      world_building_style: card.world_building_style,
      character_style: card.character_style,
      sentence_style: card.sentence_style,
      dialogue_style: card.dialogue_style,
      signature_techniques: card.signature_techniques,
      strengths: card.strengths,
      weaknesses: card.weaknesses,
      seed_prompt: card.seed_prompt,
      source: 'mysql:nwriter.kb_author_personas',
      source_row_id: card.source_row_id,
    }, null, 2);
    const provenance = JSON.stringify({
      type: 'styleseed_import_provenance',
      tool: 'scripts/novelos-import-personas.mjs',
      source: 'mysql:nwriter.kb_author_personas',
      source_row_id: card.source_row_id,
      imported_at: new Date().toISOString(),
      alias_merge: card.author_raw === card.author ? null : `${card.author_raw} → ${card.author}`,
      normalization_notes: card.conversion_notes,
      original_fields: card.original_row ?? null,
      note: '原表字段全文快照仅存库（data/*.db 已 gitignore）；personas 原文禁入 git（裁-5/U12）',
    }, null, 2);
    return {
      axis: card.axis,
      display_name: `${card.author}·${card.book_source}风格卡`,
      seedResourceId: `resource:${crypto.randomUUID()}`,
      derivResourceId: `resource:${crypto.randomUUID()}`,
      profileId: `creator-profile:${crypto.randomUUID()}`,
      versionId: `creator-profile-version:${crypto.randomUUID()}`,
      seedContent: seedJson,
      seedHash: `sha256:${sha256Hex(seedJson)}`,
      derivContent: provenance,
      derivHash: `sha256:${sha256Hex(provenance)}`,
      original_author: card.author,
      book: card.book_source,
      quality: card.quality_score,
    };
  });
}

function guardTargetDb(dbPath) {
  if (!COMMIT) return;
  const allowProd = process.argv.includes('--allow-production'); // R5 执行轮（U5/U6 已裁决）：显式放行生产库，默认仍拒绝
  if (!TARGET_DB || TARGET_DB === 'undefined') {
    console.error('REFUSE --commit 须显式 --db 指向副本库（生产库零写入红线）');
    process.exit(1);
  }
  if (!fs.existsSync(TARGET_DB)) {
    console.error(`REFUSE 目标库不存在: ${TARGET_DB} —— --commit 只允许对既有副本库执行`);
    process.exit(1);
  }
  if (TARGET_DB === path.resolve(PROD_DB) && !allowProd) {
    console.error('REFUSE 目标库是生产库 data/novelos-v2.db —— 生产库零写入（硬编码保护；U5/U6 已裁决后加 --allow-production 显式放行）');
    process.exit(1);
  }
  if (TARGET_DB === path.resolve(PROD_DB) && !fs.existsSync(path.join(path.dirname(TARGET_DB), '.allow-production-r5'))) {
    console.error('REFUSE --allow-production 需要现场凭据：先执行 touch data/.allow-production-r5（裁决留痕，导入后删除）');
    process.exit(1);
  }
}

function assertSeedReady(db) {
  const ddl = db.prepare("SELECT sql FROM sqlite_master WHERE type='table' AND name='creator_profiles'").get()?.sql ?? '';
  if (!ddl.includes("'style_seed'")) {
    console.error('REFUSE 目标库 creator_profiles.ownership CHECK 不含 \'style_seed\' —— 先在副本应用 db/migrations/020_creator_profiles_style_seed.sql');
    process.exit(1);
  }
  const existing = db.prepare("SELECT COUNT(*) n FROM creator_profiles WHERE ownership='style_seed'").get().n;
  if (existing > 0) {
    console.error(`REFUSE 目标库已有 ${existing} 行 style_seed —— 重复导入拒绝（清理步骤见 tasks/r5-plans/u5-u7-signature-package.md 回滚节）`);
    process.exit(1);
  }
}

function commit(plan, dbPath) {
  guardTargetDb(dbPath);
  const db = new DatabaseSync(dbPath);
  assertSeedReady(db);
  db.exec('PRAGMA foreign_keys = ON');
  db.exec('BEGIN IMMEDIATE');
  try {
    const insRes = db.prepare("INSERT INTO resources (id, media_type, content, content_hash) VALUES (?, 'application/json', CAST(? AS BLOB), ?)");
    const insProfile = db.prepare("INSERT INTO creator_profiles (id, display_name, status, version, ownership) VALUES (?, ?, 'active', 1, 'style_seed')");
    const insVersion = db.prepare("INSERT INTO creator_profile_versions (id, profile_id, revision, content_resource_id, subject_hash, parent_version_id, derivation_resource_id) VALUES (?, ?, 1, ?, ?, NULL, ?)");
    for (const row of plan) {
      insRes.run(row.seedResourceId, row.seedContent, row.seedHash);
      insRes.run(row.derivResourceId, row.derivContent, row.derivHash);
      insProfile.run(row.profileId, row.display_name);
      insVersion.run(row.versionId, row.profileId, row.seedResourceId, row.seedHash, row.derivResourceId);
    }
    db.exec('COMMIT');
  } catch (err) {
    db.exec('ROLLBACK');
    db.close();
    console.error(`FAIL 事务回滚零写入: ${err.message}`);
    process.exit(1);
  }
  // 落库后自证：行数 + content_hash 重算抽查
  const cnt = db.prepare("SELECT COUNT(*) n FROM creator_profiles WHERE ownership='style_seed'").get().n;
  const verCnt = db.prepare("SELECT COUNT(*) n FROM creator_profile_versions v JOIN creator_profiles cp ON cp.id=v.profile_id WHERE cp.ownership='style_seed'").get().n;
  console.log(`COMMIT OK ${dbPath} —— creator_profiles.style_seed=${cnt} 行, 关联 versions=${verCnt} 行`);
  const sample = db.prepare("SELECT v.id, v.subject_hash, CAST(r.content AS TEXT) c FROM creator_profile_versions v JOIN resources r ON r.id=v.content_resource_id JOIN creator_profiles cp ON cp.id=v.profile_id WHERE cp.ownership='style_seed' LIMIT 3").all();
  for (const s of sample) {
    const rehash = `sha256:${sha256Hex(s.c)}`;
    console.log(`  verify ${s.id} content_hash ${rehash === s.subject_hash ? 'OK' : 'MISMATCH'}`);
    if (rehash !== s.subject_hash) process.exitCode = 1;
  }
  db.close();
}

// ── 产物落盘 ──────────────────────────────────────────────────────────────────

function writeAliasMap(mergeLog) {
  const doc = {
    version: 1,
    generated_by: 'scripts/novelos-import-personas.mjs 内置归并规则投影（每次运行重写，勿手改）',
    updated: new Date().toISOString().slice(0, 10),
    note: 'author_name 归并裁决材料（U6）。匹配在 trim 之后按序进行；无法机械归并的变体呈报用户裁决（红方 F5）。同一作者多行但字符串相同（实测 17 组）不属别名归并，由「同作者 ≤2」选样纪律处理',
    trim: { note: TRIM_NOTE },
    rules: ALIAS_RULES,
    stats: {
      alias_hits: mergeLog.aliasHits.length,
      trim_hits: mergeLog.trimHits.length,
      same_book_dropped: mergeLog.sameBookDropped.length,
    },
  };
  fs.writeFileSync(ALIAS_OUT, `${JSON.stringify(doc, null, 2)}\n`);
}

function writePilot(cards, stats) {
  fs.mkdirSync(path.dirname(PILOT_OUT), { recursive: true });
  const doc = {
    generated_at: new Date().toISOString(),
    source: 'mysql:nwriter.kb_author_personas（只读）',
    channel: '裁-5：MySQL 直连导入试点；原文只落 data/（gitignore）',
    selection_rules: {
      pool: 'quality_score >= 9',
      per_author_max: 2,
      female_channel_min: 2,
      weaknesses_nonempty: true,
      target_cards: TARGET_CARDS,
      axes: AXIS_PLAN,
    },
    stats,
    cards,
  };
  fs.writeFileSync(PILOT_OUT, `${JSON.stringify(doc, null, 2)}\n`);
}

// ── 主流程 ────────────────────────────────────────────────────────────────────

let picked = [];
let poolSize = 0;
let weaknessesEmptyIds = [];
const mergeLog = { trimHits: [], aliasHits: [], sameBookDropped: [], axisShortfall: [], authorOverflow: [] };

if (!process.env.MYSQL_PWD && fs.existsSync(PILOT_OUT)) {
  console.log(`未设置 MYSQL_PWD，直接读取已有试点文件: ${PILOT_OUT}`);
  const pilotData = JSON.parse(fs.readFileSync(PILOT_OUT, 'utf8'));
  picked = pilotData.cards || [];
  poolSize = pilotData.stats?.pool_q9 ?? picked.length;
} else {
  console.log('读 MySQL kb_author_personas（只读）…');
  const rows = readMysqlRows();
  console.log(`  全表 ${rows.length} 行 / ${new Set(rows.map((r) => (r.author_name ?? '').trim())).size} 作者（trim 后）`);
  const sel = selectCards(rows, mergeLog);
  picked = sel.picked;
  poolSize = sel.poolSize;
  weaknessesEmptyIds = sel.weaknessesEmptyIds;
  writeAliasMap(mergeLog);
  writePilot(picked, {
    total_rows: rows.length,
    pool_q9: poolSize,
    selected: picked.length,
    female_channel: picked.filter((c) => c.axis === '女频（必取）').length,
    alias_map: ALIAS_RULES.map((r) => `${r.pattern}→${r.to}`),
    merge_log: mergeLog,
  });
  console.log(`\npilot JSON → ${PILOT_OUT}（gitignore）`);
  console.log(`alias map  → ${ALIAS_OUT}（入 git 裁决材料）`);
}

const femaleCount = picked.filter((c) => c.axis === '女频（必取）').length;
const rowPlan = buildWritePlan(picked);
console.log(`  q≥9 池 ${poolSize} 条；weaknesses 空排除 ${weaknessesEmptyIds.length} 条（id: ${weaknessesEmptyIds.join(', ') || '无'}）`);
console.log(`\n选样 ${picked.length} 卡（女频 ${femaleCount}）：`);
for (const c of picked) {
  console.log(`  [${c.axis}] ${c.author}·《${c.book_source}》 q=${c.quality_score} src_id=${c.source_row_id} weaknesses=${c.weaknesses?.length ?? 0}条`);
}
if (mergeLog.axisShortfall.length > 0) {
  console.log(`⚠ 轴缺口: ${JSON.stringify(mergeLog.axisShortfall)}`);
}
console.log(`\n将写行数：${rowPlan.length} 卡 × 4 行 = ${rowPlan.length * 4}（resources ${rowPlan.length * 2} / creator_profiles ${rowPlan.length} / creator_profile_versions ${rowPlan.length}）`);
for (const r of rowPlan) {
  console.log(`  ${r.display_name}`);
  console.log(`    resource:${r.seedResourceId.slice('resource:'.length, 14)}… seed   hash=${r.seedHash.slice(0, 19)}…`);
  console.log(`    resource:${r.derivResourceId.slice('resource:'.length, 14)}… provenance hash=${r.derivHash.slice(0, 19)}…`);
  console.log(`    ${r.profileId.slice(0, 40)}… (ownership='style_seed')`);
  console.log(`    ${r.versionId.slice(0, 46)}… (revision=1, parent=NULL)`);
}

if (COMMIT) {
  commit(rowPlan, TARGET_DB);
} else {
  console.log('DRY-RUN 未写任何数据库（--commit --db <副本库路径> 才写；生产库路径被硬编码拒绝）');
}
