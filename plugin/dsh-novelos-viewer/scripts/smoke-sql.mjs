// 六视图 SQL 冒烟测试：与 src/client/index.ts 的 VIEWS 查询逐一对应，
// 用真实 wasm + 真实 db 字节在 Node 中执行（sql.js 同为 WASM，行为一致）。
import initSqlJs from 'sql.js'
import { readFileSync } from 'node:fs'

const SQL = await initSqlJs({
  locateFile: () => 'D:/github/codex_novelos/plugin/dsh-novelos-viewer/node_modules/sql.js/dist/sql-wasm.wasm',
})
const db = new SQL.Database(new Uint8Array(readFileSync('D:/github/codex_novelos/data/novelos-v2.db')))

const QUERIES = [
  // overview
  `select id, name, description, version, updated_at from projects`,
  `select name from sqlite_master where type='table' order by name`,
  `select id, display_name, status, version, created_at, updated_at, ownership from creator_profiles order by created_at desc limit 20`,
  // volume-outline
  `select id, book_id, number, title, status, updated_at from volumes order by number`,
  `select id, asset_type, revision, status, scope_ref, producer_role, updated_at from planning_assets where asset_type like '%volume%' order by updated_at desc`,
  // chapters
  `select id, volume_id, number, title, status, summary, updated_at from chapters order by volume_id, number`,
  `select id, asset_type, revision, status, scope_ref, updated_at from planning_assets where asset_type like '%chapter%' order by updated_at desc`,
  // characters
  `select id, name, role_class, status, updated_at from characters order by name`,
  `select id, revision, status, scope_ref, updated_at from planning_assets where asset_type = 'character_contract' order by updated_at desc`,
  // world
  `select id, name, updated_at from worlds order by name`,
  `select name, updated_at from rules order by name limit 50`,
  `select name, updated_at from factions order by name limit 50`,
  `select id, revision, status, scope_ref, updated_at from planning_assets where asset_type = 'world_contract' order by updated_at desc`,
  // continuity
  `select count(*) from chapter_facts`,
  `select count(*) from relationship_states`,
  `select count(*) from expectation_ledgers`,
  `select count(*) from narrative_promises`,
  `select count(*) from arc_states`,
  `select count(*) from timelines`,
  `select count(*) from continuity_candidate_sets`,
  `select id, subject_type, subject_ref, verdict, created_at from reviews order by created_at desc limit 50`,
]

let pass = 0
for (const sql of QUERIES) {
  try {
    const r = db.exec(sql)
    console.log(`OK (${r[0]?.values.length ?? 0} rows) <- ${sql.slice(0, 70)}`)
    pass++
  } catch (e) {
    console.log(`FAIL: ${e.message}\n  ${sql}`)
  }
}
console.log(`\n${pass}/${QUERIES.length} queries passed`)
process.exit(pass === QUERIES.length ? 0 : 1)
