import { describe, expect, it } from 'vitest'

import { addRecent, MAX_RECENT } from './recent-searches'

describe('addRecent', () => {
  it('puts the newest first and drops a repeat regardless of case', () => {
    expect(addRecent(['b', 'ITC', 'a'], 'itc')).toEqual(['itc', 'b', 'a'])
  })

  it('keeps at most eight and ignores an empty query', () => {
    const many = Array.from({ length: 12 }, (_, i) => `q${i}`)
    expect(addRecent(many, 'new')).toHaveLength(MAX_RECENT)
    expect(addRecent(['a'], '   ')).toEqual(['a'])
  })
})
