/**
 * @dsh-external/dsh-novelos-viewer — client 面板（conversation.view slot）。
 *
 * 架构（docs/novelos-viewer-design.md）：
 * - client 端 sql.js(WASM) 内存直读 host 提供的 data/novelos-v2.db 字节流，
 *   纯 JS 渲染六视图；物理只读（sql.js 无回写 API），零子进程零 argv。
 * - ⚠️ 两个必坑（2026-08 实测）：① apply 用 ctx.slots 必须 export const inject
 *   = ['slots']；② register 必须带 name 字段——缺 name 报 "slot undefined is not declared"。
 */
import initSqlJs from 'sql.js'

/**
 * rc.7 安装版 dsh-client-ui-slots 不导出 SlotsService 类型（脚手架模板超前于
 * 安装版 .d.ts），这里按运行时 Service wrapper 实际面声明最小类型。
 */
type SlotsService = {
  inject(slot: string, factory: () => unknown): unknown
  register(options: Record<string, unknown>): unknown
}

type ClientContext = {
  slots: SlotsService
  effect(fn: () => unknown, label?: string): unknown
}

export const inject = ['slots']

const API = '/@dsh-external/dsh-novelos-viewer/api'
const PLUGIN_ID = '@dsh-external/dsh-novelos-viewer-panel'

// ---------- 查询辅助 ----------

type Db = { exec(sql: string): { columns: string[]; values: unknown[][] }[] }

function q(db: Db, sql: string): { columns: string[]; values: unknown[][] } | null {
  try {
    const r = db.exec(sql)
    return r.length ? r[0] : null
  } catch {
    return null
  }
}

function countOf(db: Db, table: string): number {
  const r = q(db, `select count(*) from "${table}"`)
  return r ? Number(r.values[0][0]) : 0
}

function rows(db: Db, sql: string): unknown[][] {
  return q(db, sql)?.values ?? []
}

// ---------- 六视图定义 ----------

interface ViewDef {
  id: string
  label: string
  render(root: HTMLElement, db: Db): void
}

function sectionTitle(root: HTMLElement, text: string): void {
  const h = document.createElement('h3')
  h.textContent = text
  h.style.cssText = 'margin:14px 0 6px;font-size:13px;color:#c9463d;letter-spacing:.12em;'
  root.appendChild(h)
}

function renderTable(root: HTMLElement, columns: string[], values: unknown[][]): void {
  if (!values.length) {
    const empty = document.createElement('div')
    empty.textContent = '暂无数据'
    empty.style.cssText = 'color:#8a7f76;font-size:12px;padding:4px 2px;'
    root.appendChild(empty)
    return
  }
  const table = document.createElement('table')
  table.style.cssText = 'width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px;'
  const thead = document.createElement('thead')
  const trh = document.createElement('tr')
  for (const c of columns) {
    const th = document.createElement('th')
    th.textContent = c
    th.style.cssText = 'text-align:left;color:#a89a8c;border-bottom:1px solid #3a332e;padding:4px 6px;font-weight:normal;'
    trh.appendChild(th)
  }
  thead.appendChild(trh)
  table.appendChild(thead)
  const tbody = document.createElement('tbody')
  for (const row of values.slice(0, 200)) {
    const tr = document.createElement('tr')
    for (const cell of row) {
      const td = document.createElement('td')
      const text = cell == null ? '—' : typeof cell === 'string' && cell.length > 80 ? cell.slice(0, 80) + '…' : String(cell)
      td.textContent = text
      td.title = typeof cell === 'string' ? cell : ''
      td.style.cssText = 'color:#d8cfc4;border-bottom:1px solid #26211d;padding:4px 6px;vertical-align:top;'
      tr.appendChild(td)
    }
    tbody.appendChild(tr)
  }
  table.appendChild(tbody)
  root.appendChild(table)
}

const VIEWS: ViewDef[] = [
  {
    id: 'overview',
    label: '总览',
    render(root, db) {
      sectionTitle(root, '项目')
      renderTable(root,
        ['id', 'name', 'description', 'version', 'updated_at'],
        rows(db, 'select id, name, description, version, updated_at from projects'))
      sectionTitle(root, '表行数')
      const tables = rows(db, "select name from sqlite_master where type='table' order by name").flat()
      const counts: unknown[][] = []
      for (const t of tables) {
        if (typeof t !== 'string') continue
        if (t === 'schema_migrations') continue
        const c = countOf(db, t)
        if (c > 0) counts.push([t, c])
      }
      renderTable(root, ['table', 'rows'], counts)
      sectionTitle(root, '创作档案')
      renderTable(root,
        ['id', 'parent_version', 'created_at'],
        rows(db, 'select id, parent_version, created_at from creator_profiles order by created_at desc limit 20'))
    },
  },
  {
    id: 'volume-outline',
    label: '卷纲',
    render(root, db) {
      sectionTitle(root, '卷')
      renderTable(root,
        ['id', 'index', 'title', 'status', 'updated_at'],
        rows(db, 'select id, idx, title, status, updated_at from volumes order by idx'))
      sectionTitle(root, '卷纲资产（planning_assets）')
      renderTable(root,
        ['id', 'asset_type', 'revision', 'status', 'scope_ref', 'producer_role', 'updated_at'],
        rows(db, `select id, asset_type, revision, status, scope_ref, producer_role, updated_at
                  from planning_assets where asset_type like '%volume%' order by updated_at desc`))
    },
  },
  {
    id: 'chapters',
    label: '章节',
    render(root, db) {
      sectionTitle(root, '章节')
      renderTable(root,
        ['id', 'volume_id', 'number', 'title', 'status', 'summary', 'updated_at'],
        rows(db, 'select id, volume_id, number, title, status, summary, updated_at from chapters order by volume_id, number'))
      sectionTitle(root, '章纲资产')
      renderTable(root,
        ['id', 'asset_type', 'revision', 'status', 'scope_ref', 'updated_at'],
        rows(db, `select id, asset_type, revision, status, scope_ref, updated_at
                  from planning_assets where asset_type like '%chapter%' order by updated_at desc`))
    },
  },
  {
    id: 'characters',
    label: '人物',
    render(root, db) {
      sectionTitle(root, '人物')
      renderTable(root,
        ['id', 'name', 'role_class', 'status', 'updated_at'],
        rows(db, 'select id, name, role_class, status, updated_at from characters order by name'))
      sectionTitle(root, '人物契约资产')
      renderTable(root,
        ['id', 'revision', 'status', 'scope_ref', 'updated_at'],
        rows(db, `select id, revision, status, scope_ref, updated_at
                  from planning_assets where asset_type = 'character_contract' order by updated_at desc`))
    },
  },
  {
    id: 'world',
    label: '世界',
    render(root, db) {
      sectionTitle(root, '世界')
      renderTable(root,
        ['id', 'name', 'updated_at'],
        rows(db, 'select id, name, updated_at from worlds order by name'))
      sectionTitle(root, '规则与阵营')
      renderTable(root, ['rules.name', 'rules.updated_at'], rows(db, 'select name, updated_at from rules order by name limit 50'))
      renderTable(root, ['factions.name', 'factions.updated_at'], rows(db, 'select name, updated_at from factions order by name limit 50'))
      sectionTitle(root, '世界契约资产')
      renderTable(root,
        ['id', 'revision', 'status', 'scope_ref', 'updated_at'],
        rows(db, `select id, revision, status, scope_ref, updated_at
                  from planning_assets where asset_type = 'world_contract' order by updated_at desc`))
    },
  },
  {
    id: 'continuity',
    label: '连续性',
    render(root, db) {
      sectionTitle(root, '连续性账本')
      const ledgers = [
        'chapter_facts', 'relationship_states', 'expectation_ledgers',
        'narrative_promises', 'arc_states', 'timelines', 'continuity_candidate_sets',
      ]
      const counts: unknown[][] = ledgers.map((t) => [t, countOf(db, t)])
      renderTable(root, ['ledger', 'rows'], counts)
      sectionTitle(root, '审查记录')
      renderTable(root,
        ['id', 'subject_type', 'subject_ref', 'verdict', 'created_at'],
        rows(db, 'select id, subject_type, subject_ref, verdict, created_at from reviews order by created_at desc limit 50'))
    },
  },
]

// ---------- 项目向导（R1-4）----------

/** 向导 iframe 经 JSON-RPC postMessage 与父页桥接；面板做最小应答器 */
let wizardContextSink: ((text: string) => void) | null = null
let bridgeInstalled = false

function installWizardBridge(): void {
  if (bridgeInstalled) return
  bridgeInstalled = true
  window.addEventListener('message', (event) => {
    const msg = event.data as any
    if (!msg || msg.jsonrpc !== '2.0') return
    if (msg.id !== undefined && msg.id !== null && msg.method === 'ui/initialize') {
      ;(event.source as Window | null)?.postMessage(
        { jsonrpc: '2.0', id: msg.id, result: { protocolVersion: '2026-01-26', capabilities: {} } }, '*')
      return
    }
    if (msg.method === 'ui/update-model-context' && Array.isArray(msg.params?.content)) {
      const text = msg.params.content.map((c: any) => String(c?.text ?? '')).join('\n')
      wizardContextSink?.(text)
    }
  })
}

function mountWizard(container: HTMLElement): void {
  installWizardBridge()
  container.textContent = ''
  const frame = document.createElement('iframe')
  frame.src = `${API}/wizard`
  frame.style.cssText = 'width:100%;height:78vh;min-height:560px;border:1px solid #3a332e;border-radius:4px;background:#161311;'
  container.appendChild(frame)
  const capLabel = document.createElement('div')
  capLabel.textContent = '向导提交的项目创建请求（v3）——复制后发给 Main Agent：'
  capLabel.style.cssText = 'font-size:12px;color:#a89a8c;margin:8px 0 4px;'
  const capBox = document.createElement('textarea')
  capBox.readOnly = true
  capBox.placeholder = '在向导中点击「生成」后，项目创建请求会出现在这里。'
  capBox.style.cssText = 'width:100%;height:160px;box-sizing:border-box;background:#0f0d0b;color:#d8cfc4;border:1px solid #3a332e;border-radius:3px;padding:6px;font-size:11px;font-family:monospace;'
  const copyBtn = document.createElement('button')
  copyBtn.textContent = '复制 JSON'
  copyBtn.style.cssText = 'margin-top:4px;border:1px solid #c9463d;background:transparent;color:#c9463d;border-radius:3px;padding:3px 10px;cursor:pointer;font-size:12px;'
  copyBtn.addEventListener('click', () => {
    navigator.clipboard?.writeText(capBox.value).catch(() => {})
    copyBtn.textContent = '已复制'
    setTimeout(() => { copyBtn.textContent = '复制 JSON' }, 1500)
  })
  container.append(capLabel, capBox, copyBtn)
  wizardContextSink = (text) => { capBox.value = text }
}

// ---------- 面板组件 ----------

export function apply(ctx: ClientContext): void {
  ctx.effect(() => ctx.slots.inject('conversation.view', () =>
    ctx.slots.register({
      name: 'conversation.view',
      id: PLUGIN_ID,
      label: () => 'NovelOS 查看器',
      component: () => ({
        render() {
          const el = document.createElement('div')
          el.style.cssText = [
            'padding:16px', 'background:#161311', 'min-height:100%',
            'font-family:"Noto Serif SC",serif', 'box-sizing:border-box',
          ].join(';')

          // 头部
          const head = document.createElement('div')
          head.style.cssText = 'margin-bottom:10px;'
          const title = document.createElement('div')
          title.textContent = 'NovelOS · 权威库查看器'
          title.style.cssText = 'font-size:18px;color:#d8cfc4;letter-spacing:.2em;margin-bottom:4px;'
          head.appendChild(title)
          const meta = document.createElement('div')
          meta.textContent = '加载中…'
          meta.style.cssText = 'font-size:11px;color:#8a7f76;white-space:pre-wrap;word-break:break-all;'
          head.appendChild(meta)
          el.appendChild(head)

          // 视图标签栏
          const tabs = document.createElement('div')
          tabs.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;'
          const content = document.createElement('div')
          el.appendChild(tabs)
          el.appendChild(content)

          // 「项目向导」入口（不依赖库加载成功，始终可用）
          const wizardBtn = document.createElement('button')
          wizardBtn.textContent = '项目向导'
          wizardBtn.style.cssText = [
            'border:1px solid #c9463d', 'border-radius:3px', 'padding:3px 12px',
            'font-size:12px', 'cursor:pointer', 'letter-spacing:.15em',
            'background:transparent', 'color:#c9463d',
          ].join(';')
          wizardBtn.addEventListener('click', () => {
            for (const b of Array.from(tabs.children)) {
              ;(b as HTMLElement).style.background = 'transparent'
              ;(b as HTMLElement).style.color = '#a89a8c'
            }
            wizardBtn.style.borderColor = '#c9463d'
            mountWizard(content)
          })
          const wizRow = document.createElement('div')
          wizRow.style.cssText = 'margin-bottom:8px;'
          wizRow.appendChild(wizardBtn)
          el.insertBefore(wizRow, tabs)

          let activeBtn: HTMLElement | null = null
          const activate = (v: ViewDef, db: Db | null) => {
            for (const b of Array.from(tabs.children)) {
              ;(b as HTMLElement).style.background = 'transparent'
              ;(b as HTMLElement).style.color = '#a89a8c'
            }
            activeBtn!.style.background = '#c9463d'
            activeBtn!.style.color = '#161311'
            content.textContent = ''
            if (!db) return
            v.render(content, db)
          }

          ;(async () => {
            // 1. manifest 元信息
            let manifest: any = null
            try {
              manifest = await (await fetch(`${API}/manifest`)).json()
            } catch {}
            if (!manifest?.ok) {
              meta.textContent = manifest?.error ?? 'host API 不可达'
              return
            }
            const kb = (manifest.sizeBytes / 1024).toFixed(1)
            meta.textContent =
              `${manifest.dbPath}\n${kb} KB · ${manifest.mtimeIso} · sha256 ${String(manifest.sha256).slice(0, 12)}…`

            // 2. 加载 sql.js WASM（由本插件 host 路由提供）
            const SQL = await initSqlJs({ locateFile: () => `${API}/sql-wasm.wasm` })

            // 3. 拉 db 字节流，内存打开（物理只读）
            const bytes = new Uint8Array(await (await fetch(`${API}/db-bytes`)).arrayBuffer())
            const db = new SQL.Database(bytes)

            // 4. 建标签并默认进「总览」
            for (const v of VIEWS) {
              const btn = document.createElement('button')
              btn.textContent = v.label
              btn.style.cssText = [
                'border:1px solid #3a332e', 'border-radius:3px', 'padding:3px 12px',
                'font-size:12px', 'cursor:pointer', 'letter-spacing:.15em',
                'background:transparent', 'color:#a89a8c',
              ].join(';')
              btn.addEventListener('click', () => activate(v, db))
              tabs.appendChild(btn)
            }
            activeBtn = tabs.children[0] as HTMLElement
            activate(VIEWS[0], db)
          })().catch((e) => {
            meta.textContent = '加载失败：' + (e instanceof Error ? e.message : String(e))
          })

          return el
        },
      }),
    }),
  ), PLUGIN_ID)
}
