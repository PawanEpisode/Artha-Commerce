import { describe, expect, it } from 'vitest'

import { readerSearchSchema } from './reader-schema'

describe('readerSearchSchema', () => {
  it('accepts a full reader URL', () => {
    const id = '11111111-1111-4111-8111-111111111111'
    expect(
      readerSearchSchema.parse({ page: 12, zoom: 'fit', q: 'ITC', panel: 'search', tool: 'highlight', ann: id }),
    ).toEqual({
      page: 12,
      zoom: 'fit',
      q: 'ITC',
      panel: 'search',
      tool: 'highlight',
      ann: id,
    })
  })

  it('reads a numeric zoom the way the router parses it', () => {
    expect(readerSearchSchema.parse({ zoom: 125 }).zoom).toBe(125)
    expect(readerSearchSchema.parse({ zoom: '150' }).zoom).toBe(150)
  })

  it('drops bad values and keeps the rest', () => {
    const parsed = readerSearchSchema.parse({
      page: 'x',
      zoom: 9,
      q: '   ',
      panel: 'nope',
      tool: 'laser',
      ann: 'not-a-uuid',
    })
    expect(parsed).toEqual({})
    expect(readerSearchSchema.parse({ page: 0, zoom: 'fit', q: 'a'.repeat(300) })).toEqual({ zoom: 'fit' })
  })

  it('opens with no parameters', () => {
    expect(readerSearchSchema.parse({})).toEqual({})
  })
})
