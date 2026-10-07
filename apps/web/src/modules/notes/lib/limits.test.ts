import { describe, expect, it } from 'vitest'

import { nearLimit, saveBlock, splitNote, splitPoint } from './limits'

describe('saveBlock', () => {
  it('allows a note at the limit and blocks one over it, saying by how much', () => {
    expect(saveBlock('a'.repeat(100), 100)).toEqual({ blocked: false })
    expect(saveBlock('a'.repeat(130), 100)).toEqual({ blocked: true, reason: 'too_long', over: 30 })
  })
})

describe('splitting a long note', () => {
  it('cuts at the blank line nearest the middle', () => {
    const body = 'one\n\ntwo\n\nthree\n\nfour'
    const [a, b] = splitNote(body)
    expect(a + '\n\n' + b).toBe(body)
    expect(splitPoint(body)).toBe(body.indexOf('\n\n', 8))
  })

  it('cuts at the middle when there is no blank line', () => {
    expect(splitNote('abcdef')).toEqual(['abc', 'def'])
  })
})

describe('nearLimit', () => {
  it('warns from 90 percent', () => {
    expect(nearLimit(89, 100)).toBe(false)
    expect(nearLimit(90, 100)).toBe(true)
    expect(nearLimit(5, 0)).toBe(false)
  })
})
