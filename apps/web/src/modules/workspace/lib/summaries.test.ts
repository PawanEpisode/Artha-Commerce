import { describe, expect, it } from 'vitest'

import type { DueRow, SubjectRow } from '~/modules/coverage'

import { dueNote, topDue, weakestSubjects } from './summaries'

const subject = (name: string, pct: number, total = 5) =>
  ({ name, pct_simple: pct, chapters_total: total }) as SubjectRow

describe('dueNote', () => {
  it.each([
    [0, 'Due today'],
    [-1, 'Due today'],
    [1, '1 day late'],
    [7, '7 days late'],
  ])('%i -> %s', (days, text) => expect(dueNote(days)).toBe(text))
})

describe('topDue', () => {
  it('keeps the first three in server order', () => {
    const rows = [1, 2, 3, 4].map((n) => ({ id: String(n) }) as DueRow)
    expect(topDue(rows).map((r) => r.id)).toEqual(['1', '2', '3'])
    expect(topDue([])).toEqual([])
  })
})

describe('weakestSubjects', () => {
  it('lowest first, ties by name, empty papers skipped', () => {
    const list = [
      subject('Tax', 40),
      subject('Audit', 10),
      subject('Law', 10),
      subject('Excluded', 0, 0),
      subject('Cost', 90),
    ]
    expect(weakestSubjects(list).map((s) => s.name)).toEqual(['Audit', 'Law', 'Tax'])
  })
  it('does not reorder the input', () => {
    const list = [subject('B', 50), subject('A', 10)]
    weakestSubjects(list)
    expect(list.map((s) => s.name)).toEqual(['B', 'A'])
  })
})
