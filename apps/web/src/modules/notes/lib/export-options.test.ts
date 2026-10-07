import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import {
  buildExportOptions,
  defaultExportForm,
  EXPORT_KINDS,
  exportBlock,
  exportBlockText,
  exportFailureText,
  exportNotAllowed,
  isExportFinished,
  linkIsStale,
  parsePageSpec,
} from './export-options'

describe('export page range', () => {
  it('means the whole file when empty', () =>
    expect(parsePageSpec('  ', 40)).toEqual({ ok: true, spec: undefined, count: 40 }))
  it('canonicalises, sorts and merges', () => {
    expect(parsePageSpec('7, 1-3 ,4, 10-12', 40)).toEqual({ ok: true, spec: '1-4,7,10-12', count: 8 })
    expect(parsePageSpec('5-5', null)).toEqual({ ok: true, spec: '5', count: 1 })
  })
  it('refuses nonsense in words', () => {
    for (const bad of ['a', '1-', '0-3', '5-2', '1;2']) expect(parsePageSpec(bad, 40).ok).toBe(false)
    expect(parsePageSpec('1-41', 40)).toEqual({ ok: false, message: 'This PDF has 40 pages.' })
  })
})

describe('export options', () => {
  it('sends only what narrows the export', () => {
    expect(buildExportOptions(defaultExportForm(), undefined)).toEqual({})
    const form = { ...defaultExportForm(), include: ['highlight' as const], colors: ['y'], tags: ['t'], appendix: true }
    expect(buildExportOptions(form, '1-5')).toEqual({
      pages: '1-5',
      include: ['highlight'],
      colors: ['y'],
      tags: ['t'],
      appendix: true,
    })
  })
  it('offers every mark kind by default', () => expect(defaultExportForm().include).toHaveLength(EXPORT_KINDS.length))
})

describe('why export is off', () => {
  it('blocks locked, preparing and restricted files with a reason', () => {
    const ok = { status: 'ready' as const, can_copy: true, can_modify: true }
    expect(exportBlock(ok)).toBeNull()
    expect(exportBlock({ ...ok, status: 'needs_password' })).toBe('locked')
    expect(exportBlock({ ...ok, status: 'scanning' })).toBe('not_ready')
    expect(exportBlock({ ...ok, can_copy: false })).toBe('restricted')
    expect(exportBlockText('restricted')).toMatch(/does not allow copying/)
  })
  it('reads the server reason and defaults to "not ready"', () => {
    const e = (reason?: string) =>
      new ApiError(422, 'x', { error: { code: 'export_not_allowed', message: 'm', details: { reason } } })
    expect(exportNotAllowed(e('locked'))).toBe('locked')
    expect(exportNotAllowed(e('mystery'))).toBe('not_ready')
    expect(exportNotAllowed(new Error('x'))).toBeNull()
  })
})

describe('export jobs', () => {
  it('suggests a range when the export is too large', () => {
    expect(exportFailureText({ error_code: 'export_too_large', details: { suggested_pages: '1-120' } })).toBe(
      'This is too large to build in one go. Try pages 1-120.',
    )
    expect(exportFailureText({ error_code: 'export_too_large', details: null })).toMatch(/Choose fewer pages/)
    expect(exportFailureText({ error_code: 'failed', details: null })).toMatch(/could not build/)
  })
  it('knows when a job is finished, and when its link is stale after 23 hours', () => {
    expect(isExportFinished({ status: 'done' })).toBe(true)
    expect(isExportFinished({ status: 'expired' })).toBe(true)
    expect(isExportFinished({ status: 'running' } as never)).toBe(false)
    expect(linkIsStale(0, 22 * 3_600_000)).toBe(false)
    expect(linkIsStale(0, 24 * 3_600_000)).toBe(true)
  })
})
