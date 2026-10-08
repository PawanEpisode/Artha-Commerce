import type { DocumentSummary } from './document-types'
import { errorCode } from './errors'
import type { Usage } from './types'

/** Seconds of Tesseract time per page, as measured on the worker; the real figure comes back from `POST ocr/`. */
export const SECONDS_PER_PAGE = 4.7

export const ocrEstimateSeconds = (pages: number) => Math.round(Math.max(0, pages) * SECONDS_PER_PAGE)

/** "About 25 minutes": rounded to 5 minutes from 10 minutes up, whole minutes below, hours past 90 minutes. */
export function formatEstimate(seconds: number): string {
  const minutes = seconds / 60
  if (minutes < 1) return 'Less than a minute'
  if (minutes < 10) return `About ${Math.round(minutes)} minute${Math.round(minutes) === 1 ? '' : 's'}`
  if (minutes <= 90) return `About ${Math.round(minutes / 5) * 5} minutes`
  const hours = Math.round((minutes / 60) * 2) / 2
  return `About ${hours} hours`
}

export interface OcrOffer {
  /** Pages that would be read. */
  needed: number
  /** The monthly allowance and what is left of it. */
  limit: number
  left: number
  fits: boolean
  /** "About 25 minutes, uses 320 of 300 pages this month" */
  summary: string
  /** The first part only, for a progress line. */
  estimateText: string
  /** When the allowance is all used: the range that still fits ("1-120"), or null when nothing is left. */
  partialRange: string | null
}

/** Pages of OCR left this month, never negative. */
export const ocrPagesLeft = (usage: Pick<Usage, 'limits' | 'used'> | undefined): number | null =>
  usage ? Math.max(0, (usage.limits.ocr_pages_per_month ?? 0) - (usage.used.ocr_pages ?? 0)) : null

export function ocrOffer(
  doc: Pick<DocumentSummary, 'ocr_pages_total' | 'page_count'>,
  usage: Pick<Usage, 'limits' | 'used'> | undefined,
): OcrOffer {
  const needed = doc.ocr_pages_total || doc.page_count || 0
  const limit = usage?.limits.ocr_pages_per_month ?? 0
  const left = ocrPagesLeft(usage) ?? needed
  const estimateText = formatEstimate(ocrEstimateSeconds(needed))
  return {
    needed,
    limit,
    left,
    fits: usage ? needed <= left : true,
    summary: `${estimateText}, uses ${needed.toLocaleString('en-IN')} of ${limit.toLocaleString('en-IN')} pages this month`,
    estimateText,
    partialRange: usage && left > 0 && left < needed ? `1-${left}` : null,
  }
}

/** "1 Nov 2026" from the usage `resets_on` day. A calendar day, so it is formatted in UTC and never shifts with the device zone. */
export const resetDateText = (resetsOn: string | undefined | null) =>
  resetsOn
    ? new Date(`${resetsOn}T00:00:00Z`).toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        timeZone: 'UTC',
      })
    : ''

/** The line shown on a card or banner while OCR runs: "OCR 120 of 320, searchable as pages finish". */
export const ocrProgressText = (done: number, total: number) =>
  `OCR ${done.toLocaleString('en-IN')} of ${total ? total.toLocaleString('en-IN') : '…'}${done > 0 ? ', searchable as pages finish' : ''}`

export type OcrOutcomeReason = 'quota' | 'locked' | 'not_allowed' | 'not_ready' | 'invalid_pages' | 'has_text' | 'other'

/** What a failed `POST ocr/` means for the dialog: the code (never the status alone) picks the state. */
export function classifyOcrError(error: unknown): { reason: OcrOutcomeReason; message: string } {
  const code = errorCode(error)
  switch (code) {
    case 'quota_exceeded':
      return { reason: 'quota', message: "You have used this month's OCR pages." }
    case 'locked':
      return { reason: 'locked', message: 'Locked: search and OCR need the password.' }
    case 'ocr_not_allowed':
      return {
        reason: 'not_allowed',
        message: 'This file does not allow copying its text, so it cannot be read with OCR.',
      }
    case 'not_ready':
      return { reason: 'not_ready', message: 'This PDF is still being prepared. Try again in a moment.' }
    case 'invalid_pages':
      return { reason: 'invalid_pages', message: 'Those pages are not in this PDF. Use numbers like 1-40.' }
    case 'not_scanned_or_no_pages':
      return { reason: 'has_text', message: 'Every page of this PDF already has searchable text.' }
    default:
      return { reason: 'other', message: 'Something went wrong on our side. Please try again.' }
  }
}
