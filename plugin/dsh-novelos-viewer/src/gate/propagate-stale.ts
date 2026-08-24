/**
 * JS 写门 · stale 传播（R2 补齐）。
 *
 * 移植自 legacy-python/scripts/novelos_propagate_stale.py：
 * 上游规划资产修订后，沿 planning_asset_dependencies 依赖图标记下游 locked 资产为 stale。
 *
 * 两种模式（与 py CLI --fine 对应）：
 * - coarse（默认）：BFS 收集直接+间接全部下游 locked 资产，全量标 stale。
 * - fine：仅直接下游按「依赖边 upstream_version + content_hash 双重比对」分类，
 *   内容未变（观测等价）的判 neutral 不误伤；间接下游只列为间接待重估，不自动标。
 *
 * 红线：资产不存在必须 GateFail 阻断；事务内 UPDATE 失败整体回滚。
 */
import type { DatabaseSync } from 'node:sqlite'
import { GateFail } from './primitives.js'

export interface DownstreamAsset {
  id: string
  project_id: string
  asset_type: string
  scope_ref: string
  status: string
}

/** py: _collect_downstream —— BFS 递归依赖图，收集所有下游（直接+间接）locked 资产 */
export function collectDownstream(conn: DatabaseSync, assetId: string): DownstreamAsset[] {
  const result: DownstreamAsset[] = []
  const seen = new Set<string>()
  const queue = [assetId]

  while (queue.length) {
    const current = queue.shift()!
    const rows = conn.prepare(`
      SELECT pa.id, pa.project_id, pa.asset_type, pa.scope_ref, pa.status
      FROM planning_asset_dependencies pad
      JOIN planning_assets pa ON pa.id = pad.asset_id
      WHERE pad.upstream_asset_id = ?
        AND pa.status = 'locked'
    `).all(current) as Array<Record<string, string>>
    for (const row of rows) {
      if (seen.has(row.id)) continue
      seen.add(row.id)
      result.push({
        id: row.id,
        project_id: row.project_id,
        asset_type: row.asset_type,
        scope_ref: row.scope_ref,
        status: row.status,
      })
      queue.push(row.id)
    }
  }
  return result
}

export interface FineClassification extends DownstreamAsset {
  verdict: 'neutral' | 'stale'
  reason: string
}

/** py: _classify_fine —— 直接下游按依赖边版本号 + 内容 hash 双重比对（机械，无 LLM） */
export function classifyFine(conn: DatabaseSync, upstreamId: string): FineClassification[] {
  const scopeRow = conn.prepare(
    'SELECT project_id, asset_type, scope_ref FROM planning_assets WHERE id = ?',
  ).get(upstreamId) as { project_id: string; asset_type: string; scope_ref: string } | undefined
  if (!scopeRow) return []
  const { project_id: pid, asset_type: atype, scope_ref: scope } = scopeRow

  const revHash = (revision: number): string | null => {
    const row = conn.prepare(
      'SELECT r.content_hash FROM planning_assets pa '
      + 'JOIN resources r ON r.id = pa.content_resource_id '
      + 'WHERE pa.project_id = ? AND pa.asset_type = ? AND pa.scope_ref = ? AND pa.revision = ?',
    ).get(pid, atype, scope, revision) as { content_hash: string } | undefined
    return row?.content_hash ?? null
  }

  const current = conn.prepare(
    "SELECT revision FROM planning_assets WHERE project_id = ? AND asset_type = ? "
    + "AND scope_ref = ? AND status = 'locked' ORDER BY revision DESC LIMIT 1",
  ).get(pid, atype, scope) as { revision: number } | undefined
  if (!current) return []
  const m = Number(current.revision)
  const hM = revHash(m)

  const rows = conn.prepare(
    "SELECT pa.id, pa.asset_type, pa.scope_ref, pa.status, pad.upstream_version "
    + "FROM planning_asset_dependencies pad "
    + "JOIN planning_assets pa ON pa.id = pad.asset_id "
    + "WHERE pad.upstream_asset_id = ? AND pa.status = 'locked'",
  ).all(upstreamId) as Array<Record<string, any>>

  return rows.map((row): FineClassification => {
    const base: FineClassification = {
      id: String(row.id),
      project_id: String(row.project_id),
      asset_type: String(row.asset_type),
      scope_ref: String(row.scope_ref),
      status: String(row.status),
      verdict: 'stale',
      reason: '',
    }
    const v = Number(row.upstream_version)
    if (v === m) {
      return { ...base, verdict: 'neutral', reason: `依赖边已对齐 rev ${m}` }
    }
    const hV = revHash(v)
    if (hM !== null && hV === hM) {
      return { ...base, verdict: 'neutral', reason: `rev ${v} 与 rev ${m} content_hash 相同（内容未变）` }
    }
    return { ...base, verdict: 'stale', reason: `依赖 rev ${v}，当前 rev ${m} 且内容已变` }
  })
}

export interface PropagateOptions {
  /** fine=true 用精细模式（内容未变不误伤）；默认 coarse 全量标 */
  fine?: boolean
  /** 干跑：只返回报告不执行 UPDATE */
  dryRun?: boolean
}

export interface PropagateReport {
  upstream: { id: string; asset_type: string; status: string }
  mode: 'coarse' | 'fine'
  dryRun: boolean
  marked: number
  neutral: number
  /** coarse 模式：被标 stale 的资产明细 */
  markedAssets?: Array<Pick<DownstreamAsset, 'id' | 'asset_type' | 'scope_ref'>>
  /** fine 模式：逐资产判定与理由 */
  classification?: FineClassification[]
  /** fine 模式：间接下游待重估清单（不自动标，保守正确） */
  indirectPending?: string[]
}

/**
 * 主入口：传播 stale。dryRun 只报告；否则单事务内批量 UPDATE，
 * 任一步失败回滚并抛 GateFail。
 */
export function propagateStale(conn: DatabaseSync, assetId: string, opts: PropagateOptions = {}): PropagateReport {
  const upstream = conn.prepare(
    'SELECT id, asset_type, status FROM planning_assets WHERE id = ?',
  ).get(assetId) as { id: string; asset_type: string; status: string } | undefined
  if (!upstream) throw new GateFail(`资产不存在: ${assetId}`)

  const markStale = (ids: string[]): void => {
    try {
      conn.exec('BEGIN')
      const stmt = conn.prepare(
        "UPDATE planning_assets SET status='stale', updated_at=CURRENT_TIMESTAMP WHERE id=?",
      )
      for (const id of ids) stmt.run(id)
      conn.exec('COMMIT')
    } catch (e) {
      try { conn.exec('ROLLBACK') } catch { /* already rolled back */ }
      throw new GateFail(`stale 传播事务失败已回滚：${e instanceof Error ? e.message : String(e)}`)
    }
  }

  if (opts.fine) {
    const classified = classifyFine(conn, assetId)
    const stale = classified.filter((c) => c.verdict === 'stale')
    const indirectIds = new Set(collectDownstream(conn, assetId).map((d) => d.id))
    for (const c of classified) indirectIds.delete(c.id)
    if (!opts.dryRun && stale.length) markStale(stale.map((c) => c.id))
    return {
      upstream, mode: 'fine', dryRun: opts.dryRun === true,
      marked: stale.length, neutral: classified.length - stale.length,
      classification: classified, indirectPending: [...indirectIds].sort(),
    }
  }

  const downstream = collectDownstream(conn, assetId)
  if (!opts.dryRun && downstream.length) markStale(downstream.map((d) => d.id))
  return {
    upstream, mode: 'coarse', dryRun: opts.dryRun === true,
    marked: downstream.length, neutral: 0,
    markedAssets: downstream.map(({ id, asset_type, scope_ref }) => ({ id, asset_type, scope_ref })),
  }
}
