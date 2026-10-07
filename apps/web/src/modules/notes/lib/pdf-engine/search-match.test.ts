import { describe, expect, it } from 'vitest'

import { findMatches, snippetAround } from './search-match'

describe('findMatches', () => {
  const text = 'Input tax credit (ITC) is blocked. The ITC on motor vehicles is\nnot available; itc again.'

  it('finds every occurrence, ignoring case, in offsets of the original text', () => {
    const hits = findMatches(text, 'itc')
    expect(hits).toHaveLength(3)
    for (const h of hits) expect(text.slice(h.start, h.end).toLowerCase()).toBe('itc')
  })

  it('ignores odd spaces and line breaks between words', () => {
    const hits = findMatches('Input  tax\ncredit', 'input tax credit')
    expect(hits).toEqual([{ start: 0, end: 17 }])
  })

  it('joins a word hyphenated at a line end', () => {
    expect(findMatches('the elig-\nible amount', 'eligible')).toHaveLength(1)
  })

  it('finds reference-style queries', () => {
    expect(findMatches('See section 17(5) for blocked credits', '17(5)')).toHaveLength(1)
  })

  it('finds Devanagari', () => {
    expect(findMatches('इनपुट टैक्स क्रेडिट मिलता है', 'टैक्स')).toHaveLength(1)
  })

  it('needs two characters and returns nothing for none', () => {
    expect(findMatches(text, 'i')).toEqual([])
    expect(findMatches(text, 'zzz')).toEqual([])
    expect(findMatches(text, '  ')).toEqual([])
  })

  it('does not return overlapping hits', () => {
    expect(findMatches('aaaa', 'aa')).toHaveLength(2)
  })
})

describe('snippetAround', () => {
  it('shows context on one line with ellipses where cut', () => {
    const text = `${'x'.repeat(100)}\nITC is blocked${'y'.repeat(100)}`
    const s = snippetAround(text, { start: 101, end: 104 }, 10)
    expect(s.startsWith('…')).toBe(true)
    expect(s.endsWith('…')).toBe(true)
    expect(s).toContain('ITC is')
    expect(s).not.toContain('\n')
  })

  it('has no ellipsis when the text is short', () => {
    expect(snippetAround('ITC is blocked', { start: 0, end: 3 })).toBe('ITC is blocked')
  })
})
