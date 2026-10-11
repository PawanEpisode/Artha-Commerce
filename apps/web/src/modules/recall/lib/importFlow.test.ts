import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { canImport, doneDetail, doneHeading, importFailure, previewSentence, rowResult } from './importFlow'
import type { ImportResult, ImportRow } from './schemas'

const row = (over: Partial<ImportRow> = {}): ImportRow => ({
  line: 1,
  status: 'ok',
  kind: 'pointer',
  front: 'Q',
  back: 'A',
  issues: [],
  card_id: null,
  ...over,
})
const result = (over: Partial<ImportResult> = {}): ImportResult => ({
  dry_run: true,
  total: 3,
  valid: 2,
  invalid: 1,
  created: 0,
  existing: 0,
  quota: { room: 10, needed: 2, fits: true },
  rows: [],
  ...over,
})

describe('import flow', () => {
  it('says what the preview will do', () => {
    expect(previewSentence(result())).toBe('2 rows are ready, and 1 row with a problem will be skipped.')
    expect(previewSentence(result({ valid: 1, invalid: 0, total: 1 }))).toBe('1 row is ready.')
    expect(previewSentence(result({ valid: 0, invalid: 3 }))).toMatch(/None of the 3 rows/)
    expect(previewSentence(result({ total: 0, valid: 0, invalid: 0 }))).toBe('There are no rows to import.')
  })
  it('says what the import did', () => {
    const done = result({ dry_run: false, created: 2, invalid: 1 })
    expect(doneHeading(done)).toBe('2 rows imported')
    expect(doneDetail(done)).toBe('1 row had a problem and was skipped.')
    expect(doneHeading(result({ dry_run: false, created: 0, existing: 3, valid: 0 }))).toBe(
      'These cards were already imported',
    )
    expect(doneDetail(result({ dry_run: false, created: 2, invalid: 0 }))).toMatch(/show up in your reviews/)
  })
  it('puts the problems of a row in plain words', () => {
    expect(rowResult(row())).toEqual({ tone: 'ok', lines: ['Ready'] })
    const bad = row({
      status: 'error',
      issues: [{ field: 'back', code: 'required', message: 'back is required.' }],
    })
    expect(rowResult(bad)).toEqual({ tone: 'error', lines: ['back is required.'] })
    expect(rowResult(row({ status: 'error' })).lines).toEqual(['This row cannot be imported.'])
  })
  it('allows the import only after a fresh preview that fits', () => {
    expect(canImport(null, false)).toBe(false)
    expect(canImport(result(), false)).toBe(true)
    expect(canImport(result(), true)).toBe(false)
    expect(canImport(result({ valid: 0 }), false)).toBe(false)
    expect(canImport(result({ quota: { room: 1, needed: 2, fits: false } }), false)).toBe(false)
  })
  it('explains a failure and always says nothing was added', () => {
    const api = (status: number, code: string) => new ApiError(status, 'x', { error: { code, message: 'No room.' } })
    expect(importFailure(api(422, 'import_too_large'))).toMatch(/at most 200 rows/)
    expect(importFailure(api(429, 'quota_exceeded'))).toMatch(/Nothing was added/)
    expect(importFailure(new TypeError('network'))).toMatch(/Nothing was added/)
    expect(importFailure(api(500, 'oops'))).toMatch(/Nothing was added/)
  })
})
