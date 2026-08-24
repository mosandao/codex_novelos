/**
 * JS 写门测试夹具助手（R2）。
 *
 * 用重生成后的 db/migrations/schema.sql（v18 终态合并基线，与生产 25 表全列一致）
 * 在 :memory: 里构建空库，供 ajv 门 + node:sqlite 事务测试使用。
 * 用法：node --test 或 vitest 中 `import { makeDb } from './gate-fixture.mjs'`。
 */
import { DatabaseSync } from 'node:sqlite'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
export const REPO_ROOT = resolveRepoRoot(HERE)
export const SCHEMA_SQL = join(REPO_ROOT, 'db', 'migrations', 'schema.sql')
export const SCHEMAS_DIR = join(REPO_ROOT, 'config', 'schemas')

function resolveRepoRoot(from) {
  let dir = from
  for (let i = 0; i < 6; i++) {
    if (exists(join(dir, 'AGENTS.md'))) return dir
    dir = dirname(dir)
  }
  throw new Error('repo root not found from ' + from)
}

function exists(p) {
  try { readFileSync(p); return true } catch { return false }
}

/** 构建与生产结构一致的内存空库（foreign_keys 开启） */
export function makeDb() {
  const db = new DatabaseSync(':memory:')
  db.exec('PRAGMA foreign_keys = ON')
  db.exec(readFileSync(SCHEMA_SQL, 'utf8'))
  return db
}
