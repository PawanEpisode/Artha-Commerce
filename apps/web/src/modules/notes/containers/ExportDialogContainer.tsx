import { useState } from 'react'

import { useOnline } from '~/modules/personalization'

import { ExportDialog } from '../components/library/ExportDialog'
import { ExportJobStatus } from '../components/library/ExportJobStatus'
import { useTags } from '../hooks/useNotesQueries'
import { useNotesSettings } from '../hooks/useNotesSettings'
import { useExportJob, useOnExportDone, useStartExport } from '../hooks/useOcrExport'
import { notesAnalytics } from '../lib/analytics'
import type { DocumentSummary, ExportJob } from '../lib/document-types'
import { openSignedUrl } from '../lib/download'
import { documentErrorMessage, type DocumentQuotaDetails, documentQuotaExceeded } from '../lib/errors'
import {
  buildExportOptions,
  defaultExportForm,
  exportBlock,
  type ExportBlockReason,
  exportNotAllowed,
  linkIsStale,
  parsePageSpec,
} from '../lib/export-options'
import { notifyDocs } from '../lib/notify-documents'

interface ExportDialogContainerProps {
  doc: DocumentSummary
  open: boolean
  onOpenChange: (open: boolean) => void
  onQuota?: (details: DocumentQuotaDetails) => void
}

/** Fetches the finished job again when its link is old, then opens the fresh signed URL. */
async function downloadFresh(job: ExportJob, fetchedAt: number, refetch: () => Promise<{ data?: ExportJob }>) {
  const fresh = linkIsStale(fetchedAt) ? ((await refetch()).data ?? job) : job
  if (fresh.download_url) openSignedUrl(fresh.download_url)
  else notifyDocs.error(undefined, 'The download link is not ready. Try again.')
}

/** Export dialog wired to the API: options form, the job (polled until it ends), download, and every refusal. */
export function ExportDialogContainer({ doc, open, onOpenChange, onQuota }: ExportDialogContainerProps) {
  const online = useOnline()
  const tags = useTags()
  const settings = useNotesSettings()
  const { document: startExport } = useStartExport()
  const [form, setForm] = useState(defaultExportForm)
  const [jobId, setJobId] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const [serverBlock, setServerBlock] = useState<ExportBlockReason | null>(null)
  const job = useExportJob(jobId)
  const pageSpec = parsePageSpec(form.pages, doc.page_count)
  const options = pageSpec.ok ? buildExportOptions(form, pageSpec.spec) : null
  const kind = form.appendix ? 'marks_appendix' : 'marks'
  const blocked = exportBlock(doc) ?? serverBlock

  useOnExportDone(job.data, (done) => {
    notifyDocs.exportReady()
    notesAnalytics.exportCompleted({ pages: done.page_count, options: kind })
  })

  const submit = async (override?: { pages: string }) => {
    const spec = override ? parsePageSpec(override.pages, doc.page_count) : pageSpec
    if (!spec.ok) return
    const body = buildExportOptions(override ? { ...form, pages: override.pages } : form, spec.spec)
    if (override) setForm((f) => ({ ...f, pages: override.pages }))
    setBusy(true)
    setError(undefined)
    const result = await startExport(doc.id, body)
    setBusy(false)
    if (result.ok) {
      notesAnalytics.exportRequested({ pages: spec.count || doc.page_count, options: kind })
      setJobId(result.job.id)
      return
    }
    const quota = documentQuotaExceeded(result.error)
    if (quota) onQuota?.(quota)
    const reason = exportNotAllowed(result.error)
    if (reason) setServerBlock(reason)
    else setError(documentErrorMessage(result.error))
  }

  const status = job.data ? (
    <ExportJobStatus
      job={job.data}
      onDownload={() => void downloadFresh(job.data as ExportJob, job.dataUpdatedAt, () => job.refetch())}
      onRetryPages={(pages) => void submit({ pages })}
      onRetry={() => {
        setJobId(undefined)
        void submit()
      }}
    />
  ) : undefined

  return (
    <ExportDialog
      open={open}
      onOpenChange={onOpenChange}
      doc={doc}
      form={form}
      onFormChange={(next) => {
        setForm(next)
        if (jobId && job.data && job.data.status !== 'running' && job.data.status !== 'queued') setJobId(undefined)
      }}
      legend={settings.data?.color_legend}
      tags={tags.data ?? []}
      blocked={blocked}
      online={online}
      pagesError={pageSpec.ok ? undefined : pageSpec.message}
      error={error}
      busy={busy || job.data?.status === 'queued' || job.data?.status === 'running'}
      status={status}
      onSubmit={() => void (options && submit())}
    />
  )
}
