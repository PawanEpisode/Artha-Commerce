import { useEffect, useRef } from 'react'

import { notesAnalytics } from '../lib/analytics'
import type { OcrStatus } from '../lib/document-types'
import { notifyDocs } from '../lib/notify-documents'

export interface OcrEntry {
  id: string
  status: OcrStatus
  pages: number
}

const WORKING = new Set<OcrStatus>(['pending', 'running', 'partial'])

/**
 * Says so when OCR that was running finishes or fails (a toast and an analytics event), once per document. A document seen
 * for the first time already `done` says nothing: only a change the student waited for is announced.
 */
export function useOcrTransitions(entries: readonly OcrEntry[], onOpen?: (id: string) => void) {
  const last = useRef(new Map<string, OcrStatus>())
  useEffect(() => {
    for (const { id, status, pages } of entries) {
      const before = last.current.get(id)
      last.current.set(id, status)
      if (before === undefined || !WORKING.has(before)) continue
      if (status === 'done') {
        notifyDocs.ocrDone(onOpen ? () => onOpen(id) : undefined)
        notesAnalytics.ocrCompleted({ pages })
      } else if (status === 'failed') {
        notifyDocs.ocrFailed()
        notesAnalytics.ocrFailed({ pages })
      }
    }
  }, [entries, onOpen])
}
