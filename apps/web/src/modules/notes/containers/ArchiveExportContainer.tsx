import { Button, Download } from '@artha/design-system'
import { useState } from 'react'

import { useOnline } from '~/modules/personalization'

import { ExportJobStatus } from '../components/library/ExportJobStatus'
import { useExportJob, useOnExportDone, useStartExport } from '../hooks/useOcrExport'
import { notesAnalytics } from '../lib/analytics'
import { openSignedUrl } from '../lib/download'
import { documentErrorMessage } from '../lib/errors'
import { linkIsStale } from '../lib/export-options'
import { notifyDocs } from '../lib/notify-documents'

/** "Download my notes": a zip of notes as Markdown and a highlight digest per PDF. Free of the monthly export count. */
export function ArchiveExportContainer() {
  const online = useOnline()
  const { archive } = useStartExport()
  const [jobId, setJobId] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const job = useExportJob(jobId)

  useOnExportDone(job.data, (done) => {
    notifyDocs.exportReady()
    notesAnalytics.exportCompleted({ pages: done.page_count, options: 'archive' })
  })

  const start = async () => {
    setBusy(true)
    setError(undefined)
    const result = await archive()
    setBusy(false)
    if (result.ok) {
      notesAnalytics.exportRequested({ options: 'archive' })
      setJobId(result.job.id)
    } else setError(documentErrorMessage(result.error))
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        A zip with each note as a Markdown file (with its chapter and tags) and your highlights from every PDF, as
        Markdown and CSV. It does not use your monthly exports.
      </p>
      {!jobId || job.data?.status === 'failed' || job.data?.status === 'expired' ? (
        <Button variant="outline" onClick={() => void start()} disabled={!online || busy} loading={busy}>
          <Download aria-hidden /> Download my notes
        </Button>
      ) : null}
      {!online ? <p className="text-sm text-muted-foreground">You are offline. This needs a connection.</p> : null}
      {error ? (
        <p role="alert" className="text-sm font-medium text-error-fg">
          {error}
        </p>
      ) : null}
      {job.data ? (
        <ExportJobStatus
          job={job.data}
          onDownload={() =>
            void (async () => {
              const fresh = linkIsStale(job.dataUpdatedAt) ? ((await job.refetch()).data ?? job.data) : job.data
              if (fresh.download_url) openSignedUrl(fresh.download_url)
            })()
          }
          onRetry={() => {
            setJobId(undefined)
            void start()
          }}
        />
      ) : null}
    </div>
  )
}
