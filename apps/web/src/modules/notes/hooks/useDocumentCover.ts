import { useEffect, useState } from 'react'

import { getCachedCover, loadCover, shouldGenerateCover } from '../lib/document-cover'
import type { DocumentSummary } from '../lib/document-types'
import type { PdfEngine } from '../lib/pdf-engine'
import { useInView } from './useInView'

export interface UseDocumentCoverOptions {
  doc: Pick<DocumentSummary, 'id' | 'status' | 'cover_url'>
  /** Compact cards only show a cover that is already made; they never start one. */
  compact?: boolean
  /** Test seam; the app uses pdf.js. */
  engine?: PdfEngine
}

/**
 * What image a card shows: the server's thumbnail, else (when the card is on screen) one drawn from the PDF's first
 * page. `onError` reports a broken image so the next source, or the icon, takes over.
 */
export function useDocumentCover({ doc, compact = false, engine }: UseDocumentCoverOptions) {
  const [ref, visible] = useInView<HTMLDivElement>()
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const [generated, setGenerated] = useState<{ id: string; url: string } | null>(null)

  const serverSrc = doc.cover_url && doc.cover_url !== failedSrc ? doc.cover_url : null
  const generatedSrc = generated?.id === doc.id ? generated.url : getCachedCover(doc.id)
  const generate =
    !compact &&
    shouldGenerateCover({
      status: doc.status,
      visible,
      online: typeof navigator === 'undefined' || navigator.onLine !== false,
      needsFallback: !serverSrc && !generatedSrc,
    })

  useEffect(() => {
    if (!generate) return
    let cancelled = false
    void loadCover(doc.id, engine).then((url) => {
      if (!cancelled && url) setGenerated({ id: doc.id, url })
    })
    return () => {
      cancelled = true
    }
  }, [generate, doc.id, engine])

  const candidate = serverSrc ?? generatedSrc
  const src = candidate && candidate !== failedSrc ? candidate : null
  return { ref, src, onError: () => setFailedSrc(src) }
}
