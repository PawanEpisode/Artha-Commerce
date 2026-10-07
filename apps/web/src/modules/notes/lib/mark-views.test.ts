import { afterEach, describe, expect, it, vi } from 'vitest'

import { neighbourMark } from '../hooks/useMarkNavigation'
import { activeFilterCount, applyFilters, NO_FILTERS, tagsOf, toRow } from './annotation-filters'
import { DEFAULT_LEGEND } from './annotation-legend'
import { heaviestInkPages, marksNotice } from './annotation-limits'
import { DOC, makeMark } from './annotation-testing'
import { hitTest } from './hit-test'
import { describeMark } from './mark-label'
import { consumeOpenedFrom, markOpenedFrom } from './opened-from'
import { FILED_LINK } from './testing'

const ink = (id: string, page: number, points: number) =>
  makeMark({
    id,
    page,
    kind: 'ink',
    color: 'i1',
    geometry: {
      strokes: [
        { pts: Array.from({ length: points }, (_, i) => [0.1 + i * 0.001, 0.2] as [number, number]), w: 0.0035 },
      ],
      bbox: [0.1, 0.19, 0.1, 0.02],
    },
  })

describe('what a row says', () => {
  it('reads kind, page, colour in words with the student’s name for it, and the quote', () => {
    expect(describeMark(makeMark({ page: 14, color: 'y' }), DEFAULT_LEGEND)).toBe(
      'Highlight, page 14, yellow (Important), ITC blocked credits',
    )
    expect(describeMark(makeMark({ page: 3, kind: 'ink', color: 'i2', quote_exact: null }), DEFAULT_LEGEND)).toBe(
      'Drawing, page 3, Red pen',
    )
  })

  it('makes a row view with the chapter, the colour as words and a clamp flag for long comments', () => {
    const row = toRow(
      makeMark({
        kind: 'sticky',
        color: 'g',
        comment: 'x'.repeat(400),
        link: FILED_LINK,
        tags: [{ id: 't', name: 'Doubt', color_key: null }],
      }),
      { ...DEFAULT_LEGEND, g: 'Formula' },
    )
    expect(row).toMatchObject({
      heading: 'Note, page 14',
      colorText: 'green (Formula)',
      chapter: 'GST: Input tax credit',
      clamped: true,
      unsynced: false,
    })
    expect(toRow(makeMark({ local_only: true }), DEFAULT_LEGEND).unsynced).toBe(true)
  })
})

describe('filters', () => {
  const marks = [
    makeMark({
      id: 'a',
      color: 'y',
      created_at: new Date().toISOString(),
      tags: [{ id: 't1', name: 'Doubt', color_key: null }],
    }),
    makeMark({ id: 'b', color: 'g', kind: 'underline', created_at: '2020-01-01T00:00:00Z' }),
    ink('c', 5, 3),
  ]
  it('narrows by colour, tag, kind and "mine today"', () => {
    expect(applyFilters(marks, { ...NO_FILTERS, color: 'g' }).map((m) => m.id)).toEqual(['b'])
    expect(applyFilters(marks, { ...NO_FILTERS, tag: 't1' }).map((m) => m.id)).toEqual(['a'])
    expect(applyFilters(marks, { ...NO_FILTERS, kind: 'ink' }).map((m) => m.id)).toEqual(['c'])
    expect(applyFilters(marks, { ...NO_FILTERS, today: true }).map((m) => m.id)).toContain('a')
    expect(applyFilters(marks, { ...NO_FILTERS, today: true }).map((m) => m.id)).not.toContain('b')
    expect(applyFilters(marks, { ...NO_FILTERS, color: 'o' })).toEqual([])
  })
  it('counts active filters and lists the tags in use once each', () => {
    expect(activeFilterCount({ color: 'y', tag: '', kind: 'ink', today: true })).toBe(3)
    expect(
      tagsOf([...marks, makeMark({ id: 'd', tags: [{ id: 't1', name: 'Doubt', color_key: null }] })]),
    ).toHaveLength(1)
  })
})

describe('the cap on marks', () => {
  it('is quiet below 95%, a notice from 95% and blocked at the cap', () => {
    expect(marksNotice({ count: 18_999, limit: 20_000 })).toBe('ok')
    expect(marksNotice({ count: 19_000, limit: 20_000 })).toBe('near')
    expect(marksNotice({ count: 20_000, limit: 20_000 })).toBe('blocked')
  })

  it('lists the pages with the most ink, heaviest first, ignoring deleted drawings', () => {
    const gone = { ...ink('x', 9, 400), deleted_at: '2026-10-01T00:00:00Z' }
    const pages = heaviestInkPages([ink('a', 2, 10), ink('b', 7, 300), ink('c', 7, 100), ink('d', 4, 50), gone])
    expect(pages.map((p) => p.page)).toEqual([7, 4, 2])
    expect(pages[0]).toMatchObject({ page: 7, drawings: 2 })
  })
})

describe('tapping a mark', () => {
  it('finds the mark under a point, small things first', () => {
    const highlight = makeMark({ id: 'h', geometry: { quads: [[0.1, 0.2, 0.5, 0.02]] } })
    const pin = makeMark({ id: 'p', kind: 'sticky', geometry: { pt: [0.3, 0.21] }, color: 'y' })
    const tol: [number, number] = [0.02, 0.015]
    expect(hitTest([highlight, pin], 14, [0.3, 0.21], tol)?.id).toBe('p')
    expect(hitTest([highlight, pin], 14, [0.5, 0.21], tol)?.id).toBe('h')
    expect(hitTest([highlight, pin], 14, [0.9, 0.9], tol)).toBeNull()
    expect(hitTest([highlight], 13, [0.3, 0.21], tol)).toBeNull()
    expect(hitTest([{ ...highlight, deleted_at: 'x' }], 14, [0.3, 0.21], tol)).toBeNull()
  })
})

describe('[ and ] between marks', () => {
  const list = [
    { id: 'a', page: 2 },
    { id: 'b', page: 5 },
    { id: 'c', page: 9 },
  ]
  it('goes to the next mark after the selected one and wraps', () => {
    expect(neighbourMark(list, 'a', 1, 1)).toBe('b')
    expect(neighbourMark(list, 'c', 1, 1)).toBe('a')
    expect(neighbourMark(list, 'a', 1, -1)).toBe('c')
  })
  it('starts from the current page when nothing is selected', () => {
    expect(neighbourMark(list, undefined, 5, 1)).toBe('b')
    expect(neighbourMark(list, undefined, 6, 1)).toBe('c')
    expect(neighbourMark(list, undefined, 6, -1)).toBe('b')
    expect(neighbourMark(list, undefined, 1, -1)).toBe('c')
    expect(neighbourMark([], undefined, 1, 1)).toBeNull()
  })
})

describe('where a PDF was opened from', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('uses what the linking screen said once, then the URL, then the library', () => {
    const data = new Map<string, string>()
    vi.stubGlobal('window', {
      sessionStorage: {
        getItem: (k: string) => data.get(k) ?? null,
        setItem: (k: string, v: string) => void data.set(k, v),
        removeItem: (k: string) => void data.delete(k),
      },
    })
    markOpenedFrom('chapter')
    expect(consumeOpenedFrom({})).toBe('chapter')
    expect(consumeOpenedFrom({ q: 'itc' })).toBe('search')
    expect(consumeOpenedFrom({ ann: DOC })).toBe('aggregate')
    expect(consumeOpenedFrom({})).toBe('library')
  })
})
