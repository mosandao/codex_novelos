/**
 * JS 写门 · 人物注册表登记/状态迁移测试。
 * 权威对照：legacy-python/scripts/novelos_register_characters.py；
 * :memory: 库（schema.sql v18 基线）+ 真实 planning-candidate.schema.json。
 */
import { describe, it, expect } from 'vitest'
import type { DatabaseSync } from 'node:sqlite'
import { makeDb, SCHEMAS_DIR } from './gate-fixture.mjs'
import { contentHash, GateFail, newId } from '../src/gate/primitives.ts'
import {
  STATUS_VALUES, EXIT_TYPES, EXIT_STATUSES, normName,
  validateRoster, validateEntries, validateStatusUpdate,
  registerCharactersRun, checkPendingStatus, checkAuditEntries,
} from '../src/gate/register-characters.ts'

const PROJECT_ID = 'project:char-test'

function freshDb(): DatabaseSync {
  return makeDb() as unknown as DatabaseSync
}

// ---------------------------------------------------------------------------
// 种子助手
// ---------------------------------------------------------------------------

function seedProject(db: DatabaseSync, id: string = PROJECT_ID): void {
  db.prepare('INSERT INTO projects (id, name) VALUES (?, ?)').run(id, '测试项目·人物')
}

/** 写 resources.content 必须 CAST(? AS BLOB)，同时算 content_hash（写库三件事） */
function seedResource(db: DatabaseSync, id: string, text: string): void {
  db.prepare(
    'INSERT INTO resources (id, media_type, content, content_hash) VALUES (?, ?, CAST(? AS BLOB), ?)',
  ).run(id, 'application/json', text, contentHash(text))
}

function seedChapterChain(db: DatabaseSync): string {
  db.prepare('INSERT INTO books (id, project_id, title) VALUES (?, ?, ?)')
    .run('book:t1', PROJECT_ID, '测试书')
  db.prepare('INSERT INTO volumes (id, book_id, number, title) VALUES (?, ?, 1, ?)')
    .run('volume:t1', 'book:t1', '第一卷')
  seedResource(db, 'resource:ch-seed', '第十二章正文种子')
  db.prepare(
    'INSERT INTO chapters (id, volume_id, number, title, content_resource_id) VALUES (?, ?, 12, ?, ?)',
  ).run('chapter:t12', 'volume:t1', '第十二章', 'resource:ch-seed')
  return 'chapter:t12'
}

function seedCharacter(db: DatabaseSync, name: string, status = 'active'): void {
  db.prepare(
    "INSERT INTO characters (id, project_id, name, role_class, status) VALUES (?, ?, ?, 'secondary', ?)",
  ).run(newId('character'), PROJECT_ID, name, status)
}

function seedCandidateSet(
  db: DatabaseSync,
  opts: { setId: string; chapterId: string; cand: unknown; status: string; createdAt: string },
): void {
  const resId = `resource:cand-${opts.setId}`
  seedResource(db, resId, JSON.stringify(opts.cand))
  db.prepare(
    'INSERT INTO continuity_candidate_sets '
    + '(id, project_id, chapter_id, source_content_hash, authority_snapshot_json, '
    + 'candidate_resource_id, subject_hash, owners_json, status, created_at) '
    + "VALUES (?, ?, ?, ?, '{}', ?, ?, '[]', ?, ?)",
  ).run(opts.setId, PROJECT_ID, opts.chapterId, `sha256-src-${opts.setId}`, resId, `sha256subj${opts.setId}`, opts.status, opts.createdAt)
}

function seedVolumeAsset(db: DatabaseSync, scope: string, revision: number, meta: unknown): void {
  const resId = `resource:vo-${scope}-r${revision}`
  seedResource(db, resId, `卷纲 ${scope} r${revision} 正文`)
  // 部分唯一索引 idx_planning_assets_current：每 scope 仅一行 locked——重锁先把旧 revision 置 superseded
  db.prepare(
    "UPDATE planning_assets SET status = 'superseded' "
    + "WHERE project_id = ? AND asset_type = 'volume_outline' AND scope_ref = ? AND status = 'locked'",
  ).run(PROJECT_ID, scope)
  db.prepare(
    "INSERT INTO planning_assets (id, project_id, asset_type, scope_ref, revision, status, "
    + 'content_resource_id, producer_role, metadata_json) '
    + "VALUES (?, ?, 'volume_outline', ?, ?, 'locked', ?, 'planning/volume_outline', ?)",
  ).run(`planning:${scope}-r${revision}`, PROJECT_ID, scope, revision, resId, JSON.stringify(meta))
}

function charRow(db: DatabaseSync, name: string): any {
  return db.prepare('SELECT * FROM characters WHERE project_id = ? AND name = ?').get(PROJECT_ID, name)
}

function charCount(db: DatabaseSync): number {
  return (db.prepare('SELECT COUNT(*) AS n FROM characters').get() as any).n
}

// ---------------------------------------------------------------------------
// 常量与归一化
// ---------------------------------------------------------------------------

describe('常量与归一化（py L73-75/L137-141）', () => {
  it('词表常量与 py 逐字一致且顺序稳定', () => {
    expect([...STATUS_VALUES]).toEqual(['active', 'peripheral', 'dormant', 'departed', 'transformed', 'dead'])
    expect([...EXIT_TYPES]).toEqual(['完成型', '迁移型', '转化型', '关系型', '功能转移型', '休眠型', '死亡型'])
    expect([...EXIT_STATUSES]).toEqual(['departed', 'transformed', 'dormant', 'dead'])
  })

  it('normName：NFKC 全半角折叠 + 去全部空白 + 小写折叠', () => {
    expect(normName('ＭＩＫＥ')).toBe('mike')
    expect(normName('Mike')).toBe('mike')
    expect(normName('沈　青梧')).toBe(normName('沈青梧'))
    expect(normName('沈 青梧\n')).toBe(normName('沈青梧'))
    expect(normName('')).toBe('')
  })
})

// ---------------------------------------------------------------------------
// 校验层
// ---------------------------------------------------------------------------

describe('校验层 validateRoster / validateEntries / validateStatusUpdate', () => {
  const GOOD_ROSTER = [{
    name: '沈青梧', role_class: 'main', arc_role: '主线侦探',
    登场卷: 1, 预期退场: '完成型',
  }]

  it('roster 合法零错误；缺必填/多余键/空数组按 py 路径格式报错', () => {
    expect(validateRoster(GOOD_ROSTER, SCHEMAS_DIR)).toEqual([])
    expect(validateRoster([{ ...GOOD_ROSTER[0], seat_ref: '北渡口', essence: '观察者' }], SCHEMAS_DIR)).toEqual([])

    // 缺必填（instancePath=/0）——jsonschema iter_errors 同粒度：每个缺失键一条
    const miss = validateRoster([{ name: '沈青梧', role_class: 'main' }], SCHEMAS_DIR)
    expect(miss).toHaveLength(3)
    expect(miss.every((e) => e.includes('roster[0]'))).toBe(true)
    expect(miss.join()).toContain('arc_role')
    expect(miss.join()).toContain('登场卷')
    expect(miss.join()).toContain('预期退场')

    // 多余键（additionalProperties=false）——py/ajv 同样锚定在对象路径，消息附违规键名
    const extra = validateRoster([{ ...GOOD_ROSTER[0], zzz: 1 }], SCHEMAS_DIR)
    expect(extra).toHaveLength(1)
    expect(extra[0]).toContain('roster[0]')
    expect(extra[0]).toContain('additional')
    expect(extra[0]).toContain('(zzz)')

    // 空数组 → 根级 <root>
    expect(validateRoster([], SCHEMAS_DIR)[0]).toContain('roster[<root>]')

    // role_class 出枚举
    const badRc = validateRoster([{ ...GOOD_ROSTER[0], role_class: 'minor' }], SCHEMAS_DIR)
    expect(badRc.join()).toContain('role_class')
  })

  it('entry 四规则：name 非空 / role_class 枚举 / 预期退场枚举 / 来源卷 1-99 整数', () => {
    expect(validateEntries([{ name: '路人', role_class: 'minor' }])).toEqual([])
    expect(validateEntries([{ name: '路人' }])).toEqual([]) // role_class 缺省 secondary

    const errs = validateEntries([
      { role_class: 'minor' },                       // name 缺失
      { name: '  ', role_class: 'minor' },           // name 全空白
      { name: '甲', role_class: '主角' },             // role_class 非法
      { name: '甲', 预期退场: '当场去世' },            // 预期退场非法
      { name: '甲', 来源卷: 0 },                      // 下界
      { name: '甲', 来源卷: 100 },                    // 上界
      { name: '甲', 来源卷: 1.5 },                    // 非整数
    ])
    expect(errs.filter((e) => e.includes('name 非空必填'))).toHaveLength(2)
    expect(errs.filter((e) => e.includes('role_class 非法'))).toHaveLength(1)
    expect(errs.filter((e) => e.includes('预期退场非法'))).toHaveLength(1)
    expect(errs.filter((e) => e.includes('来源卷须为 1-99 整数'))).toHaveLength(3)
  })

  it('status-update 规则：dead 必须 死亡型；非退场状态禁带 exit_type', () => {
    expect(validateStatusUpdate({ name: '沈青梧', status: 'departed', exit_type: '迁移型' })).toEqual([])
    expect(validateStatusUpdate({ name: '沈青梧', status: 'active', exit_type: null })).toEqual([])

    expect(validateStatusUpdate({ name: '甲', status: 'dead', exit_type: '死亡型' })).toEqual([])
    expect(
      validateStatusUpdate({ name: '甲', status: 'dead', exit_type: '完成型' }).join(),
    ).toContain('status=dead 时 exit_type 必须为 死亡型')
    expect(
      validateStatusUpdate({ name: '甲', status: 'dead' }).join(),
    ).toContain('status=dead 时 exit_type 必须为 死亡型')

    const revive = validateStatusUpdate({ name: '甲', status: 'active', exit_type: '完成型' })
    expect(revive).toHaveLength(1)
    expect(revive.join()).toContain('非退场状态，不应携带 exit_type')
  })

  it('status 非法即短路（py 相同：后续规则不再累加）', () => {
    const errs = validateStatusUpdate({ name: '甲', status: 'ascended', exit_type: '乱写的' })
    expect(errs).toHaveLength(1)
    expect(errs[0]).toContain('status 非法')
  })
})

// ---------------------------------------------------------------------------
// 正例登记 + 幂等重入
// ---------------------------------------------------------------------------

describe('registerCharactersRun 正例登记', () => {
  it('roster+entry 单事务落库：ID 格式、state_json 键序与紧凑串、first_chapter_id', () => {
    const db = freshDb()
    seedProject(db)
    const chapterId = seedChapterChain(db)

    const { results, warns } = registerCharactersRun(db, {
      projectId: PROJECT_ID,
      schemasDir: SCHEMAS_DIR,
      roster: [
        { name: '沈青梧', role_class: 'main', arc_role: '主线侦探', 登场卷: 1, 预期退场: '完成型', essence: '冷静观察者' },
        { name: '裴远舟', role_class: 'secondary', arc_role: '对照组', 登场卷: 2, 预期退场: '持续活跃' },
      ],
      entries: [{ name: '赵小四', role_class: 'minor', first_chapter_id: chapterId, notes: '执行卡微档案' }],
    })

    expect(warns).toEqual([])
    expect(results).toHaveLength(3)
    expect(results[0]).toMatch(/^roster 沈青梧 -> character:[0-9a-f-]{36}$/)
    expect(results[2]).toMatch(/^entry 赵小四 -> character:[0-9a-f-]{36}$/)
    expect(charCount(db)).toBe(3)

    const shen = charRow(db, '沈青梧')
    expect(shen.role_class).toBe('main')
    expect(shen.status).toBe('active')
    expect(shen.first_chapter_id).toBeNull()
    // py json.dumps 默认紧凑风格（键值间带空格）+ 键插入序：arc_role 打头
    expect(shen.state_json.startsWith('{"arc_role": "主线侦探", "预期退场": "完成型", "登场卷": 1')).toBe(true)
    const state = JSON.parse(shen.state_json)
    expect(state).toMatchObject({ arc_role: '主线侦探', '预期退场': '完成型', '登场卷': 1, essence: '冷静观察者' })

    const zhao = charRow(db, '赵小四')
    expect(zhao.role_class).toBe('minor')
    expect(zhao.first_chapter_id).toBe(chapterId)
    expect(JSON.parse(zhao.state_json).notes).toBe('执行卡微档案')
  })

  it('幂等重入：同 id 合并补充字段，绝不覆盖 status/exit 与状态史', () => {
    const db = freshDb()
    seedProject(db)
    const chapterId = seedChapterChain(db)

    registerCharactersRun(db, {
      projectId: PROJECT_ID, schemasDir: SCHEMAS_DIR,
      roster: [{ name: '沈青梧', role_class: 'main', arc_role: '初版弧线', 登场卷: 1, 预期退场: '完成型' }],
    })
    const idFirst = charRow(db, '沈青梧').id

    registerCharactersRun(db, {
      projectId: PROJECT_ID,
      statusUpdate: [{ name: '沈青梧', status: 'departed', exit_type: '迁移型', exit_chapter_id: chapterId }],
    })

    const { results, warns } = registerCharactersRun(db, {
      projectId: PROJECT_ID, schemasDir: SCHEMAS_DIR,
      roster: [{ name: '沈青梧', role_class: 'secondary', arc_role: '重锁后弧线', 登场卷: 1, 预期退场: '完成型' }],
    })

    expect(results[0].startsWith('roster 沈青梧 -> ')).toBe(true)
    expect(results[0]).toContain(idFirst) // 幂等：同人物返回同一 id
    expect(warns).toEqual([])
    expect(charCount(db)).toBe(1)

    const row = charRow(db, '沈青梧')
    expect(row.id).toBe(idFirst)
    expect(row.role_class).toBe('secondary')       // 合并更新 role_class
    expect(row.status).toBe('departed')            // 关键不变量：状态不被登记路径覆盖
    expect(row.exit_type).toBe('迁移型')
    expect(row.exit_chapter_id).toBe(chapterId)
    const state = JSON.parse(row.state_json)
    expect(state.arc_role).toBe('重锁后弧线')
    expect(state['状态史']).toHaveLength(1)          // 状态史原样保留
  })

  it('first_chapter_id COALESCE：重入未带值时不清掉既有值', () => {
    const db = freshDb()
    seedProject(db)
    const chapterId = seedChapterChain(db)

    registerCharactersRun(db, {
      projectId: PROJECT_ID,
      entries: [{ name: '赵小四', role_class: 'minor', first_chapter_id: chapterId }],
    })
    registerCharactersRun(db, {
      projectId: PROJECT_ID,
      entries: [{ name: '赵小四', role_class: 'minor', notes: '补一条备注' }],
    })
    expect(charRow(db, '赵小四').first_chapter_id).toBe(chapterId)
    expect(JSON.parse(charRow(db, '赵小四').state_json)).toMatchObject({
      notes: '补一条备注', first_chapter_id: chapterId,
    })
  })
})

// ---------------------------------------------------------------------------
// 状态迁移
// ---------------------------------------------------------------------------

describe('状态迁移 applyStatusUpdate（经 registerCharactersRun）', () => {
  it('退场迁移写入 status/exit 字段并追加状态史审计', () => {
    const db = freshDb()
    seedProject(db)
    const chapterId = seedChapterChain(db)

    const { results } = registerCharactersRun(db, {
      projectId: PROJECT_ID,
      entries: [{ name: '沈青梧', role_class: 'secondary' }],
    })
    expect(results[0].startsWith('entry 沈青梧 -> ')).toBe(true)

    const out = registerCharactersRun(db, {
      projectId: PROJECT_ID,
      statusUpdate: [{ name: '沈青梧', status: 'departed', exit_type: '迁移型', exit_chapter_id: chapterId }],
    })
    expect(out.results).toEqual(['status 沈青梧 active -> departed'])

    const row = charRow(db, '沈青梧')
    expect(row.status).toBe('departed')
    expect(row.exit_type).toBe('迁移型')
    expect(row.exit_chapter_id).toBe(chapterId)
    const history = JSON.parse(row.state_json)['状态史']
    expect(history).toHaveLength(1)
    expect(history[0]).toMatchObject({
      from: 'active', to: 'departed', exit_type: '迁移型', chapter_id: chapterId,
    })
    expect(history[0].at).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
  })

  it('复活/回归整体清空退场痕迹，不留半截记录；状态史累计两条', () => {
    const db = freshDb()
    seedProject(db)
    const chapterId = seedChapterChain(db)
    seedCharacter(db, '沈青梧')

    registerCharactersRun(db, {
      projectId: PROJECT_ID,
      statusUpdate: [{ name: '沈青梧', status: 'departed', exit_type: '迁移型', exit_chapter_id: chapterId }],
    })
    registerCharactersRun(db, {
      projectId: PROJECT_ID,
      statusUpdate: [{ name: '沈青梧', status: 'active' }],
    })

    const row = charRow(db, '沈青梧')
    expect(row.status).toBe('active')
    expect(row.exit_type).toBeNull()
    expect(row.exit_chapter_id).toBeNull() // 复活不留半截 exit_chapter_id
    const history = JSON.parse(row.state_json)['状态史']
    expect(history).toHaveLength(2)
    expect(history[1]).toMatchObject({ from: 'departed', to: 'active', exit_type: null, chapter_id: null })
  })

  it('连续性提名的未登记人物按 minor 自动补建（补登标记 + 迁移照常生效）', () => {
    const db = freshDb()
    seedProject(db)
    const chapterId = seedChapterChain(db)

    const { results, warns } = registerCharactersRun(db, {
      projectId: PROJECT_ID,
      statusUpdate: [{ name: '无名者', status: 'departed', exit_type: '休眠型', exit_chapter_id: chapterId }],
    })
    expect(warns).toEqual([])
    expect(results).toEqual([`status 无名者 active -> departed`])

    const row = charRow(db, '无名者')
    expect(row.role_class).toBe('minor')
    expect(row.status).toBe('departed')
    expect(row.exit_type).toBe('休眠型')
    const state = JSON.parse(row.state_json)
    expect(state['补登']).toBe('连续性状态迁移先于登记')
    expect(state['状态史'][0].from).toBe('active')
  })
})

// ---------------------------------------------------------------------------
// 非法迁移拒绝 + 事务回滚
// ---------------------------------------------------------------------------

describe('非法输入阻断与事务边界', () => {
  it('非法状态迁移 → GateFail 且零写入（校验在事务前）', () => {
    const db = freshDb()
    seedProject(db)

    expect(() => registerCharactersRun(db, {
      projectId: PROJECT_ID,
      statusUpdate: [{ name: '沈青梧', status: 'dead', exit_type: '完成型' }],
    })).toThrow(GateFail)
    expect(() => registerCharactersRun(db, {
      projectId: PROJECT_ID,
      statusUpdate: [{ name: '沈青梧', status: 'peripheral', exit_type: '完成型' }],
    })).toThrow(/不应携带 exit_type/)
    expect(() => registerCharactersRun(db, {
      projectId: PROJECT_ID,
      statusUpdate: [{ name: '沈青梧', status: 'ascended' }],
    })).toThrow(/status 非法/)
    expect(charCount(db)).toBe(0)
  })

  it('批内中途 FK 失败 → ROLLBACK 整体回滚，此前成功项一并撤销', () => {
    const db = freshDb()
    seedProject(db)

    expect(() => registerCharactersRun(db, {
      projectId: PROJECT_ID, schemasDir: SCHEMAS_DIR,
      roster: [{ name: '甲', role_class: 'main', arc_role: 'x', 登场卷: 1, 预期退场: '完成型' }],
      entries: [
        { name: '乙', role_class: 'minor' },
        { name: '丙', role_class: 'minor', first_chapter_id: 'chapter:missing-fk' },
      ],
    })).toThrow()
    expect(charCount(db)).toBe(0) // BEGIN IMMEDIATE 内任一失败 → 全量回滚
  })

  it('项目不存在 → 三入口全部 GateFail；无输入 → 守卫 FAIL', () => {
    const db = freshDb()
    expect(() => registerCharactersRun(db, {
      projectId: 'project:ghost',
      entries: [{ name: '甲' }],
    })).toThrow(/项目不存在: project:ghost/)
    expect(() => checkPendingStatus(db, 'project:ghost')).toThrow(/项目不存在/)
    expect(() => checkAuditEntries(db, 'project:ghost')).toThrow(/项目不存在/)
    // py run() 先查项目存在（return 2）再查输入守卫——项目在库但三输入全空 → 守卫 FAIL
    seedProject(db)
    expect(() => registerCharactersRun(db, { projectId: PROJECT_ID })).toThrow(/至少提供/)
  })
})

// ---------------------------------------------------------------------------
// 近重名 WARN
// ---------------------------------------------------------------------------

describe('近重名归一化告警（纯提示类，不阻断）', () => {
  it('在库撞名与批内撞名分别 WARN；完全同名走幂等不告警', () => {
    const db = freshDb()
    seedProject(db)
    seedCharacter(db, '沈青梧')

    // 与在库人物归一化撞名（全角空格变体）
    const r1 = registerCharactersRun(db, { projectId: PROJECT_ID, entries: [{ name: '沈　青梧' }] })
    expect(r1.warns).toHaveLength(1)
    expect(r1.warns[0]).toContain('WARN 近重名')
    expect(r1.warns[0]).toContain('在库人物')

    // 批内两个原始名不同但归一化相同
    const r2 = registerCharactersRun(db, {
      projectId: PROJECT_ID,
      entries: [{ name: 'ＭＩＫＥ' }, { name: 'mike ' }],
    })
    expect(r2.warns.some((w) => w.includes('批内近重名'))).toBe(true)

    // 完全同名 → 幂等合并路径，无告警
    const r3 = registerCharactersRun(db, { projectId: PROJECT_ID, entries: [{ name: '沈青梧' }] })
    expect(r3.warns).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// 席位对账 + 重锁对账
// ---------------------------------------------------------------------------

describe('world 席位对账与旧 roster 重锁提醒', () => {
  const WORLD = {
    seats: [
      { name: '北渡口', disposition: '待契约认领' },
      { name: '旧书房', disposition: '待契约认领' },
      { name: '祠堂', disposition: '已认领' },
    ],
  }

  it('seat_ref 引用不存在席位 → GateFail 阻断且零写入（数据完整性类）', () => {
    const db = freshDb()
    seedProject(db)
    expect(() => registerCharactersRun(db, {
      projectId: PROJECT_ID, world: WORLD,
      entries: [{ name: '甲', seat_ref: '幽灵席' }],
    })).toThrow(/引用不存在的席位/)
    expect(charCount(db)).toBe(0)
  })

  it('认领席位消除其 WARN，未认领承诺席位保留提示', () => {
    const db = freshDb()
    seedProject(db)
    const { warns } = registerCharactersRun(db, {
      projectId: PROJECT_ID, world: WORLD,
      entries: [{ name: '摆渡人', role_class: 'minor', seat_ref: '北渡口' }],
    })
    expect(warns.some((w) => w.includes('「北渡口」'))).toBe(false)
    expect(warns.some((w) => w.includes('「旧书房」') && w.includes('尚无认领人'))).toBe(true)

    // 第二轮：北渡口已在库（claimed 扫描），仍不告警
    const again = registerCharactersRun(db, {
      projectId: PROJECT_ID, world: WORLD,
      entries: [{ name: '摆渡人', role_class: 'minor', seat_ref: '北渡口' }],
    })
    expect(again.warns.some((w) => w.includes('「北渡口」'))).toBe(false)
  })

  it('重锁对账：曾在旧 roster 但不在新 roster 的人物 WARN 提醒退役或补回', () => {
    const db = freshDb()
    seedProject(db)
    registerCharactersRun(db, {
      projectId: PROJECT_ID, schemasDir: SCHEMAS_DIR,
      roster: [
        { name: '沈青梧', role_class: 'main', arc_role: '主线', 登场卷: 1, 预期退场: '完成型' },
        { name: '裴远舟', role_class: 'secondary', arc_role: '副线', 登场卷: 1, 预期退场: '持续活跃' },
      ],
    })
    const { warns } = registerCharactersRun(db, {
      projectId: PROJECT_ID, schemasDir: SCHEMAS_DIR,
      roster: [{ name: '沈青梧', role_class: 'main', arc_role: '主线修订', 登场卷: 1, 预期退场: '完成型' }],
    })
    const dropped = warns.find((w) => w.includes('裴远舟'))
    expect(dropped).toBeTruthy()
    expect(dropped!).toContain('曾在旧契约 roster 但不在新 roster')
  })
})

// ---------------------------------------------------------------------------
// 账本↔注册表对账
// ---------------------------------------------------------------------------

describe('checkPendingStatus（promoted 候选 vs 注册表）', () => {
  function seedWorld(db: DatabaseSync): string {
    seedProject(db)
    const chapterId = seedChapterChain(db)
    // 更早的 promoted 集（被超越的历史迁移）
    seedCandidateSet(db, {
      setId: 'set-a', chapterId, status: 'promoted', createdAt: '2026-01-01 09:00:00',
      cand: { candidates: [
        { type: 'character_status', name: '沈青梧', status: 'departed' },
        { type: 'character_status', name: '赵铁山', status: 'dormant' },
        { type: 'fact', name: '无关事实候选', status: '' },
      ] },
    })
    // 更新的 promoted 集（最新候选以此为准）
    seedCandidateSet(db, {
      setId: 'set-b', chapterId, status: 'promoted', createdAt: '2026-02-01 09:00:00',
      cand: { candidates: [
        { type: 'character_status', name: '沈青梧', status: 'active' },
        { type: 'character_status', name: '李未登记', status: 'dormant' },
      ] },
    })
    // working 集不参与对账
    seedCandidateSet(db, {
      setId: 'set-c', chapterId, status: 'working', createdAt: '2026-03-01 09:00:00',
      cand: { candidates: [{ type: 'character_status', name: '王五', status: 'dead' }] },
    })
    seedCharacter(db, '沈青梧', 'active')
    seedCharacter(db, '赵铁山', 'dormant')
    return chapterId
  }

  it('漂移（未登记/状态不符）→ GateFail 逐条列出；补齐后通过', () => {
    const db = freshDb()
    seedWorld(db)

    // 李未登记：候选 dormant 但注册表无此人
    try {
      checkPendingStatus(db, PROJECT_ID)
      throw new Error('应当抛出 GateFail')
    } catch (e) {
      expect(e).toBeInstanceOf(GateFail)
      const msg = (e as Error).message
      expect(msg).toContain('DRIFT 李未登记')
      expect(msg).toContain('注册表未登记')
      expect(msg).not.toContain('王五') // working 集不参与
      expect(msg).toContain('处理完再继续后续章节')
    }

    seedCharacter(db, '李未登记', 'dormant')
    const report = checkPendingStatus(db, PROJECT_ID)
    expect(report.checked).toBe(3) // 沈青梧/赵铁山/李未登记
    expect(report.note).toBeUndefined()

    // 状态漂移：把赵铁山改成 departed 再对账 → 状态不符类漂移
    db.prepare('UPDATE characters SET status = ? WHERE name = ?').run('departed', '赵铁山')
    expect(() => checkPendingStatus(db, PROJECT_ID)).toThrow(/DRIFT 赵铁山：候选 dormant（set-a）≠ 注册表 departed/)
  })

  it('无表跳过（py 返回 0 的兼容路径）；无候选平凡通过', () => {
    const db = freshDb()
    seedProject(db)
    db.exec('DROP TABLE continuity_candidate_sets')
    expect(checkPendingStatus(db, PROJECT_ID)).toMatchObject({ checked: 0, note: '对账跳过：库中无 continuity_candidate_sets 表。' })

    const db2 = freshDb()
    seedProject(db2)
    const ch = seedChapterChain(db2)
    seedCandidateSet(db2, {
      setId: 'set-x', chapterId: ch, status: 'promoted', createdAt: '2026-01-01 09:00:00',
      cand: { candidates: [{ type: 'fact', name: '只有事实' }] },
    })
    expect(checkPendingStatus(db2, PROJECT_ID)).toMatchObject({ checked: 0 })
  })
})

// ---------------------------------------------------------------------------
// 卷纲班底落表终核
// ---------------------------------------------------------------------------

describe('checkAuditEntries（locked 卷纲班底逐名核对）', () => {
  it('漏登记 → GateFail 只对最新 revision 核对；补齐后 PASS 并列出待登记设定', () => {
    const db = freshDb()
    seedProject(db)
    // 第一卷：r1 被 r2 取代（班底旧 不应对账）
    seedVolumeAsset(db, 'v1', 1, {
      volume_characters: [{ name: '班底甲' }, { name: '班底旧' }],
      volume_settings: [{ name: '北渡集市', kind: '地点', disposition: '登记入world' }],
    })
    seedVolumeAsset(db, 'v1', 2, {
      volume_characters: [{ name: '班底甲' }, { name: '班底乙' }],
      volume_settings: [{ name: '南岸灯塔', kind: '地点', disposition: '登记入world' }],
    })
    // 第二卷：T39 前旧卷纲无 volume_characters 字段 → 跳过
    seedVolumeAsset(db, 'v2', 1, { note: '早期卷纲无班底字段' })
    seedCharacter(db, '班底甲')

    try {
      checkAuditEntries(db, PROJECT_ID)
      throw new Error('应当抛出 GateFail')
    } catch (e) {
      expect(e).toBeInstanceOf(GateFail)
      const msg = (e as Error).message
      expect(msg).toContain('"班底乙" 未入注册表')
      expect(msg).toContain('卷纲[v1]')
      expect(msg).not.toContain('班底旧') // 已被 r2 取代
    }

    seedCharacter(db, '班底乙')
    const report = checkAuditEntries(db, PROJECT_ID)
    expect(report).toEqual({
      volumes: 2,
      entries: 2,
      pendingSettings: ['卷纲[v1] 设定 南岸灯塔（地点）待登记入 world'],
    })
  })
})
