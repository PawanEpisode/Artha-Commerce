import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import type { PageRange } from './document-types'
import {
  emptyRow,
  mergeSuggestions,
  nextRowStart,
  overlapRows,
  parsePage,
  type RangeRow,
  rowsFromOutlineSuggestions,
  rowsFromRanges,
  sameAsSaved,
  toRangeInputs,
  validateRows,
} from './page-ranges'

const row = (key: string, from: string, to: string, chapterId = 'c1'): RangeRow => ({
  ...emptyRow(from),
  key,
  to,
  chapterId,
})
const saved = (id: string, from: number, to: number, chapter = 'c1'): PageRange =>
  ({
    id,
    page_from: from,
    page_to: to,
    chapter_id: chapter,
    topic_id: null,
    source: 'user',
    chapter_name: 'ITC',
    subject_name: 'GST',
  }) as PageRange

describe('page range rows', () => {
  it('parses whole pages only', () => {
    expect(parsePage('12')).toBe(12)
    for (const bad of ['', '0', '2.5', '3a', '-1', '1234567']) expect(parsePage(bad)).toBeNull()
  })
  it('starts the next row after the last one, or blank past the end', () => {
    expect(nextRowStart([], 100)).toBe('1')
    expect(nextRowStart([row('a', '1', '40')], 100)).toBe('41')
    expect(nextRowStart([row('a', '1', '100')], 100)).toBe('')
  })
  it('builds rows from saved ranges in page order with the chapter label', () => {
    const rows = rowsFromRanges([saved('b', 20, 30), saved('a', 1, 10)])
    expect(rows.map((r) => r.from)).toEqual(['1', '20'])
    expect(rows[0]?.chapterLabel).toBe('GST › ITC')
  })
  it('says what is wrong with each row', () => {
    const rows = [row('a', 'x', '5'), row('b', '9', '3'), row('c', '1', '500'), row('d', '1', '5', '')]
    const problems = validateRows(rows, 100)
    expect(problems.a).toMatch(/whole page numbers/)
    expect(problems.b).toMatch(/first page must not be after/)
    expect(problems.c).toBe('This PDF has 100 pages.')
    expect(problems.d).toMatch(/Choose a chapter/)
    expect(validateRows([row('a', '1', '10'), row('b', '11', '20')], 100)).toEqual({})
  })
  it('flags both rows of an overlap inline', () => {
    const problems = validateRows([row('a', '1', '10'), row('b', '10', '20')], 100)
    expect(problems.a).toBe('Overlaps pages 10 to 20.')
    expect(problems.b).toBe('Overlaps pages 1 to 10.')
  })
  it('orders the request by page and maps the server overlap back to the same rows', () => {
    const { inputs, order } = toRangeInputs([row('late', '20', '30', 'c2'), row('early', '1', '10')])
    expect(inputs.map((i) => i.page_from)).toEqual([1, 20])
    const error = new ApiError(409, 'x', { error: { code: 'ranges_overlap', message: 'm', details: { a: 0, b: 1 } } })
    expect(overlapRows(error, order)).toEqual({ early: 'Overlaps pages 20 to 30.', late: 'Overlaps pages 1 to 10.' })
    expect(overlapRows(new Error('other'), order)).toEqual({})
  })
  it('knows when nothing changed', () => {
    const ranges = [saved('a', 1, 10)]
    expect(sameAsSaved(rowsFromRanges(ranges), ranges)).toBe(true)
    expect(sameAsSaved([row('a', '1', '11')], ranges)).toBe(false)
    expect(sameAsSaved([], ranges)).toBe(false)
  })
  it("turns outline entries into rows and merges them without touching the student's own", () => {
    const suggestions = rowsFromOutlineSuggestions(
      [
        { title: 'Chapter 1', page: 1, children: [] },
        { title: 'Chapter 2', page: 21, children: [] },
      ],
      40,
    )
    expect(suggestions.map((s) => [s.from, s.to, s.source])).toEqual([
      ['1', '20', 'outline'],
      ['21', '40', 'outline'],
    ])
    const mine = [row('mine', '1', '10')]
    const merged = mergeSuggestions(mine, suggestions)
    expect(merged.map((r) => r.key)).toContain('mine')
    expect(merged.some((r) => r.from === '1' && r.source === 'outline')).toBe(false)
    expect(merged.some((r) => r.from === '21')).toBe(true)
  })
})
