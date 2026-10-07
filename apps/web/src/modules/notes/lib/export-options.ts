import type { DocumentSummary, ExportJob, ExportOptions, MarkExportKind } from './document-types'
import { errorCode } from './errors'

export const EXPORT_KINDS: ReadonlyArray<{ value: MarkExportKind; label: string }> = [
  { value: 'highlight', label: 'Highlights' },
  { value: 'underline', label: 'Underlines' },
  { value: 'ink', label: 'Pen drawings' },
  { value: 'textbox', label: 'Text boxes' },
  { value: 'sticky', label: 'Sticky notes' },
  { value: 'area', label: 'Area highlights' },
]

export type PageSpec = { ok: true; spec: string | undefined; count: number } | { ok: false; message: string }

/**
 * Turns "1-40, 50" into the canonical "1-40,50" the API takes. Empty means the whole file (no `pages` sent). Pages must
 * be inside the file when its length is known, in order of appearance not required (the API sorts and merges).
 */
export function parsePageSpec(text: string, pageCount: number | null): PageSpec {
  const raw = text.trim()
  if (raw === '') return { ok: true, spec: undefined, count: pageCount ?? 0 }
  const parts = raw.split(',').map((p) => p.trim())
  const spans: Array<[number, number]> = []
  for (const part of parts) {
    const m = /^(\d{1,6})(?:\s*-\s*(\d{1,6}))?$/.exec(part)
    if (!m) return { ok: false, message: 'Use page numbers like 1-40 or 1-3, 7.' }
    const from = Number(m[1])
    const to = m[2] === undefined ? from : Number(m[2])
    if (from < 1 || to < from)
      return { ok: false, message: 'Each range must go from a smaller page to a larger one, from 1.' }
    if (pageCount !== null && to > pageCount) return { ok: false, message: `This PDF has ${pageCount} pages.` }
    spans.push([from, to])
  }
  spans.sort((a, b) => a[0] - b[0])
  const merged: Array<[number, number]> = []
  for (const span of spans) {
    const last = merged[merged.length - 1]
    if (last && span[0] <= last[1] + 1) last[1] = Math.max(last[1], span[1])
    else merged.push([...span])
  }
  const spec = merged.map(([a, b]) => (a === b ? String(a) : `${a}-${b}`)).join(',')
  return { ok: true, spec, count: merged.reduce((n, [a, b]) => n + (b - a + 1), 0) }
}

export interface ExportForm {
  pages: string
  include: MarkExportKind[]
  colors: string[]
  tags: string[]
  appendix: boolean
}

export const defaultExportForm = (): ExportForm => ({
  pages: '',
  include: EXPORT_KINDS.map((k) => k.value),
  colors: [],
  tags: [],
  appendix: false,
})

/** The request options: only what narrows the export is sent (all kinds, no colour and no tag filter is "everything"). */
export function buildExportOptions(form: ExportForm, spec: string | undefined): ExportOptions {
  const options: ExportOptions = {}
  if (spec) options.pages = spec
  const all = form.include.length === EXPORT_KINDS.length
  if (!all) options.include = EXPORT_KINDS.map((k) => k.value).filter((k) => form.include.includes(k))
  if (form.colors.length > 0) options.colors = form.colors
  if (form.tags.length > 0) options.tags = form.tags
  if (form.appendix) options.appendix = true
  return options
}

export type ExportBlockReason = 'restricted' | 'locked' | 'not_ready'

const BLOCK_TEXT: Record<ExportBlockReason, string> = {
  restricted: 'This file does not allow copying or changing its content, so a copy with your marks cannot be made.',
  locked: 'This PDF is locked. Open it with its password first; exports need the password.',
  not_ready: 'This PDF is still being prepared. Try again in a moment.',
}

export const exportBlockText = (reason: ExportBlockReason) => BLOCK_TEXT[reason]

/** Why Export is off for this document before asking the server, or null. */
export function exportBlock(
  doc: Pick<DocumentSummary, 'status' | 'can_copy' | 'can_modify'>,
): ExportBlockReason | null {
  if (doc.status === 'needs_password') return 'locked'
  if (doc.status !== 'ready') return 'not_ready'
  if (doc.can_copy === false || doc.can_modify === false) return 'restricted'
  return null
}

/** The reason of a 422 `export_not_allowed` (`details.reason`). */
export function exportNotAllowed(error: unknown): ExportBlockReason | null {
  if (errorCode(error) !== 'export_not_allowed') return null
  const reason = (error as { body?: { error?: { details?: { reason?: unknown } } } }).body?.error?.details?.reason
  return reason === 'restricted' || reason === 'locked' || reason === 'not_ready' ? reason : 'not_ready'
}

const LINK_HOURS = 23

/** A download link is signed for 24 hours: after 23 the dialog fetches the job again for a fresh one. */
export const linkIsStale = (fetchedAt: number, now: number = Date.now()) => now - fetchedAt > LINK_HOURS * 3_600_000

export const isExportFinished = (job: Pick<ExportJob, 'status'>) =>
  job.status === 'done' || job.status === 'failed' || job.status === 'expired'

export function exportFailureText(job: Pick<ExportJob, 'error_code' | 'details'>): string {
  switch (job.error_code) {
    case 'export_too_large':
      return job.details?.suggested_pages
        ? `This is too large to build in one go. Try pages ${job.details.suggested_pages}.`
        : 'This is too large to build in one go. Choose fewer pages.'
    case 'restricted':
      return exportBlockText('restricted')
    case 'locked':
      return exportBlockText('locked')
    default:
      return 'We could not build this export. Please try again.'
  }
}
