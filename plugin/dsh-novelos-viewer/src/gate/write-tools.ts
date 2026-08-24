/**
 * JS 写门 · defineTool 注册层（R2 写口收口）。
 *
 * 这是 NovelOS 权威库的**唯一写入口**：五个工具对应 py CLI 五段管线，
 * 每次调用独立开连接、过门、事务落库；任何 FAIL 返回 ok:false 且不产生写入。
 * agent 无裸 SQL 写通道——绕过此层的写请求没有工具面。
 *
 * 与 py CLI 的对应：
 * - novelos_gate_entry      ← --payload（入口校验，只读）
 * - novelos_kernel_commit   ← --kernel-candidate [--payload] [--dry-run]
 * - novelos_project_commit  ← --candidate --payload [--dry-run]
 * - novelos_propagate_stale ← --asset [--check] [--fine]
 * - novelos_delete_project  ← --project [--dry-run] [--backup] [--clean-orphans]
 */
import { DatabaseSync } from 'node:sqlite'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { GateFail, parseCandidateText } from './primitives.js'
import {
  checkMismatchAdjudication,
  loadWizardData,
  persistKernel,
  persistProject,
  stitchBoundPayload,
  validateKernelCandidate,
  validatePersonaCandidate,
  validateRequest,
} from './create-project.js'
import { propagateStale } from './propagate-stale.js'
import {
  backupDatabase,
  cleanOrphans,
  collectIds,
  deleteProject,
  surveyProject,
  verify,
} from './delete-project.js'

export interface WriteToolDeps {
  /** 解析当前权威库路径（null = 未找到） */
  dbPath(): string | null
  /** config/schemas 目录（null = 仓库根未找到） */
  schemasDir(): string | null
  /** plugin/client/project-wizard-data.js 路径 */
  wizardFile(): string | null
}

function errText(e: unknown): string {
  if (e instanceof GateFail) return e.message
  if (e instanceof Error) return e.message
  return String(e)
}

function parseJsonText(text: string, what: string): unknown {
  try {
    return JSON.parse(text)
  } catch (e) {
    throw new GateFail(`${what} 不是合法 JSON：${errText(e)}`)
  }
}

/** 统一输出渲染：canonical value 为 JSON 字符串 */
const STRING_OUTPUT = {
  schema: { type: 'string' as const },
  render: (_args: unknown, value: unknown) => [{ type: 'text' as const, text: String(value) }],
}

function openDb(dbPath: string): DatabaseSync {
  const conn = new DatabaseSync(dbPath)
  conn.exec('PRAGMA foreign_keys = ON')
  return conn
}

/** 构建三个写门工具（宿主在 apply 里逐个 register） */
export function createWriteTools(deps: WriteToolDeps) {
  const requireCtx = (): { db: string; schemas: string; wizard: string } => {
    const db = deps.dbPath()
    const schemas = deps.schemasDir()
    const wizard = deps.wizardFile()
    if (!db) throw new GateFail('data/novelos-v2.db 未找到（检查插件设置或工作区）')
    if (!schemas) throw new GateFail('config/schemas 目录未找到')
    if (!wizard) throw new GateFail('plugin/client/project-wizard-data.js 未找到')
    return { db, schemas, wizard }
  }

  const gateEntry = defineTool({
    name: 'novelos_gate_entry',
    description: 'NovelOS 入口校验门（只读）：校验向导产出的 novelos.project.create.v3 JSON '
      + '（ajv 结构 + 词表级联 + 内核库内反查）。FAIL 必须整改后重提，禁止绕过。',
    parameters: {
      payload: { type: 'string', description: 'novelos.project.create.v3 JSON 文本', required: true },
    },
    output: STRING_OUTPUT,
    async execute(args: any) {
      const { db, schemas, wizard } = requireCtx()
      const payload = parseJsonText(String(args.payload), 'payload') as Record<string, any>
      const conn = new DatabaseSync(db, { readOnly: true })
      try {
        const v = validateRequest(payload, loadWizardData(wizard), conn, schemas)
        return JSON.stringify({ ok: v.errors.length === 0, ...v })
      } finally {
        conn.close()
      }
    },
  })

  const kernelCommit = defineTool({
    name: 'novelos_kernel_commit',
    description: 'NovelOS 内核阶段写门：容错解析内核融合候选 → 信封+author-kernel 校验 → '
      + 'revise 基底反查 / create 重名查 → 单事务落库。mode=create 且提供 payload 时自动缝合 select 形态返回 boundPayload。'
      + 'dryRun=true 只校验不落库。',
    parameters: {
      candidate: { type: 'string', description: '融合智能体产出的内核候选原文（裸 JSON 或带围栏）', required: true },
      payload: { type: 'string', description: '项目创建 payload JSON（mode=create 建快照并缝合时需要）' },
      dryRun: { type: 'boolean', description: '只校验不落库' },
    },
    output: STRING_OUTPUT,
    async execute(args: any) {
      const { db, schemas } = requireCtx()
      const parsed = parseCandidateText(String(args.candidate), 'kernel')
      const candidate = parsed.obj as Record<string, any>
      let payload: Record<string, any> | null = null
      if (args.payload != null && String(args.payload).trim()) {
        payload = parseJsonText(String(args.payload), 'payload') as Record<string, any>
      }
      const conn = openDb(db)
      try {
        const { errors, kernelHash } = validateKernelCandidate(candidate, conn, schemas)
        if (errors.length) {
          return JSON.stringify({ ok: false, stage: 'kernel', errors, notes: parsed.notes })
        }
        if (args.dryRun === true) {
          return JSON.stringify({ ok: true, dryRun: true, subject_hash: kernelHash, notes: parsed.notes })
        }
        const ids = persistKernel(conn, candidate, kernelHash, payload)
        let boundPayload: unknown = undefined
        if (payload?.setup?.author_kernel?.mode === 'create') {
          boundPayload = stitchBoundPayload(payload, ids as { kernel_version: string; subject_hash: string })
        }
        return JSON.stringify({ ok: true, notes: parsed.notes, ids, boundPayload })
      } catch (e) {
        return JSON.stringify({ ok: false, stage: 'kernel', error: errText(e) })
      } finally {
        conn.close()
      }
    },
  })

  const projectCommit = defineTool({
    name: 'novelos_project_commit',
    description: 'NovelOS 项目落库写门（六表单事务）：容错解析分身融合候选 → 信封+签名v2+parent反查+'
      + '逐字复制+条数校验 → 错配裁决门（parent_rationale 含错配警告时必须 userAdjudicated=true 才放行，F2 整改）→ '
      + 'projects/creator_profiles/creator_profile_versions/resources×2/project_creator_bindings 一次写入。'
      + 'dryRun=true 只校验不落库。',
    parameters: {
      payload: { type: 'string', description: 'select 形态 payload JSON（经缝合或原 select）', required: true },
      candidate: { type: 'string', description: '分身融合候选原文', required: true },
      userAdjudicated: { type: 'boolean', description: '用户已对 mismatch 冲突作出裁决（默认 false=阻断）' },
      dryRun: { type: 'boolean', description: '只校验不落库' },
    },
    output: STRING_OUTPUT,
    async execute(args: any) {
      const { db, schemas } = requireCtx()
      const parsed = parseCandidateText(String(args.candidate), 'persona')
      const candidate = parsed.obj as Record<string, any>
      const payload = parseJsonText(String(args.payload), 'payload') as Record<string, any>
      const conn = openDb(db)
      try {
        const { errors, sigHash } = validatePersonaCandidate(candidate, payload, conn, schemas)
        if (errors.length) {
          return JSON.stringify({ ok: false, stage: 'project', errors, notes: parsed.notes })
        }
        // 裁决门：mismatch 标记命中且无显式用户裁决 → 阻断（红队 F2 整改）
        try {
          checkMismatchAdjudication(candidate, { userAdjudicated: args.userAdjudicated === true })
        } catch (e) {
          return JSON.stringify({ ok: false, stage: 'adjudication', error: errText(e), sigHash })
        }
        if (args.dryRun === true) {
          return JSON.stringify({ ok: true, dryRun: true, sigHash, notes: parsed.notes })
        }
        const ids = persistProject(conn, payload, candidate, sigHash)
        return JSON.stringify({ ok: true, notes: parsed.notes, ids })
      } catch (e) {
        return JSON.stringify({ ok: false, stage: 'project', error: errText(e) })
      } finally {
        conn.close()
      }
    },
  })

  const propagateStaleTool = defineTool({
    name: 'novelos_propagate_stale',
    description: 'NovelOS stale 传播写门：上游规划资产修订后沿 planning_asset_dependencies 依赖图标记下游 '
      + 'locked 资产为 stale。默认粗模式（直接+间接全量标）；fine=true 精细模式（依赖边版本+content_hash 双重比对，'
      + '内容未变的下游不误伤，间接下游仅列待重估不自动标）。dryRun=true 干跑只报告。',
    parameters: {
      asset: { type: 'string', description: '变更的上游 asset_id（如 planning:xxx）', required: true },
      fine: { type: 'boolean', description: '精细模式：内容未变不误伤（默认 false=粗模式全量标）' },
      dryRun: { type: 'boolean', description: '干跑：只显示会被标记的资产，不执行 UPDATE' },
    },
    output: STRING_OUTPUT,
    async execute(args: any) {
      const { db } = requireCtx()
      const conn = openDb(db)
      try {
        const report = propagateStale(conn, String(args.asset), {
          fine: args.fine === true,
          dryRun: args.dryRun === true,
        })
        return JSON.stringify({ ok: true, ...report })
      } catch (e) {
        return JSON.stringify({ ok: false, stage: 'propagate_stale', error: errText(e) })
      } finally {
        conn.close()
      }
    },
  })

  const deleteProjectTool = defineTool({
    name: 'novelos_delete_project',
    description: 'NovelOS 项目删除写门：按依赖逆序在 foreign_keys=OFF 下逐表删除项目全部内容'
      + '（不动 creator_profile_versions 引用的跨项目共享系统原型资源），删后 foreign_keys=ON 复验完整性。'
      + 'dryRun=true 只调查规模不删除；backup=true 删前备份数据库文件。'
      + 'md 投影目录已随视图链退役，无需清理。',
    parameters: {
      project: { type: 'string', description: '项目 ID（如 project:xxx）', required: true },
      dryRun: { type: 'boolean', description: '只调查项目范围，不删除' },
      backup: { type: 'boolean', description: '删前备份数据库文件（.bak-时间戳）' },
      cleanOrphans: { type: 'boolean', description: '额外清理全库孤儿 reviews/dependencies' },
    },
    output: STRING_OUTPUT,
    async execute(args: any) {
      const { db } = requireCtx()
      const pid = String(args.project)
      const conn = openDb(db)
      try {
        const survey = surveyProject(conn, pid)
        if (args.dryRun === true) {
          return JSON.stringify({ ok: true, dryRun: true, survey })
        }
        let backupPath: string | undefined
        if (args.backup === true) backupPath = backupDatabase(db)
        const steps = deleteProject(conn, pid, collectIds(conn, pid))
        let orphans: ReturnType<typeof cleanOrphans> | undefined
        if (args.cleanOrphans === true) orphans = cleanOrphans(conn)
        const verification = verify(conn, pid)
        return JSON.stringify({ ok: true, project: survey.project, steps, orphans, verification, backupPath })
      } catch (e) {
        return JSON.stringify({ ok: false, stage: 'delete_project', error: errText(e) })
      } finally {
        conn.close()
      }
    },
  })

  return [
    { tool: gateEntry, label: '@dsh-external/dsh-novelos-viewer: gate entry tool' },
    { tool: kernelCommit, label: '@dsh-external/dsh-novelos-viewer: kernel commit tool' },
    { tool: projectCommit, label: '@dsh-external/dsh-novelos-viewer: project commit tool' },
    { tool: propagateStaleTool, label: '@dsh-external/dsh-novelos-viewer: propagate stale tool' },
    { tool: deleteProjectTool, label: '@dsh-external/dsh-novelos-viewer: delete project tool' },
  ]
}
