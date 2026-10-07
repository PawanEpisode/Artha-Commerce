import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import {
  documentConflict,
  documentErrorMessage,
  documentQuotaExceeded,
  errorCode,
  fileTooLarge,
  isFeatureDisabled,
  isLocked,
  isNotUploaded,
  isRangesOverlap,
  isUnsupportedType,
  requestIdOf,
  tooManyPages,
} from './errors'

const err = (status: number, code: string, details?: unknown, extra: object = {}) =>
  new ApiError(status, 'x', { error: { code, message: 'm', details, ...extra } })

describe('document error mapping', () => {
  it('reads the machine code', () => {
    expect(errorCode(err(413, 'file_too_large'))).toBe('file_too_large')
    expect(errorCode(new Error('plain'))).toBeUndefined()
  })

  it('maps the upload refusals with their limits', () => {
    expect(fileTooLarge(err(413, 'file_too_large', { limit_mb: 50 }))).toEqual({ limitMb: 50 })
    expect(fileTooLarge(err(500, 'file_too_large'))).toBeNull()
    expect(tooManyPages(err(422, 'too_many_pages', { limit: 1000 }))).toEqual({ limit: 1000 })
    expect(isUnsupportedType(err(415, 'unsupported_type'))).toBe(true)
    expect(isNotUploaded(err(409, 'not_uploaded'))).toBe(true)
  })

  it('maps quota kinds with the largest documents', () => {
    const q = documentQuotaExceeded(
      err(429, 'quota_exceeded', {
        kind: 'storage',
        used: 500,
        limit: 500,
        plan: 'free',
        largest_documents: [{ id: 'a', title: 'T', bytes: 9 }],
      }),
    )
    expect(q?.kind).toBe('storage')
    expect(q?.largest_documents).toHaveLength(1)
    expect(
      documentQuotaExceeded(
        err(429, 'quota_exceeded', { kind: 'ocr', used: 300, limit: 300, plan: 'free', resets_on: '2026-11-01' }),
      )?.resets_on,
    ).toBe('2026-11-01')
    expect(documentQuotaExceeded(err(429, 'throttled'))).toBeNull()
    expect(documentQuotaExceeded(err(429, 'quota_exceeded'))?.kind).toBe('storage')
  })

  it('maps ranges, locks, conflicts, flags', () => {
    expect(isRangesOverlap(err(409, 'ranges_overlap'))).toBe(true)
    expect(isLocked(err(409, 'locked'))).toBe(true)
    expect(isFeatureDisabled(err(403, 'feature_disabled'))).toBe(true)
    expect(documentConflict(err(409, 'document_conflict', { theirs: { id: 'a' } }))?.theirs).toEqual({ id: 'a' })
    expect(documentConflict(err(409, 'document_conflict'))).toBeNull()
  })

  it('finds a request id when the API sends one', () => {
    expect(requestIdOf(err(500, 'x', undefined, { request_id: 'req-1' }))).toBe('req-1')
    expect(requestIdOf(err(500, 'x'))).toBeUndefined()
  })

  it('writes plain sentences without file names', () => {
    expect(documentErrorMessage(err(413, 'file_too_large', { limit_mb: 50 }))).toMatch(/50 MB/)
    expect(documentErrorMessage(err(422, 'too_many_pages', { limit: 1000 }))).toMatch(/1000 pages/)
    expect(documentErrorMessage(err(415, 'unsupported_type'))).toMatch(/PDF/)
    expect(documentErrorMessage(err(429, 'quota_exceeded', { kind: 'ocr' }))).toMatch(/OCR/)
    expect(documentErrorMessage(err(429, 'quota_exceeded', { kind: 'storage' }))).toMatch(/storage/)
    expect(documentErrorMessage(err(409, 'ranges_overlap'))).toMatch(/overlap/)
    expect(documentErrorMessage(err(404, 'not_found'))).toMatch(/could not find/)
    expect(documentErrorMessage(new Error('boom'))).toMatch(/Something went wrong/)
  })
})
