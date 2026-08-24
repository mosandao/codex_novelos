/**
 * JS 写门 · 项目创建固化管线（R2）。
 *
 * 与 legacy-python/scripts/novelos_create_project.py 全量对齐移植：
 * 入口校验（ajv + 词表级联）→ 内核候选门 → 内核落库 → 分身候选门 → 单事务六表落库。
 *
 * 对 py 版的一处**有意偏离**（红队 F2 整改）：
 * py main() 在 parent_rationale 含错配标记时仅打印提示仍继续落库（纸面化裁决门）；
 * 本实现 checkMismatchAdjudication 默认抛 GateFail 阻断，
 * 仅当调用方传入显式用户裁决（userAdjudicated=true）才放行。
 *
 * 红线：任何 FAIL 必须阻断；禁止手工 SQL 绕过本门写库。
 */
import { readFileSync } from 'node:fs'
// config/schemas 全部 $schema: draft 2020-12 —— 必须用 Ajv2020，普通 Ajv 不识别该 meta-schema。
// 注意子路径必须带 .js：本仓库 pnpm 布局的 ajv 是平铺 dist（dist/2020.js），
// Node ESM 对无 exports map 的包按文件路径解析，'ajv/dist/2020' 会 ENOENT。
import Ajv2020 from 'ajv/dist/2020.js'
import type { DatabaseSync } from 'node:sqlite'
import {
  GateFail,
  contentHash,
  lookupKernelVersion,
  newId,
  MISMATCH_MARKERS,
} from './primitives.js'

/** ajv 校验函数最小结构面（避免依赖 ajv 内部类型布局） */
interface SchemaValidator {
  (data: unknown): boolean
  errors?: Array<{ instancePath: string; message?: string }> | null
}

// ---------------------------------------------------------------------------
// 常量（py L66-88）
// ---------------------------------------------------------------------------

export const SCALES = [
  '短篇（30万字以下）',
  '中篇（30-100万字）',
  '长篇（100-300万字）',
  '超长篇（300万字以上）',
] as const

export const SIGNATURE_FIELDS = [
  'sympathies',
  'distrusts',
  'recurring_attention',
  'narrative_principles',
  'forbidden_conveniences',
  'expression_preferences',
  'negative_constraints',
] as const

/** 内核 identity 中可与分身七字段发生逐字复制的清单字段 */
export const KERNEL_IDENTITY_LIST_FIELDS = [
  'core_questions',
  'value_axioms',
  'aesthetic_commitments',
  'creative_axioms',
] as const

export type JsonObj = Record<string, any>

// ---------------------------------------------------------------------------
// 基础设施
// ---------------------------------------------------------------------------

const ajv = new Ajv2020({ allErrors: false })

const schemaCache = new Map<string, SchemaValidator>()

/** 加载并编译 config/schemas 下的 JSON Schema（进程内缓存） */
export function loadSchema(schemasDir: string, name: string): SchemaValidator {
  const key = `${schemasDir}/${name}`
  let v = schemaCache.get(key)
  if (!v) {
    const schema = JSON.parse(readFileSync(key, 'utf8'))
    v = ajv.compile(schema)
    schemaCache.set(key, v)
  }
  return v
}

/**
 * py: load_wizard_data —— 从 project-wizard-data.js 提取首 { 到尾 } 的 JSON。
 * 该文件是 `window.NOVELOS_WIZARD_DATA = {...}` 形态的静态权威词表。
 */
export function loadWizardData(file: string): JsonObj {
  const raw = readFileSync(file, 'utf8')
  return JSON.parse(raw.slice(raw.indexOf('{'), raw.lastIndexOf('}') + 1))
}

/**
 * 与 Python json.dumps(obj, ensure_ascii=False, indent=2) 字节级对齐：
 * 键序保持插入序、UTF-8 原文、两空格缩进、无尾随空白。
 * hash 兼容性依赖此函数——改动前必须跑等价迁移测试。
 * 已知分歧（规格 §风险1，接受）：浮点 1.0↔1、>2^53 大整数、\uXXXX 转义策略。
 */
export function pyJson(obj: unknown): string {
  return JSON.stringify(obj, null, 2)
}

/** Python json.dumps 默认紧凑风格：键值间带空格 `{"a": 1, "b": [1, 2]}`（metadata_json 用） */
export function pyJsonCompact(obj: unknown): string {
  if (obj === null || typeof obj === 'string' || typeof obj === 'number' || typeof obj === 'boolean') {
    return JSON.stringify(obj)
  }
  if (Array.isArray(obj)) return '[' + obj.map(pyJsonCompact).join(', ') + ']'
  return '{' + Object.entries(obj as JsonObj)
    .map(([k, v]) => `${JSON.stringify(k)}: ${pyJsonCompact(v)}`)
    .join(', ') + '}'
}

/** 键序无关深比较（py == 对 dict 的语义）；词表 CJK 匹配不做任何归一化 */
export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((v, i) => deepEqual(v, b[i]))
  }
  if (typeof a === 'object' && typeof b === 'object' && a !== null && b !== null) {
    const ka = Object.keys(a as object)
    const kb = Object.keys(b as object)
    if (ka.length !== kb.length) return false
    return ka.every((k) => deepEqual((a as JsonObj)[k], (b as JsonObj)[k]))
  }
  return false
}

// ---------------------------------------------------------------------------
// 入口校验（py validate_request L259-365）
// ---------------------------------------------------------------------------

export interface Verdict {
  errors: string[]
  warns: string[]
}

/**
 * py: validate_request —— 入口校验（E0 结构层是唯一短路点；E1.. 累加不短路）。
 * schemasDir 必填：config/schemas 目录（Draft 2020-12，Ajv2020 编译）。
 */
export function validateRequest(
  payload: JsonObj,
  wizard: JsonObj,
  conn: DatabaseSync,
  schemasDir: string,
): Verdict {
  const errors: string[] = []
  const warns: string[] = []

  // E0 结构校验
  {
    const validate = loadSchema(schemasDir, 'project-create-request.schema.json')
    if (!validate(payload)) {
      const e = validate.errors![0]
      const path = e.instancePath || '<root>'
      errors.push(`结构校验 FAIL [${path}]: ${e.message}`)
      return { errors, warns } // 结构坏了，后续词表校验无意义
    }
  }

  const s = payload['setup']
  const ch: string = s['channel']

  // 词表级联
  const platforms = wizard['channels']?.[ch]?.platforms
  if (!platforms || !platforms.includes(s['platform'])) {
    errors.push(`platform=${JSON.stringify(s['platform'])} 不属于 ${ch} 平台列表 ${JSON.stringify(platforms ?? [])}`)
  }
  const pt = wizard['platform_traits']?.[s['platform']]
  if (pt != null && !deepEqual(s['platform_traits'], pt)) {
    errors.push('platform_traits 与词表快照不一致（伪造或数据旧版）')
  }
  if (!(SCALES as readonly string[]).includes(s['scale'])) {
    errors.push(`scale=${JSON.stringify(s['scale'])} 非四档之一`)
  }
  let genres: string[] = wizard['genres']?.[ch] ?? []
  if (!Array.isArray(genres)) genres = Object.keys(genres)
  if (!genres.includes(s['primary_genre'])) {
    errors.push(`primary_genre=${JSON.stringify(s['primary_genre'])} 不在 ${ch} 题材库`)
  }
  const sdMap = wizard['secondary_directions']?.[ch]
  const sdList: string[] = (sdMap && typeof sdMap === 'object' && !Array.isArray(sdMap))
    ? (sdMap[s['primary_genre']] ?? [])
    : []
  const unknown = (s['secondary_directions'] as string[]).filter((d) => !sdList.includes(d))
  if (unknown.length) {
    warns.push(`secondary_directions 超出词表（${JSON.stringify(unknown)}）——自由发挥或词表需更新`)
  }

  // 表里基调
  const pool = new Map<string, string>()
  for (const t of wizard['tone_pools']?.[ch] ?? []) pool.set(t.value, t.pole)
  const badSurface = (s['emotional_surface'] as string[]).filter((v) => !pool.has(v))
  if (badSurface.length) {
    errors.push(`emotional_surface 不在 ${ch} 基调池: ${JSON.stringify(badSurface)}`)
  }
  const poles = (s['emotional_surface'] as string[])
    .filter((v) => pool.has(v))
    .map((v) => pool.get(v)!)
  if (poles.includes('light') && poles.includes('dark')) {
    errors.push(`emotional_surface 同层 light+dark 互斥: ${
      (s['emotional_surface'] as string[]).map((v, i) => [v, poles[i]])
    }`)
  }
  if (!pool.has(s['emotional_core'])) {
    errors.push(`emotional_core=${JSON.stringify(s['emotional_core'])} 不在 ${ch} 基调池`)
  }
  if ((s['emotional_surface'] as string[]).includes(s['emotional_core'])) {
    errors.push('emotional_core 与 surface 重复')
  }

  // 美学
  const badAes = (s['aesthetic_styles'] as string[]).filter(
    (a) => !(wizard['aesthetic_styles'] as string[]).includes(a),
  )
  if (badAes.length) {
    errors.push(`aesthetic_styles 超出词表: ${JSON.stringify(badAes)}`)
  }

  // 题材信息包快照核对
  const gp = wizard['genre_profiles']?.[`${ch}|${s['primary_genre']}`]
  if (s['genre_profile'] == null && gp != null) {
    warns.push('genre_profile=null 但词表已有该题材包，快照漏带')
  }
  if (s['genre_profile'] != null && !deepEqual(s['genre_profile'], gp)) {
    errors.push('genre_profile 与词表快照不一致')
  }

  const ak = s['author_kernel']
  if (ak['mode'] === 'select') {
    const row = lookupKernelVersion(conn, ak['kernel_version_id'])
    if (row == null) {
      errors.push(`kernel_version_id=${JSON.stringify(ak['kernel_version_id'])} 库中不存在`)
    } else {
      if (row.ownership !== 'author_kernel') {
        errors.push(`kernel_version_id 指向 ownership=${row.ownership} 的版本——只能绑定 author_kernel 内核`)
      }
      if (row.status !== 'active') {
        errors.push(`内核 profile status=${row.status}，非 active`)
      }
      if (row.subject_hash !== ak['subject_hash']) {
        errors.push('内核 subject_hash 与库内反查不符')
      }
      if (ak['display_name'] && ak['display_name'] !== row.display_name) {
        warns.push(`内核 display_name 与库不符（库内 ${JSON.stringify(row.display_name)}）`)
      }
      const newest = conn.prepare(
        'SELECT MAX(revision) FROM creator_profile_versions WHERE profile_id = ?',
      ).get(row.profile_id)![0] as number | null
      if (newest != null && newest > row.revision) {
        warns.push(`绑定的内核版本非最新（绑定 r${row.revision}，最新 r${newest}）——确认是沿用旧版还是改绑新版`)
      }
    }
  } else {
    warns.push(...kernelHintsDupWarnings(conn, ak['kernel_hints'] ?? {}))
    warns.push(...orphanKernelWarnings(conn))
  }

  return { errors, warns }
}

// ---------------------------------------------------------------------------
// create 模式防近重复 / 孤儿内核警告（py L196-256）
// ---------------------------------------------------------------------------

function hintLines(hints: JsonObj): Set<string> {
  const lines = new Set<string>()
  for (const v of Object.values(hints)) {
    if (Array.isArray(v)) for (const x of v) if (String(x).trim()) lines.add(String(x).trim())
  }
  return lines
}

export function kernelHintsDupWarnings(conn: DatabaseSync, hints: JsonObj): string[] {
  const newLines = hintLines(hints)
  if (!newLines.size) return []
  let rows: Array<{ display_name: string; deriv_json: string }>
  try {
    rows = conn.prepare(
      "SELECT p.display_name, CAST(r.content AS TEXT) AS deriv_json "
      + 'FROM creator_profiles p '
      + 'JOIN creator_profile_versions v ON v.profile_id = p.id '
      + 'JOIN resources r ON r.id = v.derivation_resource_id '
      + "WHERE p.ownership = 'author_kernel'",
    ).all() as any
  } catch {
    return []
  }
  const best = new Map<string, number>()
  for (const { display_name, deriv_json } of rows) {
    let snap: JsonObj
    try {
      snap = JSON.parse(deriv_json)?.user_input_snapshot ?? {}
    } catch {
      continue
    }
    const old = hintLines(snap?.author_kernel?.kernel_hints ?? {})
    if (!old.size) continue
    let inter = 0
    for (const l of newLines) if (old.has(l)) inter++
    const union = new Set([...newLines, ...old]).size
    const overlap = union ? inter / union : 0
    best.set(String(display_name), Math.max(best.get(String(display_name)) ?? 0, overlap))
  }
  return [...best.entries()]
    .filter(([, score]) => score >= 0.8)
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([name, score]) =>
      `内核素材与既有内核「${name}」高度重合（相似度 ${score.toFixed(2)}）——若非有意另立人格，应改为 select 该内核`)
}

export function orphanKernelWarnings(conn: DatabaseSync): string[] {
  let rows: Array<{ display_name: string }>
  try {
    rows = conn.prepare(
      "SELECT p.display_name FROM creator_profiles p "
      + "WHERE p.ownership = 'author_kernel' AND NOT EXISTS ("
      + '  SELECT 1 FROM project_creator_bindings b '
      + '  JOIN creator_profile_versions v ON v.id = b.kernel_version_id '
      + '  WHERE v.profile_id = p.id)',
    ).all() as any
  } catch {
    return []
  }
  if (!rows.length) return []
  const names = rows.map((r) => String(r.display_name)).join('、')
  return [
    `库中存在未被任何项目绑定的内核（${names}）——若为此前失败尝试的孤儿，确认后另行清理，勿重复建核`,
  ]
}

// ---------------------------------------------------------------------------
// 内核候选门（py validate_kernel_candidate L368-417）
// ---------------------------------------------------------------------------

/** 信封 + author-kernel 深层 + revise 基底反查。schemasDir 为空时跳过结构层（形状已由 parseCandidateText 保证）。 */
export function validateKernelCandidate(
  candidate: JsonObj,
  conn: DatabaseSync,
  schemasDir?: string,
): { errors: string[]; kernelHash: string } {
  const errors: string[] = []

  if (schemasDir) {
    const env = loadSchema(schemasDir, 'kernel-candidate.schema.json')
    if (!env(candidate)) errors.push(`内核候选信封 schema FAIL: ${env.errors![0].message}`)
    const ks = loadSchema(schemasDir, 'author-kernel.schema.json')
    if (!ks(candidate['kernel'])) errors.push(`author-kernel schema FAIL: ${ks.errors![0].message}`)
  }

  const kernel = candidate['kernel'] ?? {}
  if (candidate['mode'] === 'revise') {
    const baseRow = lookupKernelVersion(conn, candidate['base_version'] ?? '')
    if (baseRow == null) {
      errors.push(`base_version=${JSON.stringify(candidate['base_version'])} 库中不存在`)
    } else {
      if (baseRow.ownership !== 'author_kernel') {
        errors.push('base_version 指向非 author_kernel 版本——内核只能修订内核')
      }
      const baseIdentity = JSON.parse(baseRow.kernel_json)?.identity ?? {}
      if (kernel?.identity?.display_name !== baseIdentity.display_name) {
        errors.push('revise 的 identity.display_name 与基底不一致——修订是演化不是重写')
      }
      const baseLog: unknown[] = JSON.parse(baseRow.kernel_json)?.growth_log ?? []
      if ((kernel?.growth_log?.length ?? 0) <= baseLog.length) {
        errors.push('revise 的 growth_log 未追加新条目——每次修订必须带本次归因')
      }
    }
  } else {
    const dup = conn.prepare(
      "SELECT COUNT(*) AS n FROM creator_profiles WHERE ownership = 'author_kernel' AND display_name = ?",
    ).get(candidate['display_name'] ?? '')!.n as number
    if (dup) {
      errors.push('display_name 与既有内核重名——内核是跨书根，必须可区分')
    }
  }

  return { errors, kernelHash: contentHash(pyJson(kernel)) }
}

// ---------------------------------------------------------------------------
// 内核落库（py persist_kernel L420-517）
// ---------------------------------------------------------------------------

export interface PersistResult {
  kernel_profile?: string
  kernel_version?: string
  resource_kernel?: string
  resource_deriv?: string
  subject_hash?: string
  project?: string
  profile?: string
  profile_version?: string
  resource_sig?: string
  sig_hash?: string
}

function blob(text: string): Buffer {
  return Buffer.from(text, 'utf8')
}

function insertResource(conn: DatabaseSync, id: string, content: string, hash: string): void {
  conn.prepare(
    'INSERT INTO resources (id, media_type, content, content_hash) VALUES (?, ?, ?, ?)',
  ).run(id, 'application/json', blob(content), hash)
}

/** UNIQUE(content_hash, media_type) 撞车 → 业务 FAIL（幂等硬去重），其余错误原样上抛 */
function translateConstraint(e: unknown): unknown {
  if (e instanceof Error && /UNIQUE constraint failed/i.test(e.message)) {
    return new GateFail(`落库失败：资源重复（${e.message}）——同一内容已存在，事务已整体回滚。`)
  }
  return e
}

export function persistKernel(
  conn: DatabaseSync,
  candidate: JsonObj,
  kernelHash: string,
  payload?: JsonObj | null,
): PersistResult {
  const kernel = candidate['kernel']
  const kernelJson = pyJson(kernel)

  let snapshot: JsonObj | null = null
  if (payload != null && typeof payload['setup'] === 'object') {
    const setup = payload['setup']
    snapshot = {
      author_kernel: setup['author_kernel'],
      setup: Object.fromEntries(Object.entries(setup).filter(([k]) => k !== 'author_kernel')),
    }
  } else if (payload != null) {
    // revise 信封（novelos.kernel.revise.v1）没有 setup——记录修订素材与基底
    snapshot = {
      kernel_revise: {
        base_version: payload['base_version'],
        kernel_hints: payload['kernel_hints'],
      },
    }
  }
  const deriv: JsonObj = {
    mode: candidate['mode'],
    rationale: candidate['rationale'],
    user_input_snapshot: snapshot,
  }
  if (candidate['mode'] === 'revise') deriv['base_version'] = candidate['base_version']
  const derivJson = pyJson(deriv)

  conn.exec('BEGIN IMMEDIATE')
  try {
    const resKernel = newId('resource')
    const resDeriv = newId('resource')
    insertResource(conn, resKernel, kernelJson, kernelHash)
    insertResource(conn, resDeriv, derivJson, contentHash(derivJson))

    let profileId: string
    let versionId: string
    if (candidate['mode'] === 'revise') {
      const base = lookupKernelVersion(conn, candidate['base_version'])
      if (base == null) throw new GateFail(`revise 基底版本库中不存在: ${candidate['base_version']}`)
      profileId = base.profile_id
      const revision = conn.prepare(
        'SELECT COALESCE(MAX(revision), 0) + 1 AS next FROM creator_profile_versions WHERE profile_id = ?',
      ).get(profileId)!.next as number
      versionId = newId('creator-profile-version')
      conn.prepare(
        'INSERT INTO creator_profile_versions '
        + '(id, profile_id, revision, content_resource_id, subject_hash, parent_version_id, derivation_resource_id) '
        + 'VALUES (?, ?, ?, ?, ?, ?, ?)',
      ).run(versionId, profileId, revision, resKernel, kernelHash, candidate['base_version'], resDeriv)
      conn.prepare(
        'UPDATE creator_profiles SET version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
      ).run(profileId)
    } else {
      profileId = newId('creator-profile')
      versionId = newId('creator-profile-version')
      conn.prepare(
        "INSERT INTO creator_profiles (id, display_name, ownership) VALUES (?, ?, 'author_kernel')",
      ).run(profileId, candidate['display_name'])
      conn.prepare(
        'INSERT INTO creator_profile_versions '
        + '(id, profile_id, revision, content_resource_id, subject_hash, parent_version_id, derivation_resource_id) '
        + 'VALUES (?, ?, 1, ?, ?, NULL, ?)',
      ).run(versionId, profileId, resKernel, kernelHash, resDeriv)
    }
    conn.exec('COMMIT')
    return {
      kernel_profile: profileId,
      kernel_version: versionId,
      resource_kernel: resKernel,
      resource_deriv: resDeriv,
      subject_hash: kernelHash,
    }
  } catch (e) {
    conn.exec('ROLLBACK')
    throw translateConstraint(e)
  }
}

// ---------------------------------------------------------------------------
// 分身候选门（py validate_candidate L520-581）
// ---------------------------------------------------------------------------

export function validatePersonaCandidate(
  candidate: JsonObj,
  payload: JsonObj,
  conn: DatabaseSync,
  schemasDir?: string,
): { errors: string[]; sigHash: string } {
  const errors: string[] = []

  if (schemasDir) {
    const env = loadSchema(schemasDir, 'creator-derivation-candidate.schema.json')
    if (!env(candidate)) errors.push(`候选信封 schema FAIL: ${env.errors![0].message}`)
    const sigSchema = loadSchema(schemasDir, 'creator-signature.schema.json')
    if (!sigSchema(candidate['signature'])) errors.push(`签名 schema v2 FAIL: ${sigSchema.errors![0].message}`)
  }

  const sig = candidate['signature'] ?? {}
  const parentLists: Record<string, string[]> = {}
  const ak = payload['setup']['author_kernel']
  const row = lookupKernelVersion(conn, ak['kernel_version_id'])
  if (row == null) {
    errors.push(`parent 内核版本库中不存在: ${JSON.stringify(ak['kernel_version_id'])}`)
  } else {
    if (candidate['parent_version_id'] !== ak['kernel_version_id']) {
      errors.push('parent_version_id 与 payload 绑定的内核版本不符')
    }
    if (candidate['parent_subject_hash'] !== row.subject_hash) {
      errors.push('parent_subject_hash 与内核库内反查不符')
    }
    if (candidate['display_name'] === row.display_name) {
      errors.push('display_name 逐字复制内核名——分身须凝聚为本书人格名')
    }
    const identity = JSON.parse(row.kernel_json)?.identity ?? {}
    for (const field of KERNEL_IDENTITY_LIST_FIELDS) {
      parentLists[field] = Array.isArray(identity[field]) ? identity[field] : []
    }
    const origin = sig['kernel_origin']
    if (origin != null) {
      if (origin['kernel_version_id'] !== ak['kernel_version_id']) {
        errors.push('kernel_origin.kernel_version_id 与绑定内核不符')
      }
      if (origin['kernel_subject_hash'] !== row.subject_hash) {
        errors.push('kernel_origin.kernel_subject_hash 与内核反查不符')
      }
    }
  }

  if (Object.keys(parentLists).length) {
    const allParentValues = new Set(Object.values(parentLists).flat())
    for (const field of SIGNATURE_FIELDS) {
      for (const item of sig[field] ?? []) {
        if (allParentValues.has(item)) {
          errors.push(`逐字复制父值 [${field}]: ${String(item).slice(0, 30)}…`)
        }
      }
      const n = (sig[field] ?? []).length
      if (!(2 <= n && n <= 4)) {
        errors.push(`${field} 条数 ${n} 超出 2-4`)
      }
    }
  }

  return { errors, sigHash: contentHash(pyJson(sig)) }
}

// ---------------------------------------------------------------------------
// 裁决门（红队 F2 整改 —— py 版此处纸面化，JS 版必须阻断）
// ---------------------------------------------------------------------------

/**
 * parent_rationale 含错配警告字样时阻断落库；
 * 仅显式传入用户裁决结果（userAdjudicated=true）才放行。
 */
export function checkMismatchAdjudication(
  candidate: JsonObj,
  opts: { userAdjudicated?: boolean } = {},
): void {
  const rationale: string = candidate['parent_rationale'] ?? ''
  const hits = MISMATCH_MARKERS.filter((m) => rationale.includes(m))
  if (!hits.length) return
  if (opts.userAdjudicated !== true) {
    throw new GateFail(
      'parent_rationale 含错配警告字样（' + hits.join('/') + '）——按协议必须把冲突与调和建议'
      + '呈报用户裁决，未获裁决不得落库（F2 整改：禁止仅警告放行）。',
    )
  }
}

// ---------------------------------------------------------------------------
// 项目落库（py persist L584-684，六表单事务）
// ---------------------------------------------------------------------------

export function persistProject(
  conn: DatabaseSync,
  payload: JsonObj,
  candidate: JsonObj,
  sigHash: string,
): PersistResult {
  const setup = payload['setup']
  const sig = candidate['signature']
  const sigJson = pyJson(sig)

  conn.exec('BEGIN IMMEDIATE')
  try {
    const ak = setup['author_kernel']
    const kernelRow = lookupKernelVersion(conn, ak['kernel_version_id'])
    if (kernelRow == null || kernelRow.ownership !== 'author_kernel') {
      throw new GateFail(`绑定的内核版本无效: ${JSON.stringify(ak['kernel_version_id'])}（落库前校验门应已拦截）`)
    }
    const deriv = {
      parent_version_id: ak['kernel_version_id'],
      parent_display_name: kernelRow.display_name,
      parent_subject_hash: kernelRow.subject_hash,
      auxiliary_archetypes: [],
      rationale: candidate['parent_rationale'],
      user_input_snapshot: {
        author_kernel: Object.fromEntries(Object.entries(ak).filter(([k]) => k !== 'kernel_hints')),
        setup: Object.fromEntries(Object.entries(setup).filter(([k]) => k !== 'author_kernel')),
      },
    }
    const derivJson = pyJson(deriv)
    const traitsModel = (setup['platform_traits'] ?? {})['model'] ?? ''
    const description = `${setup['channel']}·${setup['primary_genre']} | ${setup['platform']}·${traitsModel} | ${setup['scale']}`
    const meta = {
      setup_schema_version: 3,
      setup: Object.fromEntries(Object.entries(setup).filter(([k]) => k !== 'author_kernel')),
    }

    const resourceSig = newId('resource')
    const resourceDeriv = newId('resource')
    const profile = newId('creator-profile')
    const profileVersion = newId('creator-profile-version')
    const project = newId('project')

    insertResource(conn, resourceSig, sigJson, sigHash)
    insertResource(conn, resourceDeriv, derivJson, contentHash(derivJson))
    conn.prepare(
      "INSERT INTO creator_profiles (id, display_name, ownership) VALUES (?, ?, 'user')",
    ).run(profile, candidate['display_name'])
    conn.prepare(
      'INSERT INTO creator_profile_versions '
      + '(id, profile_id, revision, content_resource_id, subject_hash, parent_version_id, derivation_resource_id) '
      + 'VALUES (?, ?, 1, ?, ?, ?, ?)',
    ).run(profileVersion, profile, resourceSig, sigHash, candidate['parent_version_id'], resourceDeriv)
    conn.prepare(
      'INSERT INTO projects (id, name, description, version, metadata_json) VALUES (?, ?, ?, 1, ?)',
    ).run(project, setup['title'], description, pyJsonCompact(meta))
    conn.prepare(
      'INSERT INTO project_creator_bindings '
      + '(project_id, profile_id, profile_version_id, profile_revision, subject_hash, binding_mode, kernel_version_id) '
      + 'VALUES (?, ?, ?, 1, ?, ?, ?)',
    ).run(project, profile, profileVersion, sigHash, 'kernel_derive', ak['kernel_version_id'])

    conn.exec('COMMIT')
    return {
      project,
      profile,
      profile_version: profileVersion,
      resource_sig: resourceSig,
      resource_deriv: resourceDeriv,
      sig_hash: sigHash,
      kernel_version: ak['kernel_version_id'],
    }
  } catch (e) {
    conn.exec('ROLLBACK')
    throw translateConstraint(e)
  }
}

// ---------------------------------------------------------------------------
// 缝合（py _stitch_bound_payload L687-700）
// ---------------------------------------------------------------------------

/** mode=create 建核后，把 payload 缝合为 select 形态（机械回填 id/hash，不改内容）。 */
export function stitchBoundPayload(
  payload: JsonObj,
  kernel: { kernel_version: string; subject_hash: string },
): JsonObj {
  const bound = JSON.parse(JSON.stringify(payload))
  const ak = bound['setup']['author_kernel']
  const stitched: JsonObj = {
    mode: 'select',
    kernel_version_id: kernel.kernel_version,
    subject_hash: kernel.subject_hash,
    kernel_hints: ak['kernel_hints'] ?? {},
  }
  if (typeof ak['display_name'] === 'string') stitched['display_name'] = ak['display_name']
  bound['setup']['author_kernel'] = stitched
  return bound
}
