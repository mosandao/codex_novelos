#!/usr/bin/env node
/**
 * novelos-gate · harness 中立 CLI 写门（R7-T3，修正案 A2）。
 *
 * 背景：R2 建成并验证的 defineTool 写门（159 用例全绿）随插件退役一并删除后，
 * 机器强制层降级为主控自查（对抗审查 P1-5/P3-7 成立判）。本文件以 harness 中立
 * CLI 形态复活门语义：FAIL 即 GateFail 阻断 + 零写入，不依赖任何插件/host。
 * 规格来源：docs/r2-js-gate-spec.md（考古）+ git 历史 9e80bb7/27d34a4/da9ee5c
 * （propagate-stale.ts / register-characters.ts 逐段移植）+ tasks/README.md WP5
 * 记账（状态机语义）+ 8af69a8^ 的 legacy-python 七件校验器（常量/阈值逐字）。
 *
 * 已声明偏离（零 npm 纪律）：
 * - validate-asset 的 jsonschema 结构层 → 手写必需字段检查（REQUIRED_FIELDS）；
 *   语义门（数字/枚举/对账规则）逐字移植，红队 F2 红线不变：FAIL 阻断零写入。
 * - register-characters 的 ajv roster 校验 → 手写结构规则（name/role_class/登场卷/预期退场）。
 * - WP5 的 state-machine.ts 从未入库（记账 DONE 而代码消失，P2-5 行为证据）——
 *   本文件按其记账语义重写：封跳审/封错绑、旧 locked 翻 superseded、幂等重放仅限
 *   hash 未变、accept 必写 chapters.review_id。
 *
 * 安全模型：dry-run 默认（只报告零写入）；写库须 --commit；对默认生产库路径
 * （data/novelos-v2.db）--commit 还须 --allow-production。写路径单事务
 * BEGIN IMMEDIATE + foreign_keys=ON，任一步失败整体回滚。
 *
 * 用法（node scripts/novelos-gate.mjs <子命令> …）：
 *   lock-asset      --asset <planning:id> --review <review:id> [--commit]
 *   accept-chapter  --chapter <chapter:id> --review <review:id> [--commit]
 *   commit-review   --receipt <file|内联JSON> [--allow-empty] [--no-check-hash] [--commit]
 *   propagate-stale --asset <planning:id> [--fine] [--commit]
 *   validate-asset  (--asset <planning:id> | --asset-type <t> --project <id> [--scope-ref <r>]) [--scale <s>]
 *   register-characters --project <id> [--roster <json>] [--entry <json>] [--status-update <json>] [--world <json>] [--commit]
 *   通用：[--db <路径>]（默认 data/novelos-v2.db）[--json]
 * exit：0 = 通过；1 = GateFail（阻断，零写入）；2 = 用法/输入错误。
 */

import { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { contentHash, pyJsonDumps } from './novelos-compose-prompt.mjs';
import { loadReceipt, checkFindings, normalizeForMatch } from './novelos-verify-review-evidence.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROG = 'novelos-gate';
const VERSION = '1.0.0';
const DEFAULT_DB = path.join(ROOT, 'data/novelos-v2.db');

export class GateFail extends Error {}
export class UsageError extends Error {}

// ── 常量（legacy-python / 旧 TS 逐字） ──────────────────────────────────────

/** 人物状态六值（characters.status CHECK 同源） */
export const STATUS_VALUES = ['active', 'peripheral', 'dormant', 'departed', 'transformed', 'dead'];
/** 退场八型（第七型死亡型为 dead 专用） */
export const EXIT_TYPES = ['完成型', '迁移型', '转化型', '关系型', '功能转移型', '休眠型', '死亡型'];
/** 携带退场痕迹的状态子集 */
export const EXIT_STATUSES = ['departed', 'transformed', 'dormant', 'dead'];

// scale 档位前缀 → 各数字门区间（story-direction 规模表同源；None 上限 = 不设上限）
const SCALE_CADENCE_RULES = { '短篇': [1, 2], '中篇': [3, null], '长篇': [3, null], '超长篇': [5, null] };
const SCALE_ENGINE_RULES = { '短篇': [2, 1], '中篇': [3, 2], '长篇': [3, 3], '超长篇': [5, 4] }; // [油耗下限, 空窗上限卷]
const SCALE_STAGE_RULES = { '短篇': [1, 2], '中篇': [2, 4], '长篇': [3, 8], '超长篇': [5, 12] };
const SCALE_ROSTER_RULES = { '短篇': [2, 5], '中篇': [3, 8], '长篇': [5, 12], '超长篇': [8, 16] };
const SCALE_ARC_RULES = { '短篇': [1, 2], '中篇': [2, 3], '长篇': [3, 5], '超长篇': [5, 7] };
const TIER_BEATS_RULES = { '高': [1.0, 6.0], '中': [0.5, 1.0], '低': [0.0, 0.5] }; // 高档上限含
const CONSUMPTION_OUTPUTS = new Set(['rhythm_table', 'reveal_ladder', 'promise_cadence', 'power_escalation', 'spiral_rotation', 'engine_config', 'upstream_receipts']);
const ACTIVE_DUTIES = new Set(['推进', '兑现', '收束']);
const SLUG_RE = /^[a-z][a-z0-9_]{1,39}$/;
const CLIMAX_GAP_WORDS = 300_000;   // 相邻高潮间距上限（字）
const CLIMAX_UNIT_WORDS = 250_000;  // 高潮密度基准（字/个）
const REVIEWER_PROFILE_RE = /^(model|agent):.+/;

// ── 基础设施 ────────────────────────────────────────────────────────────────

export function newId(kind) {
  return `${kind}:${randomUUID()}`;
}

/** py: _norm_name —— NFKC + 去全部空白 + 折叠大小写 */
export function normName(name) {
  return String(name ?? '').normalize('NFKC').replace(/\s+/gu, '').toLowerCase();
}

/** characters.state_json 容错解析（py `json.loads(x or "{}")`；损坏按 {} 兜底） */
export function parseStateJson(text) {
  try {
    const v = JSON.parse(text || '{}');
    return typeof v === 'object' && v !== null && !Array.isArray(v) ? v : {};
  } catch {
    return {};
  }
}

/** py datetime.now() 本地时间状态史审计戳 */
export function nowStamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** py 紧凑串（", " / ": " 分隔符，键序保留）——state_json/findings_json 落库形态 */
export function pyCompact(obj) {
  return pyJsonDumps(obj);
}

function matchScale(scale) {
  for (const prefix of Object.keys(SCALE_CADENCE_RULES)) {
    if (scale.startsWith(prefix)) return prefix;
  }
  return null;
}

/** 单写事务：BEGIN IMMEDIATE → fn → COMMIT；异常 ROLLBACK，非 GateFail 错误统一包成 GateFail */
export function withTransaction(conn, fn) {
  conn.exec('PRAGMA foreign_keys = ON');
  conn.exec('BEGIN IMMEDIATE');
  try {
    const out = fn();
    conn.exec('COMMIT');
    return out;
  } catch (e) {
    try { conn.exec('ROLLBACK'); } catch { /* 已回滚 */ }
    if (e instanceof GateFail) throw e;
    throw new GateFail(`事务失败已回滚：${e instanceof Error ? e.message : String(e)}`);
  }
}

function openDb(dbPath) {
  try {
    return new DatabaseSync(dbPath);
  } catch (e) {
    throw new UsageError(`库打不开：${dbPath}（${e.message}）`);
  }
}

// ── 库内解析（validate-asset 自动装配） ─────────────────────────────────────

/** setup.scale 完整标签 → 档位前缀（如「超长篇（300万字以上）」→ 超长篇）；查不到返回 null */
function resolveProjectScale(conn, projectId) {
  const row = conn.prepare('SELECT metadata_json FROM projects WHERE id = ?').get(projectId);
  if (!row) throw new GateFail(`项目不存在: ${projectId}`);
  try {
    const setup = (JSON.parse(row.metadata_json || '{}') || {}).setup || {};
    const raw = setup.scale;
    return typeof raw === 'string' && raw ? raw.split('（')[0].trim() : null;
  } catch {
    return null;
  }
}

/** locked 上游 metadata（同 project 最新 revision；查不到返回 null，不硬失败） */
function lockedUpstreamMetadata(conn, projectId, assetType) {
  const row = conn.prepare(
    "SELECT metadata_json FROM planning_assets WHERE project_id = ? AND asset_type = ? "
    + "AND status = 'locked' ORDER BY revision DESC LIMIT 1",
  ).get(projectId, assetType);
  if (!row) return null;
  try {
    return JSON.parse(row.metadata_json || '{}');
  } catch {
    return null;
  }
}

// ── 子命令 1：propagate-stale（27d34a4 propagate-stale.ts 逐段移植） ────────

/** BFS 递归依赖图，收集所有下游（直接+间接）locked 资产 */
export function collectDownstream(conn, assetId) {
  const result = [];
  const seen = new Set();
  const queue = [assetId];
  while (queue.length) {
    const current = queue.shift();
    const rows = conn.prepare(`
      SELECT pa.id, pa.project_id, pa.asset_type, pa.scope_ref, pa.status
      FROM planning_asset_dependencies pad
      JOIN planning_assets pa ON pa.id = pad.asset_id
      WHERE pad.upstream_asset_id = ? AND pa.status = 'locked'
    `).all(current);
    for (const row of rows) {
      if (seen.has(row.id)) continue;
      seen.add(row.id);
      result.push(row);
      queue.push(row.id);
    }
  }
  return result;
}

/** fine 模式：直接下游按「依赖边 upstream_version + content_hash 双重比对」分类（机械，无 LLM） */
export function classifyFine(conn, upstreamId) {
  const scopeRow = conn.prepare(
    'SELECT project_id, asset_type, scope_ref FROM planning_assets WHERE id = ?',
  ).get(upstreamId);
  if (!scopeRow) return [];
  const { project_id: pid, asset_type: atype, scope_ref: scope } = scopeRow;

  const revHash = (revision) => {
    const row = conn.prepare(
      'SELECT r.content_hash FROM planning_assets pa JOIN resources r ON r.id = pa.content_resource_id '
      + 'WHERE pa.project_id = ? AND pa.asset_type = ? AND pa.scope_ref = ? AND pa.revision = ?',
    ).get(pid, atype, scope, revision);
    return row?.content_hash ?? null;
  };
  const current = conn.prepare(
    "SELECT revision FROM planning_assets WHERE project_id = ? AND asset_type = ? "
    + "AND scope_ref = ? AND status = 'locked' ORDER BY revision DESC LIMIT 1",
  ).get(pid, atype, scope);
  if (!current) return [];
  const m = Number(current.revision);
  const hM = revHash(m);

  const rows = conn.prepare(
    "SELECT pa.id, pa.asset_type, pa.scope_ref, pa.status, pad.upstream_version "
    + "FROM planning_asset_dependencies pad JOIN planning_assets pa ON pa.id = pad.asset_id "
    + "WHERE pad.upstream_asset_id = ? AND pa.status = 'locked'",
  ).all(upstreamId);

  return rows.map((row) => {
    const base = { id: String(row.id), asset_type: String(row.asset_type), scope_ref: String(row.scope_ref), verdict: 'stale', reason: '' };
    const v = Number(row.upstream_version);
    if (v === m) return { ...base, verdict: 'neutral', reason: `依赖边已对齐 rev ${m}` };
    const hV = revHash(v);
    if (hM !== null && hV === hM) return { ...base, verdict: 'neutral', reason: `rev ${v} 与 rev ${m} content_hash 相同（内容未变）` };
    return { ...base, verdict: 'stale', reason: `依赖 rev ${v}，当前 rev ${m} 且内容已变` };
  });
}

/**
 * 传播 stale。dryRun 只报告；否则单事务批量 UPDATE，任一步失败回滚抛 GateFail。
 * coarse（默认）：直接+间接全部下游 locked 全量标；fine：内容未变不误伤，
 * 间接下游只列 indirectPending 不自动标（保守正确）。
 */
export function propagateStale(conn, assetId, { fine = false, dryRun = true } = {}) {
  const upstream = conn.prepare('SELECT id, asset_type, status FROM planning_assets WHERE id = ?').get(assetId);
  if (!upstream) throw new GateFail(`资产不存在: ${assetId}`);

  const markStale = (ids) => {
    try {
      conn.exec('BEGIN IMMEDIATE');
      const stmt = conn.prepare("UPDATE planning_assets SET status='stale', updated_at=CURRENT_TIMESTAMP WHERE id=?");
      for (const id of ids) stmt.run(id);
      conn.exec('COMMIT');
    } catch (e) {
      try { conn.exec('ROLLBACK'); } catch { /* 已回滚 */ }
      throw new GateFail(`stale 传播事务失败已回滚：${e instanceof Error ? e.message : String(e)}`);
    }
  };

  if (fine) {
    const classified = classifyFine(conn, assetId);
    const stale = classified.filter((c) => c.verdict === 'stale');
    const indirectIds = new Set(collectDownstream(conn, assetId).map((d) => d.id));
    for (const c of classified) indirectIds.delete(c.id);
    if (!dryRun && stale.length) markStale(stale.map((c) => c.id));
    return {
      upstream, mode: 'fine', dryRun, marked: stale.length,
      neutral: classified.length - stale.length,
      classification: classified, indirectPending: [...indirectIds].sort(),
    };
  }

  const downstream = collectDownstream(conn, assetId);
  if (!dryRun && downstream.length) markStale(downstream.map((d) => d.id));
  return {
    upstream, mode: 'coarse', dryRun, marked: downstream.length, neutral: 0,
    markedAssets: downstream.map(({ id, asset_type, scope_ref }) => ({ id, asset_type, scope_ref })),
  };
}

// ── 子命令 2：register-characters（da9ee5c 逐段移植，roster 校验手写偏离声明） ─

/** py: _validate_entries —— 动态配角条目手写校验（name/role_class/预期退场/来源卷） */
export function validateEntries(entries) {
  const errors = [];
  entries.forEach((e, i) => {
    const name = e?.name;
    if (typeof name !== 'string' || !name.trim()) errors.push(`entry[${i}]: name 非空必填`);
    const rc = e?.role_class ?? 'secondary';
    if (!(rc === 'minor' || rc === 'secondary' || rc === 'main')) {
      errors.push(`entry[${i}]: role_class 非法 ${JSON.stringify(rc)}`);
    }
    const et = e?.['预期退场'];
    if (et != null && !EXIT_TYPES.includes(et) && et !== '持续活跃') {
      errors.push(`entry[${i}]: 预期退场非法 ${JSON.stringify(et)}（${EXIT_TYPES.join(', ')} 或 持续活跃）`);
    }
    const vol = e?.['来源卷'];
    if (vol != null && !(typeof vol === 'number' && Number.isInteger(vol) && 1 <= vol && vol <= 99)) {
      errors.push(`entry[${i}]: 来源卷须为 1-99 整数，got ${JSON.stringify(vol)}`);
    }
  });
  return errors;
}

/**
 * py: _validate_status_update —— status 非法即短路返回；
 * dead 必须带 死亡型；非退场状态不得携带 exit_type（复活会整体清空退场痕迹）。
 */
export function validateStatusUpdate(update) {
  const errors = [];
  const name = update?.name;
  if (typeof name !== 'string' || !name.trim()) errors.push('status-update: name 非空必填');
  const status = update?.status;
  if (!STATUS_VALUES.includes(status)) {
    errors.push(`status-update: status 非法 ${JSON.stringify(status)}（${STATUS_VALUES.join(', ')}）`);
    return errors; // 与 py 相同：status 非法时短路
  }
  const et = update?.exit_type;
  if (et != null && !EXIT_TYPES.includes(et)) {
    errors.push(`status-update: exit_type 非法 ${JSON.stringify(et)}（${EXIT_TYPES.join(', ')}）`);
  }
  if (status === 'dead' && et !== '死亡型') errors.push('status-update: status=dead 时 exit_type 必须为 死亡型');
  if (!EXIT_STATUSES.includes(status) && et != null) {
    errors.push(`status-update: status=${JSON.stringify(status)} 是非退场状态，不应携带 exit_type（复活/回归会整体清空退场痕迹）`);
  }
  return errors;
}

/** py/旧 TS: _validate_roster —— 手写结构规则（ajv 偏离声明见文件头） */
export function validateRoster(roster) {
  const errors = [];
  if (!Array.isArray(roster)) return ['roster: 须为数组'];
  roster.forEach((item, i) => {
    const name = item?.name;
    if (typeof name !== 'string' || !name.trim()) errors.push(`roster[${i}]: name 非空必填`);
    const rc = item?.role_class;
    if (!(rc === 'main' || rc === 'secondary')) {
      errors.push(`roster[${i}]: role_class 非法 ${JSON.stringify(rc)}（roster 仅 main/secondary）`);
    }
    if (typeof item?.arc_role !== 'string' || !item.arc_role.trim()) errors.push(`roster[${i}]: arc_role 非空必填`);
    const vol = item?.['登场卷'];
    if (!(typeof vol === 'number' && Number.isInteger(vol) && 1 <= vol && vol <= 99)) {
      errors.push(`roster[${i}]: 登场卷须为 1-99 整数，got ${JSON.stringify(vol)}`);
    }
    const et = item?.['预期退场'];
    if (typeof et !== 'string' || !et.trim()) errors.push(`roster[${i}]: 预期退场 非空必填`);
  });
  return errors;
}

/** py: _near_dup_warns —— 归一化撞名 WARN（原始名不同才算，完全同名走幂等合并） */
export function nearDupWarns(conn, projectId, incoming) {
  const warns = [];
  const existing = new Map();
  for (const r of conn.prepare('SELECT name FROM characters WHERE project_id = ?').all(projectId)) {
    existing.set(normName(r.name), r.name);
  }
  const batch = new Map();
  for (const item of incoming) {
    const raw = String(item?.name ?? '');
    const norm = normName(raw);
    if (!norm) continue;
    const hit = existing.get(norm);
    if (hit !== undefined && hit !== raw) {
      warns.push(`WARN 近重名：${JSON.stringify(raw)} 与在库人物 ${JSON.stringify(hit)} 归一化后相同（全半角/空白/大小写）——确认是否笔误`);
    } else if (batch.has(norm) && batch.get(norm) !== raw) {
      warns.push(`WARN 批内近重名：${JSON.stringify(raw)} 与 ${JSON.stringify(batch.get(norm))} 归一化后相同——确认是否笔误`);
    }
    if (!batch.has(norm)) batch.set(norm, raw);
  }
  return warns;
}

/** py: _upsert —— 幂等登记：新建 active；已存在只合并 role_class 与 state_json 补充字段，
 *  first_chapter_id 仅在新值非空时回填（COALESCE），不触碰 status/exit 字段。 */
export function upsertCharacter(conn, projectId, name, roleClass, statePatch, firstChapterId = null) {
  const existing = conn.prepare(
    'SELECT id, state_json FROM characters WHERE project_id = ? AND name = ?',
  ).get(projectId, name);
  if (existing === undefined) {
    const charId = newId('character');
    conn.prepare(
      "INSERT INTO characters (id, project_id, name, role_class, status, state_json, first_chapter_id) "
      + "VALUES (?, ?, ?, ?, 'active', ?, ?)",
    ).run(charId, projectId, name, roleClass, pyCompact(statePatch), firstChapterId);
    return charId;
  }
  const state = parseStateJson(existing.state_json);
  Object.assign(state, statePatch);
  conn.prepare(
    'UPDATE characters SET role_class = ?, state_json = ?, '
    + "first_chapter_id = COALESCE(?, first_chapter_id), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
  ).run(roleClass, pyCompact(state), firstChapterId, existing.id);
  return existing.id;
}

/** py: _apply_status_update —— 状态史审计追加 + 退场痕迹对称维护；未登记按 minor 补建 */
export function applyStatusUpdate(conn, projectId, upd) {
  const row = conn.prepare(
    'SELECT id, status, exit_type, state_json FROM characters WHERE project_id = ? AND name = ?',
  ).get(projectId, upd.name);
  let charId; let oldStatus; let state;
  if (row === undefined) {
    charId = upsertCharacter(conn, projectId, upd.name, 'minor', { '补登': '连续性状态迁移先于登记' }, upd.exit_chapter_id ?? null);
    oldStatus = 'active';
    state = { '补登': '连续性状态迁移先于登记' };
  } else {
    charId = row.id;
    oldStatus = row.status;
    state = parseStateJson(row.state_json);
  }
  const history = Array.isArray(state['状态史']) ? state['状态史'] : [];
  history.push({
    from: oldStatus, to: upd.status, exit_type: upd.exit_type ?? null,
    chapter_id: upd.exit_chapter_id ?? null, at: nowStamp(),
  });
  state['状态史'] = history;
  const stateJson = pyCompact(state);
  if (EXIT_STATUSES.includes(upd.status)) {
    conn.prepare(
      'UPDATE characters SET status = ?, exit_type = ?, exit_chapter_id = COALESCE(?, exit_chapter_id), '
      + 'state_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
    ).run(upd.status, upd.exit_type ?? null, upd.exit_chapter_id ?? null, stateJson, charId);
  } else {
    // 复活/回归：退场痕迹整体清空，不留半截记录
    conn.prepare(
      'UPDATE characters SET status = ?, exit_type = NULL, exit_chapter_id = NULL, '
      + 'state_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
    ).run(upd.status, stateJson, charId);
  }
  return `status ${upd.name} ${oldStatus} -> ${upd.status}`;
}

/** register-characters 主入口：预检 → BEGIN IMMEDIATE 单事务 → COMMIT/ROLLBACK */
export function registerCharactersRun(conn, input) {
  const projectId = input.projectId;
  const proj = conn.prepare('SELECT id FROM projects WHERE id = ?').get(projectId);
  if (proj === undefined) throw new GateFail(`项目不存在: ${projectId}`);

  const norm = (v) => (v == null ? null : Array.isArray(v) ? [...v] : [v]);
  const updates = norm(input.statusUpdate);
  const entryList = norm(input.entries);
  const rosterList = Array.isArray(input.roster) ? input.roster : null;
  if (rosterList == null && entryList == null && updates == null) {
    throw new UsageError('至少提供 roster / entry / statusUpdate 之一');
  }

  const warns = [];
  const errors = [];
  const incoming = [...(rosterList ?? []), ...(entryList ?? [])];
  warns.push(...nearDupWarns(conn, projectId, incoming));

  if (input.world != null && incoming.length > 0) {
    // 席位对账（F2 阻断类：seat_ref 引用不存在席位）
    const seats = Array.isArray(input.world.seats) ? input.world.seats : [];
    const seatNames = new Set(seats.filter((s) => s?.name).map((s) => String(s.name)));
    for (const item of incoming) {
      if (item?.seat_ref && !seatNames.has(String(item.seat_ref))) {
        errors.push(`${item?.name ?? '?'}: seat_ref 引用不存在的席位: ${JSON.stringify(item.seat_ref)}`);
      }
    }
    const claimed = new Set();
    for (const r of conn.prepare('SELECT state_json FROM characters WHERE project_id = ?').all(projectId)) {
      const ref = parseStateJson(r.state_json)?.seat_ref;
      if (ref) claimed.add(String(ref));
    }
    for (const item of incoming) if (item?.seat_ref) claimed.add(String(item.seat_ref));
    for (const s of seats) {
      if (s?.name && (s.disposition === '待契约认领' || s.disposition === '待卷级班底') && !claimed.has(String(s.name))) {
        warns.push(`WARN 席位「${s.name}」world 标注「${s.disposition}」但注册表尚无认领人`);
      }
    }
  }

  if (rosterList != null) errors.push(...validateRoster(rosterList));
  if (entryList != null) errors.push(...validateEntries(entryList));
  if (updates != null) for (const upd of updates) errors.push(...validateStatusUpdate(upd));
  if (errors.length > 0) {
    throw new GateFail(
      `人物登记校验未通过（${errors.length} 处 FAIL，未开事务零写入）：\n`
      + errors.map((e) => `FAIL ${e}`).join('\n'),
    );
  }

  const results = [];
  withTransaction(conn, () => {
    for (const item of rosterList ?? []) {
      const patch = { 'arc_role': item.arc_role, '预期退场': item['预期退场'], '登场卷': item['登场卷'] };
      for (const extra of ['seat_ref', 'essence']) if (item[extra]) patch[extra] = item[extra];
      const charId = upsertCharacter(conn, projectId, item.name, item.role_class, patch);
      results.push(`roster ${item.name} -> ${charId}`);
    }
    for (const item of entryList ?? []) {
      const patch = Object.fromEntries(Object.entries(item).filter(([k]) => k !== 'name' && k !== 'role_class'));
      const charId = upsertCharacter(conn, projectId, item.name, item.role_class ?? 'secondary', patch, item.first_chapter_id ?? null);
      results.push(`entry ${item.name} -> ${charId}`);
    }
    for (const upd of updates ?? []) results.push(applyStatusUpdate(conn, projectId, upd));
  });
  return { results, warns };
}

// ── 子命令 3：commit-review（WP5 commitReview 语义 + A1/P4-2 关口） ──────────

function loadSubject(conn, subjectRef) {
  if (typeof subjectRef === 'string' && subjectRef.startsWith('chapter:')) {
    const row = conn.prepare(
      'SELECT c.id, c.status, c.review_id, CAST(r.content AS TEXT) AS content, r.content_hash '
      + 'FROM chapters c JOIN resources r ON r.id = c.content_resource_id WHERE c.id = ?',
    ).get(subjectRef);
    if (!row) throw new GateFail(`subject 不存在: ${subjectRef}`);
    return { kind: 'chapter', row, content: row.content ?? '', contentHash: row.content_hash };
  }
  if (typeof subjectRef === 'string' && subjectRef.startsWith('planning:')) {
    const row = conn.prepare(
      'SELECT pa.id, pa.status, pa.locked_review_id, pa.version, CAST(r.content AS TEXT) AS content, r.content_hash '
      + 'FROM planning_assets pa JOIN resources r ON r.id = pa.content_resource_id WHERE pa.id = ?',
    ).get(subjectRef);
    if (!row) throw new GateFail(`subject 不存在: ${subjectRef}`);
    return { kind: 'planning', row, content: row.content ?? '', contentHash: row.content_hash };
  }
  throw new GateFail(`不支持的 subject_ref 形态: ${JSON.stringify(subjectRef)}（R7 门支持 chapter:*/planning:*）`);
}

/**
 * 回执落库门：reviewer_profile 前缀强校验（P4-2）→ subject 存在 → subject_hash 绑定
 * → G2 引文验证 in-process（finding 级 no_hit/missing FATAL；空 findings+approved 默认
 * FATAL，--allow-empty 留痕豁免）→ 单事务 INSERT reviews。dry-run 默认。
 */
export function commitReview(conn, input) {
  const receipt = loadReceipt(typeof input.receiptRaw === 'string' && input.receiptRaw.trimStart().startsWith('{')
    ? input.receiptRaw
    : readFileSync(input.receiptRaw, 'utf8'));

  const errors = [];
  if (!REVIEWER_PROFILE_RE.test(String(receipt.reviewer_profile ?? ''))) {
    errors.push(`reviewer_profile 须以 model:<provider:model> 或 agent:<name>@<model> 开头，got ${JSON.stringify(receipt.reviewer_profile ?? null)}（P4-2：防共谋身份前缀机器强制）`);
  }
  if (receipt.verdict !== 'approved' && receipt.verdict !== 'rejected') {
    errors.push(`verdict 非法 ${JSON.stringify(receipt.verdict)}（仅 approved/rejected）`);
  }
  if (errors.length > 0) throw new GateFail(`回执门校验未通过（未开事务零写入）：\n${errors.map((e) => `FAIL ${e}`).join('\n')}`);

  const subject = loadSubject(conn, receipt.subject_ref);
  const fatalList = [];
  if (input.checkHash !== false && receipt.subject_hash !== subject.contentHash) {
    fatalList.push({ type: 'hash_mismatch', detail: `subject_hash ${receipt.subject_hash} ≠ 库内 ${subject.contentHash}（回执对错版本写的）` });
  }
  const { rows, summary } = checkFindings(receipt.findings, normalizeForMatch(subject.content));
  for (const row of rows) {
    if (row.fatal) {
      fatalList.push({
        type: row.status === 'missing' ? 'missing_excerpt' : 'no_hit',
        detail: `#${row.index} ${row.id}（${row.severity}）excerpt「${row.excerpt_head}」${row.status === 'missing' ? '缺失/空串' : '归一化后未在 subject 内容命中'}`,
      });
    }
  }
  const advisories = [];
  if (summary.findings_total === 0 && receipt.verdict === 'approved') {
    if (input.allowEmpty) {
      advisories.push({ type: 'empty_findings_approved', detail: '空查回执 --allow-empty 显式豁免留痕（R7-A1）' });
    } else {
      fatalList.push({ type: 'empty_findings_approved', detail: 'findings=0 且 verdict=approved：什么都没查的回执（R7-A1 默认 FATAL；确需放行加 --allow-empty）' });
    }
  }
  if (fatalList.length > 0) {
    throw new GateFail(`G2 引文验证未通过（未开事务零写入）：\n${fatalList.map((f) => `FAIL ${f.type}: ${f.detail}`).join('\n')}`);
  }

  const reviewId = newId('review');
  const meta = {
    gate_version: VERSION,
    verify: { fatal_total: 0, advisories: advisories.length, allow_empty: input.allowEmpty === true },
    dry_run: input.dryRun !== false,
  };
  const insert = () => {
    conn.prepare(
      'INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict, findings_json, '
      + 'reviewer_profile, metadata_json, evidence_refs_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
    ).run(
      reviewId,
      String(receipt.subject_type ?? subject.kind),
      String(receipt.subject_ref),
      String(receipt.subject_hash),
      String(receipt.verdict),
      pyCompact(receipt.findings),
      String(receipt.reviewer_profile),
      pyCompact(meta),
      pyCompact(Array.isArray(receipt.evidence_refs) ? receipt.evidence_refs : []),
    );
  };
  if (input.dryRun !== false) {
    return { reviewId, dryRun: true, advisories, summary, results: [`dry-run：将通过门校验落库 review ${reviewId}（${receipt.verdict}，${summary.findings_total} findings）——加 --commit 执行`] };
  }
  withTransaction(conn, insert);
  return { reviewId, dryRun: false, advisories, summary, results: [`review ${reviewId} 已落库（${receipt.verdict}，${summary.findings_total} findings）`] };
}

// ── 子命令 4/5：状态机门 lock-asset / accept-chapter（WP5 语义重写） ─────────

function bindReviewGuard(conn, reviewId, subjectRef, subjectHash) {
  const review = conn.prepare('SELECT id, verdict, subject_ref, subject_hash FROM reviews WHERE id = ?').get(reviewId);
  if (!review) throw new GateFail(`回执不存在: ${reviewId}`);
  if (review.verdict !== 'approved') {
    throw new GateFail(`跳审阻断：回执 ${reviewId} verdict=${review.verdict}，仅 approved 可绑定（F2 红线）`);
  }
  if (review.subject_ref !== subjectRef) {
    throw new GateFail(`错绑阻断：回执 ${reviewId} subject_ref=${review.subject_ref} ≠ 目标 ${subjectRef}`);
  }
  if (review.subject_hash !== subjectHash) {
    throw new GateFail(`错版阻断：回执 ${reviewId} subject_hash=${review.subject_hash} ≠ 当前内容 ${subjectHash}（须重审出新回执）`);
  }
  return review;
}

/** 锁定规划资产：candidate→locked，旧 locked（同 project/type/scope）翻 superseded */
export function lockAsset(conn, { assetId, reviewId, dryRun = true }) {
  const asset = conn.prepare(
    'SELECT pa.id, pa.status, pa.locked_review_id, pa.project_id, pa.asset_type, pa.scope_ref, r.content_hash '
    + 'FROM planning_assets pa JOIN resources r ON r.id = pa.content_resource_id WHERE pa.id = ?',
  ).get(assetId);
  if (!asset) throw new GateFail(`资产不存在: ${assetId}`);
  bindReviewGuard(conn, reviewId, asset.id, asset.content_hash);

  if (asset.status === 'locked') {
    if (asset.locked_review_id === reviewId) {
      return { results: [`幂等重放：${asset.id} 已由 ${reviewId} 锁定（零写入）`], idempotent: true };
    }
    throw new GateFail(`${asset.id} 已锁定（review=${asset.locked_review_id}）——修订走新 revision，不得换回执重锁`);
  }
  if (asset.status !== 'candidate') {
    throw new GateFail(`${asset.id} 状态为 ${asset.status}，仅 candidate 可锁定（stale/superseded 须先修订）`);
  }

  const siblings = conn.prepare(
    "SELECT id FROM planning_assets WHERE project_id = ? AND asset_type = ? AND scope_ref = ? "
    + "AND status = 'locked' AND id <> ?",
  ).all(asset.project_id, asset.asset_type, asset.scope_ref, asset.id);

  const run = () => {
    for (const s of siblings) {
      conn.prepare("UPDATE planning_assets SET status='superseded', updated_at=CURRENT_TIMESTAMP WHERE id=?").run(s.id);
    }
    conn.prepare(
      "UPDATE planning_assets SET status='locked', locked_review_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
    ).run(reviewId, asset.id);
  };
  if (dryRun) {
    return {
      results: [
        `dry-run：将锁定 ${asset.id}（${asset.asset_type}/${asset.scope_ref}）← review ${reviewId}`,
        ...siblings.map((s) => `dry-run：旧 locked ${s.id} 将翻 superseded`),
      ],
    };
  }
  withTransaction(conn, run);
  return {
    results: [
      `${asset.id} 已锁定 ← review ${reviewId}`,
      ...siblings.map((s) => `旧 locked ${s.id} 已翻 superseded`),
    ],
  };
}

/** 接受章节：draft→accepted，写 chapters.review_id 机器痕迹；幂等重放仅限 hash 未变 */
export function acceptChapter(conn, { chapterId, reviewId, dryRun = true }) {
  const chapter = conn.prepare(
    'SELECT c.id, c.status, c.review_id, c.volume_id, r.content_hash '
    + 'FROM chapters c JOIN resources r ON r.id = c.content_resource_id WHERE c.id = ?',
  ).get(chapterId);
  if (!chapter) throw new GateFail(`章节不存在: ${chapterId}`);
  const projectRow = conn.prepare(
    'SELECT b.project_id AS project_id FROM volumes v JOIN books b ON b.id = v.book_id WHERE v.id = ?',
  ).get(chapter.volume_id);
  bindReviewGuard(conn, reviewId, chapter.id, chapter.content_hash);

  let claremont = null;
  if (projectRow) {
    const open = conn.prepare(
      "SELECT COUNT(*) AS n FROM narrative_promises WHERE project_id = ? AND status = 'open'",
    ).get(projectRow.project_id);
    const broken = conn.prepare(
      "SELECT COUNT(*) AS n FROM narrative_promises WHERE project_id = ? AND status = 'broken'",
    ).get(projectRow.project_id);
    claremont = { open: open.n, broken: broken.n, warn: open.n > 2 };
  }

  if (chapter.status === 'accepted') {
    if (chapter.review_id === reviewId) {
      return { results: [`幂等重放：${chapter.id} 已由 ${reviewId} 接受（零写入）`], idempotent: true, claremont };
    }
    throw new GateFail(`${chapter.id} 已接受（review=${chapter.review_id}）——免审直改禁止：重开 draft → 改稿 → 重审 → 重接受`);
  }
  if (chapter.status !== 'draft') {
    throw new GateFail(`${chapter.id} 状态为 ${chapter.status}，仅 draft 可接受`);
  }

  const run = () => {
    conn.prepare(
      "UPDATE chapters SET status='accepted', review_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
    ).run(reviewId, chapter.id);
  };
  const results = dryRun
    ? [`dry-run：将接受 ${chapter.id} ← review ${reviewId}（写 chapters.review_id 机器痕迹）`]
    : (withTransaction(conn, run), [`${chapter.id} 已接受 ← review ${reviewId}`]);
  const out = { results, claremont };
  if (claremont?.warn) {
    out.results.push(`WARN Claremont 收口：未收伏笔 ${claremont.open} 条（>2）——评估本卷回收排期（不阻断）`);
  }
  return out;
}

// ── 子命令 6：validate-asset（七件校验器语义移植；jsonschema→必需字段偏离声明） ─

const REQUIRED_FIELDS = {
  story_arc: ['arcs', 'volume_plan', 'arc_volume_map', 'plant_payoff_ledger'],
  volume_outline: ['volume_number', 'word_range', 'lines', 'climax_positions', 'volume_form'],
};

function validateBookSoul(doc, scale) {
  const errors = [];
  const lineage = doc.lineage;
  if (lineage) {
    const fields = new Set(lineage.map((x) => x.field));
    for (const must of ['organizing_principle', 'central_contradiction']) {
      if (!fields.has(must)) errors.push('lineage 缺 ' + must + ' 的映射条目——血缘核验无抓手');
    }
  }
  const cadence = doc.cadence_plan;
  if (cadence && scale) {
    const prefix = matchScale(scale);
    if (prefix === null) {
      errors.push(`scale 不认识的档位: ${JSON.stringify(scale)}（须以 短篇/中篇/长篇/超长篇 开头）`);
    } else {
      const [low, high] = SCALE_CADENCE_RULES[prefix];
      const count = cadence.fulfillment_count;
      if (count < low || (high !== null && count > high)) {
        const bound = high !== null ? `${low}-${high} 次` : `≥${low} 次`;
        errors.push(`cadence_plan.fulfillment_count=${count} 与 ${prefix} 档位失配（要求 ${bound}）——数字门见 story-direction 规模表`);
      }
    }
  }
  return errors;
}

function validateWorld(metadata) {
  const errors = [];
  const DISPOSITIONS = ['待契约认领', '待卷级班底', '显式虚位'];
  const seats = metadata.seats ?? [];
  const names = seats.map((s) => s?.name ?? '');
  const dup = names.filter((n, i) => names.indexOf(n) !== i);
  if (dup.length > 0) errors.push(`岗位重名: ${[...new Set(dup)].sort().join('、')}——同名席位使 seat_ref 回指歧义`);
  seats.forEach((s, i) => {
    if (s?.disposition != null && !DISPOSITIONS.includes(s.disposition)) {
      errors.push(`seats[${i}].disposition 非法 ${JSON.stringify(s.disposition)}（${DISPOSITIONS.join('，')}）`);
    }
  });
  (metadata.dimension_costs ?? []).forEach((c, i) => {
    const rev = c?.reversibility;
    if (rev === '压制' && !(c?.release ?? '').trim()) {
      errors.push(`dimension_costs[${i}]（${c?.dimension}）压制型代价缺解除通道 release——封印/禁制类机制无解除通道即死设定`);
    }
    if (rev === '不可逆' && !(c?.threshold ?? '').trim()) {
      errors.push(`dimension_costs[${i}]（${c?.dimension}）不可逆档缺阈值 threshold——回不去的边界在哪必须可指认`);
    }
    if (c?.bearer === 'protagonist_permanent' && !(c?.book_soul_ref ?? '').trim()) {
      errors.push(`dimension_costs[${i}]（${c?.dimension}）主角永久代价缺 book_soul_ref——世界层不得新增主角永久代价，只许回指 strategy 已声明的条目`);
    }
  });
  return errors;
}

function validateArchitecture(metadata, scale) {
  const errors = [];
  const mechanisms = metadata.mechanisms ?? [];
  const sourceTypes = new Set(mechanisms.flatMap((m) => (m?.sources ?? []).map((s) => s?.source_type)));
  if (mechanisms.length > 0 && !sourceTypes.has('direction_field')) {
    errors.push('机制 sources 无 direction_field 条目——上游翻译血缘缺失');
  }
  if (mechanisms.length > 0 && !sourceTypes.has('persona_part')) {
    errors.push('机制 sources 无 persona_part 条目——persona 消费是声明而非可核验血缘（目光/盲区/库存任一部件均可）');
  }
  const unitArc = metadata.unit_arc;
  if (unitArc && (unitArc.min_chapters ?? 0) > (unitArc.max_chapters ?? 0)) {
    errors.push(`unit_arc 粒度倒置：min ${unitArc.min_chapters} > max ${unitArc.max_chapters}`);
  }
  const density = metadata.mainline_density;
  if (density) {
    const tier = density.tier; const beats = density.beats_per_volume;
    if (tier in TIER_BEATS_RULES && typeof beats === 'number') {
      const [low, high] = TIER_BEATS_RULES[tier];
      if (!((low <= beats && beats < high) || (tier === '高' && beats === high))) {
        errors.push(`mainline_density.tier=${tier} 与 beats_per_volume=${beats} 失配（${tier} 档要求 ${tier === '高' ? '≥1' : `[${low}, ${high})`}）`);
      }
    }
    if (scale) {
      const prefix = matchScale(scale);
      if (prefix === null) errors.push(`scale 不认识的档位: ${JSON.stringify(scale)}（须以 短篇/中篇/长篇/超长篇 开头）`);
      else {
        const gapCap = SCALE_ENGINE_RULES[prefix][1];
        const gap = density.gap_limit_volumes;
        if (typeof gap === 'number' && gap > gapCap) {
          errors.push(`mainline_density.gap_limit_volumes=${gap} 超出 ${prefix} 档空窗上限 ${gapCap} 卷——低密度主线合法但空窗随规模受限（柯南式爆发点设计见方法论）`);
        }
      }
    }
  }
  const engines = metadata.engines;
  if (engines && scale) {
    const prefix = matchScale(scale);
    if (prefix === null) errors.push(`scale 不认识的档位: ${JSON.stringify(scale)}（须以 短篇/中篇/长篇/超长篇 开头）`);
    else {
      const floor = SCALE_ENGINE_RULES[prefix][0];
      for (const engine of ['production', 'integrator']) {
        const spec = engines?.[engine];
        if (typeof spec === 'object' && spec !== null && Number.isInteger(spec?.escalation_levels) && spec.escalation_levels < floor) {
          errors.push(`engines.${engine}.escalation_levels=${spec.escalation_levels} 低于 ${prefix} 档下限 ${floor}——油耗数字门与 story-direction cadence 规则同源`);
        }
      }
    }
  }
  return errors;
}

function validateStrategy(metadata, scale) {
  const errors = [];
  const outputs = new Set((metadata.consumption ?? []).map((r) => r?.output));
  const missing = [...CONSUMPTION_OUTPUTS].filter((o) => !outputs.has(o));
  if (missing.length > 0) errors.push(`上游消费表缺行：${missing.sort()}——上游产出在阶段边界静默蒸发`);
  const stages = metadata.stages ?? [];
  if (scale) {
    const prefix = matchScale(scale);
    if (prefix === null) errors.push(`scale 不认识的档位: ${JSON.stringify(scale)}（须以 短篇/中篇/长篇/超长篇 开头）`);
    else {
      const [low, high] = SCALE_STAGE_RULES[prefix];
      if (!(low <= stages.length && stages.length <= high)) {
        errors.push(`阶段数 ${stages.length} 超出 ${prefix} 档区间 [${low}, ${high}]——区间外须论证豁免（空转/无曲线两端失败模式由区间拦截）`);
      }
    }
  }
  if (stages.length > 0) {
    const limit = metadata?.pairing_cycle?.debt_streak_limit ?? 2;
    let streak = 0; let maxStreak = 0;
    for (const st of stages) {
      if (st?.payoff === 'debt') { streak += 1; maxStreak = Math.max(maxStreak, streak); } else streak = 0;
    }
    if (maxStreak > limit) {
      errors.push(`连续纯存债阶段 ${maxStreak} 段超上限 ${limit}——存债阶段合法但须有 progress 并按周期爆发兑付`);
    }
    if (!stages.some((st) => st?.payoff === 'heavy' || st?.payoff === 'light')) {
      errors.push('全书无任何 heavy/light 阶段——只种不收（至少一个兑付爆发阶段）');
    }
  }
  if (stages.length >= 3 && !('midpoint_renewal' in metadata)) {
    errors.push('阶段数 ≥3 而无 midpoint_renewal——中盘塌陷（中期疲软）是长篇头部弃书原因，中段必须有换挡事件');
  }
  const renewal = metadata.midpoint_renewal;
  if (renewal && stages.length > 0 && !(1 <= (renewal.stage ?? 0) && (renewal.stage ?? 0) <= stages.length)) {
    errors.push(`midpoint_renewal.stage=${renewal.stage} 不在阶段表内（1-${stages.length}）`);
  }
  if (metadata.terminal_mode === 'closed') {
    const terminal = metadata.terminal ?? {};
    const terminalClaims = (metadata.claim_ledger ?? []).filter((c) => c?.disposition === 'terminal').length;
    const budget = terminal.closure_budget;
    if (Number.isInteger(budget) && terminalClaims > budget) {
      errors.push(`终局待收承诺 ${terminalClaims} 条超收束预算 ${budget}——鞭尸式赶工烂尾形态，剩余应转 silence 或中途收`);
    }
    const floor = terminal.word_floor;
    const lastMin = stages.length > 0 ? stages[stages.length - 1]?.word_range?.min : null;
    if (Number.isInteger(floor) && Number.isInteger(lastMin) && lastMin < floor) {
      errors.push(`终局阶段字数下限 ${lastMin} 万 < 声明下限 ${floor} 万——终局压缩是赶工烂尾的典型形态`);
    }
  }
  return errors;
}

function validateCharacterRoster(metadata, scale, world) {
  const errors = [];
  const warns = [];
  const roster = metadata.character_roster;
  if (roster === undefined || roster === null) {
    errors.push('metadata.character_roster 缺失——立档人物必须有结构化出口');
    return [errors, warns];
  }
  errors.push(...validateRoster(roster));
  const names = roster.map((p) => p?.name);
  const dup = names.filter((n, i) => names.indexOf(n) !== i);
  if (dup.length > 0) errors.push(`roster 重名: ${[...new Set(dup)].sort().join('、')}——人物注册表 project_id+name 唯一`);
  if (!roster.some((p) => p?.role_class === 'main')) errors.push('roster 无 main 人物——主角必须立档（role_class=main）');
  if (scale != null) {
    if (!(scale in SCALE_ROSTER_RULES)) {
      errors.push(`未知 scale 档位 ${JSON.stringify(scale)}（${Object.keys(SCALE_ROSTER_RULES).join('，')}）`);
    } else {
      const [low, high] = SCALE_ROSTER_RULES[scale];
      const n = roster.length;
      if (n < low) errors.push(`roster 规模 ${n} 低于 ${scale} 档区间 [${low}, ${high}] 下限——主线载体缺口：补立档或确认由卷级班底承载并说明`);
      else if (n > high) errors.push(`roster 规模 ${n} 超出 ${scale} 档区间 [${low}, ${high}] 上限——契约越权吸食班底职责：次要角色移交卷纲/执行卡`);
    }
  }
  if (world != null) {
    const seatNames = new Set((world.seats ?? []).map((s) => s?.name));
    const claimed = new Set();
    for (const p of roster) {
      const ref = p?.seat_ref;
      if (ref) {
        claimed.add(ref);
        if (!seatNames.has(ref)) errors.push(`roster[${p.name}].seat_ref 引用不存在的席位: ${JSON.stringify(ref)}`);
      }
    }
    for (const s of world.seats ?? []) {
      if (claimed.has(s.name) || s.disposition === '显式虚位') continue;
      if (s.disposition === '待契约认领') {
        errors.push(`席位「${s.name}」标注「待契约认领」但 roster 无人认领——处置标注是承诺不是免检标签：认领（seat_ref）或经 change proposal 改 world 处置`);
      } else if (s.disposition === '待卷级班底') {
        warns.push(`席位「${s.name}」标注「待卷级班底」——卷纲班底义务，锁定卷纲时 register --world 终核`);
      } else {
        warns.push(`席位「${s.name}」未被认领且无处置标注——主要席位须在正文标注 认领/移交班底/虚位 之一`);
      }
    }
  }
  return [errors, warns];
}

function validateStoryArc(metadata, opts) {
  const { scale, character, world, architecture, strategy } = opts;
  const errors = [];
  const warns = [];
  const arcs = metadata.arcs;
  const plan = metadata.volume_plan;
  const amap = metadata.arc_volume_map;
  const ledger = metadata.plant_payoff_ledger;
  const nVols = plan.length;

  const idx = plan.map((v) => v.index);
  if (JSON.stringify(idx) !== JSON.stringify(Array.from({ length: nVols }, (_, i) => i + 1))) {
    errors.push(`volume_plan 卷号不连续: ${JSON.stringify(idx)}——须为 1..${nVols}`);
  }
  if (scale != null) {
    if (!(scale in SCALE_ARC_RULES)) {
      errors.push(`未知 scale 档位 ${JSON.stringify(scale)}（${Object.keys(SCALE_ARC_RULES).join('，')}）`);
    } else {
      const [low, high] = SCALE_ARC_RULES[scale];
      const n = arcs.length;
      if (n < low) errors.push(`弧数 ${n} 低于 ${scale} 档区间 [${low}, ${high}] 下限——线程轴单薄`);
      else if (n > high) errors.push(`弧数 ${n} 超出 ${scale} 档区间 [${low}, ${high}] 上限——弧线过散，收束不住`);
    }
  }
  const mainline = arcs.filter((a) => a.kind === '主线');
  if (mainline.length !== 1) errors.push(`主线弧须恰 1 条（当前 ${mainline.length}）——central_contradiction 的唯一承载`);
  const arcIds = arcs.map((a) => a.arc_id);
  const dup = arcIds.filter((x, i) => arcIds.indexOf(x) !== i);
  if (dup.length > 0) errors.push(`arc_id 重复: ${[...new Set(dup)].sort()}`);

  const byVolume = new Map();
  const arcRows = new Map();
  const arcIdSet = new Set(arcIds);
  for (const row of amap) {
    const aid = row.arc_id; const vol = row.volume;
    if (!arcIdSet.has(aid)) { errors.push(`映射表引用不存在的 arc_id: ${aid}`); continue; }
    if (!(1 <= vol && vol <= nVols)) { errors.push(`弧 ${aid} 映射卷 ${vol} 越界（volume_plan 共 ${nVols} 卷）`); continue; }
    if (!byVolume.has(vol)) byVolume.set(vol, []);
    byVolume.get(vol).push([aid, row.duty]);
    if (!arcRows.has(aid)) arcRows.set(aid, []);
    arcRows.get(aid).push(vol);
  }
  for (const a of arcs) {
    if (!arcRows.has(a.arc_id)) errors.push(`弧 ${a.arc_id} 在映射表无任何职责格——每弧至少一格`);
  }
  for (let vol = 1; vol <= nVols; vol++) {
    const rows = byVolume.get(vol) ?? [];
    if (rows.length === 0) { errors.push(`卷 ${vol} 映射表无任何弧职责格`); continue; }
    const duties = rows.map(([, d]) => d);
    const advancing = duties.filter((d) => d === '推进');
    const active = duties.filter((d) => ACTIVE_DUTIES.has(d));
    if (active.length === 0) errors.push(`卷 ${vol} 无任何活跃弧（推进/兑现/收束皆无）——全蓄势/全休眠是调度失败`);
    else if (advancing.length === 0) warns.push(`卷 ${vol} 无「推进」弧（仅兑现/收束）——终卷形态合法，其余卷提示节奏软塌`);
    if (advancing.length > 2) warns.push(`卷 ${vol} 推进弧 ${advancing.length} 条（>2）——活跃焦点过散`);
    if (active.length > 4) errors.push(`卷 ${vol} 同时活跃弧 ${active.length} 条（>4）——超出并行活跃上限`);
    if (arcs.length >= 3 && new Set(duties).size === 1 && ACTIVE_DUTIES.has(duties[0])) {
      warns.push(`卷 ${vol} 全部弧同职责「${duties[0]}」——全推进/全兑现同样不合格，须有蓄势/休眠弧`);
    }
  }

  const roster = character ? (character.character_roster ?? []) : [];
  const rosterNames = new Map(roster.map((p) => [p?.name, p]));
  const seatNames = world ? new Set((world.seats ?? []).map((s) => s?.name)) : new Set();
  for (const a of arcs) {
    const kind = a.kind; const aid = a.arc_id;
    const carriers = a.carriers ?? [];
    const named = carriers.filter((c) => c.ref_type === 'roster');
    if (character != null && ['主线', '人物', '关系'].includes(kind) && named.length === 0) {
      errors.push(`弧 ${aid}（${kind}）无 roster 具名载体——人物类弧必须绑定契约人物`);
    }
    for (const c of carriers) {
      if (c.ref_type === 'roster' && character != null && !rosterNames.has(c.ref)) {
        errors.push(`弧 ${aid} 载体 ${JSON.stringify(c.ref)} 不在契约 roster——引用不存在的人物`);
      } else if (c.ref_type === 'seat' && world != null && !seatNames.has(c.ref)) {
        errors.push(`弧 ${aid} 载体席位 ${JSON.stringify(c.ref)} 不在 world 岗位表——引用不存在的席位`);
      } else if (c.ref_type === 'latent') {
        warns.push(`弧 ${aid} 载体 ${JSON.stringify(c.ref)} 为 latent（待造）——远卷对手可暂悬空，近硬窗内须落位（roster/席位/班底）`);
      }
    }
    const vols = arcRows.get(aid);
    const firstVol = vols && vols.length > 0 ? Math.min(...vols) : nVols + 1;
    for (const c of named) {
      const p = rosterNames.get(c.ref) ?? {};
      const debut = p['登场卷'];
      if (Number.isInteger(debut) && firstVol < debut) {
        errors.push(`弧 ${aid} 首个活跃卷 ${firstVol} 早于载体 ${c.ref} 登场卷 ${debut}——弧不能在人物登场前活跃`);
      }
    }
  }

  for (const row of ledger) {
    const hasClose = row.close_volume !== undefined && row.close_volume !== null;
    const hasExempt = Boolean(row.exempt);
    if (hasClose && hasExempt) errors.push(`台账行 ${row.line_id} 兼有 close_volume 与 exempt——二选一`);
    else if (!hasClose && !hasExempt) errors.push(`台账行 ${row.line_id} 既无 close_volume 也无 exempt——只种不收：给收束卷，或引用豁免（deliberate_silences / open 喂料线）`);
    const plant = row.plant_volume;
    if (!(1 <= plant && plant <= nVols)) errors.push(`台账行 ${row.line_id} 种下卷 ${plant} 越界`);
    else if (hasClose && row.close_volume <= plant) errors.push(`台账行 ${row.line_id} 收束卷不晚于种下卷——先收后种`);
    for (const pv of row.partial_payoffs ?? []) {
      if (!(1 <= pv && pv <= nVols) || (hasClose && pv >= row.close_volume)) {
        errors.push(`台账行 ${row.line_id} 阶段兑现卷 ${pv} 越界或不早于收束卷`);
      }
    }
  }
  for (let vol = 2; vol <= nVols; vol++) {
    const hit = ledger.some((r) => r.close_volume === vol || (r.partial_payoffs ?? []).includes(vol));
    if (!hit) errors.push(`卷 ${vol} 无任何前序悬念兑现（close/partial 均未命中）——每卷至少兑现一条，读者容忍的是晚收益不是无收益`);
  }

  const mechNames = new Set((architecture?.mechanisms ?? []).map((m) => m?.name));
  const allocCount = new Map();
  for (const row of metadata.variation_alloc ?? []) {
    allocCount.set(row.test_ref, (allocCount.get(row.test_ref) ?? 0) + 1);
    if (!(1 <= row.volume && row.volume <= nVols)) errors.push(`变奏分配 ${JSON.stringify(row.test_ref)} 卷 ${row.volume} 越界`);
    const ref = row.mech_ref;
    if (ref && mechNames.size > 0 && !mechNames.has(ref)) {
      errors.push(`变奏分配 ${JSON.stringify(row.test_ref)} 的 mech_ref ${JSON.stringify(ref)} 不在 architecture mechanisms——变奏声明须引用真实机制`);
    }
  }
  for (const [t, n] of allocCount) {
    if (n > 3) warns.push(`母题 ${JSON.stringify(t)} 已分配 ${n} 次变奏（>3）——须评估剩余空间，耗尽即转收束`);
  }

  if (strategy) {
    const stages = strategy.stages ?? [];
    try {
      const stageSum = stages.reduce((s, x) => s + x.word_range.max, 0);
      const planSum = plan.reduce((s, x) => s + x.word_range.max, 0);
      if (stageSum && planSum && !(0.6 <= planSum / stageSum && planSum / stageSum <= 1.6)) {
        warns.push(`卷计划总字数 ${planSum} 与 strategy 阶段字数总和 ${stageSum} 比值 ${(planSum / stageSum).toFixed(2)} 越界 [0.6, 1.6]——卷切分与阶段骨架对表`);
      }
    } catch {
      warns.push('strategy stages 缺 word_range——卷计划与阶段字数对表跳过');
    }
    if (strategy.terminal_mode === 'open' && !('open_window' in metadata)) {
      errors.push('strategy terminal_mode=open 但缺 open_window——开放连载必须声明滚动窗口（近 hard_volumes 卷硬格，远卷软格待重映射）');
    }
  }
  return [errors, warns];
}

function validateVolumeOutline(metadata, opts) {
  const { scale, storyArc, architecture, strategy, prevVolumeNumbers, registryNames } = opts;
  const errors = [];
  const warns = [];
  const volNo = metadata.volume_number;
  const target = metadata.word_range?.target;
  const lines = metadata.lines;

  if (prevVolumeNumbers !== null && prevVolumeNumbers !== undefined) {
    const expect = Array.from({ length: volNo - 1 }, (_, i) => i + 1);
    const sorted = [...prevVolumeNumbers].sort((a, b) => a - b);
    if (JSON.stringify(sorted) !== JSON.stringify(expect)) {
      errors.push(`前置锁定卷号 ${JSON.stringify(sorted)} ≠ 1..${volNo - 1}——乱序规划：前置链按卷号注入，缺卷即错位，先补锁前置卷`);
    } else if (prevVolumeNumbers.includes(volNo)) {
      errors.push(`卷 ${volNo} 已存在 locked 记录——这是修订而非新卷，走修订流程`);
    }
  }

  const arcs = storyArc?.arcs ?? [];
  const arcIds = new Set(arcs.map((a) => a?.arc_id));
  const amap = storyArc?.arc_volume_map ?? [];
  const plan = storyArc?.volume_plan ?? [];
  const ledger = storyArc?.plant_payoff_ledger ?? [];

  if (plan.length > 0) {
    const row = plan.find((v) => v.index === volNo);
    if (!row) {
      errors.push(`卷号 ${volNo} 不在 story_arc volume_plan（共 ${plan.length} 卷）——卷号以卷计划为权威`);
    } else {
      const pw = row.word_range ?? {};
      const w = metadata.word_range;
      if (pw.min != null && pw.max != null) {
        if (w.max < pw.min || w.min > pw.max) {
          errors.push(`本卷字数 [${w.min}, ${w.max}] 与 volume_plan 卷 ${volNo} [${pw.min}, ${pw.max}] 无交集——卷纲不得重切卷计划`);
        } else if (!(pw.min <= target && target <= pw.max)) {
          warns.push(`本卷 target ${target} 落在 volume_plan 区间外（交集内但偏离计划重心）`);
        }
      }
    }
  }

  const positions = metadata.climax_positions;
  const sortedPos = [...positions].sort((a, b) => a - b);
  if (JSON.stringify(positions) !== JSON.stringify(sortedPos) || new Set(positions).size !== positions.length) {
    errors.push(`climax_positions 须严格升序且不重复: ${JSON.stringify(positions)}`);
  } else {
    if (positions[positions.length - 1] !== 1) {
      errors.push(`climax_positions 末位 ${positions[positions.length - 1]} ≠ 1——卷末主高潮必须封顶`);
    }
    const degenerate = target < CLIMAX_UNIT_WORDS * 0.8 || scale === '短篇';
    const pts = [0.0, ...positions.map((p) => parseFloat(p))];
    if (!degenerate) {
      for (let i = 1; i < pts.length; i++) {
        const gapWords = (pts[i] - pts[i - 1]) * target;
        if (gapWords > CLIMAX_GAP_WORDS) {
          errors.push(`高潮 ${i} 与前一节点间距 ${Math.floor(gapWords)} 字（> ${CLIMAX_GAP_WORDS}）——中段空窗，副高湂数按本卷字数条件化（每 20-30 万字一个）`);
        }
      }
      const need = Math.ceil(target / CLIMAX_UNIT_WORDS);
      if (positions.length < need) {
        errors.push(`高潮总数 ${positions.length} < ${need}（target ${target} 字 ÷ ${CLIMAX_UNIT_WORDS} 向上取整，含卷末主高潮）`);
      }
    } else if (positions.length === 1 && target >= CLIMAX_UNIT_WORDS) {
      warns.push('短篇退化形态：仅卷末主高潮——确认这是刻意的紧凑卷而非漏报副高潮');
    }
  }

  for (const ln of lines) {
    if (ln.scope === '跨卷弧') {
      const aid = ln.arc_id;
      if (!aid) errors.push(`冲突线「${ln.name}」scope=跨卷弧 但无 arc_id——跨卷线必须回指映射表`);
      else if (arcs.length > 0 && !arcIds.has(aid)) errors.push(`冲突线「${ln.name}」引用不存在的 arc_id: ${aid}`);
      else if (amap.length > 0) {
        const duty = (amap.find((r) => r.arc_id === aid && r.volume === volNo) ?? {}).duty ?? null;
        if (duty === null) warns.push(`冲突线「${ln.name}」挂弧 ${aid}，但映射表卷 ${volNo} 无该弧职责格`);
        else if (!ACTIVE_DUTIES.has(duty)) warns.push(`冲突线「${ln.name}」挂弧 ${aid} 本卷 duty=${duty}——蓄势/休眠弧不得反向活跃承载`);
      }
    } else if (!ln.note) {
      warns.push(`自含线「${ln.name}」无加压/结算点声明——自含线靠独立开合替代弧调度`);
    }
  }
  if (arcs.length > 0 && amap.length > 0) {
    const lineArcs = new Set(lines.filter((ln) => ln.scope === '跨卷弧').map((ln) => ln.arc_id));
    for (const row of amap) {
      if (row.volume === volNo && ACTIVE_DUTIES.has(row.duty) && !lineArcs.has(row.arc_id)) {
        errors.push(`弧 ${row.arc_id} 本卷 duty=${row.duty} 但无冲突线承载——职责蒸发`);
      }
    }
  }
  const shareSum = lines.reduce((s, ln) => s + ln.share_pct, 0);
  if (!(90 <= shareSum && shareSum <= 110)) {
    warns.push(`冲突线篇幅占比合计 ${shareSum}%（合法窗 90-110）——配比申报失真`);
  }
  const mainlineLines = lines.filter((ln) => ln.mainline);
  if (mainlineLines.length > 1) errors.push(`mainline 线 ${mainlineLines.length} 条（>1）——主线唯一`);
  const density = architecture?.mainline_density ?? {};
  if (mainlineLines.length > 0) {
    const share = mainlineLines[0].share_pct;
    const tier = density.tier;
    if (tier === '低' && share > 55) warns.push(`主线占比 ${share}% 而 mainline_density.tier=低——低密度主线被卷内排布削平`);
    if (tier === '高' && share < 30) warns.push(`主线占比 ${share}% 而 mainline_density.tier=高——高密度主线喂不饱`);
  }
  const beats = metadata.mainline_beats;
  if (beats != null && density.beats_per_volume != null) {
    if (Math.abs(beats - density.beats_per_volume) > 2) {
      warns.push(`mainline_beats ${beats} 偏离架构 beats_per_volume ${density.beats_per_volume}（±2 内对表）`);
    }
  }

  if (metadata.volume_form === '单元编排') {
    const units = metadata.units;
    if (!units) errors.push('volume_form=单元编排 但缺 units——副本/案件/赛季卷必须有单元编排表');
    else {
      const chapterBudget = Math.ceil(target / 2500);
      let windowSum = 0;
      for (const u of units) {
        const w = u.chapter_window;
        if (w.min > w.max) errors.push(`单元 ${u.unit_id} 章数窗 min>max`);
        if (!u.interlude && (u.mainline_advance ?? 0) < 1) {
          errors.push(`单元 ${u.unit_id} 非间歇但主线渗透 <1 拍——单元剧防散架：每单元至少推一步主线`);
        }
        windowSum += w.max;
      }
      if (windowSum > chapterBudget) {
        warns.push(`单元章数窗总量 ${windowSum} 超卷容量约 ${chapterBudget} 章（target ${target} ÷ 2500）——副本篇幅过长是单元剧头号差评`);
      }
    }
  } else if (metadata.units) {
    warns.push('volume_form=连续四段 但带 units——改用单元编排形态或删表');
  }

  const exitSet = metadata.exit_settlement;
  if (exitSet) {
    const ledgerIds = new Set(ledger.map((r) => r?.line_id));
    for (const field of ['cut', 'pre_close']) {
      for (const ref of exitSet[field] ?? []) {
        if (SLUG_RE.test(ref) && ledgerIds.size > 0 && !ledgerIds.has(ref)) {
          warns.push(`exit_settlement.${field} 引用台账无此 line_id: ${ref}——斩断/离图收账须指向真实悬念行`);
        }
      }
    }
  }

  const seen = new Set();
  for (const row of metadata.new_plants ?? []) {
    const lid = row.line_id;
    if (seen.has(lid)) errors.push(`new_plants line_id 重复: ${lid}`);
    seen.add(lid);
    const hasClose = row.close_volume !== undefined && row.close_volume !== null;
    const hasExempt = Boolean(row.exempt);
    if (hasClose && hasExempt) errors.push(`新种 ${lid} 兼有 close_volume 与 exempt——二选一`);
    else if (!hasClose && !hasExempt) errors.push(`新种 ${lid} 既无 close_volume 也无 exempt——只种不收`);
    if (hasClose && row.close_volume < volNo) errors.push(`新种 ${lid} 收束卷 ${row.close_volume} 早于本卷 ${volNo}——先收后种`);
    if (ledger.length > 0 && ledger.some((r) => r?.line_id === lid)) {
      errors.push(`新种 ${lid} 与既有台账 line_id 冲突——增量行不得复用旧 id`);
    }
  }
  if (plan.length > 0) {
    const finalVol = Math.max(...plan.map((v) => v.index ?? 0));
    if (volNo === finalVol) {
      for (const row of metadata.new_plants ?? []) {
        if (row.close_volume != null && row.close_volume > volNo) {
          errors.push(`终卷新种 ${row.line_id} 收束卷 ${row.close_volume} 溢出终卷——终卷纪律：写到这里就该收了`);
        }
        if (row.exempt && strategy?.terminal_mode === 'closed') {
          errors.push(`终卷新种 ${row.line_id} 豁免而 terminal_mode=closed——闭合终局不留新坑`);
        }
      }
      if (strategy?.terminal_mode === 'open' && (metadata.new_plants ?? []).some((r) => r.exempt)) {
        warns.push('终卷豁免新种（terminal_mode=open）——确认计入 open 滚动窗口');
      }
    }
  }

  for (const row of metadata.drift ?? []) {
    if (arcs.length > 0 && !arcIds.has(row.arc_id)) errors.push(`drift 引用不存在的 arc_id: ${row.arc_id}`);
  }

  if (storyArc) {
    const allocHere = new Set((storyArc.variation_alloc ?? []).filter((r) => r.volume === volNo).map((r) => r.test_ref));
    const claimed = new Set((metadata.test_alloc ?? []).map((r) => r.test_ref));
    for (const ref of [...allocHere].filter((x) => !claimed.has(x)).sort()) {
      warns.push(`variation_alloc 本卷行 ${JSON.stringify(ref)} 未被 test_alloc 承接——分配不得静默蒸发`);
    }
    for (const ref of [...claimed].filter((x) => !allocHere.has(x)).sort()) {
      warns.push(`test_alloc ${JSON.stringify(ref)} 超出 variation_alloc 本卷分配——变奏以分配表为准，另造走 change proposal`);
    }
  }

  const span = metadata.stage_span;
  if (span) {
    const stages = strategy?.stages ?? [];
    if (stages.length > 0 && !(1 <= span[0] && span[0] <= span[1] && span[1] <= stages.length)) {
      errors.push(`stage_span ${JSON.stringify(span)} 越界（strategy 共 ${stages.length} 阶段）`);
    }
  }

  if (registryNames !== null && registryNames !== undefined) {
    for (const p of metadata.volume_characters ?? []) {
      if (!registryNames.has(p?.name)) {
        warns.push(`班底 ${p.name} 尚未入注册表——锁定后跑 register --entry，漏跑由 --audit-entries 终核`);
      }
    }
  }

  const settings = metadata.volume_settings ?? [];
  const settingNames = settings.map((s) => s?.name);
  const dupSettings = settingNames.filter((n, i) => settingNames.indexOf(n) !== i);
  if (dupSettings.length > 0) errors.push(`volume_settings 名称重复: ${[...new Set(dupSettings)].sort()}`);
  const pending = settings.filter((s) => s?.disposition === '登记入world').map((s) => s.name);
  if (pending.length > 0) warns.push(`volume_settings 待登记入 world（锁定后走 change proposal）: ${JSON.stringify(pending)}`);

  return [errors, warns];
}

const VALIDATORS = {
  direction: (meta, o) => validateBookSoul(meta.book_soul ?? meta, o.scale),
  world_contract: (meta) => validateWorld(meta),
  architecture: (meta, o) => validateArchitecture(meta, o.scale),
  strategy: (meta, o) => validateStrategy(meta, o.scale),
  character_contract: (meta, o) => validateCharacterRoster(meta, o.scale, o.world),
  story_arc: (meta, o) => validateStoryArc(meta, o),
  volume_outline: (meta, o) => validateVolumeOutline(meta, o),
};

/** validate-asset 主入口：只读。--asset 或 --asset-type+--project[+--scope-ref]（取最新 revision）。 */
export function validateAsset(conn, input) {
  let row;
  if (input.assetId) {
    row = conn.prepare('SELECT * FROM planning_assets WHERE id = ?').get(input.assetId);
    if (!row) throw new GateFail(`资产不存在: ${input.assetId}`);
  } else {
    if (!input.assetType || !VALIDATORS[input.assetType]) {
      throw new UsageError(`--asset-type 须为七类之一：${Object.keys(VALIDATORS).join('，')}（或改用 --asset <id>）`);
    }
    if (!input.projectId) throw new UsageError('validate-asset 需要 --asset <id> 或 --asset-type + --project');
    const scopeClause = input.scopeRef ? 'AND scope_ref = ?' : '';
    const args = input.scopeRef ? [input.projectId, input.assetType, input.scopeRef] : [input.projectId, input.assetType];
    row = conn.prepare(
      `SELECT * FROM planning_assets WHERE project_id = ? AND asset_type = ? ${scopeClause} ORDER BY revision DESC LIMIT 1`,
    ).get(...args);
    if (!row) throw new GateFail(`资产不存在: project=${input.projectId} type=${input.assetType}${input.scopeRef ? ` scope=${input.scopeRef}` : ''}（无任何 revision）`);
  }
  let meta;
  try {
    meta = JSON.parse(row.metadata_json || '{}');
  } catch {
    throw new GateFail(`metadata_json 不可解析: ${row.id}`);
  }
  const scale = input.scale ?? resolveProjectScale(conn, row.project_id);
  const opts = {
    scale,
    world: lockedUpstreamMetadata(conn, row.project_id, 'world_contract'),
    character: lockedUpstreamMetadata(conn, row.project_id, 'character_contract'),
    architecture: lockedUpstreamMetadata(conn, row.project_id, 'architecture'),
    strategy: lockedUpstreamMetadata(conn, row.project_id, 'strategy'),
    storyArc: lockedUpstreamMetadata(conn, row.project_id, 'story_arc'),
    prevVolumeNumbers: conn.prepare(
      "SELECT scope_ref FROM planning_assets WHERE project_id = ? AND asset_type = 'volume_outline' "
      + "AND status = 'locked' AND scope_ref <> ?",
    ).all(row.project_id, row.scope_ref).map((r) => parseInt(r.scope_ref, 10)).filter((n) => !Number.isNaN(n)),
    registryNames: new Set(conn.prepare('SELECT name FROM characters WHERE project_id = ?').all(row.project_id).map((r) => r.name)),
  };

  const required = REQUIRED_FIELDS[row.asset_type] ?? [];
  const missing = required.filter((f) => meta?.[f] === undefined || meta?.[f] === null);
  if (missing.length > 0) {
    return {
      asset: row.id, asset_type: row.asset_type, scale, errors: missing.map((f) => `metadata 缺必需字段「${f}」（schema 必填，语义门跳过）`), warns: [],
    };
  }
  const raw = VALIDATORS[row.asset_type](meta, opts);
  // 单数组返回（纯 errors 语义门）与 [errors, warns] 双返回统一归一
  const [errors, warns] = Array.isArray(raw[0]) ? raw : [raw, []];
  return { asset: row.id, asset_type: row.asset_type, scope_ref: row.scope_ref, scale, errors, warns };
}

// ── CLI ─────────────────────────────────────────────────────────────────────

function parseArgs(argv, spec) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const name = a.slice(2);
      if (!spec.includes(name)) throw new UsageError(`未知参数：${a}`);
      if (name === 'commit' || name === 'fine' || name === 'json' || name === 'allow-production' || name === 'allow-empty' || name === 'no-check-hash') {
        out[name] = true;
      } else {
        out[name] = argv[++i];
        if (out[name] === undefined) throw new UsageError(`参数 ${a} 缺值`);
      }
    } else out._.push(a);
  }
  return out;
}

const WRITE_SUBCOMMANDS = new Set(['lock-asset', 'accept-chapter', 'commit-review', 'propagate-stale', 'register-characters']);

function usage() {
  return [
    `用法：node scripts/${PROG}.mjs <子命令> [参数]`,
    '',
    '子命令：',
    '  lock-asset      --asset <planning:id> --review <review:id>',
    '  accept-chapter  --chapter <chapter:id> --review <review:id>',
    '  commit-review   --receipt <file|内联JSON> [--allow-empty] [--no-check-hash]',
    '  propagate-stale --asset <planning:id> [--fine]',
    '  validate-asset  (--asset <planning:id> | --asset-type <t> --project <id> [--scope-ref <r>]) [--scale <s>]',
    '  register-characters --project <id> [--roster <json>] [--entry <json>] [--status-update <json>] [--world <json>]',
    '通用：[--db <路径>]（默认 data/novelos-v2.db）[--json]',
    '',
    '安全模型：dry-run 默认（零写入）；写库须 --commit；对生产库路径 --commit 还须 --allow-production。',
    'exit：0 = 通过；1 = GateFail（阻断，零写入）；2 = 用法/输入错误。',
  ].join('\n');
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv.length === 0 || argv.includes('--help') || argv.includes('-h')) {
    console.log(usage());
    return;
  }
  const sub = argv[0];
  const flags = ['db', 'json', 'commit', 'fine', 'allow-production', 'allow-empty', 'no-check-hash',
    'asset', 'review', 'chapter', 'receipt', 'asset-type', 'project', 'scope-ref', 'scale',
    'roster', 'entry', 'status-update', 'world'];
  const args = parseArgs(argv.slice(1), flags);
  const dbPath = path.resolve(args.db ?? DEFAULT_DB);
  const isProduction = path.resolve(dbPath) === path.resolve(DEFAULT_DB);
  const dryRun = !args.commit;
  if (WRITE_SUBCOMMANDS.has(sub) && !dryRun && isProduction && !args['allow-production']) {
    throw new UsageError(`拒绝写入：${dbPath} 是生产库路径——--commit 须搭配 --allow-production（先备份）`);
  }
  const conn = openDb(dbPath);

  const loadJsonInput = (v) => {
    if (v === undefined) return undefined;
    const text = v.trimStart().startsWith('{') || v.trimStart().startsWith('[') ? v : readFileSync(v, 'utf8');
    return JSON.parse(text);
  };

  let report;
  switch (sub) {
    case 'propagate-stale': {
      if (!args.asset) throw new UsageError('propagate-stale 需要 --asset <planning:id>');
      report = propagateStale(conn, args.asset, { fine: args.fine === true, dryRun });
      break;
    }
    case 'register-characters': {
      if (!args.project) throw new UsageError('register-characters 需要 --project <id>');
      report = registerCharactersRun(conn, {
        projectId: args.project,
        roster: loadJsonInput(args.roster),
        entries: loadJsonInput(args.entry),
        statusUpdate: loadJsonInput(args['status-update']),
        world: loadJsonInput(args.world),
      });
      break;
    }
    case 'commit-review': {
      if (!args.receipt) throw new UsageError('commit-review 需要 --receipt <file|内联JSON>');
      report = commitReview(conn, {
        receiptRaw: args.receipt, allowEmpty: args['allow-empty'] === true,
        checkHash: args['no-check-hash'] !== true, dryRun,
      });
      break;
    }
    case 'lock-asset': {
      if (!args.asset || !args.review) throw new UsageError('lock-asset 需要 --asset <planning:id> --review <review:id>');
      report = lockAsset(conn, { assetId: args.asset, reviewId: args.review, dryRun });
      break;
    }
    case 'accept-chapter': {
      if (!args.chapter || !args.review) throw new UsageError('accept-chapter 需要 --chapter <chapter:id> --review <review:id>');
      report = acceptChapter(conn, { chapterId: args.chapter, reviewId: args.review, dryRun });
      break;
    }
    case 'validate-asset': {
      report = validateAsset(conn, {
        assetId: args.asset, assetType: args['asset-type'], projectId: args.project,
        scopeRef: args['scope-ref'], scale: args.scale,
      });
      break;
    }
    default:
      throw new UsageError(`未知子命令：${sub}\n\n${usage()}`);
  }
  conn.close();

  for (const w of report.warns ?? []) console.log(w);
  for (const line of report.results ?? []) console.log(line);
  if (sub === 'validate-asset') {
    for (const w of report.warns ?? []) console.log(`WARN: ${w}`);
    if (report.errors.length > 0) {
      console.error(`FAIL（${report.errors.length} 处缺陷）:`);
      for (const e of report.errors) console.error(`  - ${e}`);
      process.exitCode = 1;
      return;
    }
    console.log(`PASS: ${report.asset_type} ${report.asset} 校验通过${report.scale ? `（scale=${report.scale}）` : ''}（WARN ${report.warns.length} 条）`);
  } else if (report.dryRun) {
    console.log('（dry-run 零写入；加 --commit 执行）');
  }
  if (args.json) console.log(JSON.stringify(report, null, 2));
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
    if (e instanceof GateFail) {
      console.error(`GATE FAIL（阻断，零写入）: ${e.message}`);
      process.exitCode = 1;
    } else if (e instanceof UsageError) {
      console.error(`${e.message}\n\n${usage()}`);
      process.exitCode = 2;
    } else {
      console.error(e && e.stack ? e.stack : String(e));
      process.exitCode = 2;
    }
  }
}
