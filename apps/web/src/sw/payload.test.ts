import { describe, expect, it } from 'vitest'

import { FALLBACK_BODY, FALLBACK_TAG, FALLBACK_TITLE, parsePushPayload } from './payload'

const valid = {
  v: 1,
  id: 'n_123',
  category: 'timer',
  title: 'Round 2 done',
  body: '25 minutes on GST. Take 5, you earned it.',
  tag: 'timer:abc-123',
  url: '/app/focus?n=n_123',
  actions: [
    { id: 'break', title: 'Start break' },
    { id: 'extend', title: '+5 min' },
  ],
}
const parse = (value: unknown) => parsePushPayload(typeof value === 'string' ? value : JSON.stringify(value))

describe('parsePushPayload, version 1', () => {
  it('reads every field of the PRD example', () => {
    const result = parse(valid)
    expect(result.recognised).toBe(true)
    expect(result.content).toEqual({
      title: 'Round 2 done',
      body: '25 minutes on GST. Take 5, you earned it.',
      tag: 'timer:abc-123',
      url: '/app/focus?n=n_123',
      id: 'n_123',
      category: 'timer',
      actions: valid.actions,
    })
  })

  it('ignores fields it does not know', () => {
    const result = parse({ ...valid, future: { a: 1 }, icon: 'https://evil.example/x.png' })
    expect(result.recognised).toBe(true)
    expect(result.content).not.toHaveProperty('future')
    expect(result.content).not.toHaveProperty('icon')
  })

  it('allows a missing body and missing actions', () => {
    const result = parse({ v: 1, title: 'Hello', tag: 'x' })
    expect(result.recognised).toBe(true)
    expect(result.content.body).toBe('')
    expect(result.content.actions).toEqual([])
  })

  it('replaces a refused link with the app home, keeping the rest', () => {
    for (const url of ['//evil.example', 'https://evil.example/app', '/admin', 42, undefined]) {
      const result = parse({ ...valid, url })
      expect(result.recognised).toBe(true)
      expect(result.content.url).toBe('/app')
      expect(result.content.title).toBe('Round 2 done')
    }
  })

  it('uses the shared fallback tag when the tag is missing or unusable', () => {
    for (const tag of [undefined, '', 'has space', 'x'.repeat(81), 5]) {
      expect(parse({ ...valid, tag }).content.tag).toBe(FALLBACK_TAG)
    }
  })

  it('drops an unusable id or category instead of failing', () => {
    const result = parse({ ...valid, id: 'bad id!', category: { x: 1 } })
    expect(result.recognised).toBe(true)
    expect(result.content.id).toBeNull()
    expect(result.content.category).toBeNull()
  })

  it('keeps at most two well-formed actions', () => {
    const actions = [
      { id: 'a', title: 'A' },
      { id: '', title: 'no id' },
      'junk',
      { id: 'b', title: 'B' },
      { id: 'c', title: 'C' },
    ]
    expect(parse({ ...valid, actions }).content.actions).toEqual([
      { id: 'a', title: 'A' },
      { id: 'b', title: 'B' },
    ])
    expect(parse({ ...valid, actions: 'nope' }).content.actions).toEqual([])
  })

  it('trims and bounds long text', () => {
    const result = parse({ ...valid, title: `  ${'t'.repeat(500)}  `, body: 'b'.repeat(5000) })
    expect(result.content.title).toHaveLength(120)
    expect(result.content.body).toHaveLength(300)
  })
})

describe('parsePushPayload, anything else still shows something', () => {
  const generic = { title: FALLBACK_TITLE, body: FALLBACK_BODY, tag: FALLBACK_TAG, url: '/app', id: null }

  it.each([
    ['null (an empty push)', null, 'empty'],
    ['an empty string', '', 'empty'],
    ['whitespace', '   ', 'empty'],
    ['text that is not JSON', 'hello', 'invalid_json'],
    ['a JSON array', '[1,2]', 'not_object'],
    ['a JSON string', '"hi"', 'not_object'],
    ['JSON null', 'null', 'not_object'],
    ['an unknown version', JSON.stringify({ ...valid, v: 2 }), 'unsupported_version'],
    ['a missing version', JSON.stringify({ title: 'x' }), 'unsupported_version'],
    ['a version sent as text', JSON.stringify({ ...valid, v: '1' }), 'unsupported_version'],
    ['a missing title', JSON.stringify({ v: 1, body: 'x' }), 'invalid_fields'],
    ['a blank title', JSON.stringify({ v: 1, title: '   ' }), 'invalid_fields'],
    ['a title that is not text', JSON.stringify({ v: 1, title: 7 }), 'invalid_fields'],
  ])('%s', (_label, raw, reason) => {
    const result = parsePushPayload(raw as string | null)
    expect(result.recognised).toBe(false)
    if (result.recognised) return
    expect(result.reason).toBe(reason)
    expect(result.content).toMatchObject(generic)
    expect(result.content.actions).toEqual([])
  })

  it('never throws, whatever it is given', () => {
    for (const raw of ['{', '{"v":1', '\u0000', '{"v":1,"title":"x","actions":[null,[],{"id":1}]}', 'undefined']) {
      expect(() => parsePushPayload(raw)).not.toThrow()
    }
    expect(() => parsePushPayload(undefined)).not.toThrow()
  })
})
