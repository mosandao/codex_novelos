/**
 * JS 写门 · 项目创建管线测试（R2）。
 * 真实词表 plugin/client/project-wizard-data.js + 真实 schemas（Ajv2020/Draft 2020-12）
 * + :memory: 库（schema.sql v18 基线）。
 */
import { describe, it, expect } from 'vitest'
import { DatabaseSync } from 'node:sqlite'
import { join } from 'node:path'
import { makeDb, REPO_ROOT, SCHEMAS_DIR } from './gate-fixture.mjs'
import {
  loadWizardData,
  loadSchema,
  pyJson,
  pyJsonCompact,
  deepEqual,
  validateRequest,
  validateKernelCandidate,
  validatePersonaCandidate,
  persistKernel,
  persistProject,
  stitchBoundPayload,
  checkMismatchAdjudication,
  SCALES,
} from '../src/gate/create-project.ts'
import { contentHash, GateFail } from '../src/gate/primitives.ts'

const WIZARD_FILE = join(REPO_ROOT, 'plugin', 'client', 'project-wizard-data.js')

function freshDb(): DatabaseSync {
  const db = makeDb()
  return db as DatabaseSync
}

const KERNEL_A = () => ({
  identity: {
    display_name: '内核甲',
    core_questions: ['何为正义', '代价几何'],
    value_axioms: ['真实高于舒适', '选择定义人'],
    aesthetic_commitments: [],
    creative_axioms: [],
  },
  growth_log: ['初始融合：来自向导素材'],
})

function seedKernel(db: DatabaseSync, displayName = '内核甲') {
  const kernel = KERNEL_A()
  kernel.identity.display_name = displayName
  const json = pyJson(kernel)
  // rationale 必须可区分：deriv 资源受 UNIQUE(content_hash,media_type) 硬去重约束
  const cand = { mode: 'create', rationale: `种子数据：${displayName}`, display_name: displayName, kernel }
  const { kernelHash } = validateKernelCandidate(cand, db)
  if (kernelHash !== contentHash(json)) throw new Error('hash 前像不一致')
  const res = persistKernel(db, cand, kernelHash, null)
  return { versionId: res.kernel_version, hash: res.subject_hash, displayName, kernel }
}

function buildPayload(wizard: any, seeded: ReturnType<typeof seedKernel>) {
  const ch: string = Object.keys(wizard.channels)[0]
  const platform: string = wizard.channels[ch].platforms[0]
  let genres: string[] = wizard.genres[ch]
  if (!Array.isArray(genres)) genres = Object.keys(genres)
  const primaryGenre: string = genres[0]
  const tones: Array<{ value: string; pole: string }> = wizard.tone_pools[ch]
  const first = tones[0]
  const core = tones.find((t) => t.value !== first.value) ?? first
  const gp = wizard.genre_profiles?.[`${ch}|${primaryGenre}`] ?? null
  return {
    request_type: 'novelos.project.create.v3',
    setup: {
      title: '测试项目甲',
      channel: ch,
      platform,
      platform_traits: JSON.parse(JSON.stringify(wizard.platform_traits[platform])),
      scale: SCALES[1],
      primary_genre: primaryGenre,
      secondary_directions: [],
      emotional_surface: [first.value],
      emotional_core: core.value,
      tonal_contrast: null,
      aesthetic_styles: [wizard.aesthetic_styles[0]],
      genre_profile: gp ? JSON.parse(JSON.stringify(gp)) : null,
      reference_material: null,
      author_kernel: {
        mode: 'select',
        kernel_version_id: seeded.versionId,
        subject_hash: seeded.hash,
        display_name: seeded.displayName,
        kernel_hints: {},
      },
    },
  }
}

describe('序列化原语', () => {
  it('pyJsonCompact 对齐 Python 默认紧凑风格（键值间带空格）', () => {
    expect(pyJsonCompact({ a: 1, b: [1, 2], c: 'x', d: { e: null } }))
      .toBe('{"a": 1, "b": [1, 2], "c": "x", "d": {"e": null}}')
  })

  it('deepEqual 键序无关（快照比对语义）', () => {
    expect(deepEqual({ a: 1, b: [2, { c: 3 }] }, { b: [2, { c: 3 }], a: 1 })).toBe(true)
    expect(deepEqual({ a: 1 }, { a: 2 })).toBe(false)
  })
})

describe('入口校验 validateRequest', () => {
  const wizard = loadWizardData(WIZARD_FILE)

  it('E0 结构短路：坏载荷只报结构 FAIL 不进词表层', () => {
    const db = freshDb()
    const v = validateRequest({}, wizard, db, SCHEMAS_DIR)
    expect(v.errors).toHaveLength(1)
    expect(v.errors[0]).toContain('结构校验 FAIL')
  })

  it('合法 select 载荷通过（结构 + 词表级联 + 库内反查）零 FAIL', () => {
    const db = freshDb()
    const seeded = seedKernel(db)
    const payload = buildPayload(wizard, seeded)
    const v = validateRequest(payload, wizard, db, SCHEMAS_DIR)
    expect(v.errors).toEqual([])
  })

  it('subject_hash 与库内反查不符 → FAIL；伪造 platform → FAIL', () => {
    const db = freshDb()
    const seeded = seedKernel(db)
    const p1 = buildPayload(wizard, seeded)
    p1.setup.author_kernel.subject_hash = 'sha256:deadbeef'
    expect(validateRequest(p1, wizard, db, SCHEMAS_DIR).errors.join()).toContain('subject_hash')

    const p2 = buildPayload(wizard, seeded)
    p2.setup.platform = '__伪平台__'
    const v2 = validateRequest(p2, wizard, db, SCHEMAS_DIR)
    expect(v2.errors.join()).toContain('不属于')
  })
})

describe('内核候选门', () => {
  it('create 重名 → FAIL；revise 基底缺失 / growth_log 未追加 → FAIL', () => {
    const db = freshDb()
    seedKernel(db, '内核甲')
    // 同名新建
    const dup = validateKernelCandidate(
      { mode: 'create', rationale: 'x', display_name: '内核甲', kernel: KERNEL_A() },
      db,
    )
    expect(dup.errors.join()).toContain('重名')

    // revise 基底不存在
    const miss = validateKernelCandidate(
      { mode: 'revise', base_version: 'creator-profile-version:nope', rationale: 'x', kernel: KERNEL_A() },
      db,
    )
    expect(miss.errors.join()).toContain('库中不存在')

    // revise 正常路径（display_name 连续 + growth_log 追加）
    seedKernel(db, '内核乙')
    const okK = KERNEL_A(); okK.identity.display_name = '内核乙'; okK.growth_log.push('r2：归因修正')
    const okVersionId = (db.prepare(
      "SELECT v.id FROM creator_profile_versions v JOIN creator_profiles p ON p.id = v.profile_id "
      + "WHERE p.display_name = '内核乙'",
    ).get() as any).id
    const ok = validateKernelCandidate(
      { mode: 'revise', base_version: okVersionId, rationale: '演化', kernel: okK },
      db,
    )
    expect(ok.errors).toEqual([])
    const badK = KERNEL_A(); badK.identity.display_name = '内核乙'
    const bad = validateKernelCandidate(
      { mode: 'revise', base_version: okVersionId, rationale: '演化', kernel: badK },
      db,
    )
    expect(bad.errors.join()).toContain('growth_log')
  })
})

describe('全链路：建核 → 缝合 → 分身门 → 六表落库', () => {
  const wizard = loadWizardData(WIZARD_FILE)

  it('缝合后 payload 为 select 形态且通过入口校验', () => {
    const db = freshDb()
    const cand = { mode: 'create', rationale: '测试', display_name: '内核丙', kernel: KERNEL_A() }
    const { kernelHash } = validateKernelCandidate(cand, db)
    const k = persistKernel(db, cand, kernelHash, null)
    const rawPayload = buildPayload(wizard, {
      versionId: k.kernel_version,
      hash: k.subject_hash,
      displayName: cand.display_name,
      kernel: cand.kernel,
    })
    rawPayload.setup.author_kernel.mode = 'create' // create 形态入口也必须可过（schema 允许）
    const bound = stitchBoundPayload(rawPayload, k)
    expect(bound.setup.author_kernel.mode).toBe('select')
    expect(validateRequest(bound, wizard, db, SCHEMAS_DIR).errors).toEqual([])
    expect(bound.setup.author_kernel.kernel_version_id).toBe(k.kernel_version)
  })

  function makePersona(): any {
    return {
      narrative: '他出身小城，少年时因一次不公而学会先看后言。写作于他是把沉默者的证词誊清的工作，'
        + '既克制又固执：克制在于从不替人物辩护，固执在于非把因果链闭合不可。他自知的矛盾是'
        + '既渴望秩序又怀疑一切秩序的成本，这使他的叙事总在收束处留一道裂缝。他相信细节的重量'
        + '超过形容词的总和，因此在动笔前会反复核对手边的实物证据；对无法核实的事物，他宁可'
        + '让它停留在人物的目光之外，也不用想象去填补。这种近乎苛刻的诚实让他的文字显得冷淡，'
        + '但熟读的人知道那层冷淡下面是对被讲述者最深的敬意。',
      anchors: {
        profile_sketch: '小城出身的观察者型作者',
        five_dimensions: {
          generation_age: '八零末，县城成长',
          education_horizon: '地方本科，中文系',
          class_circle_inventory: '小镇公务员与个体户之间',
          career_track: '编辑转自由写作',
          life_trajectory: '两次迁居，一次失败创业',
        },
        trait_profile: ['记录癖：随身携带摘抄本', '延迟判断：听完三方再下结论', '仪式感：定稿前通读三遍'],
        theme_orientation: { dominant: 'agency', evidence: '主角总在被动局面里主动选择代价' },
        inner_tension: '既渴望秩序又怀疑秩序的成本——风格发动机，不许消解',
        voice_samples: ['灯还亮着，只是没人了。'],
        blindspots: {
          refuses: ['俯视式的苦难奇观'],
          cannot_write: ['金融圈与贵族院落的真实肌理'],
        },
      },
    }
  }

  function makePersonaCandidate(seeded: ReturnType<typeof seedKernel>) {
    return {
      parent_version_id: seeded.versionId,
      parent_subject_hash: seeded.hash,
      parent_rationale: '承接内核的追问方式，落位于本书题材',
      display_name: '分身丁',
      signature: {
        schema_version: 2,
        persona: makePersona(),
        sympathies: ['在秩序中寻找例外', '对沉默者抱有耐心'],
        distrusts: ['轻率的原谅', '无代价的救赎'],
        recurring_attention: ['被忽略的旁观者', '重复出现的小物件'],
        narrative_principles: ['先给后果再补动机', '场景内解决冲突'],
        forbidden_conveniences: ['巧合救场', '反派自述动机'],
        expression_preferences: ['短句收尾', '动作代替心理描写'],
        negative_constraints: ['不写超自然', '不使用第一人称'],
        kernel_origin: {
          kernel_version_id: seeded.versionId,
          kernel_subject_hash: seeded.hash,
        },
      },
    }
  }

  it('分身门三查：parent 反查 / 逐字复制 / 条数', () => {
    const db = freshDb()
    const seeded = seedKernel(db)
    const payload = buildPayload(wizard, seeded)

    const good = validatePersonaCandidate(makePersonaCandidate(seeded), payload, db, SCHEMAS_DIR)
    expect(good.errors).toEqual([])

    // 逐字复制父值
    const copy = makePersonaCandidate(seeded)
    copy.signature.sympathies = ['何为正义', '代价几何']
    expect(validatePersonaCandidate(copy, payload, db).errors.join()).toContain('逐字复制父值')

    // 条数越界（1 条）
    const few = makePersonaCandidate(seeded)
    few.signature.distrusts = ['只有一条']
    expect(validatePersonaCandidate(few, payload, db).errors.join()).toContain('超出 2-4')

    // parent hash 不符
    const badHash = makePersonaCandidate(seeded)
    badHash.parent_subject_hash = 'sha256:0'
    expect(validatePersonaCandidate(badHash, payload, db).errors.join()).toContain('parent_subject_hash')

    // display_name 逐字复制内核名
    const copyName = makePersonaCandidate(seeded)
    copyName.display_name = seeded.displayName
    expect(validatePersonaCandidate(copyName, payload, db).errors.join()).toContain('逐字复制内核名')
  })

  it('六表单事务落库 + metadata_json 快照 + 回滚干净', () => {
    const db = freshDb()
    const seeded = seedKernel(db)
    const payload = buildPayload(wizard, seeded)
    const candidate = makePersonaCandidate(seeded)
    const { sigHash } = validatePersonaCandidate(candidate, payload, db)
    const ids = persistProject(db, payload, candidate, sigHash)

    expect(ids.project!.startsWith('project:')).toBe(true)
    expect((db.prepare('SELECT COUNT(*) AS n FROM projects').get() as any).n).toBe(1)
    expect((db.prepare('SELECT COUNT(*) AS n FROM creator_profiles').get() as any).n).toBe(2) // 内核+分身
    expect((db.prepare('SELECT COUNT(*) AS n FROM creator_profile_versions').get() as any).n).toBe(2)
    expect((db.prepare('SELECT COUNT(*) AS n FROM project_creator_bindings').get() as any).n).toBe(1)
    expect((db.prepare('SELECT COUNT(*) AS n FROM resources').get() as any).n).toBe(4) // 内核+派生+签名+项目派生

    const proj = db.prepare('SELECT * FROM projects WHERE id = ?').get(ids.project) as any
    expect(proj.name).toBe('测试项目甲')
    expect(proj.metadata_json.startsWith('{"setup_schema_version": 3,')).toBe(true)
    expect(JSON.parse(proj.metadata_json).setup.title).toBe('测试项目甲')

    const binding = db.prepare('SELECT * FROM project_creator_bindings').get() as any
    expect(binding.binding_mode).toBe('kernel_derive')
    expect(binding.kernel_version_id).toBe(seeded.versionId)
    expect(binding.profile_revision).toBe(1)
  })

  it('UNIQUE(content_hash,media_type) 撞车 → 业务 FAIL 且事务整体回滚', () => {
    const db = freshDb()
    const cand = { mode: 'create', rationale: '同内容两次', display_name: '内核戊', kernel: KERNEL_A() }
    const { kernelHash } = validateKernelCandidate(cand, db)
    persistKernel(db, cand, kernelHash, null)
    const before = (db.prepare('SELECT COUNT(*) AS n FROM resources').get() as any).n
    try {
      persistKernel(db, cand, kernelHash, null)
      throw new Error('应当抛出 GateFail')
    } catch (e) {
      expect(e).toBeInstanceOf(GateFail)
      expect((e as Error).message).toContain('资源重复')
    }
    expect((db.prepare('SELECT COUNT(*) AS n FROM resources').get() as any).n).toBe(before)
  })
})

describe('裁决门（红队 F2 整改）', () => {
  it('mismatch 标记默认阻断，显式用户裁决放行', () => {
    const candidate = { parent_rationale: '……但存在错配警告：根本冲突未调和……' }
    expect(() => checkMismatchAdjudication(candidate)).toThrow(GateFail)
    expect(() => checkMismatchAdjudication(candidate, { userAdjudicated: true })).not.toThrow()
    expect(() => checkMismatchAdjudication({ parent_rationale: '干净理由' })).not.toThrow()
  })
})

describe('schema 编译冒烟（Ajv2020 / Draft 2020-12）', () => {
  it('五个消费 schema 全部可编译', () => {
    for (const name of [
      'project-create-request.schema.json',
      'kernel-candidate.schema.json',
      'author-kernel.schema.json',
      'creator-derivation-candidate.schema.json',
      'creator-signature.schema.json',
    ]) {
      expect(() => loadSchema(SCHEMAS_DIR, name)).not.toThrow()
    }
  })
})
