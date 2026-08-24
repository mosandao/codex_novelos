/**
 * JS 写门 · stale 传播 + 项目删除测试（R2 补齐）。
 * :memory: 库（schema.sql v18 基线），seed 走真实门原语。
 */
import { describe, it, expect } from 'vitest'
import { DatabaseSync } from 'node:sqlite'
import { makeDb } from './gate-fixture.mjs'
import { contentHash, newId } from '../src/gate/primitives.ts'
import {
  collectDownstream,
  classifyFine,
  propagateStale,
} from '../src/gate/propagate-stale.ts'
import {
  surveyProject,
  collectIds,
  deleteProject,
  cleanOrphans,
  verify,
} from '../src/gate/delete-project.ts'

function freshDb(): DatabaseSync {
  return makeDb() as DatabaseSync
}

let seq = 0
function uniq(prefix: string): string {
  seq += 1
  return `${prefix}${seq}`
}

/** 最小合法 seed：项目 + 内容资源 */
function seedProject(db: DatabaseSync, pid = 'project:t'): string {
  db.prepare('INSERT INTO projects (id, name) VALUES (?, ?)').run(pid, '测试项目')
  return pid
}

function seedResource(db: DatabaseSync, text: string): string {
  const id = newId('resource')
  const hash = contentHash(text)
  db.prepare('INSERT INTO resources (id, media_type, content, content_hash) VALUES (?, ?, CAST(? AS BLOB), ?)')
    .run(id, 'text/markdown', text, hash)
  return id
}

function seedAsset(
  db: DatabaseSync,
  pid: string,
  assetType: string,
  opts: { scope?: string; revision?: number; status?: string; body?: string } = {},
): string {
  const id = newId('planning')
  const rid = seedResource(db, opts.body ?? `${assetType}:${opts.scope ?? 'book'}:${opts.revision ?? 1}:${uniq('body')}`)
  db.prepare(
    `INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role)
     VALUES (?, ?, ?, ?, ?, ?, ?, 'agent')`,
  ).run(id, pid, assetType, opts.scope ?? 'book', opts.revision ?? 1, opts.status ?? 'locked', rid)
  return id
}

function seedDependency(db: DatabaseSync, assetId: string, upstreamId: string, upstreamVersion: number): void {
  db.prepare(
    'INSERT INTO planning_asset_dependencies (asset_id, upstream_asset_id, upstream_version) VALUES (?, ?, ?)',
  ).run(assetId, upstreamId, upstreamVersion)
}

const assetStatus = (db: DatabaseSync, id: string): string =>
  (db.prepare('SELECT status FROM planning_assets WHERE id=?').get(id) as { status: string }).status

describe('propagateStale · coarse 模式', () => {
  it('dryRun 只报告不执行 UPDATE', () => {
    const db = freshDb()
    const pid = seedProject(db)
    const up = seedAsset(db, pid, 'world_contract')
    const down = seedAsset(db, pid, 'character_contract')
    seedDependency(db, down, up, 1)

    const report = propagateStale(db, up, { dryRun: true })
    expect(report.dryRun).toBe(true)
    expect(report.marked).toBe(1)
    expect(report.markedAssets![0]!.id).toBe(down)
    expect(assetStatus(db, down)).toBe('locked')
  })

  it('执行时直接+间接下游全量标 stale，candidate 与上游不动', () => {
    const db = freshDb()
    const pid = seedProject(db)
    const up = seedAsset(db, pid, 'world_contract')
    const mid = seedAsset(db, pid, 'story_arc')
    const leaf = seedAsset(db, pid, 'volume_outline', { scope: 'v1' })
    const candidate = seedAsset(db, pid, 'character_contract', { status: 'candidate' })
    seedDependency(db, mid, up, 2)
    seedDependency(db, leaf, mid, 1)

    expect(collectDownstream(db, up).map((d) => d.id).sort()).toEqual([leaf, mid].sort())
    const report = propagateStale(db, up)
    expect(report.marked).toBe(2)
    expect(assetStatus(db, mid)).toBe('stale')
    expect(assetStatus(db, leaf)).toBe('stale')
    expect(assetStatus(db, candidate)).toBe('candidate')
    expect(assetStatus(db, up)).toBe('locked')
  })

  it('无下游时 marked=0 且不报错', () => {
    const db = freshDb()
    const pid = seedProject(db)
    const up = seedAsset(db, pid, 'direction')
    const report = propagateStale(db, up)
    expect(report.marked).toBe(0)
  })

  it('资产不存在抛 GateFail', async () => {
    const db = freshDb()
    seedProject(db)
    const { GateFail } = await import('../src/gate/primitives.ts')
    expect(() => propagateStale(db, 'planning:nope')).toThrow(GateFail)
  })

})

describe('propagateStale · fine 模式', () => {
  it('rev 对齐判 neutral，内容未变判 neutral，内容已变判 stale', () => {
    const db = freshDb()
    const pid = seedProject(db)
    const upV1Body = '世界契约 v1 正文'
    const upV2Body = '世界契约 v2 正文'
    const upR1 = seedAsset(db, pid, 'world_contract', { revision: 1, body: upV1Body, status: 'superseded' })
    // 取回 r1 的 resource 以便复用 hash：直接查 content_hash
    const h1 = (db.prepare(
      'SELECT r.content_hash FROM planning_assets pa JOIN resources r ON r.id=pa.content_resource_id WHERE pa.id=?',
    ).get(upR1) as { content_hash: string }).content_hash

    // 上游 rev2：复用 v1 同一资源（同内容同 hash，UNIQUE 去重下观测等价）
    const upR2SameContent = (() => {
      const id = newId('planning')
      const rid = (db.prepare('SELECT id FROM resources WHERE content_hash=?').get(h1) as { id: string }).id
      db.prepare(
        `INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, content_resource_id, producer_role)
         VALUES (?, ?, ?, ?, ?, ?, ?, 'agent')`,
      ).run(id, pid, 'world_contract', 'book', 2, 'locked', rid)
      return id
    })()

    const aligned = seedAsset(db, pid, 'character_contract')
    const sameHash = seedAsset(db, pid, 'story_arc')
    seedDependency(db, aligned, upR2SameContent, 2)   // 边版本 == 当前 rev → neutral
    seedDependency(db, sameHash, upR2SameContent, 1)  // rev1 内容与 rev2 相同 → neutral

    const classified = classifyFine(db, upR2SameContent)
    const byId = new Map(classified.map((c) => [c.id, c]))
    expect(byId.get(aligned)!.verdict).toBe('neutral')
    expect(byId.get(sameHash)!.verdict).toBe('neutral')

    // 内容已变场景：上游换新正文 rev3（旧 locked rev2 先翻 superseded——
    // partial unique index 只允许每 (project,type,scope) 一个 locked）
    db.prepare("UPDATE planning_assets SET status='superseded' WHERE id=?").run(upR2SameContent)
    const upR3 = seedAsset(db, pid, 'world_contract', { revision: 3, body: upV2Body })
    const stale = seedAsset(db, pid, 'volume_outline', { scope: 'v1' })
    seedDependency(db, stale, upR3, 2)
    void upV2Body
    const report = propagateStale(db, upR3, { fine: true })
    expect(report.mode).toBe('fine')
    expect(report.classification!.find((c) => c.id === stale)!.verdict).toBe('stale')
    expect(assetStatus(db, stale)).toBe('stale')
  })

  it('间接下游列入待重估不自动标', () => {
    const db = freshDb()
    const pid = seedProject(db)
    const up = seedAsset(db, pid, 'strategy')
    const direct = seedAsset(db, pid, 'world_contract')
    const indirect = seedAsset(db, pid, 'story_arc')
    seedDependency(db, direct, up, 1)
    seedDependency(db, indirect, direct, 1)

    const report = propagateStale(db, up, { fine: true })
    expect(report.indirectPending).toContain(indirect)
    expect(assetStatus(db, indirect)).toBe('locked')
  })
})

describe('deleteProject', () => {
  it('survey 统计规模；项目不存在抛 GateFail', async () => {
    const db = freshDb()
    const { GateFail } = await import('../src/gate/primitives.ts')
    expect(() => surveyProject(db, 'project:ghost')).toThrow(GateFail)
    const pid = seedProject(db)
    seedAsset(db, pid, 'direction')
    const s = surveyProject(db, pid)
    expect(s.project.name).toBe('测试项目')
    expect(s.counts.assetsByTypeStatus).toEqual([{ asset_type: 'direction', status: 'locked', count: 1 }])
  })

  it('按依赖逆序删净项目且共享系统原型资源不受影响', async () => {
    const db = freshDb()
    const pid = seedProject(db, 'project:del')
    // 项目专属资源链：asset → resource
    const asset = seedAsset(db, pid, 'world_contract')
    // 共享系统原型资源：creator_profile_versions 引用，不属于项目删除面
    const sysRes = seedResource(db, '系统原型资源（跨项目共享）')
    const profileId = 'creator_profile:sys'
    const versionId = 'creator_version:sys'
    db.prepare("INSERT INTO creator_profiles (id, display_name, status, ownership) VALUES (?, ?, 'active', 'author_kernel')")
      .run(profileId, '系统分身')
    db.prepare(
      'INSERT INTO creator_profile_versions (id, profile_id, revision, subject_hash, content_resource_id) VALUES (?, ?, 1, ?, ?)',
    ).run(versionId, profileId, contentHash('系统内核'), sysRes)
    // 审查记录挂在 asset 上（reviews 表）
    const reviewId = newId('review')
    db.prepare(
      "INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict, reviewer_profile) VALUES (?, 'planning_asset', ?, ?, 'approved', 'agent')",
    ).run(reviewId, asset, contentHash('review:' + asset))

    const ids = collectIds(db, pid)
    expect(ids.resources.size).toBeGreaterThanOrEqual(1)

    const steps = deleteProject(db, pid, ids)
    const byLabel = new Map(steps.map((s) => [s.label, s.changes]))
    expect(byLabel.get('projects')).toBe(1)
    expect(byLabel.get('resources')).toBe(ids.resources.size)
    expect(byLabel.get('reviews')).toBe(1)

    const v = verify(db, pid)
    expect(v.projectLeft).toBe(0)
    expect(v.planningAssetsLeft).toBe(0)
    // 共享系统原型完好
    expect((db.prepare('SELECT count(*) AS n FROM creator_profile_versions WHERE id=?').get(versionId) as { n: number }).n).toBe(1)
    expect((db.prepare('SELECT count(*) AS n FROM resources WHERE id=?').get(sysRes) as { n: number }).n).toBe(1)
  })

  it('cleanOrphans 清理历史遗留孤儿并计入 verify 报告', async () => {
    const db = freshDb()
    const pid = seedProject(db, 'project:o')
    const asset = seedAsset(db, pid, 'direction')
    const reviewId = newId('review')
    db.prepare(
      "INSERT INTO reviews (id, subject_type, subject_ref, subject_hash, verdict, reviewer_profile) VALUES (?, 'planning_asset', ?, ?, 'approved', 'agent')",
    ).run(reviewId, asset, contentHash('review:' + asset))
    // 制造孤儿：直接删 asset 不删 review（模拟历史遗留）
    db.prepare('DELETE FROM planning_asset_dependencies WHERE asset_id=? OR upstream_asset_id=?').run(asset, asset)
    db.prepare('UPDATE planning_assets SET content_resource_id=(SELECT id FROM resources LIMIT 1) WHERE id=?').run(asset)
    db.prepare('DELETE FROM planning_assets WHERE id=?').run(asset)

    let v = verify(db, pid)
    expect(v.orphanReviews).toBe(1)
    const cleaned = cleanOrphans(db)
    expect(cleaned.reviews).toBe(1)
    v = verify(db, pid)
    expect(v.orphanReviews).toBe(0)
    expect(v.orphanDependencies).toBe(0)
  })

  it('事务失败整体回滚且外键开关复原', async () => {
    const db = freshDb()
    const pid = seedProject(db, 'project:r')
    const asset = seedAsset(db, pid, 'direction')
    const ids = collectIds(db, pid)
    // 注入一个会失败的步骤：临时把 projects 改名使 DELETE 影响行数为 0 不算失败——
    // 改为直接破坏：把 assets 里塞入不存在 id 使 IN 删除仍成功……改用触发器强制失败。
    db.exec(`CREATE TRIGGER fail_projects BEFORE DELETE ON projects BEGIN SELECT RAISE(ABORT, 'injected failure'); END`)
    const { GateFail } = await import('../src/gate/primitives.ts')
    expect(() => deleteProject(db, 'project:r', ids)).toThrow(GateFail)
    // 回滚完整：资产仍在、外键约束恢复 ON（依赖边引用不存在的 asset 应被 FK 拒绝）
    expect(assetStatus(db, asset)).toBe('locked')
    expect(() => seedDependency(db, 'planning:ghost', asset, 1)).toThrow()
  })
})
