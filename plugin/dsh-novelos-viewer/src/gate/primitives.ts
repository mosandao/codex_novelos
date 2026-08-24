/**
 * JS 写门 · 确定性原语（R2）。
 *
 * 与 legacy-python/scripts/novelos_create_project.py 逐点对齐移植；
 * 校验步骤全序与错误文案以 docs/r2-js-gate-spec.md 为准。
 * 红线：任何 FAIL 必须阻断，禁止 mismatch 仅警告放行（红队 F2 教训）。
 */
import { createHash, randomUUID } from 'node:crypto'
import type { DatabaseSync } from 'node:sqlite'

/** py: content_hash(text) = f"sha256:{sha256(text.encode('utf-8')).hexdigest()}" */
export function contentHash(text: string): string {
  return 'sha256:' + createHash('sha256').update(text, 'utf8').digest('hex')
}

export function newId(kind: string): string {
  return `${kind}:${randomUUID()}`
}

export interface KernelVersionRow {
  id: string
  revision: number
  subject_hash: string
  profile_id: string
  display_name: string
  status: string
  ownership: string
  kernel_json: string
}

/** py: lookup_kernel_version —— 库内反查内核版本（含 profile 归属校验所需列） */
export function lookupKernelVersion(conn: DatabaseSync, versionId: string): KernelVersionRow | null {
  const row = conn.prepare(`
    SELECT v.id, v.revision, v.subject_hash, v.profile_id,
           p.display_name, p.status, p.ownership,
           CAST(r.content AS TEXT) AS kernel_json
    FROM creator_profile_versions v
    JOIN creator_profiles p ON p.id = v.profile_id
    JOIN resources r ON r.id = v.content_resource_id
    WHERE v.id = ?
  `).get(versionId) as KernelVersionRow | undefined
  return row ?? null
}

/** py: _persona_shape_ok */
export function personaShapeOk(obj: unknown): boolean {
  if (typeof obj !== 'object' || obj === null) return false
  const o = obj as Record<string, unknown>
  if (!('parent_version_id' in o) || !('signature' in o)) return false
  const sig = o.signature
  return typeof sig === 'object' && sig !== null && 'sympathies' in (sig as object)
}

/** py: _kernel_shape_ok */
export function kernelShapeOk(obj: unknown): boolean {
  if (typeof obj !== 'object' || obj === null) return false
  const o = obj as Record<string, unknown>
  if (!('mode' in o) || !('display_name' in o) || !('kernel' in o)) return false
  const k = o.kernel
  return typeof k === 'object' && k !== null && 'identity' in (k as object)
}

/** py: MISMATCH_MARKERS（顺序保留）——候选文本含任一标记即触发 mismatch 判定流程 */
export const MISMATCH_MARKERS = ['错配警告', 'mismatch', '根本冲突', '根本相斥', '调和建议'] as const

export interface ParsedCandidate {
  obj: unknown
  /** 结构性修复报告（去围栏/补括号）；修复必须上报，禁止静默 */
  notes: string[]
}

/**
 * py: parse_candidate_text —— 容错解析候选：裸 JSON → 去围栏 → 尾部截断修复。
 * 只做**安全**修复；中段缺括号（字段错位）无法安全修复——形状不过即抛
 * GateFail（要求融合智能体重出，禁止主控手工改写候选内容）。
 * 注意：Python json.loads 默认接受 NaN/Infinity 字面量而 JSON.parse 拒绝——
 * 该差异方向安全（JS 更严）。
 */
export class GateFail extends Error {}

export function parseCandidateText(raw: string, kind: 'persona' | 'kernel' = 'persona'): ParsedCandidate {
  const shapeOk = kind === 'persona' ? personaShapeOk : kernelShapeOk
  const fail = () => new GateFail(
    '候选 JSON 解析失败或字段错位：按协议要求融合智能体重新输出，'
    + '禁止主控手工改写候选内容（去围栏/尾部补括号等结构性修复除外）。',
  )
  const notes: string[] = []
  let text = raw.trim()
  try {
    return { obj: JSON.parse(text), notes }
  } catch { /* fallthrough */ }

  if (text.startsWith('```')) {
    text = text.split('\n').filter((line) => !line.trim().startsWith('```')).join('\n').trim()
    notes.push('去除 Markdown 代码围栏')
    try {
      return { obj: JSON.parse(text), notes }
    } catch { /* fallthrough */ }
  }

  // 尾部截断扫描：跟踪字符串/转义状态，收集未闭合的 { 与 [
  const unclosed: string[] = []
  let inStr = false
  let esc = false
  for (const ch of text) {
    if (inStr) {
      if (esc) esc = false
      else if (ch === '\\') esc = true
      else if (ch === '"') inStr = false
    } else if (ch === '"') {
      inStr = true
    } else if (ch === '{' || ch === '[') {
      unclosed.push(ch)
    } else if (ch === '}') {
      if (unclosed.length && unclosed[unclosed.length - 1] === '{') unclosed.pop()
    } else if (ch === ']') {
      if (unclosed.length && unclosed[unclosed.length - 1] === '[') unclosed.pop()
    }
  }
  if (unclosed.length) {
    const closer = [...unclosed].reverse().map((c) => (c === '{' ? '}' : ']')).join('')
    let obj: unknown
    try {
      obj = JSON.parse(text + closer)
    } catch {
      throw fail()
    }
    if (!shapeOk(obj)) throw fail()
    notes.push(`补齐尾部未闭合括号 ${JSON.stringify(closer)}（结构修复不改动内容）`)
    return { obj, notes }
  }
  throw fail()
}
