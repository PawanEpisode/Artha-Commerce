import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { useOnline } from '~/modules/personalization'

import { OcrDialog } from '../components/library/OcrDialog'
import { useUsage } from '../hooks/useNotesQueries'
import { useNotesSettings, useUpdateNotesSettings } from '../hooks/useNotesSettings'
import { useRequestOcr } from '../hooks/useOcrExport'
import type { DocumentProcessing, DocumentSummary, OcrLang } from '../lib/document-types'
import type { DocumentQuotaDetails } from '../lib/errors'
import { notesKeys } from '../lib/keys'

interface OcrDialogContainerProps {
  doc: DocumentSummary
  open: boolean
  onOpenChange: (open: boolean) => void
  /** The monthly allowance is used up: the host may show the quota sheet too. */
  onQuota?: (details: DocumentQuotaDetails) => void
}

/** The freshest numbers: the cheap `processing/` poll (when something is polling it) over the document row. */
export function mergeProcessing(doc: DocumentSummary, processing: DocumentProcessing | undefined): DocumentSummary {
  if (!processing) return doc
  return {
    ...doc,
    status: processing.status,
    ocr_status: processing.ocr_status,
    ocr_pages_done: processing.ocr_pages_done,
    ocr_pages_total: processing.ocr_pages_total,
    text_status: processing.text_status,
  }
}

/** The OCR offer wired to the API: usage meter, the saved language, the request, and the refusals in plain words. */
export function OcrDialogContainer({ doc, open, onOpenChange, onQuota }: OcrDialogContainerProps) {
  const online = useOnline()
  const usage = useUsage()
  const settings = useNotesSettings()
  const updateSettings = useUpdateNotesSettings()
  const requestOcr = useRequestOcr()
  const [lang, setLang] = useState<OcrLang | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const processing = useQuery<DocumentProcessing>({
    queryKey: notesKeys.documentProcessing(doc.id),
    queryFn: () => Promise.reject(new Error('observer only')),
    enabled: false,
  })
  const chosen = lang ?? settings.data?.ocr_lang ?? doc.ocr_lang

  const start = async (pages?: string) => {
    setBusy(true)
    setError(undefined)
    const outcome = await requestOcr(doc, { lang: chosen, pages })
    setBusy(false)
    if (outcome.ok) {
      if (settings.data && chosen !== settings.data.ocr_lang) updateSettings.mutate({ ocr_lang: chosen })
      onOpenChange(false)
    } else if (outcome.reason === 'quota') {
      onQuota?.(outcome.quota)
    } else {
      setError(outcome.message)
    }
  }

  return (
    <OcrDialog
      open={open}
      onOpenChange={onOpenChange}
      doc={mergeProcessing(doc, processing.data)}
      usage={usage.data}
      lang={chosen}
      onLangChange={setLang}
      hindiAvailable={settings.data?.capabilities?.ocr_hindi ?? true}
      busy={busy}
      error={error}
      online={online}
      onStart={(pages) => void start(pages)}
    />
  )
}
