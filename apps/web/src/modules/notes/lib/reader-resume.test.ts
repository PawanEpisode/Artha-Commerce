import { describe, expect, it } from 'vitest'

import { resolveResume } from './reader-resume'

const stored = { last_page: 142, last_zoom: '125' }

describe('resolveResume', () => {
  it('opens at the stored page and zoom', () => {
    expect(resolveResume({}, stored, 328)).toEqual({ page: 142, zoom: 125 })
  })

  it('lets the URL win, part by part', () => {
    expect(resolveResume({ page: 7, zoom: 'fit' }, stored, 328)).toEqual({ page: 7, zoom: 'fit' })
    expect(resolveResume({ page: 7 }, stored, 328)).toEqual({ page: 7, zoom: 125 })
    expect(resolveResume({ zoom: 200 }, stored, 328)).toEqual({ page: 142, zoom: 200 })
  })

  it('clamps a page past the end and reads fit', () => {
    expect(resolveResume({ page: 900 }, { last_page: 1, last_zoom: 'fit' }, 328)).toEqual({ page: 328, zoom: 'fit' })
    expect(resolveResume({}, { last_page: 500, last_zoom: 'fit' }, 328).page).toBe(328)
  })

  it('does not clamp when the page count is not known yet', () => {
    expect(resolveResume({}, stored, null).page).toBe(142)
  })
})
