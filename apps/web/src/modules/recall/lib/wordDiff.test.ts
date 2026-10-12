import { describe, expect, it } from 'vitest'

import { diffWords, hasWordChange, MAX_DIFF_WORDS, tokenize } from './wordDiff'

const side = (segments: ReturnType<typeof diffWords>, drop: 'added' | 'removed') =>
  segments
    .filter((s) => s.kind !== drop)
    .map((s) => s.text)
    .join('')

describe('wordDiff', () => {
  it('keeps whitespace with the word before it', () => {
    expect(tokenize('a  b ')).toEqual(['a  ', 'b '])
    expect(tokenize('')).toEqual([])
  })

  it('marks nothing when the texts are equal', () => {
    expect(diffWords('Same text', 'Same text')).toEqual([{ kind: 'same', text: 'Same text' }])
    expect(diffWords('', '')).toEqual([])
    expect(hasWordChange(diffWords('x', 'x'))).toBe(false)
  })

  it('finds a replaced word and keeps the rest', () => {
    const d = diffWords('ITC time limit is 30 days', 'ITC time limit is 60 days')
    expect(d.map((s) => [s.kind, s.text.trim()])).toEqual([
      ['same', 'ITC time limit is'],
      ['removed', '30'],
      ['added', '60'],
      ['same', 'days'],
    ])
    expect(hasWordChange(d)).toBe(true)
  })

  it('finds added and removed words', () => {
    expect(diffWords('blocked on vehicles', 'blocked on motor vehicles').map((s) => s.kind)).toEqual([
      'same',
      'added',
      'same',
    ])
    expect(diffWords('blocked on motor vehicles', 'blocked on vehicles').map((s) => s.kind)).toEqual([
      'same',
      'removed',
      'same',
    ])
  })

  it('gives back each side exactly from the segments', () => {
    const before = 'The  quick brown fox jumps'
    const after = 'The quick red fox leaps high'
    const d = diffWords(before, after)
    expect(side(d, 'added').replace(/\s+/g, ' ')).toBe(before.replace(/\s+/g, ' '))
    expect(side(d, 'removed')).toBe(after)
  })

  it('treats a whitespace-only change as no change a student can see', () => {
    expect(hasWordChange(diffWords('a b', 'a  b'))).toBe(false)
  })

  it('handles a text that is new or gone', () => {
    expect(diffWords('', 'new words')).toEqual([{ kind: 'added', text: 'new words' }])
    expect(diffWords('old words', '')).toEqual([{ kind: 'removed', text: 'old words' }])
  })

  it('shows a very long text as replaced instead of working it out', () => {
    const long = Array.from({ length: MAX_DIFF_WORDS + 1 }, (_, i) => `w${i}`).join(' ')
    expect(diffWords(long, `${long} more`).map((s) => s.kind)).toEqual(['removed', 'added'])
  })
})
