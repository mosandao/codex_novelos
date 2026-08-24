import { describe, it, expect } from 'vitest'
import { makeDb } from './gate-fixture.mjs'

describe('gate fixture', () => {
  it('builds a production-equivalent 25-table memory DB', () => {
    const db = makeDb()
    const tables = db
      .prepare("select name from sqlite_master where type='table' order by name")
      .all()
      .map((r) => r.name)
    expect(tables.length).toBe(25)
    expect(tables).toContain('projects')
    expect(tables).toContain('creator_profiles')
    expect(tables).toContain('creator_profile_versions')
    expect(tables).toContain('planning_assets')
    expect(tables).toContain('resources')
    // 空库：无项目
    expect(db.prepare('select count(*) n from projects').get().n).toBe(0)
    db.close()
  })

  it('enforces foreign keys', () => {
    const db = makeDb()
    expect(db.prepare('pragma foreign_keys').get().foreign_keys).toBe(1)
    db.close()
  })
})
