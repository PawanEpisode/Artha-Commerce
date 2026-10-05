import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { describeAccountError, exportBlob, exportFileName, isConfirmed } from './accountData'

const err = (status: number, code?: string) => new ApiError(status, 'x', code ? { error: { code } } : undefined)

describe('exportFileName', () => {
  it('uses the local date, zero padded', () => {
    expect(exportFileName(new Date(2026, 0, 5, 23, 59))).toBe('artha-data-2026-01-05.json')
    expect(exportFileName(new Date(2026, 9, 6))).toBe('artha-data-2026-10-06.json')
  })
})

describe('isConfirmed', () => {
  it.each([
    ['DELETE', true],
    [' delete ', true],
    ['Delete', true],
    ['DELET', false],
    ['', false],
    ['DELETE ME', false],
  ])('%j -> %s', (typed, expected) => expect(isConfirmed(typed)).toBe(expected))
})

describe('exportBlob', () => {
  it('is pretty JSON the student can open anywhere', async () => {
    const blob = exportBlob({ a: 1 })
    expect(blob.type).toBe('application/json')
    expect(await blob.text()).toBe('{\n  "a": 1\n}')
  })
})

describe('describeAccountError', () => {
  it('knows the cases the UI branches on', () => {
    expect(describeAccountError(err(401, 'reauth_required'), 'delete').kind).toBe('reauth')
    expect(describeAccountError(err(429), 'export').kind).toBe('rate_limited')
    expect(describeAccountError(err(500, 'deletion_incomplete'), 'delete').kind).toBe('incomplete')
    expect(describeAccountError(err(0), 'export').kind).toBe('network')
    expect(describeAccountError(new Error('x'), 'delete').kind).toBe('server')
  })
  it('words export and delete limits differently', () => {
    expect(describeAccountError(err(429), 'export').message).toMatch(/hour/)
    expect(describeAccountError(err(429), 'delete').message).toMatch(/tomorrow/)
  })
})
