import { describe, expect, it } from 'vitest'

import { bothText, diffLines, hasChanges, resolvedBody } from './conflict'
import type { NoteConflictDetail } from './types'

describe('diffLines', () => {
  it('marks unchanged, theirs-only and mine-only lines in order', () => {
    expect(diffLines('a\nb\nc', 'a\nx\nc')).toEqual([
      { kind: 'same', text: 'a' },
      { kind: 'theirs', text: 'b' },
      { kind: 'mine', text: 'x' },
      { kind: 'same', text: 'c' },
    ])
  })

  it('handles an addition at the end and identical text', () => {
    expect(diffLines('a', 'a\nb').map((l) => l.kind)).toEqual(['same', 'mine'])
    expect(hasChanges(diffLines('a\nb', 'a\nb'))).toBe(false)
  })

  it('shows everything when one side is empty', () => {
    expect(diffLines('', 'a').map((l) => l.kind)).toEqual(['theirs', 'mine'])
  })
})

describe('resolvedBody', () => {
  const detail: NoteConflictDetail = {
    theirs: { rev: 5, title: 'T', body_md: 'their text', updated_at: '2026-10-01T10:00:00Z' },
    mine: { body_md: 'my text' },
    merged: null,
  }

  it('keeps mine, theirs, or both with a rule between (as the server does)', () => {
    expect(resolvedBody('mine', detail, 'my text')).toBe('my text')
    expect(resolvedBody('theirs', detail, 'my text')).toBe('their text')
    expect(resolvedBody('both', detail, 'my text')).toBe('their text\n\n---\n\nmy text')
    expect(bothText('a', 'b')).toBe('a\n\n---\n\nb')
  })
})
