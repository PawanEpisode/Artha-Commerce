import { describe, expect, it } from 'vitest'

import {
  activeFilters,
  aggregateParams,
  aggregateQuery,
  newNoteSchema,
  noteEditorSchema,
  noteFilterSchema,
  noteSearchSchema,
  strongestFilter,
  tabOf,
  withoutFilter,
} from './filter-schema'

const TAG = '3f2b8c1e-5a4d-4e9b-8c7a-1d2e3f4a5b6c'
const LEVEL = '11111111-1111-4111-8111-111111111111'

describe('noteFilterSchema', () => {
  it('accepts every filter of the PRD URL', () => {
    const parsed = noteFilterSchema.parse({
      tab: 'notes',
      tag: TAG,
      color: 'y',
      from: '2026-09-01',
      to: '2026-10-01',
      doc: TAG,
      sort: 'recent',
      cursor: 'abc',
      topic: 'section-17',
    })
    expect(parsed.tab).toBe('notes')
    expect(parsed.topic).toBe('section-17')
  })

  it('drops a bad value without failing the page', () => {
    const parsed = noteFilterSchema.parse({
      tab: 'bogus',
      tag: 'not-a-uuid',
      from: '2026-13-45',
      sort: 'x',
      color: 'toolong',
    })
    expect(parsed).toEqual({})
  })

  it('keeps the good filters when another one is bad', () => {
    expect(noteFilterSchema.parse({ tab: 'bogus', tag: TAG })).toEqual({ tag: TAG })
  })

  it('defaults the tab to all', () => {
    expect(tabOf({})).toBe('all')
    expect(tabOf({ tab: 'notes' })).toBe('notes')
  })
})

describe('other URL schemas', () => {
  it('validates search, new-note and editor params', () => {
    expect(noteSearchSchema.parse({ q: '17(5)', scope: 'notes' })).toEqual({ q: '17(5)', scope: 'notes' })
    expect(noteSearchSchema.parse({ scope: 'everything' })).toEqual({})
    expect(newNoteSchema.parse({ level: LEVEL, subject: 'taxation', chapter: 'gst-itc' })).toEqual({
      level: LEVEL,
      subject: 'taxation',
      chapter: 'gst-itc',
    })
    expect(noteEditorSchema.parse({ v: '4', panel: 'history' })).toEqual({ v: 4, panel: 'history' })
    expect(noteEditorSchema.parse({ v: '-1', panel: 'x' })).toEqual({})
  })
})

describe('aggregateParams and aggregateQuery', () => {
  const base = { level: LEVEL, subject: 'taxation', chapter: 'gst-itc' }

  it('puts only what is set into the query, in a stable order', () => {
    const params = aggregateParams(base, { tab: 'notes', tag: TAG, cursor: 'c1' })
    expect(aggregateQuery(params, 30)).toBe(
      `level=${LEVEL}&subject=taxation&chapter=gst-itc&tab=notes&tag=${TAG}&cursor=c1&limit=30`,
    )
  })

  it('swaps a date range given backwards', () => {
    const params = aggregateParams(base, { from: '2026-10-01', to: '2026-09-01' })
    expect([params.from, params.to]).toEqual(['2026-09-01', '2026-10-01'])
  })

  it('asks for unfiled notes when told to', () => {
    expect(aggregateQuery({ level: LEVEL, tab: 'all', unfiled: true })).toBe(`level=${LEVEL}&tab=all&unfiled=1`)
  })
})

describe('filter chips', () => {
  it('lists the active filters, not the tab or the cursor', () => {
    expect(activeFilters({ tab: 'notes', cursor: 'x', tag: TAG, from: '2026-09-01' })).toEqual(['tag', 'from'])
  })

  it('removing a filter also resets the cursor', () => {
    expect(withoutFilter({ tag: TAG, tab: 'notes', cursor: 'x' }, 'tag')).toEqual({ tab: 'notes' })
  })

  it('suggests the strongest filter to drop when nothing matches', () => {
    expect(strongestFilter({ from: '2026-09-01', tag: TAG })).toBe('tag')
    expect(strongestFilter({ tab: 'notes' })).toBeNull()
  })
})
