import type { DocumentSummary } from './document-types'
import { isOcrRunning, isPreparing } from './document-types'

export type BadgeKind =
  | 'ready'
  | 'preparing'
  | 'waiting'
  | 'scanned'
  | 'ocr'
  | 'searchable'
  | 'ocr_failed'
  | 'locked'
  | 'rejected'
  | 'failed'
  | 'expired'
  | 'offline'
export type BadgeTone = 'success' | 'info' | 'warning' | 'error' | 'neutral'

export interface DocBadge {
  kind: BadgeKind
  label: string
  tone: BadgeTone
  /** One short sentence for the title attribute and the details sheet. */
  detail?: string
}

type BadgeInput = Pick<
  DocumentSummary,
  'status' | 'is_scanned' | 'ocr_status' | 'ocr_pages_done' | 'ocr_pages_total' | 'page_count' | 'text_status'
>

/** The status badges of a card, in the order they are shown. Words and an icon (set by the card), never colour alone. */
export function documentBadges(doc: BadgeInput, opts: { offlineCopy?: boolean } = {}): DocBadge[] {
  const out: DocBadge[] = []
  switch (doc.status) {
    case 'reserved':
      out.push({
        kind: 'waiting',
        label: 'Upload not finished',
        tone: 'neutral',
        detail: 'The file did not reach us. Add it again.',
      })
      break
    case 'scanning':
    case 'inspecting':
      out.push({
        kind: 'preparing',
        label: 'Preparing',
        tone: 'info',
        detail: 'We are checking the file. You can open it as soon as it is ready.',
      })
      break
    case 'needs_password':
      out.push({
        kind: 'locked',
        label: 'Locked',
        tone: 'warning',
        detail: 'Locked: opens with your password. Search and OCR need it.',
      })
      break
    case 'rejected':
      out.push({ kind: 'rejected', label: 'Rejected', tone: 'error', detail: 'We could not accept this file.' })
      break
    case 'failed':
      out.push({
        kind: 'failed',
        label: 'Failed',
        tone: 'error',
        detail: 'Something went wrong while preparing this file.',
      })
      break
    case 'expired':
      out.push({
        kind: 'expired',
        label: 'Upload expired',
        tone: 'neutral',
        detail: 'The upload was not finished in time.',
      })
      break
    case 'ready':
      out.push({ kind: 'ready', label: 'Ready', tone: 'success' })
      if (doc.is_scanned) {
        if (isOcrRunning(doc.ocr_status) || doc.ocr_status === 'partial') {
          out.push({
            kind: 'ocr',
            label: `OCR ${doc.ocr_pages_done} of ${doc.ocr_pages_total || doc.page_count || '…'}`,
            tone: 'info',
            detail: 'Searchable as pages finish.',
          })
        } else if (doc.ocr_status === 'done') {
          out.push({ kind: 'searchable', label: 'Scanned, searchable', tone: 'success' })
        } else if (doc.ocr_status === 'failed') {
          out.push({
            kind: 'ocr_failed',
            label: 'OCR failed',
            tone: 'warning',
            detail: 'We could not make it searchable. Try again.',
          })
        } else {
          out.push({
            kind: 'scanned',
            label: 'Scanned, search off',
            tone: 'warning',
            detail: 'Search and text selection need OCR.',
          })
        }
      }
      break
  }
  if (opts.offlineCopy) out.push({ kind: 'offline', label: 'Offline copy', tone: 'neutral' })
  return out
}

/** How far the student has read, 0..100, or null before the first open or when the page count is unknown. */
export function readPercent(doc: Pick<DocumentSummary, 'last_page' | 'page_count' | 'last_opened_at'>): number | null {
  if (!doc.last_opened_at || !doc.page_count || doc.page_count <= 0) return null
  return Math.max(0, Math.min(100, Math.round((doc.last_page / doc.page_count) * 100)))
}

/** The server is still working on this card (the list polls while any card is). */
export const isWorking = (doc: Pick<DocumentSummary, 'status' | 'ocr_status'>) =>
  (isPreparing(doc.status) && doc.status !== 'reserved') || isOcrRunning(doc.ocr_status)

export const canOpenDocument = (doc: Pick<DocumentSummary, 'status'>) =>
  doc.status === 'ready' || doc.status === 'needs_password' || doc.status === 'inspecting'

/** Title or a stand-in, for a card and an accessible name. */
export const documentTitle = (doc: Pick<DocumentSummary, 'title' | 'original_filename'>) =>
  doc.title.trim() || doc.original_filename.trim() || 'Untitled PDF'
