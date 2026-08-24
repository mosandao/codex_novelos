/**
 * JS 写门 · 人物注册表幂等登记 + 状态迁移 + 对账（R2）。
 *
 * 与 legacy-python/scripts/novelos_register_characters.py 全量对齐移植：
 * 契约 roster 落库 / 动态配角 entry 登记 / 连续性状态迁移（BEGIN IMMEDIATE 单事务）
 * + 账本↔注册表对账 checkPendingStatus + 卷纲班底终核 checkAuditEntries。
 * characters 表（migration 018 重建）是人物状态的唯一锚点；幂等语义：
 * 同 (project_id, name) 已存在时只合并 role_class 与 state_json 补充字段，
 * **不覆盖** status/exit 字段（状态迁移只走连续性提取路径）。
 *
 * print → GateFail 判定（红队 F2 纪律：数据完整性/裁决类必须阻断，纯提示进 warns）：
 * - 项目不存在、roster/entry/status-update 校验 FAIL、seat_ref 引用不存在席位
 *   → GateFail 阻断（py 仅 print+非零退出，纸面化）；
 * - 对账漂移 DRIFT、卷纲班底未落表 → GateFail 阻断（novel-continuity 收尾门）；
 * - 近重名 WARN / 旧 roster 退役提醒 / 未认领承诺席位 WARN / 待登记入 world 设定
 *   → 保留为返回值 warns/pendingSettings（纯提示类）。
 *
 * 与 py 的有意偏离（均为安全方向，详见各函数注释）：
 * - py 对畸形 roster 缺 name 时 KeyError 崩溃 → 本实现防御性跳过；
 * - unicodedata casefold → String.toLowerCase（ß 类特殊折叠不展开）；
 * - state_json 损坏时按 {} 处理（py 直接崩溃）；
 * - jsonschema → Ajv2020，错误文案措辞不同（路径结构逐字对齐）。
 */
import { readFileSync } from 'node:fs'
// planning-candidate.schema.json $schema: draft 2020-12 —— 必须 Ajv2020；
// 子路径必须带 .js：pnpm 平铺 dist 无 exports map，'ajv/dist/2020' 会 ENOENT。
import Ajv2020 from 'ajv/dist/2020.js'
import type { DatabaseSync } from 'node:sqlite'
import { GateFail, newId } from './primitives.js'
import { pyJsonCompact } from './create-project.js'

// ---------------------------------------------------------------------------
// 常量与类型（py L73-75）
// ---------------------------------------------------------------------------

/** 人物状态六值（characters.status CHECK 同源） */
export const STATUS_VALUES = [
  'active', 'peripheral', 'dormant', 'departed', 'transformed', 'dead',
] as const

/** 退场八型（第七型死亡型为 dead 专用） */
export const EXIT_TYPES = [
  '完成型', '迁移型', '转化型', '关系型', '功能转移型', '休眠型', '死亡型',
] as const

/** 携带退场痕迹的状态子集 */
export const EXIT_STATUSES = ['departed', 'transformed', 'dormant', 'dead'] as const

export type JsonObj = Record<string, any>

/** py --roster 条目（planning-candidate.schema.json $defs/character_roster） */
export interface RosterItem extends JsonObj {
  name: string
  role_class: 'main' | 'secondary'
  arc_role: string
  登场卷: number
  预期退场: string
  seat_ref?: string
  essence?: string
}

/** py --entry 条目：动态配角/卷纲班底；其余键随 state_json 整体落库 */
export type EntryItem = JsonObj & {
  name: string
  role_class?: 'minor' | 'secondary' | 'main'
  first_chapter_id?: string | null
}

/** py --status-update 条目（连续性 character_status 晋升后提交） */
export interface StatusUpdateItem extends JsonObj {
  name: string
  status: (typeof STATUS_VALUES)[number]
  exit_type?: (typeof EXIT_TYPES)[number] | null
  exit_chapter_id?: string | null
}

// ---------------------------------------------------------------------------
// 基础设施
// ---------------------------------------------------------------------------

/** py datetime.now().strftime("%Y-%m-%d %H:%M:%S") —— 本地时间状态史审计戳 */
function nowStamp(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} `
    + `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

/**
 * py: _norm_name —— 近重名归一化：NFKC（全半角/组合字符）+ 去全部空白 + 折叠大小写。
 * 语义判级仍是 LLM 审查职责，这里只拦机器可判的归一化撞名。
 * （casefold ≈ toLowerCase；ß→ss 类特例不展开，方向安全。）
 */
export function normName(name: string): string {
  return String(name ?? '').normalize('NFKC').replace(/\s+/gu, '').toLowerCase()
}

/** characters.state_json 容错解析（py `json.loads(x or "{}")`；损坏按 {} 兜底） */
function parseStateJson(text: string | null | undefined): JsonObj {
  try {
    const v = JSON.parse(text || '{}')
    return typeof v === 'object' && v !== null && !Array.isArray(v) ? v : {}
  } catch {
    return {}
  }
}

/** ajv 校验函数最小结构面（避免依赖 ajv 内部类型布局） */
interface SchemaValidator {
  (data: unknown): boolean
  errors?: Array<{
    instancePath: string
    message?: string
    params?: { additionalProperty?: string }
  }> | null
}

const rosterAjv = new Ajv2020({ allErrors: true })

const rosterSchemaCache = new Map<string, SchemaValidator>()

/**
 * py: SCHEMA_PATH + sub = schema["$defs"]["character_roster"]; sub["$schema"] = draft/2020-12
 * —— 从 planning-candidate.schema.json 抽取 character_roster 子模式编译（进程内缓存）。
 */
export function loadRosterValidator(schemasDir: string): SchemaValidator {
  const key = `${schemasDir}/planning-candidate.schema.json`
  let v = rosterSchemaCache.get(key)
  if (!v) {
    const schema = JSON.parse(readFileSync(key, 'utf8'))
    const sub = schema['$defs']['character_roster']
    sub['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
    v = rosterAjv.compile(sub)
    rosterSchemaCache.set(key, v)
  }
  return v
}

// ---------------------------------------------------------------------------
// 校验层（py L82-134）—— 只收集错误清单，统一由 registerCharactersRun 裁决
// ---------------------------------------------------------------------------

/**
 * py: _validate_roster —— 按 planning-candidate $defs/character_roster 校验。
 * 路径格式逐字对齐："/".join(absolute_path) or "<root>"（无前导斜杠）。
 */
export function validateRoster(roster: unknown, schemasDir: string): string[] {
  const validate = loadRosterValidator(schemasDir)
  if (validate(roster)) return []
  return validate.errors!.map((e) => {
    const path = e.instancePath.replace(/^\//, '') || '<root>'
    // py jsonschema 的 additionalProperties 错误消息含违规键名（"'zzz' is not allowed"）——
    // ajv 把键名放在 params，这里补回保持信息量对齐；错误路径两者都锚定在对象本身。
    const extra = e.params?.additionalProperty
    const message = extra ? `${e.message} (${extra})` : e.message
    return `roster[${path}]: ${message}`
  })
}

/** py: _validate_entries —— 动态配角条目手写校验（name/role_class/预期退场/来源卷） */
export function validateEntries(entries: JsonObj[]): string[] {
  const errors: string[] = []
  entries.forEach((e, i) => {
    const name = e?.['name']
    if (typeof name !== 'string' || !name.trim()) {
      errors.push(`entry[${i}]: name 非空必填`)
    }
    const rc = e?.['role_class'] ?? 'secondary'
    if (!(rc === 'minor' || rc === 'secondary' || rc === 'main')) {
      errors.push(`entry[${i}]: role_class 非法 ${JSON.stringify(rc)}`)
    }
    const et = e?.['预期退场']
    if (et != null && !(EXIT_TYPES as readonly string[]).includes(et) && et !== '持续活跃') {
      errors.push(`entry[${i}]: 预期退场非法 ${JSON.stringify(et)}（${EXIT_TYPES.join(', ')} 或 持续活跃）`)
    }
    const vol = e?.['来源卷']
    if (vol != null && !(typeof vol === 'number' && Number.isInteger(vol) && 1 <= vol && vol <= 99)) {
      errors.push(`entry[${i}]: 来源卷须为 1-99 整数，got ${JSON.stringify(vol)}`)
    }
  })
  return errors
}

/**
 * py: _validate_status_update —— status 非法即短路返回（后续规则无从谈起）；
 * dead 必须带 死亡型；非退场状态不得携带 exit_type（复活会整体清空退场痕迹）。
 */
export function validateStatusUpdate(update: JsonObj): string[] {
  const errors: string[] = []
  const name = update?.['name']
  if (typeof name !== 'string' || !name.trim()) {
    errors.push('status-update: name 非空必填')
  }
  const status = update?.['status']
  if (!(STATUS_VALUES as readonly string[]).includes(status)) {
    errors.push(`status-update: status 非法 ${JSON.stringify(status)}（${STATUS_VALUES.join(', ')}）`)
    return errors // 与 py 相同：status 非法时短路
  }
  const et = update?.['exit_type']
  if (et != null && !(EXIT_TYPES as readonly string[]).includes(et)) {
    errors.push(`status-update: exit_type 非法 ${JSON.stringify(et)}（${EXIT_TYPES.join(', ')}）`)
  }
  if (status === 'dead' && et !== '死亡型') {
    errors.push('status-update: status=dead 时 exit_type 必须为 死亡型')
  }
  if (!(EXIT_STATUSES as readonly string[]).includes(status) && et != null) {
    errors.push(
      `status-update: status=${JSON.stringify(status)} 是非退场状态，不应携带 exit_type`
      + '（复活/回归会整体清空退场痕迹）',
    )
  }
  return errors
}

// ---------------------------------------------------------------------------
// 预检对账（py L137-195）—— 事务外执行，只产 WARN/ERROR 清单
// ---------------------------------------------------------------------------

/**
 * py: _near_dup_warns —— 登记名 vs 在库名 + 批内的归一化撞名
 * （原始名不同才算——完全同名走幂等合并不告警）。
 */
export function nearDupWarns(conn: DatabaseSync, projectId: string, incoming: JsonObj[]): string[] {
  const warns: string[] = []
  const existing = new Map<string, string>()
  for (const r of conn.prepare('SELECT name FROM characters WHERE project_id = ?')
    .all(projectId) as Array<{ name: string }>) {
    existing.set(normName(r.name), r.name)
  }
  const batch = new Map<string, string>()
  for (const item of incoming) {
    const raw = String(item?.['name'] ?? '')
    const norm = normName(raw)
    if (!norm) continue
    const hit = existing.get(norm)
    if (hit !== undefined && hit !== raw) {
      warns.push(`WARN 近重名：${JSON.stringify(raw)} 与在库人物 ${JSON.stringify(hit)} 归一化后相同`
        + '（全半角/空白/大小写）——确认是否笔误')
    } else if (batch.has(norm) && batch.get(norm) !== raw) {
      warns.push(`WARN 批内近重名：${JSON.stringify(raw)} 与 ${JSON.stringify(batch.get(norm))} 归一化后相同——确认是否笔误`)
    }
    if (!batch.has(norm)) batch.set(norm, raw)
  }
  return warns
}

/**
 * py: _seat_reconciliation —— world_contract 席位对账：
 * 引用存在性（error，F2 阻断类）+ 写库后未认领承诺席位清单（warn 提示类）。
 * 在库 claimed 扫描在事务前执行，incoming 的 seat_ref 由调用方手工并入。
 */
export function seatReconciliation(
  conn: DatabaseSync,
  projectId: string,
  world: JsonObj,
  incoming: JsonObj[],
): { errors: string[]; warns: string[] } {
  const seats: JsonObj[] = Array.isArray(world?.['seats']) ? world['seats'] : []
  const seatNames = new Set<string>(seats.filter((s) => s?.['name']).map((s) => String(s['name'])))
  const errors: string[] = []
  for (const item of incoming) {
    const ref = item?.['seat_ref']
    if (ref && !seatNames.has(ref)) {
      errors.push(`${item?.['name'] ?? '?'}.seat_ref 引用不存在的席位: ${JSON.stringify(ref)}`)
    }
  }
  const claimed = new Set<string>()
  for (const r of conn.prepare('SELECT state_json FROM characters WHERE project_id = ?')
    .all(projectId) as Array<{ state_json: string }>) {
    const ref = parseStateJson(r.state_json)?.['seat_ref']
    if (ref) claimed.add(String(ref))
  }
  for (const item of incoming) {
    if (item?.['seat_ref']) claimed.add(String(item['seat_ref']))
  }
  const warns = seats
    .filter((s) => s?.['name']
      && (s['disposition'] === '待契约认领' || s['disposition'] === '待卷级班底')
      && !claimed.has(String(s['name'])))
    .map((s) => `WARN 席位「${s['name']}」world 标注「${s['disposition']}」但注册表尚无认领人`)
  return { errors, warns }
}

// ---------------------------------------------------------------------------
// 幂等落库原语（py L198-266）
// ---------------------------------------------------------------------------

/**
 * py: _upsert —— 幂等登记：新建 status='active'；已存在则只合并 role_class 与
 * state_json 补充字段，first_chapter_id 仅在新值非空时回填（COALESCE），
 * **不触碰** status/exit 字段。ID 格式 character:<uuid>。
 */
export function upsertCharacter(
  conn: DatabaseSync,
  projectId: string,
  name: string,
  roleClass: string,
  statePatch: JsonObj,
  firstChapterId: string | null = null,
): string {
  const existing = conn.prepare(
    'SELECT id, state_json FROM characters WHERE project_id = ? AND name = ?',
  ).get(projectId, name) as { id: string; state_json: string } | undefined
  if (existing === undefined) {
    const charId = newId('character')
    conn.prepare(
      "INSERT INTO characters (id, project_id, name, role_class, status, "
      + "state_json, first_chapter_id) VALUES (?, ?, ?, ?, 'active', ?, ?)",
    ).run(charId, projectId, name, roleClass, pyJsonCompact(statePatch), firstChapterId)
    return charId
  }
  const state = parseStateJson(existing.state_json)
  Object.assign(state, statePatch)
  conn.prepare(
    'UPDATE characters SET role_class = ?, state_json = ?, '
    + "first_chapter_id = COALESCE(?, first_chapter_id), updated_at = CURRENT_TIMESTAMP "
    + 'WHERE id = ?',
  ).run(roleClass, pyJsonCompact(state), firstChapterId, existing.id)
  return existing.id
}

/**
 * py: _apply_status_update —— 单条状态迁移：状态史审计追加 +
 * 退场痕迹对称维护（非退场状态整体清空 exit 字段，不留半截记录；
 * 退场状态 exit_chapter_id 仅在新值非空时回填）。人物未登记时按 minor 补建。
 */
export function applyStatusUpdate(conn: DatabaseSync, projectId: string, upd: StatusUpdateItem): string {
  const row = conn.prepare(
    'SELECT id, status, exit_type, state_json FROM characters '
    + 'WHERE project_id = ? AND name = ?',
  ).get(projectId, upd['name']) as
    | { id: string; status: string; exit_type: string | null; state_json: string }
    | undefined
  let charId: string
  let oldStatus: string
  let state: JsonObj
  if (row === undefined) {
    // 连续性提名的状态人物可能尚未登记（动态配角漏登记）——按 minor 补建
    charId = upsertCharacter(
      conn, projectId, upd['name'], 'minor',
      { '补登': '连续性状态迁移先于登记' }, upd['exit_chapter_id'] ?? null,
    )
    oldStatus = 'active'
    state = { '补登': '连续性状态迁移先于登记' }
  } else {
    charId = row.id
    oldStatus = row.status
    state = parseStateJson(row.state_json)
  }
  const history: unknown[] = Array.isArray(state['状态史']) ? state['状态史'] : []
  history.push({
    from: oldStatus,
    to: upd['status'],
    exit_type: upd['exit_type'] ?? null,
    chapter_id: upd['exit_chapter_id'] ?? null,
    at: nowStamp(),
  })
  state['状态史'] = history
  const stateJson = pyJsonCompact(state)
  if ((EXIT_STATUSES as readonly string[]).includes(upd['status'])) {
    conn.prepare(
      'UPDATE characters SET status = ?, exit_type = ?, '
      + 'exit_chapter_id = COALESCE(?, exit_chapter_id), state_json = ?, '
      + 'updated_at = CURRENT_TIMESTAMP WHERE id = ?',
    ).run(upd['status'], upd['exit_type'] ?? null, upd['exit_chapter_id'] ?? null, stateJson, charId)
  } else {
    // 复活/回归：退场痕迹整体清空，不留有 exit_chapter_id 无 exit_type 的半截记录
    conn.prepare(
      'UPDATE characters SET status = ?, exit_type = NULL, '
      + 'exit_chapter_id = NULL, state_json = ?, '
      + 'updated_at = CURRENT_TIMESTAMP WHERE id = ?',
    ).run(upd['status'], stateJson, charId)
  }
  return `status ${upd['name']} ${oldStatus} -> ${upd['status']}`
}

// ---------------------------------------------------------------------------
// 主入口（py run L332-413）：预检 → BEGIN IMMEDIATE 单事务 → COMMIT/ROLLBACK
// ---------------------------------------------------------------------------

export interface RegisterRunInput {
  projectId: string
  /** character_contract 锁定的 metadata.character_roster 数组（schema 见 planning-candidate $defs/character_roster） */
  roster?: RosterItem[] | null
  /** 动态配角登记，单对象或数组（py --entry；单对象由本函数归一为数组） */
  entries?: EntryItem | EntryItem[] | null
  /** 连续性状态迁移，单对象或数组（py --status-update） */
  statusUpdate?: StatusUpdateItem | StatusUpdateItem[] | null
  /** world_contract metadata——启用席位对账 */
  world?: JsonObj | null
  /** config/schemas 目录（roster 结构校验必需） */
  schemasDir?: string | null
}

export interface RegisterRunResult {
  /** py stdout 行：`roster 名 -> character:x` / `entry ...` / `status 名 a -> b` */
  results: string[]
  /** WARN 行（近重名 / 旧 roster 退役提醒 / 未认领承诺席位），纯提示不阻断 */
  warns: string[]
}

/**
 * py: run() 全量移植。校验 FAIL / 项目不存在 → GateFail（未开事务零写入）；
 * 通过后 BEGIN IMMEDIATE 内依序 roster→entries→updates 落库，异常 ROLLBACK 原样上抛。
 * 至少一项输入必须提供（py argparse 互斥守卫）。
 */
export function registerCharactersRun(conn: DatabaseSync, input: RegisterRunInput): RegisterRunResult {
  const projectId = input.projectId
  const proj = conn.prepare('SELECT id FROM projects WHERE id = ?').get(projectId)
  if (proj === undefined) throw new GateFail(`项目不存在: ${projectId}`)

  // py main() 归一化：单对象 → 数组
  const updates: StatusUpdateItem[] | null = input.statusUpdate == null
    ? null
    : Array.isArray(input.statusUpdate) ? [...input.statusUpdate] : [input.statusUpdate]
  const entryList: EntryItem[] | null = input.entries == null
    ? null
    : Array.isArray(input.entries) ? [...input.entries] : [input.entries]
  const rosterList: RosterItem[] | null = input.roster ?? null
  if (rosterList == null && entryList == null && updates == null) {
    throw new GateFail('至少提供 roster / entry / statusUpdate 之一（对账用 pendingStatus / auditEntries 入口）')
  }

  const warns: string[] = []
  const errors: string[] = []
  const incoming: JsonObj[] = [...(rosterList ?? []), ...(entryList ?? [])]

  warns.push(...nearDupWarns(conn, projectId, incoming))
  if (input.world != null && incoming.length > 0) {
    const seat = seatReconciliation(conn, projectId, input.world, incoming)
    errors.push(...seat.errors)
    warns.push(...seat.warns)
  }

  if (rosterList != null) {
    if (!input.schemasDir) {
      throw new GateFail('config/schemas 目录未找到（roster 结构校验必需）')
    }
    errors.push(...validateRoster(rosterList, input.schemasDir))
    // 重锁对账：曾在旧 roster（state_json 带 arc_role）但不在新 roster 的人物
    const rosterNames = new Set(
      rosterList.map((item) => item?.['name']).filter((n): n is string => typeof n === 'string'),
    )
    const wasRostered = new Set<string>()
    for (const r of conn.prepare('SELECT name, state_json FROM characters WHERE project_id = ?')
      .all(projectId) as Array<{ name: string; state_json: string }>) {
      if ('arc_role' in parseStateJson(r.state_json)) wasRostered.add(r.name)
    }
    for (const name of [...wasRostered].filter((n) => !rosterNames.has(n)).sort()) {
      warns.push(
        `WARN 人物「${name}」曾在旧契约 roster 但不在新 roster——若契约修订`
        + '删除了该人物，用 --status-update 退役（休眠型/迁移型）；若误删请补回',
      )
    }
  }
  if (entryList != null) errors.push(...validateEntries(entryList))
  if (updates != null) {
    for (const upd of updates) errors.push(...validateStatusUpdate(upd))
  }
  if (errors.length > 0) {
    // F2 纪律：FAIL 必须阻断。此时事务尚未开启，零写入。
    throw new GateFail(
      `人物登记校验未通过（${errors.length} 处 FAIL，未开事务零写入）：\n`
      + errors.map((e) => `FAIL ${e}`).join('\n'),
    )
  }

  const results: string[] = []
  conn.exec('PRAGMA foreign_keys = ON')
  conn.exec('BEGIN IMMEDIATE')
  try {
    for (const item of rosterList ?? []) {
      const patch: JsonObj = {
        'arc_role': item['arc_role'],
        '预期退场': item['预期退场'],
        '登场卷': item['登场卷'],
      }
      for (const extra of ['seat_ref', 'essence'] as const) {
        if (item[extra]) patch[extra] = item[extra]
      }
      const charId = upsertCharacter(conn, projectId, item['name'], item['role_class'], patch)
      results.push(`roster ${item['name']} -> ${charId}`)
    }
    for (const item of entryList ?? []) {
      const patch: JsonObj = Object.fromEntries(
        Object.entries(item).filter(([k]) => k !== 'name' && k !== 'role_class'),
      )
      const charId = upsertCharacter(
        conn, projectId, item['name'], item['role_class'] ?? 'secondary',
        patch, item['first_chapter_id'] ?? null,
      )
      results.push(`entry ${item['name']} -> ${charId}`)
    }
    for (const upd of updates ?? []) {
      results.push(applyStatusUpdate(conn, projectId, upd))
    }
    conn.exec('COMMIT')
  } catch (e) {
    conn.exec('ROLLBACK')
    throw e
  }
  return { results, warns }
}

// ---------------------------------------------------------------------------
// 账本↔注册表对账（py check_pending_status L269-329）——只读
// ---------------------------------------------------------------------------

export interface PendingStatusReport {
  /** 对账通过的人物数（含候选为空的平凡通过=0） */
  checked: number
  /** 库中无 continuity_candidate_sets 表时的跳过说明（py 返回 0 的跳过路径） */
  note?: string
}

/**
 * py: check_pending_status —— promoted 候选集中每人物**最新** character_status 候选
 * vs 注册表现状（历史迁移被后续超越是正常推进，不算漂移）。
 * 项目不存在或发现漂移 → GateFail 阻断（F2：对账门不得纸面化，
 * novel-continuity 收尾必须处理完漂移才开下一章）。
 */
export function checkPendingStatus(conn: DatabaseSync, projectId: string): PendingStatusReport {
  const proj = conn.prepare('SELECT id FROM projects WHERE id = ?').get(projectId)
  if (proj === undefined) throw new GateFail(`项目不存在: ${projectId}`)

  let sets: Array<{ id: string; cand_json: string }>
  try {
    sets = conn.prepare(
      'SELECT s.id, CAST(r.content AS TEXT) AS cand_json '
      + 'FROM continuity_candidate_sets s '
      + 'JOIN resources r ON r.id = s.candidate_resource_id '
      + "WHERE s.project_id = ? AND s.status = 'promoted' "
      + 'ORDER BY s.created_at, s.id',
    ).all(projectId) as Array<{ id: string; cand_json: string }>
  } catch {
    return { checked: 0, note: '对账跳过：库中无 continuity_candidate_sets 表。' }
  }

  const latest = new Map<string, { status: string; set: string }>()
  for (const { id: setId, cand_json } of sets) {
    let candidates: unknown[]
    try {
      const parsed = JSON.parse(cand_json)
      candidates = Array.isArray(parsed?.['candidates']) ? parsed['candidates'] : []
    } catch {
      continue
    }
    for (const c of candidates) {
      const item = c as { type?: unknown; name?: unknown; status?: unknown }
      if (item.type === 'character_status' && typeof item.name === 'string' && item.name !== '') {
        latest.set(item.name, { status: String(item.status ?? ''), set: setId })
      }
    }
  }
  if (!latest.size) return { checked: 0 } // 对账通过：promoted 候选集中无 character_status 候选

  const drift: string[] = []
  for (const [name, want] of [...latest.entries()].sort(([a], [b]) => (a < b ? -1 : 1))) {
    const row = conn.prepare(
      'SELECT status FROM characters WHERE project_id = ? AND name = ?',
    ).get(projectId, name) as { status: string } | undefined
    if (row === undefined) {
      drift.push(`DRIFT ${name}：候选 ${want.status}（${want.set}）但注册表未登记`)
    } else if (row.status !== want.status) {
      drift.push(`DRIFT ${name}：候选 ${want.status}（${want.set}）≠ 注册表 ${row.status}`)
    }
  }
  if (drift.length > 0) {
    throw new GateFail(
      drift.join('\n')
      + `\n对账发现 ${drift.length} 处漂移——漏跑 --status-update 或迁移被回滚，处理完再继续后续章节。`,
    )
  }
  return { checked: latest.size }
}

// ---------------------------------------------------------------------------
// 卷纲班底落表终核（py check_audit_entries L416-471）——只读
// ---------------------------------------------------------------------------

export interface AuditEntriesReport {
  /** locked 卷纲 scope 数 */
  volumes: number
  /** 班底条目总数 */
  entries: number
  /** volume_settings 中 disposition=登记入world 的待登记提示（WARN 纯提示类） */
  pendingSettings: string[]
}

/**
 * py: check_audit_entries（T39）—— locked 卷纲的 volume_characters 逐名对注册表，
 * 每 scope 取最新 revision。漏登记 → GateFail 阻断（卷纲锁定后班底必须落注册表，
 * 执行卡「卷纲已登记」引用才不悬空）；待登记入 world 的设定仅列为 pendingSettings。
 */
export function checkAuditEntries(conn: DatabaseSync, projectId: string): AuditEntriesReport {
  const proj = conn.prepare('SELECT id FROM projects WHERE id = ?').get(projectId)
  if (proj === undefined) throw new GateFail(`项目不存在: ${projectId}`)

  const rows = conn.prepare(
    'SELECT scope_ref, revision, metadata_json FROM planning_assets '
    + "WHERE project_id = ? AND asset_type = 'volume_outline' AND status = 'locked' "
    + 'ORDER BY scope_ref, revision',
  ).all(projectId) as Array<{ scope_ref: string; revision: number; metadata_json: string | null }>

  const latest = new Map<string, { revision: number; meta: JsonObj }>()
  for (const r of rows) {
    const cur = latest.get(r.scope_ref)
    if (cur === undefined || Number(r.revision) > cur.revision) {
      latest.set(r.scope_ref, { revision: Number(r.revision), meta: parseStateJson(r.metadata_json) })
    }
  }

  const missing: string[] = []
  const pendingSettings: string[] = []
  let nEntries = 0
  for (const [scope, { meta }] of [...latest.entries()].sort(([a], [b]) => (a < b ? -1 : 1))) {
    const chars = Array.isArray(meta['volume_characters']) ? meta['volume_characters'] : []
    for (const p of chars) {
      nEntries++
      const name = p?.['name']
      const hit = conn.prepare(
        'SELECT 1 FROM characters WHERE project_id = ? AND name = ?',
      ).get(projectId, name)
      if (hit === undefined) {
        missing.push(`卷纲[${scope}] 班底 ${JSON.stringify(name)} 未入注册表——漏跑 --entry`)
      }
    }
    const settings = Array.isArray(meta['volume_settings']) ? meta['volume_settings'] : []
    for (const s of settings) {
      if (s?.['disposition'] === '登记入world') {
        pendingSettings.push(`卷纲[${scope}] 设定 ${s['name']}（${s['kind']}）待登记入 world`)
      }
    }
  }
  if (missing.length > 0) {
    throw new GateFail(
      `FAIL（${missing.length} 处班底未落表）:\n`
      + missing.map((m) => `  - ${m}`).join('\n'),
    )
  }
  return { volumes: latest.size, entries: nEntries, pendingSettings }
}
