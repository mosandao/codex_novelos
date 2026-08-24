/**
 * R6 冒烟：propagate-stale + delete-project 编译产物对生产库只读验证。
 * 全程 readOnly 连接 + dryRun，零写入。骨架库无 planning_assets，
 * 成功路径由 vitest :memory: 用例覆盖（10/10），此处验证只读真实库上的行为。
 */
import { DatabaseSync } from 'node:sqlite'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { propagateStale } from '../lib/gate/propagate-stale.js'
import { surveyProject } from '../lib/gate/delete-project.js'
import { GateFail } from '../lib/gate/primitives.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const REPO = join(HERE, '..', '..', '..')
const DB = join(REPO, 'data', 'novelos-v2.db')

const conn = new DatabaseSync(DB, { readOnly: true })
let fails = 0
const check = (name, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${detail ? '  ' + detail : ''}`)
  if (!cond) fails++
}

const pid = (conn.prepare('SELECT id FROM projects LIMIT 1').get() ?? {}).id
check('生产库项目存在', !!pid, String(pid))

const s = surveyProject(conn, pid)
check('survey 规模', s.counts.books === 0 && s.project.id === pid,
  `books=${s.counts.books} resources=${s.counts.resources} chars=${s.counts.characters}`)

check('不存在资产抛 GateFail', (() => {
  try { propagateStale(conn, 'planning:nope'); return false }
  catch (e) { return e instanceof GateFail && String(e.message).includes('资产不存在') }
})())

// 真实 locked 资产存在则走 dryRun 报告路径（骨架库为空时跳过）
const anyAsset = conn.prepare("SELECT id FROM planning_assets WHERE status='locked' LIMIT 1").get()
if (anyAsset) {
  const rep = propagateStale(conn, anyAsset.id, { dryRun: true })
  check('dryRun 粗模式报告', typeof rep.marked === 'number', `marked=${rep.marked}`)
} else {
  console.log('SKIP  dryRun 粗模式报告（骨架库无 locked 资产，vitest 已覆盖）')
}

const before = Number(conn.prepare('SELECT count(*) AS n FROM projects').get().n)
try { conn.prepare('DELETE FROM projects WHERE id=?').run(pid); check('readOnly 连接拒绝写入', false) }
catch { check('readOnly 连接拒绝写入', true) }
check('库未被触碰', Number(conn.prepare('SELECT count(*) AS n FROM projects').get().n) === before)

console.log(`SMOKE ${fails === 0 ? 'PASS' : 'FAIL (' + fails + ')'}`)
process.exit(fails === 0 ? 0 : 1)
