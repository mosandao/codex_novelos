import { describe, it, expect } from 'vitest'
import { createHash } from 'node:crypto'
import {
  contentHash, newId, parseCandidateText, GateFail,
  personaShapeOk, kernelShapeOk, MISMATCH_MARKERS,
} from '../src/gate/primitives.js'

describe('contentHash（对齐 py content_hash）', () => {
  it('sha256 前缀 + utf-8 hex', () => {
    const text = '诸天无限：从大运开始'
    const expectHex = createHash('sha256').update(Buffer.from(text, 'utf8')).digest('hex')
    expect(contentHash(text)).toBe('sha256:' + expectHex)
  })
  it('空串稳定', () => {
    expect(contentHash('')).toBe('sha256:' + createHash('sha256').digest('hex'))
  })
})

describe('newId', () => {
  it('格式 类型:uuid，两次调用不同', () => {
    const a = newId('project')
    expect(a).toMatch(/^project:[0-9a-f-]{36}$/)
    expect(newId('project')).not.toBe(a)
  })
})

describe('parseCandidateText（对齐 py 容错解析）', () => {
  const persona = JSON.stringify({ parent_version_id: 'creator_profile_version:x', signature: { sympathies: [] } })
  const kernel = JSON.stringify({ mode: 'create', display_name: '核', kernel: { identity: {} } })

  it('裸 JSON 直接过，无 notes', () => {
    const r = parseCandidateText(persona)
    expect(r.notes).toEqual([])
    expect((r.obj as any).signature.sympathies).toEqual([])
  })

  it('去围栏并报告', () => {
    const fenced = '```json\n' + persona + '\n```'
    const r = parseCandidateText(fenced)
    expect(r.notes).toContain('去除 Markdown 代码围栏')
  })

  it('尾部截断补括号并报告', () => {
    const truncated = '{"mode":"create","display_name":"核","kernel":{"identity":{"a":[1,2'
    const r = parseCandidateText(truncated, 'kernel')
    expect(r.notes.some((n) => n.includes('补齐尾部未闭合括号'))).toBe(true)
    expect((r.obj as any).kernel.identity.a).toEqual([1, 2])
  })

  it('中段错位 → GateFail；裸合法 JSON 不在此层查形状（py 同语义，形状归上层 validate）', () => {
    expect(() => parseCandidateText('{"broken": [1,2}', 'persona')).toThrow(GateFail)
    expect(() => parseCandidateText('{"foo": 1}', 'persona')).not.toThrow()
    expect(() => parseCandidateText('{"foo": 1}', 'kernel')).not.toThrow()
    const repaired = parseCandidateText('{"mode":"create","display_name":"d","kernel":{"identity":{}}', 'kernel')
    expect(repaired.notes.some((n) => n.includes('补齐尾部未闭合括号'))).toBe(true)
  })

  it('形状检查器边界', () => {
    expect(personaShapeOk(null)).toBe(false)
    expect(personaShapeOk({})).toBe(false)
    expect(personaShapeOk({ parent_version_id: 'x' })).toBe(false)
    expect(kernelShapeOk({ mode: 'select', display_name: 'd', kernel: {} })).toBe(false)
  })

  it('MISMATCH_MARKERS 顺序保留', () => {
    expect(MISMATCH_MARKERS[0]).toBe('错配警告')
    expect(MISMATCH_MARKERS.length).toBe(5)
  })
})
