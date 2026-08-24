/**
 * JS 写门 · 项目删除（R2 补齐）。
 *
 * 移植自 legacy-python/scripts/novelos_delete_project.py：
 * 一个项目分布在多张表且存在大量 ON DELETE RESTRICT 约束（reviews、
 * planning_asset_dependencies.upstream_asset_id、resources 等不级联），
 * 必须在 foreign_keys=OFF 下按依赖逆序手动删除，再 ON 复验完整性。
 *
 * 与 py 的差异：
 * - 投影目录删除已省略——md 投影链路已退役（单渲染器红线），无 novels/ 可删。
 * - 备份由 backupDatabase() 提供（fs.copyFileSync，时间戳后缀与 py 同格式）。
 *
 * 关键设计保持不变：显式事务 BEGIN/COMMIT；只删项目专属内容资源，
 * **不动** creator_profile_versions 引用的共享系统原型资源。
 */
import { copyFileSync } from 'node:fs'
import type { DatabaseSync } from 'node:sqlite'
import { GateFail } from './primitives.js'

/** 项目专属内容资源的来源列（不含 creator_profile_versions——后者跨项目共享） */
const RESOURCE_SOURCES = [
  'SELECT content_resource_id FROM planning_assets WHERE project_id=?',
  `SELECT c.content_resource_id FROM chapters c
   JOIN volumes v ON c.volume_id=v.id JOIN books b ON v.book_id=b.id
   WHERE b.project_id=?`,
  'SELECT description_resource_id FROM characters WHERE project_id=? AND description_resource_id IS NOT NULL',
  'SELECT description_resource_id FROM worlds WHERE project_id=? AND description_resource_id IS NOT NULL',
  'SELECT description_resource_id FROM narrative_promises WHERE project_id=? AND description_resource_id IS NOT NULL',
  'SELECT description_resource_id FROM expectation_ledgers WHERE project_id=? AND description_resource_id IS NOT NULL',
  'SELECT state_resource_id FROM relationship_states WHERE project_id=? AND state_resource_id IS NOT NULL',
  'SELECT state_resource_id FROM arc_states WHERE project_id=? AND state_resource_id IS NOT NULL',
  'SELECT description_resource_id FROM chapter_facts WHERE project_id=? AND description_resource_id IS NOT NULL',
]
/** 连续性账本表（均有 project_id 外键，逐表删） */
const CONTINUITY_TABLES = [
  'chapter_facts', 'timelines', 'arc_states',
  'relationship_states', 'expectation_ledgers', 'narrative_promises',
]

const placeholders = (n: number): string => Array(n).fill('?').join(',')

export interface ProjectIds {
  assets: string[]
  chapters: string[]
  volumes: string[]
  books: string[]
  subjects: Set<string>
  resources: Set<string>
}

/** py: collect_ids —— 收集项目相关所有实体 id 与待删资源 id */
export function collectIds(conn: DatabaseSync, pid: string): ProjectIds {
  const assets = (conn.prepare('SELECT id FROM planning_assets WHERE project_id=?').all(pid) as Array<{ id: string }>).map((r) => r.id)
  const chapters = (conn.prepare(
    `SELECT c.id FROM chapters c JOIN volumes v ON c.volume_id=v.id
     JOIN books b ON v.book_id=b.id WHERE b.project_id=?`,
  ).all(pid) as Array<{ id: string }>).map((r) => r.id)
  const volumes = (conn.prepare(
    'SELECT v.id FROM volumes v JOIN books b ON v.book_id=b.id WHERE b.project_id=?',
  ).all(pid) as Array<{ id: string }>).map((r) => r.id)
  const books = (conn.prepare('SELECT id FROM books WHERE project_id=?').all(pid) as Array<{ id: string }>).map((r) => r.id)
  const subjects = new Set([...assets, ...chapters, ...volumes, ...books])
  const resources = new Set<string>()
  for (const sql of RESOURCE_SOURCES) {
    for (const row of conn.prepare(sql).all(pid) as Array<Record<string, unknown>>) {
      const rid = row[Object.keys(row)[0]]
      if (typeof rid === 'string' && rid) resources.add(rid)
    }
  }
  return { assets, chapters, volumes, books, subjects, resources }
}

export interface DeleteSteps {
  label: string
  changes: number
}

/**
 * py: delete_project —— 按依赖逆序删除（foreign_keys=OFF + 显式事务）。
 * 任一步失败回滚并抛 GateFail；成功返回逐步行数。
 */
export function deleteProject(conn: DatabaseSync, pid: string, ids: ProjectIds): DeleteSteps[] {
  const steps: DeleteSteps[] = []
  try {
    conn.exec('PRAGMA foreign_keys=OFF')
    conn.exec('BEGIN')
    const exe = (label: string, sql: string, args: any[] = []): void => {
      steps.push({ label, changes: Number(conn.prepare(sql).run(...args).changes) })
    }

    if (ids.assets.length) {
      exe('planning_asset_dependencies',
        `DELETE FROM planning_asset_dependencies WHERE asset_id IN (${placeholders(ids.assets.length)}) `
        + `OR upstream_asset_id IN (${placeholders(ids.assets.length)})`,
        [...ids.assets, ...ids.assets])
    }
    if (ids.subjects.size) {
      const subs = [...ids.subjects]
      exe('reviews', `DELETE FROM reviews WHERE subject_ref IN (${placeholders(subs.length)})`, subs)
    }
    for (const table of CONTINUITY_TABLES) {
      exe(table, `DELETE FROM ${table} WHERE project_id=?`, [pid])
    }
    if (ids.chapters.length) {
      exe('chapters', `DELETE FROM chapters WHERE id IN (${placeholders(ids.chapters.length)})`, ids.chapters)
    }
    if (ids.volumes.length) {
      exe('volumes', `DELETE FROM volumes WHERE id IN (${placeholders(ids.volumes.length)})`, ids.volumes)
    }
    exe('planning_assets', 'DELETE FROM planning_assets WHERE project_id=?', [pid])
    exe('characters', 'DELETE FROM characters WHERE project_id=?', [pid])
    exe('worlds', 'DELETE FROM worlds WHERE project_id=?', [pid])
    exe('project_creator_bindings', 'DELETE FROM project_creator_bindings WHERE project_id=?', [pid])
    exe('books', 'DELETE FROM books WHERE project_id=?', [pid])
    exe('projects', 'DELETE FROM projects WHERE id=?', [pid])
    if (ids.resources.size) {
      const rids = [...ids.resources]
      exe('resources', `DELETE FROM resources WHERE id IN (${placeholders(rids.length)})`, rids)
    }

    conn.exec('COMMIT')
    conn.exec('PRAGMA foreign_keys=ON')
    return steps
  } catch (e) {
    try { conn.exec('ROLLBACK') } catch { /* already rolled back */ }
    try { conn.exec('PRAGMA foreign_keys=ON') } catch { /* ignore */ }
    throw new GateFail(`项目删除事务失败已回滚：${e instanceof Error ? e.message : String(e)}`)
  }
}

export interface OrphanCounts {
  reviews: number
  dependencies: number
}

/** py: clean_orphans —— 清理全库孤儿 reviews/dependencies（独立事务） */
export function cleanOrphans(conn: DatabaseSync): OrphanCounts {
  try {
    conn.exec('BEGIN')
    const r1 = Number(conn.prepare(
      "DELETE FROM reviews WHERE subject_type='planning_asset' "
      + 'AND subject_ref NOT IN (SELECT id FROM planning_assets)',
    ).run().changes)
    const r2 = Number(conn.prepare(
      'DELETE FROM planning_asset_dependencies WHERE asset_id NOT IN (SELECT id FROM planning_assets) '
      + 'OR upstream_asset_id NOT IN (SELECT id FROM planning_assets)',
    ).run().changes)
    conn.exec('COMMIT')
    return { reviews: r1, dependencies: r2 }
  } catch (e) {
    try { conn.exec('ROLLBACK') } catch { /* already rolled back */ }
    throw new GateFail(`孤儿清理事务失败已回滚：${e instanceof Error ? e.message : String(e)}`)
  }
}

export interface VerifyReport {
  projectLeft: number
  planningAssetsLeft: number
  orphanReviews: number
  orphanDependencies: number
}

/** py: verify —— 删除后复验项目残留与全库孤儿（foreign_keys=ON） */
export function verify(conn: DatabaseSync, pid: string): VerifyReport {
  conn.exec('PRAGMA foreign_keys=ON')
  return {
    projectLeft: Number((conn.prepare('SELECT count(*) AS n FROM projects WHERE id=?').get(pid) as { n: number }).n),
    planningAssetsLeft: Number((conn.prepare('SELECT count(*) AS n FROM planning_assets WHERE project_id=?').get(pid) as { n: number }).n),
    orphanReviews: Number((conn.prepare(
      "SELECT count(*) AS n FROM reviews WHERE subject_type='planning_asset' "
      + 'AND subject_ref NOT IN (SELECT id FROM planning_assets)',
    ).get() as { n: number }).n),
    orphanDependencies: Number((conn.prepare(
      'SELECT count(*) AS n FROM planning_asset_dependencies d WHERE d.asset_id NOT IN (SELECT id FROM planning_assets) '
      + 'OR d.upstream_asset_id NOT IN (SELECT id FROM planning_assets)',
    ).get() as { n: number }).n),
  }
}

export interface ProjectSurvey {
  project: { id: string; name: string }
  ids: ProjectIds
  counts: {
    books: number
    volumes: number
    chapters: number
    assetsByTypeStatus: Array<{ asset_type: string; status: string; count: number }>
    resources: number
    reviews: number
    characters: number
    worlds: number
  }
}

/** py: survey —— 调查项目在各表的规模；项目不存在抛 GateFail */
export function surveyProject(conn: DatabaseSync, pid: string): ProjectSurvey {
  const row = conn.prepare('SELECT id, name FROM projects WHERE id=?').get(pid) as { id: string; name: string } | undefined
  if (!row) throw new GateFail(`找不到项目 ${pid}`)
  const ids = collectIds(conn, pid)
  const cnt = (sql: string): number => Number((conn.prepare(sql).get(pid) as { n: number }).n)
  return {
    project: row,
    ids,
    counts: {
      books: cnt('SELECT count(*) AS n FROM books WHERE project_id=?'),
      volumes: cnt('SELECT count(*) AS n FROM volumes v JOIN books b ON v.book_id=b.id WHERE b.project_id=?'),
      chapters: cnt('SELECT count(*) AS n FROM chapters c JOIN volumes v ON c.volume_id=v.id JOIN books b ON v.book_id=b.id WHERE b.project_id=?'),
      assetsByTypeStatus: (conn.prepare(
        'SELECT asset_type, status, count(*) AS n FROM planning_assets WHERE project_id=? '
        + 'GROUP BY asset_type, status ORDER BY asset_type',
      ).all(pid) as Array<Record<string, any>>).map((r) => ({ asset_type: String(r.asset_type), status: String(r.status), count: Number(r.n) })),
      resources: ids.resources.size,
      reviews: ids.subjects.size
        ? (() => {
            const subs = [...ids.subjects]
            return Number((conn.prepare(
              `SELECT count(*) AS n FROM reviews WHERE subject_ref IN (${placeholders(subs.length)})`,
            ).get(...subs) as { n: number }).n)
          })()
        : 0,
      characters: cnt('SELECT count(*) AS n FROM characters WHERE project_id=?'),
      worlds: cnt('SELECT count(*) AS n FROM worlds WHERE project_id=?'),
    },
  }
}

/** py --backup：删前备份数据库文件（novelos-v2.db.bak-YYYYMMDD-HHMMSS 同格式后缀） */
export function backupDatabase(dbPath: string): string {
  const now = new Date()
  const p = (x: number): string => String(x).padStart(2, '0')
  const stamp = `${now.getFullYear()}${p(now.getMonth() + 1)}${p(now.getDate())}-${p(now.getHours())}${p(now.getMinutes())}${p(now.getSeconds())}`
  const bakPath = `${dbPath}.bak-${stamp}`
  copyFileSync(dbPath, bakPath)
  return bakPath
}
