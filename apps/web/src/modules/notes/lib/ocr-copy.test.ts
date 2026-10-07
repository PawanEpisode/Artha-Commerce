import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import {
  classifyOcrError,
  formatEstimate,
  ocrEstimateSeconds,
  ocrOffer,
  ocrPagesLeft,
  ocrProgressText,
  resetDateText,
} from './ocr-copy'

const usage = (used: number, limit: number) =>
  ({ limits: { ocr_pages_per_month: limit }, used: { ocr_pages: used } }) as never
const err = (status: number, code: string) => new ApiError(status, 'x', { error: { code, message: 'm' } })

describe('OCR estimate and offer', () => {
  it('estimates at 4.7 seconds a page', () => expect(ocrEstimateSeconds(320)).toBe(1504))
  it('rounds the wording like a person would', () => {
    expect(formatEstimate(20)).toBe('Less than a minute')
    expect(formatEstimate(60)).toBe('About 1 minute')
    expect(formatEstimate(5 * 60)).toBe('About 5 minutes')
    expect(formatEstimate(1504)).toBe('About 25 minutes')
    expect(formatEstimate(3 * 3600)).toBe('About 3 hours')
  })
  it('says what it costs against the month and offers a partial range when it does not fit', () => {
    const doc = { page_count: 320, ocr_pages_total: 0 }
    const fits = ocrOffer(doc, usage(0, 500))
    expect(fits).toMatchObject({ fits: true, needed: 320, left: 500, partialRange: null })
    expect(fits.summary).toBe('About 25 minutes, uses 320 of 500 pages this month')
    const tight = ocrOffer(doc, usage(380, 500))
    expect(tight).toMatchObject({ fits: false, left: 120, partialRange: '1-120' })
    expect(ocrOffer(doc, usage(500, 500))).toMatchObject({ fits: false, left: 0, partialRange: null })
  })
  it('uses the pages OCR still has to read when some are done', () =>
    expect(ocrOffer({ page_count: 320, ocr_pages_total: 200 }, usage(0, 500)).needed).toBe(200))
  it('never shows a negative allowance and tolerates missing usage', () => {
    expect(ocrPagesLeft(usage(600, 500))).toBe(0)
    expect(ocrPagesLeft(undefined)).toBeNull()
    expect(ocrOffer({ page_count: 10, ocr_pages_total: 0 }, undefined).fits).toBe(true)
  })
  it('writes the reset date in en-IN', () => {
    expect(resetDateText('2026-11-01')).toMatch(/1 Nov(ember)? 2026/)
    expect(resetDateText(undefined)).toBe('')
  })
  it('words progress', () => {
    expect(ocrProgressText(0, 320)).toBe('OCR 0 of 320')
    expect(ocrProgressText(120, 320)).toBe('OCR 120 of 320, searchable as pages finish')
    expect(ocrProgressText(0, 0)).toBe('OCR 0 of …')
  })
})

describe('classifyOcrError', () => {
  it.each([
    ['quota_exceeded', 'quota'],
    ['locked', 'locked'],
    ['ocr_not_allowed', 'not_allowed'],
    ['not_ready', 'not_ready'],
    ['invalid_pages', 'invalid_pages'],
    ['not_scanned_or_no_pages', 'has_text'],
    ['whatever', 'other'],
  ])('%s is %s', (code, reason) => expect(classifyOcrError(err(409, code)).reason).toBe(reason))
})
