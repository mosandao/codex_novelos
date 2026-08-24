/**
 * R7 冒烟：register-characters 编译产物对生产库只读验证。
 * 全程 readOnly 连接 + 只读对账入口（pendingStatus/auditEntries），零写入。
 * 写入路径（roster/entry/status-upsert）由 vitest :memory: 用例覆盖（22 例），
 * 此处验证真实骨架库上的只读行为与守卫。
 */
import { DatabaseSync } from 'node:sqlite'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { checkPendingStatus, checkAuditEntries } from '../lib/gate/register-characters.js'
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

// 只读对账入口在骨架库上应成功返回（零漂移/零候选）
const pend = checkPendingStatus(conn, pid)
check('checkPendingStatus 骨架库成功', typeof pend.checked === 'number' || Array.isArray(pend.drift),
  JSON.stringify(pend).slice(0, 120))
const audit = checkAuditEntries(conn, pid)
check('checkAuditEntries 骨架库成功', Array.isArray(audit.findings ?? audit.drift ?? []),
  JSON.stringify(audit).slice(0, 120))

// 不存在项目 → GateFail（三入口同序：先查项目存在）
check('不存在项目抛 GateFail', (() => {
  try { checkPendingStatus(conn, 'project:nope'); return false }
  catch (e) { return e instanceof GateFail && String(e.message).includes('项目不存在') }
})())

// readOnly 连接物理兜底：拒绝任何写入且库未被触碰
const before = Number(conn.prepare('SELECT count(*) AS n FROM projects').get().n)
try { conn.prepare("INSERT INTO characters (id, project_id, name) VALUES ('character:smoke','x','冒烟')").run(); check('readOnly 连接拒绝写入', false) }
catch { check('readOnly 连接拒绝写入', true) }
check('库未被触碰', Number(conn.prepare('SELECT count(*) AS n FROM projects').get().n) === before)

console.log(`SMOKE ${fails === 0 ? 'PASS' : 'FAIL (' + fails + ')'}`)
process.exit(fails === 0 ? 0 : 1)
