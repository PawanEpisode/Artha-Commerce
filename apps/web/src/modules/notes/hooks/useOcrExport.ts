import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef } from 'react'

import { notesAnalytics } from '../lib/analytics'
import { newClientId } from '../lib/api'
import type { DocumentSummary, ExportJob, OcrLang, OcrStarted } from '../lib/document-types'
import { type ExportOptions } from '../lib/document-types'
import { createArchiveExport, createDocumentExport, getExport, startOcr } from '../lib/documents-api'
import { documentQuotaExceeded } from '../lib/errors'
import { type DocumentQuotaDetails } from '../lib/errors'
import { isExportFinished } from '../lib/export-options'
import { notesKeys } from '../lib/keys'
import { notifyDocs } from '../lib/notify-documents'
import { classifyOcrError, formatEstimate, type OcrOutcomeReason } from '../lib/ocr-copy'

export type OcrOutcome =
  | { ok: true; result: OcrStarted }
  | { ok: false; reason: 'quota'; quota: DocumentQuotaDetails }
  | { ok: false; reason: Exclude<OcrOutcomeReason, 'quota'>; message: string }

/** Asks the server to read a scanned PDF (`POST ocr/`) and refreshes what shows its progress. Never throws. */
export function useRequestOcr() {
  const qc = useQueryClient()
  return useCallback(
    async (
      doc: Pick<DocumentSummary, 'id' | 'page_count' | 'ocr_pages_total'>,
      options: { lang: OcrLang; pages?: string; quiet?: boolean },
    ): Promise<OcrOutcome> => {
      try {
        const result = await startOcr(doc.id, {
          mode: 'tesseract',
          lang: options.lang,
          ...(options.pages ? { pages: options.pages } : {}),
        })
        notesAnalytics.ocrRequested({ pages: result.ocr_pages_total || doc.page_count || 0, lang: options.lang })
        if (!options.quiet) {
          // The 202 may already say `done` with nothing charged: the same file was read for someone before.
          if (result.status === 'done' && result.charged_pages === 0) notifyDocs.alreadySearchable()
          else notifyDocs.ocrStarted(formatEstimate(result.estimate_seconds))
        }
        await Promise.all([
          qc.invalidateQueries({ queryKey: notesKeys.documentProcessing(doc.id) }),
          qc.invalidateQueries({ queryKey: notesKeys.document(doc.id), exact: true }),
          qc.invalidateQueries({ queryKey: notesKeys.documentLists }),
          qc.invalidateQueries({ queryKey: notesKeys.usage }),
        ])
        return { ok: true, result }
      } catch (error) {
        const quota = documentQuotaExceeded(error)
        if (quota) {
          notesAnalytics.quotaBlocked('ocr')
          return { ok: false, reason: 'quota', quota }
        }
        const classified = classifyOcrError(error)
        return {
          ok: false,
          reason: classified.reason === 'quota' ? 'other' : classified.reason,
          message: classified.message,
        }
      }
    },
    [qc],
  )
}

export const EXPORT_POLL_MS = 2000

/** Polls one export job until it is done, failed or expired. The job read at the end carries a fresh download link. */
export function useExportJob(jobId: string | undefined) {
  return useQuery({
    queryKey: notesKeys.exportJob(jobId ?? ''),
    queryFn: () => getExport(jobId ?? ''),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && isExportFinished(q.state.data) ? false : EXPORT_POLL_MS),
  })
}

export type ExportStart = { ok: true; job: ExportJob } | { ok: false; error: unknown }

/** Starts a flattened PDF export of one document, or the "Download my notes" archive. A fresh `client_id` per tap. */
export function useStartExport() {
  const qc = useQueryClient()
  const seed = useCallback(
    (job: ExportJob) => {
      qc.setQueryData(notesKeys.exportJob(job.id), job)
      void qc.invalidateQueries({ queryKey: notesKeys.usage })
    },
    [qc],
  )
  const document = useCallback(
    async (id: string, options: ExportOptions): Promise<ExportStart> => {
      try {
        const { export: job } = await createDocumentExport(id, { client_id: newClientId(), options })
        seed(job)
        return { ok: true, job }
      } catch (error) {
        if (documentQuotaExceeded(error)) notesAnalytics.quotaBlocked('export')
        return { ok: false, error }
      }
    },
    [seed],
  )
  const archive = useCallback(async (): Promise<ExportStart> => {
    try {
      const { export: job } = await createArchiveExport(newClientId())
      seed(job)
      return { ok: true, job }
    } catch (error) {
      return { ok: false, error }
    }
  }, [seed])
  return { document, archive }
}

/** Calls `onDone` once when a job turns `done` (a toast and an analytics event), not for a job that was done on first read. */
export function useOnExportDone(job: ExportJob | undefined, onDone: (job: ExportJob) => void) {
  const first = useRef<ExportJob['status'] | undefined>(undefined)
  const fired = useRef(false)
  useEffect(() => {
    if (!job) return
    first.current ??= job.status
    if (job.status === 'done' && first.current !== 'done' && !fired.current) {
      fired.current = true
      onDone(job)
    }
  }, [job, onDone])
}
