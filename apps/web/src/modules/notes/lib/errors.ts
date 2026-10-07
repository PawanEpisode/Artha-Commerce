import { ApiError } from '~/lib/api'

import type { NoteConflictDetail } from './types'

const envelope = (error: unknown) =>
  error instanceof ApiError
    ? (error.body as { error?: { code?: unknown; message?: unknown; details?: unknown } } | undefined)?.error
    : undefined

/** 403 `feature_disabled`: the server-side `notes` flag is off for this student. Same as the web flag being off. */
export const isFeatureDisabled = (error: unknown) =>
  error instanceof ApiError && error.status === 403 && envelope(error)?.code === 'feature_disabled'

export const isNotFound = (error: unknown) => error instanceof ApiError && error.status === 404

export function noteConflict(error: unknown): NoteConflictDetail | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null
  const e = envelope(error)
  return e?.code === 'note_conflict' && e.details ? (e.details as NoteConflictDetail) : null
}

export interface QuotaDetails {
  kind: 'notes' | 'tags' | 'storage'
  used: number
  limit: number
  plan: string
}

/** 429 `quota_exceeded` on a document call: more kinds, and what the quota sheet needs to offer a way out. */
export interface DocumentQuotaDetails {
  kind: 'storage' | 'documents' | 'ocr' | 'export' | 'marks'
  used: number
  limit: number
  plan: string
  /** Kinds storage and documents: the five largest documents, so the sheet can offer Open, Download or Delete. */
  largest_documents?: Array<{ id: string; title: string; bytes: number }>
  /** Kind ocr: the date the monthly OCR allowance resets. */
  resets_on?: string
}

export function quotaExceeded(error: unknown): QuotaDetails | null {
  if (!(error instanceof ApiError) || error.status !== 429) return null
  const e = envelope(error)
  return e?.code === 'quota_exceeded'
    ? ((e.details as QuotaDetails | null) ?? { kind: 'notes', used: 0, limit: 0, plan: 'free' })
    : null
}

export interface BodyError {
  code: string
  message: string
  line?: number | null
}

/** 422 `invalid_body`: the server's lint errors, to show beside the editor. */
export function invalidBody(error: unknown): BodyError[] | null {
  if (!(error instanceof ApiError) || error.status !== 422) return null
  const e = envelope(error)
  if (e?.code !== 'invalid_body') return null
  return ((e.details as { errors?: BodyError[] } | null)?.errors ?? []) as BodyError[]
}

export const isTagExists = (error: unknown) =>
  error instanceof ApiError && error.status === 409 && envelope(error)?.code === 'tag_exists'

// ---- Documents (R2) ----------------------------------------------------------------------------------------------------

/** The envelope's machine code, whatever the status (`file_too_large`, `ranges_overlap`, `not_uploaded`, ...). */
export const errorCode = (error: unknown): string | undefined => {
  const code = envelope(error)?.code
  return typeof code === 'string' ? code : undefined
}

const detailsOf = (error: unknown): Record<string, unknown> =>
  (envelope(error)?.details as Record<string, unknown> | undefined | null) ?? {}

/** 413 `file_too_large`: the plan's file limit in MB. */
export function fileTooLarge(error: unknown): { limitMb: number } | null {
  if (!(error instanceof ApiError) || error.status !== 413 || errorCode(error) !== 'file_too_large') return null
  return { limitMb: Number(detailsOf(error).limit_mb) || 0 }
}

/** 429 `quota_exceeded` on a document call, with the details the quota sheet shows. */
export function documentQuotaExceeded(error: unknown): DocumentQuotaDetails | null {
  if (!(error instanceof ApiError) || error.status !== 429 || errorCode(error) !== 'quota_exceeded') return null
  const details = (envelope(error)?.details as Partial<DocumentQuotaDetails> | null | undefined) ?? {}
  return { kind: 'storage', used: 0, limit: 0, plan: 'free', ...details }
}

/** 415 `unsupported_type`: the file is not a PDF. */
export const isUnsupportedType = (error: unknown) => error instanceof ApiError && error.status === 415

/** 422 `too_many_pages`: the plan's page limit. */
export function tooManyPages(error: unknown): { limit: number } | null {
  if (!(error instanceof ApiError) || error.status !== 422 || errorCode(error) !== 'too_many_pages') return null
  return { limit: Number(detailsOf(error).limit) || 0 }
}

export const isRangesOverlap = (error: unknown) => error instanceof ApiError && errorCode(error) === 'ranges_overlap'
export const isNotUploaded = (error: unknown) => error instanceof ApiError && errorCode(error) === 'not_uploaded'
/** 409 `locked`: OCR or export on a file that needs its password. */
export const isLocked = (error: unknown) => error instanceof ApiError && errorCode(error) === 'locked'

/** 409 `document_conflict` (stale `base_rev`): the stored document the edit lost against. */
export function documentConflict(error: unknown): { theirs: unknown } | null {
  if (!(error instanceof ApiError) || error.status !== 409 || errorCode(error) !== 'document_conflict') return null
  const theirs = detailsOf(error).theirs
  return theirs ? { theirs } : null
}

/** The request id the API puts in its error envelope, for the "Report" action and support. */
export const requestIdOf = (error: unknown): string | undefined => {
  const e = envelope(error) as { request_id?: unknown } | undefined
  const fromBody = e?.request_id
  return typeof fromBody === 'string' ? fromBody : undefined
}

/** Plain-English sentence for a failed document call. Never includes file names or any personal text. */
export function documentErrorMessage(error: unknown): string {
  const quota = documentQuotaExceeded(error)
  if (quota) {
    if (quota.kind === 'ocr') return "You have used this month's OCR pages. They reset on the first of the month."
    if (quota.kind === 'export') return "You have reached this month's export limit."
    if (quota.kind === 'marks') return 'This PDF has reached its limit of marks.'
    if (quota.kind === 'documents') return 'You have reached the number of PDFs your plan allows.'
    return 'Your PDF storage is full. Delete a document you no longer need, then try again.'
  }
  const tooLarge = fileTooLarge(error)
  if (tooLarge)
    return `That file is over the ${tooLarge.limitMb || 50} MB limit. Split or compress the PDF and try again.`
  const pages = tooManyPages(error)
  if (pages) return `That PDF has more than ${pages.limit || 1000} pages. Split it into parts and try again.`
  if (isUnsupportedType(error)) return 'That does not look like a PDF.'
  if (isRangesOverlap(error)) return 'Two chapter ranges overlap. Adjust the page numbers so each page is in one range.'
  if (isNotUploaded(error)) return 'The upload did not finish. Please try again.'
  if (isLocked(error)) return 'This PDF is locked. Search and OCR need its password.'
  if (isFeatureDisabled(error)) return 'PDFs are not available yet.'
  if (isNotFound(error)) return 'We could not find that document.'
  if (error instanceof ApiError && error.status === 429) return 'Too many requests. Wait a moment and try again.'
  return 'Something went wrong on our side. Please try again.'
}
