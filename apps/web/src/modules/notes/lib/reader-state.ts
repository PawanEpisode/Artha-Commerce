import type { DocumentDetail, DocumentStatus, DocumentStatusReason, OcrStatus, PageTone } from './document-types'
import { isPreparing } from './document-types'

/** What the reader shows for a document it cannot open (yet), decided from the record alone. */
export type Openability =
  { kind: 'open' } | { kind: 'preparing' } | { kind: 'unavailable'; title: string; message: string }

const REASON_TEXT: Record<DocumentStatusReason, string> = {
  type_mismatch: 'The file is not a PDF.',
  malware: 'Our scan found a problem in the file, so we removed it.',
  pdf_corrupt: 'The file is damaged and cannot be read.',
  too_many_pages: 'The file has more pages than your plan allows.',
  too_large: 'The file is larger than your plan allows.',
  decode_failed: 'The file could not be read.',
  policy: 'The file cannot be added.',
}

export function openability(
  doc: Pick<DocumentDetail, 'status' | 'status_reason' | 'can_open' | 'file_url'>,
): Openability {
  const readableStatus: DocumentStatus[] = ['inspecting', 'ready', 'needs_password']
  if (doc.can_open && doc.file_url && readableStatus.includes(doc.status)) return { kind: 'open' }
  if (isPreparing(doc.status)) return { kind: 'preparing' }
  if (doc.status === 'rejected')
    return {
      kind: 'unavailable',
      title: 'We could not accept this file',
      message: (doc.status_reason && REASON_TEXT[doc.status_reason]) || 'The file could not be accepted.',
    }
  if (doc.status === 'expired')
    return {
      kind: 'unavailable',
      title: 'This upload did not finish',
      message: 'The upload was not completed in time. Add the PDF again from your library.',
    }
  return {
    kind: 'unavailable',
    title: 'We could not open this file',
    message: (doc.status_reason && REASON_TEXT[doc.status_reason]) || 'Something went wrong while preparing it.',
  }
}

/** Page tone when the document has no choice of its own: paper in the Reading theme (it "follows" it), as printed otherwise. */
export const defaultTone = (resolvedTheme: string): PageTone => (resolvedTheme === 'reading' ? 'paper' : 'original')

/** Night is suggested once, in the Dark theme, when the page is bright. */
export const shouldSuggestNight = (resolvedTheme: string, tone: PageTone, alreadySuggested: boolean) =>
  resolvedTheme === 'dark' && tone !== 'night' && !alreadySuggested

/** Scanned and not yet searchable: the banner's condition. Native-text PDFs and finished OCR never show it. */
export const needsOcrBanner = (isScanned: boolean | null, ocr: OcrStatus) => isScanned === true && ocr !== 'done'

/** Where search is answered: scanned files only have text on the server (OCR), big files are too heavy for the browser. */
export const searchMode = (large: boolean, isScanned: boolean | null): 'local' | 'server' =>
  large || isScanned === true ? 'server' : 'local'

/** Buckets for the one product event; no ids, names or text. */
export const ttfpBucket = (ms: number) => (ms < 1000 ? 'lt1s' : ms < 2000 ? '1-2s' : ms < 4000 ? '2-4s' : '4s+')
export const pagesBucket = (n: number) => (n <= 20 ? '1-20' : n <= 100 ? '21-100' : n <= 400 ? '101-400' : '400+')
