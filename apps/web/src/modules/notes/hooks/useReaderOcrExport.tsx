import { Button, Download } from '@artha/design-system'
import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { DocumentDialogs } from '../containers/DocumentDialogs'
import type { ReaderExtensions } from '../containers/reader-extensions'
import type { DocumentProcessing } from '../lib/document-types'
import { notesKeys } from '../lib/keys'
import { useDocumentDialogState } from './useDocumentDialogState'
import { useDocument } from './useDocuments'
import { useOcrTransitions } from './useOcrTransitions'

/**
 * The library's seams into the reader (WEB-3): an "Export" button for the top bar and the OCR offer behind the scanned
 * banner's "Make searchable". `PdfReaderScreen` merges `extensions` into its own and passes `onMakeSearchable` to the
 * container. The dialogs render inside `topActions` (they portal to the page), so the reader needs no other change.
 * Without the `notes_pdf` flag, or before the document loads, it contributes nothing.
 */
export function useReaderOcrExport(documentId: string): {
  extensions: Partial<ReaderExtensions>
  onMakeSearchable?: () => void
} {
  const enabled = useFeatureFlag('notes_pdf')
  const query = useDocument(documentId)
  const doc = enabled ? query.data : undefined
  const dialogs = useDocumentDialogState()
  const { openExport, openOcr } = dialogs

  // The reader's own `processing/` poll fills this cache entry; this only watches it, so no second poll runs.
  const processing = useQuery<DocumentProcessing>({
    queryKey: notesKeys.documentProcessing(documentId),
    queryFn: () => Promise.reject(new Error('observer only')),
    enabled: false,
  })
  const entries = useMemo(
    () =>
      processing.data
        ? [{ id: documentId, status: processing.data.ocr_status, pages: processing.data.ocr_pages_total }]
        : [],
    [documentId, processing.data],
  )
  useOcrTransitions(entries)

  return useMemo(() => {
    if (!doc) return { extensions: {} }
    return {
      extensions: {
        topActions: (
          <>
            <Button
              variant="ghost"
              size="icon"
              className="size-11"
              aria-label="Export with my marks"
              title="Export with my marks"
              onClick={() => openExport(doc)}
            >
              <Download aria-hidden />
            </Button>
            <DocumentDialogs controller={dialogs} showLibraryLink />
          </>
        ),
      },
      onMakeSearchable: () => openOcr(doc),
    }
    // `dialogs` changes with its state, which is what keeps the open dialog current.
  }, [doc, dialogs, openExport, openOcr])
}
