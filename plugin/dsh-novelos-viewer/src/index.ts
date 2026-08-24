/**
 * @dsh-external/dsh-novelos-viewer — host 侧（ui-panel 形态）。
 *
 * 设计红线（docs/novelos-viewer-design.md + R2 写口收口）：
 * - 读路径：仅暴露零参数 GET 路由，物理只读；/db-bytes 返回 data/novelos-v2.db
 *   字节流，client 端 sql.js(WASM) 内存加载，零子进程、零 argv、零编码转换（F3/F4 整改）。
 * - 写路径：唯一写入口 = 本插件 defineTool 五写门工具（gate_entry / kernel_commit /
 *   project_commit / propagate_stale / delete_project），全部经 JS 校验门 + 单事务；
 *   agent 无裸 SQL 写通道。
 * - 多模型分工（R3）：设置卡 roleWriter/roleReviewer/roleMemory → /model-roles 路由
 *   + novelos_model_roles 工具，编排侧按 provider/model 覆盖，改配置不改代码。
 */
import { createHash } from 'node:crypto'
import { existsSync, readFileSync, realpathSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import z from '@deepseek-ai/schemastery'
import { DatabaseSync } from 'node:sqlite'
import { createWriteTools } from './gate/write-tools.js'

export const name = '@dsh-external/dsh-novelos-viewer'
export const inject = ['tools', 'webServer']

const API_PREFIX = '/@dsh-external/dsh-novelos-viewer/api'

export interface Config {
  title: string
  /** 显式指定 data/novelos-v2.db 绝对路径；留空则自动探测 */
  dbPath: string
  /**
   * 多模型分工映射（R3）：角色 → 'provider:model' 或裸 model 名。
   * 写作=强创意模型；审查=异构厂商模型（防共谋）；记忆=廉价快速模型。
   * 留空 = 不覆盖，沿用主会话模型。编排侧（workflow/subagent）经
   * /model-roles 路由或 novelos_model_roles 工具读取后按 provider/model 覆盖。
   */
  roleWriter: string
  roleReviewer: string
  roleMemory: string
}

export const Config = z.object({
  title: z.string().default('NovelOS 查看器'),
  dbPath: z.string().default(''),
  roleWriter: z.string().default(''),
  roleReviewer: z.string().default(''),
  roleMemory: z.string().default(''),
})

export interface ModelRoles {
  writer?: { provider?: string; model: string }
  reviewer?: { provider?: string; model: string }
  memory?: { provider?: string; model: string }
}

/** 解析 'provider:model' / 'model' / '' 为 workflow 可用的 provider/model 覆盖 */
export function parseModelRole(raw: string): { provider?: string; model: string } | null {
  const text = String(raw ?? '').trim()
  if (!text) return null
  const idx = text.indexOf(':')
  if (idx > 0) return { provider: text.slice(0, idx), model: text.slice(idx + 1) }
  return { model: text }
}

export function buildModelRoles(config: Config): ModelRoles {
  const out: ModelRoles = {}
  const writer = parseModelRole(config.roleWriter)
  if (writer) out.writer = writer
  const reviewer = parseModelRole(config.roleReviewer)
  if (reviewer) out.reviewer = reviewer
  const memory = parseModelRole(config.roleMemory)
  if (memory) out.memory = memory
  return out
}

const MODULE_DIR = dirname(fileURLToPath(import.meta.url))

/** 仓库根（lib → dsh-novelos-viewer → plugin → repo）；junction 加载时先 realpath 规范化 */
function resolveRepoRoot(): string | null {
  for (const base of [MODULE_DIR, (() => { try { return realpathSync(MODULE_DIR) } catch { return null } })()]) {
    if (!base) continue
    const root = resolve(base, '../../..')
    if (existsSync(join(root, 'AGENTS.md'))) return root
  }
  return null
}

function resolveClientFile(name: string): string | null {
  const root = resolveRepoRoot()
  const candidates: string[] = []
  if (root) candidates.push(join(root, 'plugin', 'client', name))
  candidates.push(resolve(MODULE_DIR, '../../client', name))
  for (const c of candidates) {
    try {
      if (existsSync(c) && statSync(c).isFile()) return c
    } catch {}
  }
  return null
}

function resolveDbPath(configDbPath: string): string | null {
  const candidates: string[] = []
  if (configDbPath) candidates.push(resolve(configDbPath))
  // 注入后模块经 profile node_modules junction 加载，import.meta.url 可能保留
  // junction 路径——先 realpath 规范化再回推仓库根（plugin/<name> → 上两级）。
  try {
    candidates.push(resolve(realpathSync(MODULE_DIR), '../../../data/novelos-v2.db'))
  } catch {}
  // 源码目录直载（无 junction）时上两级即仓库根
  candidates.push(resolve(MODULE_DIR, '../../../data/novelos-v2.db'))
  candidates.push(resolve(process.cwd(), 'data/novelos-v2.db'))
  for (const c of candidates) {
    try {
      if (existsSync(c) && statSync(c).isFile()) return c
    } catch {}
  }
  return null
}

function json(res: any, status: number, body: unknown): void {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8' })
  res.end(JSON.stringify(body))
}

// ---------- kernel-roster 实时直查（R1-4：替代静态镜像 kernel-roster.js）----------
// 与 legacy-python/scripts/novelos_export_kernel_roster.py 的 build_roster 同一 SQL：
// ownership='author_kernel' 且 status='active' 的内核，每 profile 取最高 revision。
// 镜像只是便利层，权威校验仍在 create_project 入口（库内反查）——此处直查消灭镜像过期。

interface RosterEntry {
  kernel_version_id: string
  subject_hash: string
  revision: number
  display_name: string
  core_questions: string[]
}

export function buildKernelRoster(dbPath: string): RosterEntry[] {
  const conn = new DatabaseSync(dbPath, { readOnly: true })
  try {
    const rows = conn.prepare(`
      SELECT v.id AS kernel_version_id, v.subject_hash, v.revision,
             p.display_name, CAST(r.content AS TEXT) AS kernel_json
      FROM creator_profile_versions v
      JOIN creator_profiles p ON p.id = v.profile_id
      JOIN resources r ON r.id = v.content_resource_id
      WHERE p.ownership = 'author_kernel' AND p.status = 'active'
        AND v.revision = (
            SELECT MAX(v2.revision) FROM creator_profile_versions v2
            WHERE v2.profile_id = v.profile_id)
      ORDER BY p.created_at DESC
    `).all() as Array<Record<string, unknown>>
    const roster: RosterEntry[] = []
    for (const row of rows) {
      let identity: any = {}
      try { identity = JSON.parse(String(row.kernel_json)).identity ?? {} } catch {}
      roster.push({
        kernel_version_id: String(row.kernel_version_id),
        subject_hash: String(row.subject_hash ?? ''),
        revision: Number(row.revision ?? 0),
        display_name: String(row.display_name ?? ''),
        core_questions: Array.isArray(identity.core_questions)
          ? identity.core_questions.slice(0, 3).map(String) : [],
      })
    }
    return roster
  } finally {
    conn.close()
  }
}

export function apply(ctx: Context, config: Config): void {
  const webServer = (ctx as unknown as { webServer: { register(cfg: unknown, label?: string): any } }).webServer
  ctx.effect(() => webServer.register({
    kind: 'prefix',
    path: API_PREFIX,
    handler: async (req: any, res: any) => {
      const url = String(req?.url ?? '')
      // 只允许 GET；其余一律 405（零参数只读路由）
      if ((req?.method ?? 'GET') !== 'GET') {
        return json(res, 405, { ok: false, error: 'read-only endpoint' })
      }

      if (url.includes('db-bytes')) {
        const db = resolveDbPath(config.dbPath)
        if (!db) return json(res, 404, { ok: false, error: 'data/novelos-v2.db not found' })
        const buf = readFileSync(db)
        res.writeHead(200, {
          'content-type': 'application/octet-stream',
          'content-length': buf.byteLength,
          'cache-control': 'no-store',
        })
        return res.end(buf)
      }

      if (url.includes('sql-wasm.wasm')) {
        // sql.js 由插件自带（dependencies），wasm 从包内 dist 提供
        const wasmCandidates = [
          resolve(MODULE_DIR, '../node_modules/sql.js/dist/sql-wasm.wasm'),
          resolve(MODULE_DIR, 'node_modules/sql.js/dist/sql-wasm.wasm'),
        ]
        for (const w of wasmCandidates) {
          if (existsSync(w)) {
            const buf = readFileSync(w)
            res.writeHead(200, {
              'content-type': 'application/wasm',
              'content-length': buf.byteLength,
              'cache-control': 'public, max-age=86400',
            })
            return res.end(buf)
          }
        }
        return json(res, 404, { ok: false, error: 'sql-wasm.wasm not found' })
      }

      // R1-4：项目向导三路由（wizard html / 静态数据 js / kernel-roster 实时直查）
      if (url.includes('project-wizard-data.js')) {
        const file = resolveClientFile('project-wizard-data.js')
        if (!file) return json(res, 404, { ok: false, error: 'project-wizard-data.js not found' })
        const buf = readFileSync(file)
        res.writeHead(200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' })
        return res.end(buf)
      }

      if (url.includes('kernel-roster.js')) {
        const db = resolveDbPath(config.dbPath)
        if (!db) return json(res, 404, { ok: false, error: 'data/novelos-v2.db not found' })
        let roster: RosterEntry[] = []
        try { roster = buildKernelRoster(db) } catch (e) {
          return json(res, 500, { ok: false, error: e instanceof Error ? e.message : String(e) })
        }
        const body = '// 由 @dsh-external/dsh-novelos-viewer host 实时直查生成（node:sqlite 只读）——请勿手改。\n'
          + 'window.NOVELOS_KERNEL_ROSTER = ' + JSON.stringify(roster, null, 2) + ';\n'
        res.writeHead(200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' })
        return res.end(body)
      }

      if (url.includes('/wizard')) {
        const file = resolveClientFile('project-wizard.html')
        if (!file) return json(res, 404, { ok: false, error: 'project-wizard.html not found' })
        // 相对 script src 改写为绝对 API 路径，使向导可在任意挂载深度下加载
        const html = readFileSync(file, 'utf8')
          .replaceAll('./project-wizard-data.js', `${API_PREFIX}/project-wizard-data.js`)
          .replaceAll('./kernel-roster.js', `${API_PREFIX}/kernel-roster.js`)
        res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' })
        return res.end(html)
      }

      // R3：多模型分工映射（设置卡配置，编排侧消费）
      if (url.includes('model-roles')) {
        return json(res, 200, { ok: true, roles: buildModelRoles(config) })
      }

      // 默认 = manifest：库文件元信息（大小/mtime/sha256），供面板校验新鲜度
      const db = resolveDbPath(config.dbPath)
      if (!db) {
        return json(res, 200, { ok: false, error: 'data/novelos-v2.db not found', title: config.title })
      }
      const st = statSync(db)
      const sha256 = createHash('sha256').update(readFileSync(db)).digest('hex')
      return json(res, 200, {
        ok: true,
        title: config.title,
        dbPath: db,
        sizeBytes: st.size,
        mtimeIso: st.mtime.toISOString(),
        sha256,
        api: [
          `${API_PREFIX}/manifest`, `${API_PREFIX}/db-bytes`, `${API_PREFIX}/sql-wasm.wasm`,
          `${API_PREFIX}/wizard`, `${API_PREFIX}/project-wizard-data.js`, `${API_PREFIX}/kernel-roster.js`,
          `${API_PREFIX}/model-roles`,
        ],
      })
    },
  }), '@dsh-external/dsh-novelos-viewer: readonly api')

  ctx.effect(() => ctx.tools.register(defineTool({
    name: 'novelos_viewer_status',
    description: '查看 NovelOS 权威库状态（只读）：解析到的 db 路径、大小、mtime、sha256。',
    parameters: {},
    output: {
      schema: { type: 'string' },
      render: (_args: unknown, value: unknown) => [{ type: 'text', text: String(value) }],
    },
    async execute() {
      const db = resolveDbPath(config.dbPath)
      if (!db) return JSON.stringify({ ok: false, error: 'data/novelos-v2.db not found' })
      const st = statSync(db)
      return JSON.stringify({
        ok: true,
        dbPath: db,
        sizeBytes: st.size,
        mtimeIso: st.mtime.toISOString(),
        sha256: createHash('sha256').update(readFileSync(db)).digest('hex'),
      })
    },
  })), '@dsh-external/dsh-novelos-viewer: status tool')

  // R3：多模型分工映射工具（编排侧 workflow/subagent 按 provider/model 覆盖）
  ctx.effect(() => ctx.tools.register(defineTool({
    name: 'novelos_model_roles',
    description: '读取 NovelOS 多模型分工映射（设置卡配置，只读）：writer（写作·强创意）/ '
      + 'reviewer（审查·异构厂商防共谋）/ memory（记忆提取·廉价快速）。返回 { provider?, model } 覆盖值，'
      + '供 workflow 编排 per-agent 指定；留空的角色表示沿用主会话模型。',
    parameters: {},
    output: {
      schema: { type: 'string' },
      render: (_args: unknown, value: unknown) => [{ type: 'text', text: String(value) }],
    },
    async execute() {
      return JSON.stringify({ ok: true, roles: buildModelRoles(config) })
    },
  })), '@dsh-external/dsh-novelos-viewer: model roles tool')

  // R2 写口收口：唯一写入口 = 校验门 defineTool（任何 FAIL 不产生写入）
  for (const { tool, label } of createWriteTools({
    dbPath: () => resolveDbPath(config.dbPath),
    schemasDir: () => {
      const root = resolveRepoRoot()
      if (!root) return null
      const dir = join(root, 'config', 'schemas')
      return existsSync(dir) ? dir : null
    },
    wizardFile: () => resolveClientFile('project-wizard-data.js'),
  })) {
    ctx.effect(() => ctx.tools.register(tool), label)
  }
}
