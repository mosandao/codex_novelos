/**
 * JS 写门冒烟：用编译产物（lib/gate/*）对真实词表 + 真实 schemas + 生产库（只读连接）
 * 跑入口校验。与 test/ 下 vitest 用例同源逻辑，验证宿主等价运行时（Node ESM）可用性。
 * 只读：gate_entry 阶段不产生任何写入。
 */
import { DatabaseSync } from 'node:sqlite'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadWizardData, validateRequest } from '../lib/gate/create-project.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const REPO = join(HERE, '..', '..', '..')
const WIZARD = join(REPO, 'plugin', 'client', 'project-wizard-data.js')
const SCHEMAS = join(REPO, 'config', 'schemas')
const DB = join(REPO, 'data', 'novelos-v2.db')

const wizard = loadWizardData(WIZARD)
const ch = Object.keys(wizard.channels)[0]
const platform = wizard.channels[ch].platforms[0]
let genres = wizard.genres[ch]
if (!Array.isArray(genres)) genres = Object.keys(genres)
const tones = wizard.tone_pools[ch]
const gp = wizard.genre_profiles?.[`${ch}|${genres[0]}`] ?? null

// mode=create 入口校验不触内核库内反查（hints/orphan 仅 WARN），适合只读冒烟
const payload = {
  request_type: 'novelos.project.create.v3',
  setup: {
    title: '写门冒烟测试（不入库）',
    channel: ch,
    platform,
    platform_traits: JSON.parse(JSON.stringify(wizard.platform_traits[platform])),
    scale: '中篇（30-100万字）',
    primary_genre: genres[0],
    secondary_directions: [],
    emotional_surface: [tones[0].value],
    emotional_core: (tones.find((t) => t.value !== tones[0].value) ?? tones[1]).value,
    tonal_contrast: null,
    aesthetic_styles: [wizard.aesthetic_styles[0]],
    genre_profile: gp ? JSON.parse(JSON.stringify(gp)) : null,
    reference_material: null,
    author_kernel: { mode: 'create', kernel_hints: {} },
  },
}

const conn = new DatabaseSync(DB, { readOnly: true })
try {
  const v = validateRequest(payload, wizard, conn, SCHEMAS)
  console.log('positive(create-mode):', JSON.stringify(v))
  if (v.errors.length !== 0) process.exitCode = 1

  const bad = validateRequest({}, wizard, conn, SCHEMAS)
  console.log('negative(structural):', JSON.stringify(bad.errors))
  if (!(bad.errors.length === 1 && bad.errors[0].includes('结构校验 FAIL'))) process.exitCode = 1
  console.log(process.exitCode === 1 ? 'SMOKE FAIL' : 'SMOKE PASS')
} finally {
  conn.close()
}
