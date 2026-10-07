import { Button, CircleAlert, CircleCheck, Download, LoaderCircle, ProgressBar } from '@artha/design-system'

import type { ExportJob } from '../../lib/document-types'
import { exportFailureText } from '../../lib/export-options'
import { formatDate } from '../../lib/format'

interface ExportJobStatusProps {
  job: ExportJob
  /** Taps Download: the container fetches a fresh link first when the one it holds is old. */
  onDownload: () => void
  /** `export_too_large`: build it again for the suggested pages. */
  onRetryPages?: (pages: string) => void
  onRetry?: () => void
}

/** Progress, the download link, the suggested range for a too-large export and the expired state. Words and icons, not colour. */
export function ExportJobStatus({ job, onDownload, onRetryPages, onRetry }: ExportJobStatusProps) {
  if (job.status === 'queued' || job.status === 'running') {
    return (
      <div role="status" className="space-y-2">
        <p className="flex items-center gap-2 text-sm font-medium">
          <LoaderCircle aria-hidden className="size-4 animate-spin motion-reduce:animate-none" />
          {job.status === 'queued' ? 'Waiting to start…' : `Building your export… ${Math.round(job.progress)}%`}
        </p>
        <ProgressBar label="Export progress" value={job.progress} />
        <p className="text-sm text-muted-foreground">You can close this. We will tell you when it is ready.</p>
      </div>
    )
  }
  if (job.status === 'done') {
    return (
      <div role="status" className="space-y-2">
        <p className="flex items-center gap-2 text-sm font-medium">
          <CircleCheck aria-hidden className="size-4 text-success-fg" /> Your export is ready.
        </p>
        <Button onClick={onDownload}>
          <Download aria-hidden /> Download
        </Button>
        <p className="text-sm text-muted-foreground">
          The link works for 24 hours{job.expires_at ? `. The file is kept until ${formatDate(job.expires_at)}` : ''}.
          Open this dialog again for a new link.
        </p>
      </div>
    )
  }
  if (job.status === 'expired') {
    return (
      <div role="alert" className="space-y-2">
        <p className="flex items-center gap-2 text-sm font-medium">
          <CircleAlert aria-hidden className="size-4" /> This export has expired.
        </p>
        <p className="text-sm text-muted-foreground">Exports are kept for 7 days. Build it again to get a new file.</p>
        {onRetry ? (
          <Button variant="outline" onClick={onRetry}>
            Build it again
          </Button>
        ) : null}
      </div>
    )
  }
  const suggested = job.details?.suggested_pages
  return (
    <div role="alert" className="space-y-2">
      <p className="flex items-start gap-2 text-sm font-medium">
        <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" /> {exportFailureText(job)}
      </p>
      <div className="flex flex-wrap gap-2">
        {job.error_code === 'export_too_large' && suggested && onRetryPages ? (
          <Button onClick={() => onRetryPages(suggested)}>Export pages {suggested}</Button>
        ) : null}
        {job.error_code !== 'restricted' &&
        job.error_code !== 'locked' &&
        job.error_code !== 'export_too_large' &&
        onRetry ? (
          <Button variant="outline" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
      </div>
    </div>
  )
}
